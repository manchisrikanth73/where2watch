"""Saves and loads draft packages (poster + caption + metadata) to disk."""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from PIL import Image

from src.aggregator.models import Release
from src.caption.caption_generator import GeneratedCaption
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

_POSTER = "poster.png"
_CAPTION = "caption.txt"
_HASHTAGS = "hashtags.txt"
_RELEASES = "release_data.json"
_META = "metadata.json"


class DraftManager:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()

    def _dir(self, draft_date: date) -> Path:
        return self.settings.drafts_dir / draft_date.isoformat()

    def save(
        self,
        draft_date: date,
        releases: list[Release],
        caption: GeneratedCaption,
        poster: Optional[Image.Image],
    ) -> Path:
        d = self._dir(draft_date)
        d.mkdir(parents=True, exist_ok=True)

        poster_path: Optional[str] = None
        if poster is not None:
            p = d / _POSTER
            poster.save(str(p), format="PNG", optimize=True)
            poster_path = str(p)
            logger.info("Poster saved → %s", p)

        (d / _RELEASES).write_text(
            json.dumps([r.to_dict() for r in releases], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (d / _CAPTION).write_text(caption.full_post(), encoding="utf-8")
        (d / _HASHTAGS).write_text(caption.hashtags_str(), encoding="utf-8")

        meta = {
            "date": draft_date.isoformat(),
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "release_count": len(releases),
            "poster_path": poster_path,
            "instagram_post_id": None,
            "published_at": None,
            "error": None,
        }
        (d / _META).write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info("Draft saved → %s  (%d releases)", d, len(releases))
        return d

    def load_releases(self, draft_date: date) -> list[Release]:
        path = self._dir(draft_date) / _RELEASES
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return [Release.from_dict(r) for r in data]

    def load_meta(self, draft_date: date) -> Optional[dict]:
        path = self._dir(draft_date) / _META
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    def update_status(
        self,
        draft_date: date,
        status: str,
        instagram_post_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        meta = self.load_meta(draft_date) or {}
        meta["status"] = status
        if instagram_post_id:
            meta["instagram_post_id"] = instagram_post_id
        if status == "published":
            meta["published_at"] = datetime.utcnow().isoformat()
        if error:
            meta["error"] = error
        (self._dir(draft_date) / _META).write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def list_pending(self) -> list[date]:
        if not self.settings.drafts_dir.exists():
            return []
        pending: list[date] = []
        for d in sorted(self.settings.drafts_dir.iterdir()):
            if not d.is_dir():
                continue
            try:
                draft_date = date.fromisoformat(d.name)
            except ValueError:
                continue
            meta = self.load_meta(draft_date)
            if meta and meta.get("status") == "pending":
                pending.append(draft_date)
        return pending

    def get_poster_path(self, draft_date: date) -> Optional[Path]:
        p = self._dir(draft_date) / _POSTER
        return p if p.exists() else None
