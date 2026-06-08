"""Tests for DraftManager save/load/status operations."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from PIL import Image

from src.draft.draft_manager import DraftManager, _CAPTION, _META, _POSTER, _RELEASES


@pytest.fixture
def manager(mock_settings):
    return DraftManager(settings=mock_settings)


@pytest.fixture
def draft_date():
    return date(2025, 6, 7)


@pytest.fixture
def tiny_image():
    return Image.new("RGB", (10, 10), (100, 100, 100))


def test_save_creates_all_files(manager, draft_date, sample_releases, sample_caption, tiny_image):
    draft_dir = manager.save(draft_date, sample_releases, sample_caption, tiny_image)

    assert draft_dir.exists()
    assert (draft_dir / _POSTER).exists()
    assert (draft_dir / _RELEASES).exists()
    assert (draft_dir / _CAPTION).exists()
    assert (draft_dir / _META).exists()


def test_save_without_poster(manager, draft_date, sample_releases, sample_caption):
    draft_dir = manager.save(draft_date, sample_releases, sample_caption, poster=None)

    assert not (draft_dir / _POSTER).exists()
    assert (draft_dir / _RELEASES).exists()


def test_load_releases_roundtrip(manager, draft_date, sample_releases, sample_caption):
    manager.save(draft_date, sample_releases, sample_caption, poster=None)
    loaded = manager.load_releases(draft_date)

    assert len(loaded) == len(sample_releases)
    assert loaded[0].tmdb_id == sample_releases[0].tmdb_id
    assert loaded[0].title == sample_releases[0].title


def test_load_meta_initial_status_pending(manager, draft_date, sample_releases, sample_caption):
    manager.save(draft_date, sample_releases, sample_caption, poster=None)
    meta = manager.load_meta(draft_date)

    assert meta is not None
    assert meta["status"] == "pending"
    assert meta["release_count"] == len(sample_releases)


def test_update_status_approved(manager, draft_date, sample_releases, sample_caption):
    manager.save(draft_date, sample_releases, sample_caption, poster=None)
    manager.update_status(draft_date, "approved")
    meta = manager.load_meta(draft_date)

    assert meta["status"] == "approved"


def test_update_status_published_sets_post_id(manager, draft_date, sample_releases, sample_caption):
    manager.save(draft_date, sample_releases, sample_caption, poster=None)
    manager.update_status(draft_date, "published", instagram_post_id="IG123456")
    meta = manager.load_meta(draft_date)

    assert meta["status"] == "published"
    assert meta["instagram_post_id"] == "IG123456"
    assert meta["published_at"] is not None


def test_list_pending_returns_pending_dates(manager, sample_releases, sample_caption):
    d1 = date(2025, 6, 5)
    d2 = date(2025, 6, 6)
    d3 = date(2025, 6, 7)

    manager.save(d1, sample_releases, sample_caption, poster=None)
    manager.save(d2, sample_releases, sample_caption, poster=None)
    manager.save(d3, sample_releases, sample_caption, poster=None)
    manager.update_status(d2, "published")

    pending = manager.list_pending()
    assert d1 in pending
    assert d3 in pending
    assert d2 not in pending


def test_get_poster_path_none_when_no_poster(manager, draft_date, sample_releases, sample_caption):
    manager.save(draft_date, sample_releases, sample_caption, poster=None)
    assert manager.get_poster_path(draft_date) is None


def test_get_poster_path_returns_path_when_exists(
    manager, draft_date, sample_releases, sample_caption, tiny_image
):
    manager.save(draft_date, sample_releases, sample_caption, tiny_image)
    path = manager.get_poster_path(draft_date)
    assert path is not None
    assert path.exists()


def test_load_releases_returns_empty_for_missing_date(manager):
    releases = manager.load_releases(date(2000, 1, 1))
    assert releases == []
