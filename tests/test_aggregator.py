"""Tests for OTTAggregator."""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import responses as resp_mock

from src.aggregator.models import ContentType
from src.aggregator.ott_aggregator import OTTAggregator
from src.aggregator.platforms import Platform


@pytest.fixture
def aggregator(mock_settings):
    return OTTAggregator(settings=mock_settings)


@pytest.fixture
def single_platform():
    return [
        Platform(
            id="netflix",
            display_name="Netflix",
            tmdb_provider_id=8,
            region="IN",
            color="#E50914",
            text_color="#FFFFFF",
            languages=["en", "hi"],
            emoji="🔴",
        )
    ]


MOVIE_API_RESPONSE = {
    "results": [
        {
            "id": 1001,
            "title": "Action Movie",
            "original_title": "Action Movie",
            "release_date": date.today().isoformat(),
            "original_language": "en",
            "overview": "An action film.",
            "poster_path": "/poster1.jpg",
            "backdrop_path": None,
            "genre_ids": [28, 12],
            "origin_country": ["US"],
        }
    ]
}

TV_API_RESPONSE = {
    "results": [
        {
            "id": 2001,
            "name": "Drama Series",
            "original_name": "Drama Series",
            "first_air_date": date.today().isoformat(),
            "original_language": "hi",
            "overview": "A drama series.",
            "poster_path": "/poster2.jpg",
            "backdrop_path": None,
            "genre_ids": [18],
            "origin_country": ["IN"],
        }
    ]
}


@resp_mock.activate
def test_fetch_releases_returns_releases(aggregator, single_platform):
    base = aggregator.settings.tmdb_base_url
    resp_mock.add(resp_mock.GET, f"{base}/discover/movie", json=MOVIE_API_RESPONSE, status=200)
    resp_mock.add(resp_mock.GET, f"{base}/discover/tv", json=TV_API_RESPONSE, status=200)

    releases = aggregator.fetch_releases(days_back=1, platforms=single_platform)

    assert len(releases) == 2
    assert releases[0].title == "Action Movie"
    assert releases[0].content_type == ContentType.MOVIE
    assert releases[1].title == "Drama Series"
    assert releases[1].content_type == ContentType.SERIES


@resp_mock.activate
def test_fetch_releases_deduplicates(aggregator, single_platform):
    base = aggregator.settings.tmdb_base_url
    # Same movie returned twice (once in movie, once if duplicated)
    resp_mock.add(resp_mock.GET, f"{base}/discover/movie", json=MOVIE_API_RESPONSE, status=200)
    resp_mock.add(resp_mock.GET, f"{base}/discover/tv", json={"results": []}, status=200)

    releases = aggregator.fetch_releases(days_back=1, platforms=single_platform)
    ids = [r.tmdb_id for r in releases]
    assert len(ids) == len(set(ids)), "Duplicate releases found"


@resp_mock.activate
def test_fetch_releases_skips_missing_date(aggregator, single_platform):
    base = aggregator.settings.tmdb_base_url
    bad_response = {
        "results": [
            {
                "id": 9999,
                "title": "No Date Movie",
                "original_title": "No Date Movie",
                "release_date": "",  # missing date
                "original_language": "en",
                "overview": "",
                "poster_path": None,
                "genre_ids": [],
                "origin_country": [],
            }
        ]
    }
    resp_mock.add(resp_mock.GET, f"{base}/discover/movie", json=bad_response, status=200)
    resp_mock.add(resp_mock.GET, f"{base}/discover/tv", json={"results": []}, status=200)

    releases = aggregator.fetch_releases(days_back=1, platforms=single_platform)
    assert len(releases) == 0


@resp_mock.activate
def test_fetch_releases_handles_api_error_gracefully(aggregator, single_platform):
    base = aggregator.settings.tmdb_base_url
    resp_mock.add(resp_mock.GET, f"{base}/discover/movie", status=500)
    resp_mock.add(resp_mock.GET, f"{base}/discover/tv", status=500)

    # Should not raise; just return empty
    releases = aggregator.fetch_releases(days_back=1, platforms=single_platform)
    assert releases == []


def test_classify_documentary(aggregator):
    genre_ids = [99]
    ct = aggregator._classify(genre_ids, "movie", [])
    assert ct == ContentType.DOCUMENTARY


def test_classify_anime(aggregator):
    genre_ids = [16]
    ct = aggregator._classify(genre_ids, "tv", ["JP"])
    assert ct == ContentType.ANIME


def test_classify_series(aggregator):
    ct = aggregator._classify([18], "tv", ["IN"])
    assert ct == ContentType.SERIES


def test_poster_url_none_when_no_path(aggregator):
    assert aggregator._poster_url(None) is None


def test_poster_url_builds_correct_url(aggregator):
    url = aggregator._poster_url("/abc.jpg")
    assert url == f"{aggregator.settings.tmdb_image_base_url}/abc.jpg"
