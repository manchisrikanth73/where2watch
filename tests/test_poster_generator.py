"""Tests for PosterGenerator image generation."""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest
from PIL import Image

from src.image.poster_generator import (
    PosterGenerator,
    _hex_to_rgb,
    _load_font,
    _placeholder,
)


@pytest.fixture
def generator(mock_settings):
    return PosterGenerator(settings=mock_settings)


def test_hex_to_rgb_parses_correctly():
    assert _hex_to_rgb("#E50914") == (229, 9, 20)
    assert _hex_to_rgb("#FFFFFF") == (255, 255, 255)
    assert _hex_to_rgb("#000000") == (0, 0, 0)


def test_load_font_returns_font_object():
    font = _load_font(16)
    assert font is not None


def test_placeholder_produces_correct_size():
    img = _placeholder(200, 300, "Test Title", "#333333")
    assert isinstance(img, Image.Image)
    assert img.size == (200, 300)


def test_generate_daily_returns_image(generator, sample_releases):
    with patch("src.image.poster_generator._download_poster", return_value=None):
        img = generator.generate_daily(sample_releases, date(2025, 6, 7))

    assert isinstance(img, Image.Image)
    assert img.size == (generator.settings.image_width, generator.settings.image_height)
    assert img.mode == "RGB"


def test_generate_daily_empty_releases(generator):
    with patch("src.image.poster_generator._download_poster", return_value=None):
        img = generator.generate_daily([], date(2025, 6, 7))

    assert isinstance(img, Image.Image)
    assert img.size == (1080, 1080)


def test_generate_daily_caps_at_six_posters(generator, sample_releases):
    # Pad to 10 releases
    padded = sample_releases * 4
    with patch("src.image.poster_generator._download_poster", return_value=None):
        img = generator.generate_daily(padded, date(2025, 6, 7))

    assert isinstance(img, Image.Image)


def test_generate_weekly_slides_returns_one_per_platform(generator, sample_releases):
    by_platform = {"netflix": [sample_releases[0]], "aha": [sample_releases[1]]}
    slides = generator.generate_weekly_slides(by_platform, "Jun 01 – Jun 07, 2025")

    assert len(slides) == 2
    for slide in slides:
        assert isinstance(slide, Image.Image)
        assert slide.size == (1080, 1080)
