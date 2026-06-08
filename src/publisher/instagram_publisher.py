"""Instagram Graph API publisher — Phase 2 implementation placeholder.

Phase 1: This module is imported but publish operations are gated by credentials.
Phase 2: Set INSTAGRAM_ACCESS_TOKEN + INSTAGRAM_USER_ID to enable live publishing.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

_GRAPH = "https://graph.facebook.com/v19.0"
_MAX_CAROUSEL = 10


@dataclass
class PublishResult:
    success: bool
    post_id: Optional[str] = None
    error: Optional[str] = None


class InstagramPublisher:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.session = requests.Session()

    @property
    def _token_param(self) -> dict:
        return {"access_token": self.settings.instagram_access_token}

    def _has_credentials(self) -> bool:
        return bool(self.settings.instagram_access_token and self.settings.instagram_user_id)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=60))
    def _post(self, path: str, data: dict) -> dict:
        resp = self.session.post(
            f"{_GRAPH}/{path}",
            params=self._token_param,
            json=data,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=60))
    def _get(self, path: str, extra: Optional[dict] = None) -> dict:
        params = {**self._token_param, **(extra or {})}
        resp = self.session.get(f"{_GRAPH}/{path}", params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def _wait_finished(self, container_id: str, max_wait: int = 90) -> bool:
        for _ in range(max_wait // 5):
            try:
                result = self._get(container_id, {"fields": "status_code"})
                status = result.get("status_code", "")
                if status == "FINISHED":
                    return True
                if status == "ERROR":
                    logger.error("Container %s errored during processing", container_id)
                    return False
            except Exception:
                pass
            time.sleep(5)
        logger.error("Container %s timed out", container_id)
        return False

    def verify_credentials(self) -> bool:
        if not self._has_credentials():
            logger.error("INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_USER_ID must be set")
            return False
        try:
            result = self._get(self.settings.instagram_user_id, {"fields": "id,username"})
            logger.info("Instagram credentials valid — @%s", result.get("username"))
            return True
        except Exception as exc:
            logger.error("Instagram credential check failed: %s", exc)
            return False

    def publish_single(self, image_url: str, caption: str) -> PublishResult:
        """Publishes one image as a feed post. image_url must be a public HTTPS URL."""
        if not self._has_credentials():
            return PublishResult(success=False, error="Instagram credentials not configured")

        uid = self.settings.instagram_user_id
        try:
            container = self._post(f"{uid}/media", {"image_url": image_url, "caption": caption})
            cid = container.get("id")
        except Exception as exc:
            return PublishResult(success=False, error=f"Container creation failed: {exc}")

        if not cid:
            return PublishResult(success=False, error="No container ID returned")

        if not self._wait_finished(cid):
            return PublishResult(success=False, error=f"Container {cid} did not finish processing")

        try:
            result = self._post(f"{uid}/media_publish", {"creation_id": cid})
            post_id: str = result.get("id", "")
        except Exception as exc:
            return PublishResult(success=False, error=f"Publish failed: {exc}")

        logger.info("Published single post: %s", post_id)
        return PublishResult(success=True, post_id=post_id)

    def publish_carousel(self, image_urls: list[str], caption: str) -> PublishResult:
        """Publishes 2–10 images as a carousel feed post."""
        if not self._has_credentials():
            return PublishResult(success=False, error="Instagram credentials not configured")

        if len(image_urls) == 1:
            return self.publish_single(image_urls[0], caption)
        if not image_urls:
            return PublishResult(success=False, error="No images provided")

        uid = self.settings.instagram_user_id
        child_ids: list[str] = []

        for url in image_urls[:_MAX_CAROUSEL]:
            try:
                r = self._post(f"{uid}/media", {"image_url": url, "is_carousel_item": True})
                cid = r.get("id")
                if cid:
                    child_ids.append(cid)
            except Exception as exc:
                logger.warning("Skipping carousel item %s: %s", url, exc)

        if not child_ids:
            return PublishResult(success=False, error="All carousel items failed to upload")

        try:
            r = self._post(
                f"{uid}/media",
                {"media_type": "CAROUSEL", "children": ",".join(child_ids), "caption": caption},
            )
            carousel_id = r.get("id")
        except Exception as exc:
            return PublishResult(success=False, error=f"Carousel container failed: {exc}")

        if not carousel_id or not self._wait_finished(carousel_id):
            return PublishResult(success=False, error="Carousel container did not finish")

        try:
            result = self._post(f"{uid}/media_publish", {"creation_id": carousel_id})
            post_id = result.get("id", "")
        except Exception as exc:
            return PublishResult(success=False, error=f"Carousel publish failed: {exc}")

        logger.info("Published carousel: %s (%d items)", post_id, len(child_ids))
        return PublishResult(success=True, post_id=post_id)
