"""Tests for Imgur image hosting."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import responses as resp_mock
from PIL import Image

from src.publisher.image_host import ImgurHost, upload_poster, upload_slides


@pytest.fixture
def poster_file(tmp_path: Path) -> Path:
    img = Image.new("RGB", (100, 100), (200, 100, 50))
    p = tmp_path / "poster.png"
    img.save(str(p))
    return p


IMGUR_SUCCESS = {
    "data": {"id": "abc123", "link": "https://i.imgur.com/abc123.png"},
    "success": True,
    "status": 200,
}


@resp_mock.activate
def test_imgur_upload_returns_url(poster_file):
    resp_mock.add(resp_mock.POST, "https://api.imgur.com/3/image", json=IMGUR_SUCCESS, status=200)

    host = ImgurHost(client_id="test_client_id")
    url = host.upload(poster_file)

    assert url == "https://i.imgur.com/abc123.png"


@resp_mock.activate
def test_imgur_upload_sends_correct_auth_header(poster_file):
    resp_mock.add(resp_mock.POST, "https://api.imgur.com/3/image", json=IMGUR_SUCCESS, status=200)

    host = ImgurHost(client_id="my_client_id")
    host.upload(poster_file)

    assert len(resp_mock.calls) == 1
    auth = resp_mock.calls[0].request.headers.get("Authorization", "")
    assert auth == "Client-ID my_client_id"


@resp_mock.activate
def test_upload_poster_returns_none_without_client_id(poster_file, mock_settings):
    mock_settings.imgur_client_id = ""
    result = upload_poster(poster_file, settings=mock_settings)
    assert result is None


@resp_mock.activate
def test_upload_poster_returns_url_with_client_id(poster_file, mock_settings):
    mock_settings.imgur_client_id = "test_id"
    resp_mock.add(resp_mock.POST, "https://api.imgur.com/3/image", json=IMGUR_SUCCESS, status=200)

    result = upload_poster(poster_file, settings=mock_settings)
    assert result == "https://i.imgur.com/abc123.png"


@resp_mock.activate
def test_upload_poster_returns_none_on_api_error(poster_file, mock_settings):
    mock_settings.imgur_client_id = "test_id"
    resp_mock.add(resp_mock.POST, "https://api.imgur.com/3/image", status=500)

    result = upload_poster(poster_file, settings=mock_settings)
    assert result is None


@resp_mock.activate
def test_upload_slides_returns_urls_for_each(tmp_path, mock_settings):
    mock_settings.imgur_client_id = "test_id"

    slides = []
    for i in range(3):
        img = Image.new("RGB", (50, 50), (i * 50, 100, 200))
        p = tmp_path / f"slide_{i}.png"
        img.save(str(p))
        slides.append(p)

        resp_mock.add(
            resp_mock.POST,
            "https://api.imgur.com/3/image",
            json={"data": {"link": f"https://i.imgur.com/slide{i}.png"}, "success": True},
            status=200,
        )

    urls = upload_slides(slides, settings=mock_settings)
    assert len(urls) == 3
    assert all("imgur.com" in u for u in urls)


def test_upload_slides_returns_empty_without_client_id(mock_settings):
    mock_settings.imgur_client_id = ""
    result = upload_slides([Path("fake.png")], settings=mock_settings)
    assert result == []
