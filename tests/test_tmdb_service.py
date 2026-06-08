"""Tests for TMDbService metadata enrichment."""
from __future__ import annotations

from datetime import date

import pytest
import responses as resp_mock

from src.aggregator.models import ContentType, Release
from src.metadata.tmdb_service import TMDbService


@pytest.fixture
def service(mock_settings):
    return TMDbService(settings=mock_settings)


@pytest.fixture
def movie_release():
    return Release(
        tmdb_id=1001,
        title="Test Movie",
        original_title="Test Movie",
        content_type=ContentType.MOVIE,
        platform="netflix",
        release_date=date(2025, 6, 7),
        language="en",
    )


@pytest.fixture
def series_release():
    return Release(
        tmdb_id=2001,
        title="Test Series",
        original_title="Test Series",
        content_type=ContentType.SERIES,
        platform="prime_video",
        release_date=date(2025, 6, 7),
        language="hi",
    )


MOVIE_DETAIL = {
    "id": 1001,
    "genres": [{"id": 28, "name": "Action"}, {"id": 12, "name": "Adventure"}],
    "runtime": 120,
    "vote_average": 7.5,
    "poster_path": "/enriched_poster.jpg",
}

MOVIE_CREDITS = {
    "cast": [
        {"name": "Actor A", "order": 0},
        {"name": "Actor B", "order": 1},
        {"name": "Actor C", "order": 2},
    ]
}

TV_DETAIL = {
    "id": 2001,
    "genres": [{"id": 18, "name": "Drama"}],
    "episode_run_time": [45],
    "vote_average": 8.1,
    "poster_path": "/tv_poster.jpg",
}

TV_CREDITS = {"cast": [{"name": "Lead Actor", "order": 0}]}


@resp_mock.activate
def test_enrich_movie(service, movie_release):
    base = service.settings.tmdb_base_url
    resp_mock.add(resp_mock.GET, f"{base}/movie/1001", json=MOVIE_DETAIL)
    resp_mock.add(resp_mock.GET, f"{base}/movie/1001/credits", json=MOVIE_CREDITS)

    enriched = service.enrich(movie_release)

    assert enriched.genres == ["Action", "Adventure"]
    assert enriched.runtime == 120
    assert enriched.rating == 7.5
    assert enriched.cast == ["Actor A", "Actor B", "Actor C"]
    assert enriched.poster_url == f"{service.settings.tmdb_image_base_url}/enriched_poster.jpg"


@resp_mock.activate
def test_enrich_tv_series(service, series_release):
    base = service.settings.tmdb_base_url
    resp_mock.add(resp_mock.GET, f"{base}/tv/2001", json=TV_DETAIL)
    resp_mock.add(resp_mock.GET, f"{base}/tv/2001/credits", json=TV_CREDITS)

    enriched = service.enrich(series_release)

    assert enriched.genres == ["Drama"]
    assert enriched.runtime == 45
    assert enriched.rating == 8.1
    assert enriched.cast == ["Lead Actor"]


@resp_mock.activate
def test_enrich_handles_api_failure_gracefully(service, movie_release):
    base = service.settings.tmdb_base_url
    resp_mock.add(resp_mock.GET, f"{base}/movie/1001", status=404)

    # Should return original release unchanged (no crash)
    result = service.enrich(movie_release)
    assert result.tmdb_id == movie_release.tmdb_id
    assert result.genres == []


@resp_mock.activate
def test_enrich_all_processes_all_releases(service, movie_release, series_release):
    base = service.settings.tmdb_base_url
    resp_mock.add(resp_mock.GET, f"{base}/movie/1001", json=MOVIE_DETAIL)
    resp_mock.add(resp_mock.GET, f"{base}/movie/1001/credits", json=MOVIE_CREDITS)
    resp_mock.add(resp_mock.GET, f"{base}/tv/2001", json=TV_DETAIL)
    resp_mock.add(resp_mock.GET, f"{base}/tv/2001/credits", json=TV_CREDITS)

    results = service.enrich_all([movie_release, series_release])
    assert len(results) == 2
    assert results[0].runtime == 120
    assert results[1].runtime == 45
