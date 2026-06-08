"""Uploads poster images to Imgur so Instagram Graph API can fetch a public URL."""
from __future__ import annotations

import base64
import logging
from pathlib import Path
from typing import Optional

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

_IMGUR_ENDPOINT = "https://api.imgur.com/3/image"


class ImgurHost:
    """Anonymous image uploads using an Imgur OAuth2 Client-ID (no user login needed)."""

    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        self.session = requests.Session()

    @retry(
        retry=retry_if_exception_type(requests.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=30),
        reraise=True,
    )
    def upload(self, image_path: Path) -> str:
        """Uploads image_path to Imgur and returns the public link."""
        image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        resp = self.session.post(
            _IMGUR_ENDPOINT,
            headers={"Authorization": f"Client-ID {self.client_id}"},
            json={"image": image_b64, "type": "base64", "name": image_path.name},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        link: str = data["data"]["link"]
        logger.info("Uploaded %s → %s", image_path.name, link)
        return link


def upload_poster(image_path: Path, settings: Optional[Settings] = None) -> Optional[str]:
    """Uploads image to the configured host. Returns public URL or None on failure."""
    s = settings or get_settings()

    if not s.imgur_client_id:
        logger.error(
            "IMGUR_CLIENT_ID is not set. "
            "Register a free app at https://api.imgur.com/oauth2/addclient "
            "then add it as a GitHub secret."
        )
        return None

    try:
        return ImgurHost(s.imgur_client_id).upload(image_path)
    except Exception as exc:
        logger.error("Imgur upload failed for %s: %s", image_path, exc)
        return None


def upload_slides(slide_paths: list[Path], settings: Optional[Settings] = None) -> list[str]:
    """Uploads multiple slide images. Returns list of public URLs (skips failures)."""
    s = settings or get_settings()
    if not s.imgur_client_id:
        return []

    host = ImgurHost(s.imgur_client_id)
    urls: list[str] = []
    for path in slide_paths:
        try:
            urls.append(host.upload(path))
        except Exception as exc:
            logger.warning("Skipping slide %s: %s", path.name, exc)
    return urls
