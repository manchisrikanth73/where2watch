"""Shared pytest fixtures."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.aggregator.models import ContentType, Release
from src.caption.caption_generator import GeneratedCaption


@pytest.fixture
def sample_releases() -> list[Release]:
    return [
        Release(
            tmdb_id=1001,
            title="Test Movie",
            original_title="Test Movie",
            content_type=ContentType.MOVIE,
            platform="netflix",
            release_date=date(2025, 6, 7),
            language="en",
            overview="A test movie about testing.",
            poster_path="/test_poster.jpg",
            poster_url="https://image.tmdb.org/t/p/w500/test_poster.jpg",
            genres=["Action", "Drama"],
            genre_ids=[28, 18],
            rating=7.5,
            cast=["Actor One", "Actor Two"],
        ),
        Release(
            tmdb_id=1002,
            title="Telugu Series",
            original_title="Telugu Series",
            content_type=ContentType.SERIES,
            platform="aha",
            release_date=date(2025, 6, 7),
            language="te",
            overview="A Telugu web series.",
            poster_path=None,
            poster_url=None,
            genres=["Drama"],
            genre_ids=[18],
            rating=8.2,
            cast=["Actor Three"],
        ),
        Release(
            tmdb_id=1003,
            title="Documentary Film",
            original_title="Documentary Film",
            content_type=ContentType.DOCUMENTARY,
            platform="prime_video",
            release_date=date(2025, 6, 7),
            language="hi",
            overview="A Hindi documentary.",
            poster_path="/doc_poster.jpg",
            poster_url="https://image.tmdb.org/t/p/w500/doc_poster.jpg",
            genres=["Documentary"],
            genre_ids=[99],
            rating=6.9,
            cast=[],
        ),
    ]


@pytest.fixture
def sample_caption() -> GeneratedCaption:
    return GeneratedCaption(
        short_caption="🎬 New OTT releases today!",
        long_caption="Lots of great content across Netflix, Aha, and Prime Video.",
        hashtags=["#OTTReleases", "#Netflix", "#where2watch"],
        engagement_question="Which one are you watching tonight? 👇",
    )


@pytest.fixture
def mock_settings(tmp_path: Path):
    from src.config import Settings
    return Settings(
        TMDB_API_KEY="test_tmdb_key",
        OPENAI_API_KEY="test_openai_key",
        drafts_dir=tmp_path / "drafts",
        data_dir=tmp_path / "data",
    )
