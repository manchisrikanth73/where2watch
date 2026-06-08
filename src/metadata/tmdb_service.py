"""Enriches Release objects with full TMDb metadata (genres, cast, runtime, rating)."""
from __future__ import annotations

import logging
from typing import Optional

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.aggregator.models import Release
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


class TMDbService:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.session = requests.Session()

    @retry(
        retry=retry_if_exception_type(requests.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=30),
        reraise=True,
    )
    def _get(self, endpoint: str) -> dict:
        url = f"{self.settings.tmdb_base_url}{endpoint}"
        resp = self.session.get(
            url,
            params={"api_key": self.settings.tmdb_api_key},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def enrich(self, release: Release) -> Release:
        """Fetches full detail + credits and mutates release in place. Returns same object."""
        media_type = "movie" if release.content_type.value == "movie" else "tv"
        try:
            detail = self._get(f"/{media_type}/{release.tmdb_id}")
            credits = self._get(f"/{media_type}/{release.tmdb_id}/credits")
        except Exception as exc:
            logger.warning("Could not enrich '%s' (id=%d): %s", release.title, release.tmdb_id, exc)
            return release

        release.genres = [g["name"] for g in detail.get("genres", [])]
        release.rating = detail.get("vote_average") or release.rating

        if media_type == "movie":
            release.runtime = detail.get("runtime") or release.runtime
        else:
            runtimes: list[int] = detail.get("episode_run_time", [])
            release.runtime = runtimes[0] if runtimes else release.runtime

        cast_list = credits.get("cast", [])[:5]
        release.cast = [c["name"] for c in cast_list]

        poster = detail.get("poster_path") or release.poster_path
        if poster:
            release.poster_path = poster
            release.poster_url = f"{self.settings.tmdb_image_base_url}{poster}"

        return release

    def enrich_all(self, releases: list[Release]) -> list[Release]:
        result: list[Release] = []
        for i, r in enumerate(releases, 1):
            logger.info("Enriching %d/%d: %s", i, len(releases), r.title)
            result.append(self.enrich(r))
        return result
