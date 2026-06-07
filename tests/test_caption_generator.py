"""Tests for CaptionGenerator."""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from src.caption.caption_generator import CaptionGenerator, GeneratedCaption


@pytest.fixture
def generator(mock_settings):
    return CaptionGenerator(settings=mock_settings)


GOOD_RESPONSE = {
    "short_caption": "🎬 Exciting OTT releases today!",
    "long_caption": "A wonderful set of films and series dropped across platforms today.",
    "hashtags": ["#OTTReleases", "#Netflix", "#PrimeVideo", "#where2watch"],
    "engagement_question": "Which one are you watching tonight? 👇",
}


def _mock_openai(generator: CaptionGenerator, response: dict) -> None:
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = json.dumps(response)
    generator.client.chat.completions.create = MagicMock(return_value=mock_resp)


def test_generate_daily_returns_caption(generator, sample_releases):
    _mock_openai(generator, GOOD_RESPONSE)
    caption = generator.generate_daily(sample_releases, date(2025, 6, 7))

    assert isinstance(caption, GeneratedCaption)
    assert caption.short_caption == GOOD_RESPONSE["short_caption"]
    assert caption.engagement_question == GOOD_RESPONSE["engagement_question"]
    assert len(caption.hashtags) == 4


def test_generate_daily_falls_back_on_openai_error(generator, sample_releases):
    generator.client.chat.completions.create = MagicMock(side_effect=Exception("API down"))
    caption = generator.generate_daily(sample_releases, date(2025, 6, 7))

    # Falls back to defaults — should not raise
    assert isinstance(caption, GeneratedCaption)
    assert caption.short_caption  # non-empty fallback
    assert len(caption.hashtags) >= 1


def test_generate_weekly_returns_caption(generator, sample_releases):
    _mock_openai(generator, GOOD_RESPONSE)
    caption = generator.generate_weekly(sample_releases, "Jun 01 – Jun 07, 2025")

    assert isinstance(caption, GeneratedCaption)
    assert caption.short_caption


def test_full_post_format(sample_caption):
    post = sample_caption.full_post()
    assert sample_caption.short_caption in post
    assert sample_caption.engagement_question in post
    assert "#OTTReleases" in post


def test_hashtags_str_joins_with_spaces(sample_caption):
    ht = sample_caption.hashtags_str()
    assert ht == "#OTTReleases #Netflix #where2watch"
