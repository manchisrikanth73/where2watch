"""Tests for TemplateCaptionGenerator — the free, no-API caption engine."""
from __future__ import annotations

from datetime import date

import pytest

from src.aggregator.models import ContentType, Release
from src.caption.caption_generator import GeneratedCaption
from src.caption.template_generator import (
    TemplateCaptionGenerator,
    _build_hashtags,
    _platform_breakdown,
    _rotate,
)


@pytest.fixture
def generator():
    return TemplateCaptionGenerator()


# ── Unit helpers ──────────────────────────────────────────────────────────────

def test_rotate_wraps_around():
    items = ["a", "b", "c"]
    assert _rotate(items, 0) == "a"
    assert _rotate(items, 3) == "a"
    assert _rotate(items, 4) == "b"


def test_build_hashtags_includes_base_tags(sample_releases):
    tags = _build_hashtags(sample_releases)
    assert "#OTTReleases" in tags
    assert "#where2watch" in tags
    assert "#StreamingNow" in tags


def test_build_hashtags_includes_platform_tags(sample_releases):
    tags = _build_hashtags(sample_releases)
    assert "#Netflix" in tags
    assert "#Aha" in tags or "#AhaVideo" in tags


def test_build_hashtags_includes_language_tags(sample_releases):
    tags = _build_hashtags(sample_releases)
    # sample_releases has 'en', 'te', 'hi' languages
    assert "#TeluguMovies" in tags
    assert "#HindiMovies" in tags


def test_build_hashtags_includes_content_type_tags(sample_releases):
    tags = _build_hashtags(sample_releases)
    assert "#NewMovies" in tags      # has MOVIE
    assert "#WebSeries" in tags      # has SERIES
    assert "#Documentaries" in tags  # has DOCUMENTARY


def test_build_hashtags_capped_at_25(sample_releases):
    tags = _build_hashtags(sample_releases * 10)
    assert len(tags) <= 25


def test_platform_breakdown_lists_all_platforms(sample_releases):
    breakdown = _platform_breakdown(sample_releases)
    assert "Netflix" in breakdown
    assert "Aha" in breakdown
    assert "Prime" in breakdown


def test_platform_breakdown_uses_content_icons(sample_releases):
    breakdown = _platform_breakdown(sample_releases)
    assert "🎬" in breakdown   # MOVIE icon
    assert "📺" in breakdown   # SERIES icon
    assert "🎙️" in breakdown   # DOCUMENTARY icon


# ── generate_daily ────────────────────────────────────────────────────────────

def test_generate_daily_returns_generated_caption(generator, sample_releases):
    caption = generator.generate_daily(sample_releases, date(2025, 6, 7))
    assert isinstance(caption, GeneratedCaption)


def test_generate_daily_caption_contains_date(generator, sample_releases):
    caption = generator.generate_daily(sample_releases, date(2025, 6, 7))
    assert "June 07, 2025" in caption.short_caption


def test_generate_daily_caption_contains_platform(generator, sample_releases):
    caption = generator.generate_daily(sample_releases, date(2025, 6, 7))
    assert "Netflix" in caption.short_caption or "Netflix" in caption.long_caption


def test_generate_daily_long_caption_has_breakdown(generator, sample_releases):
    caption = generator.generate_daily(sample_releases, date(2025, 6, 7))
    assert "Test Movie" in caption.long_caption
    assert "Telugu Series" in caption.long_caption


def test_generate_daily_has_nonempty_hashtags(generator, sample_releases):
    caption = generator.generate_daily(sample_releases, date(2025, 6, 7))
    assert len(caption.hashtags) >= 5
    assert all(t.startswith("#") for t in caption.hashtags)


def test_generate_daily_has_engagement_question(generator, sample_releases):
    caption = generator.generate_daily(sample_releases, date(2025, 6, 7))
    assert caption.engagement_question.endswith("👇")


def test_generate_daily_empty_releases(generator):
    caption = generator.generate_daily([], date(2025, 6, 7))
    assert isinstance(caption, GeneratedCaption)
    assert caption.short_caption


def test_generate_daily_varies_by_date(generator, sample_releases):
    c1 = generator.generate_daily(sample_releases, date(2025, 6, 1))
    c2 = generator.generate_daily(sample_releases, date(2025, 6, 15))
    # Different days should produce different openers or questions
    assert c1.short_caption != c2.short_caption or c1.engagement_question != c2.engagement_question


# ── generate_weekly ────────────────────────────────────────────────────────────

def test_generate_weekly_returns_caption(generator, sample_releases):
    caption = generator.generate_weekly(sample_releases, "Jun 01 – Jun 07, 2025")
    assert isinstance(caption, GeneratedCaption)
    assert "Jun 01 – Jun 07, 2025" in caption.short_caption


def test_generate_weekly_hashtags_include_weekly_tags(generator, sample_releases):
    caption = generator.generate_weekly(sample_releases, "Jun 01 – Jun 07, 2025")
    joined = " ".join(caption.hashtags)
    assert "#WeeklyWatchlist" in joined or "#WeekendWatch" in joined


def test_generate_weekly_long_caption_has_breakdown(generator, sample_releases):
    caption = generator.generate_weekly(sample_releases, "Jun 01 – Jun 07, 2025")
    assert "Test Movie" in caption.long_caption or "Telugu Series" in caption.long_caption


# ── CaptionGenerator fallback ──────────────────────────────────────────────────

def test_caption_generator_uses_template_when_no_openai_key(sample_releases):
    """CaptionGenerator with no API key must produce a valid caption via template."""
    from src.config import Settings
    settings = Settings(TMDB_API_KEY="tmdb_key")  # no OPENAI_API_KEY
    from src.caption.caption_generator import CaptionGenerator
    gen = CaptionGenerator(settings=settings)

    assert gen.client is None  # no OpenAI client instantiated
    caption = gen.generate_daily(sample_releases, date(2025, 6, 7))
    assert isinstance(caption, GeneratedCaption)
    assert caption.short_caption
    assert len(caption.hashtags) >= 5
