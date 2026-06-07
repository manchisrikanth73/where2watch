"""Creates GitHub Issues for draft review and checks approval status via labels."""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

import requests

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

LABEL_APPROVED = "ott-approved"
LABEL_REJECTED = "ott-rejected"
LABEL_PENDING = "ott-pending"

_LABELS = [
    (LABEL_APPROVED, "0e8a16", "OTT draft approved for publishing"),
    (LABEL_REJECTED, "d93f0b", "OTT draft rejected"),
    (LABEL_PENDING, "e4e669", "OTT draft awaiting review"),
]


class ApprovalWorkflow:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _api(self, method: str, path: str, **kwargs) -> requests.Response:  # type: ignore[no-untyped-def]
        url = f"https://api.github.com/repos/{self.settings.github_repository}{path}"
        resp = requests.request(method, url, headers=self._headers, timeout=20, **kwargs)
        resp.raise_for_status()
        return resp

    def _has_credentials(self) -> bool:
        return bool(self.settings.github_token and self.settings.github_repository)

    def _ensure_labels(self) -> None:
        for name, color, desc in _LABELS:
            try:
                self._api("GET", f"/labels/{name}")
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    try:
                        self._api("POST", "/labels", json={"name": name, "color": color, "description": desc})
                    except Exception as inner:
                        logger.warning("Could not create label %s: %s", name, inner)

    def create_review_issue(self, draft_date: date, release_count: int) -> Optional[int]:
        if not self._has_credentials():
            logger.info("GitHub credentials not set — skipping review issue creation")
            return None

        self._ensure_labels()

        date_str = draft_date.strftime("%B %d, %Y")
        body = (
            f"## OTT Draft Ready for Review — {date_str}\n\n"
            f"**Releases found:** {release_count}\n\n"
            "### Review Checklist\n"
            "- [ ] Poster image looks correct\n"
            "- [ ] Caption is engaging and error-free\n"
            "- [ ] Hashtags are relevant\n"
            "- [ ] No inappropriate content\n\n"
            "### How to Approve\n"
            f"Add the `{LABEL_APPROVED}` label to queue this draft for publishing.  \n"
            f"Add `{LABEL_REJECTED}` to reject it.\n\n"
            f"*Draft key: `{draft_date.isoformat()}`*"
        )

        try:
            resp = self._api(
                "POST",
                "/issues",
                json={
                    "title": f"OTT Draft Review — {date_str}",
                    "body": body,
                    "labels": [LABEL_PENDING],
                },
            )
            number: int = resp.json()["number"]
            logger.info("Review issue created: #%d", number)
            return number
        except Exception as exc:
            logger.error("Failed to create review issue: %s", exc)
            return None

    def check_approval(self, draft_date: date) -> str:
        """Returns 'approved', 'rejected', or 'pending'."""
        if not self._has_credentials():
            logger.info("No GitHub credentials — treating as approved (local mode)")
            return "approved"

        key = draft_date.isoformat()

        for state in ("open", "closed"):
            try:
                resp = self._api("GET", "/issues", params={"state": state, "per_page": 30})
                for issue in resp.json():
                    if key not in (issue.get("body") or ""):
                        continue
                    label_names = {lbl["name"] for lbl in issue.get("labels", [])}
                    if LABEL_APPROVED in label_names:
                        return "approved"
                    if LABEL_REJECTED in label_names:
                        return "rejected"
            except Exception as exc:
                logger.warning("Issue lookup failed (%s): %s", state, exc)

        return "pending"
