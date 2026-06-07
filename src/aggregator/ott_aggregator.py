"""Fetches new OTT releases from the TMDb Discover API filtered by streaming provider."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.aggregator.models import (
    GENRE_ANIMATION,
    GENRE_DOCUMENTARY,
    ContentType,
    Release,
)
from src.aggregator.platforms import Platform, load_platforms
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


class OTTAggregator:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.session = requests.Session()
        self.platforms = load_platforms()

    @retry(
        retry=retry_if_exception_type(requests.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=30),
        reraise=True,
    )
    def _get(self, endpoint: str, params: dict) -> dict:
        full_params = {**params, "api_key": self.settings.tmdb_api_key}
        url = f"{self.settings.tmdb_base_url}{endpoint}"
        resp = self.session.get(url, params=full_params, timeout=30)
        resp.raise_for_status()
        return resp.json()  # type: ignore[no-any-return]

    def _classify(self, genre_ids: list[int], media_type: str, origin_country: list[str]) -> ContentType:
        if GENRE_DOCUMENTARY in genre_ids:
            return ContentType.DOCUMENTARY
        if GENRE_ANIMATION in genre_ids and "JP" in origin_country:
            return ContentType.ANIME
        return ContentType.MOVIE if media_type == "movie" else ContentType.SERIES

    def _poster_url(self, poster_path: Optional[str]) -> Optional[str]:
        if not poster_path:
            return None
        return f"{self.settings.tmdb_image_base_url}{poster_path}"

    def _parse_item(self, item: dict, media_type: str, platform_id: str) -> Optional[Release]:
        date_key = "release_date" if media_type == "movie" else "first_air_date"
        raw_date = item.get(date_key, "")
        if not raw_date:
            return None
        try:
            release_date = date.fromisoformat(raw_date)
        except ValueError:
            return None

        genre_ids: list[int] = item.get("genre_ids", [])
        origin_country: list[str] = item.get("origin_country", [])

        return Release(
            tmdb_id=item["id"],
            title=item.get("title") or item.get("name") or "Unknown",
            original_title=item.get("original_title") or item.get("original_name") or "",
            content_type=self._classify(genre_ids, media_type, origin_country),
            platform=platform_id,
            release_date=release_date,
            language=item.get("original_language", "en"),
            overview=item.get("overview", ""),
            poster_path=item.get("poster_path"),
            backdrop_path=item.get("backdrop_path"),
            genre_ids=genre_ids,
            poster_url=self._poster_url(item.get("poster_path")),
            origin_country=origin_country,
        )

    def fetch_releases(
        self,
        days_back: Optional[int] = None,
        platforms: Optional[list[Platform]] = None,
    ) -> list[Release]:
        if days_back is None:
            days_back = self.settings.days_lookback
        if platforms is None:
            platforms = self.platforms

        today = date.today()
        start_date = today - timedelta(days=days_back)
        seen: set[str] = set()
        releases: list[Release] = []

        for platform in platforms:
            logger.info("Fetching releases for %s (provider_id=%d)", platform.display_name, platform.tmdb_provider_id)

            for media_type in ("movie", "tv"):
                date_field = "primary_release_date" if media_type == "movie" else "first_air_date"
                params: dict = {
                    "with_watch_providers": str(platform.tmdb_provider_id),
                    "watch_region": platform.region,
                    f"{date_field}.gte": start_date.isoformat(),
                    f"{date_field}.lte": today.isoformat(),
                    "sort_by": f"{date_field}.desc",
                    "include_adult": "false",
                }
                if platform.languages:
                    params["with_original_language"] = "|".join(platform.languages)

                try:
                    data = self._get(f"/discover/{media_type}", params)
                except Exception as exc:
                    logger.error(
                        "Failed fetching %s from %s: %s",
                        media_type,
                        platform.display_name,
                        exc,
                    )
                    continue

                for raw in data.get("results", [])[: self.settings.max_releases_per_platform]:
                    key = f"{media_type}_{raw.get('id')}"
                    if key in seen:
                        continue
                    seen.add(key)
                    release = self._parse_item(raw, media_type, platform.id)
                    if release:
                        releases.append(release)

        logger.info("Total releases fetched: %d", len(releases))
        return releases
