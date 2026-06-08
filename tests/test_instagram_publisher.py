"""Tests for InstagramPublisher."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import responses as resp_mock

from src.publisher.instagram_publisher import InstagramPublisher, PublishResult


@pytest.fixture
def publisher(mock_settings):
    mock_settings.instagram_access_token = "test_token"
    mock_settings.instagram_user_id = "123456789"
    return InstagramPublisher(settings=mock_settings)


@pytest.fixture
def publisher_no_creds(mock_settings):
    mock_settings.instagram_access_token = ""
    mock_settings.instagram_user_id = ""
    return InstagramPublisher(settings=mock_settings)


GRAPH = "https://graph.facebook.com/v19.0"

CONTAINER_RESP = {"id": "container_abc"}
PUBLISH_RESP = {"id": "post_xyz123"}
FINISHED_RESP = {"status_code": "FINISHED", "id": "container_abc"}
USER_RESP = {"id": "123456789", "username": "testaccount"}


@resp_mock.activate
def test_publish_single_success(publisher):
    resp_mock.add(resp_mock.POST, f"{GRAPH}/123456789/media", json=CONTAINER_RESP)
    resp_mock.add(resp_mock.GET, f"{GRAPH}/container_abc", json=FINISHED_RESP)
    resp_mock.add(resp_mock.POST, f"{GRAPH}/123456789/media_publish", json=PUBLISH_RESP)

    result = publisher.publish_single("https://i.imgur.com/test.png", "Test caption")

    assert result.success is True
    assert result.post_id == "post_xyz123"
    assert result.error is None


def test_publish_single_fails_without_credentials(publisher_no_creds):
    result = publisher_no_creds.publish_single("https://example.com/img.png", "Caption")
    assert result.success is False
    assert result.error is not None


@resp_mock.activate
def test_publish_single_fails_on_container_error(publisher):
    resp_mock.add(resp_mock.POST, f"{GRAPH}/123456789/media", status=400)

    result = publisher.publish_single("https://i.imgur.com/test.png", "Caption")
    assert result.success is False


@resp_mock.activate
def test_publish_carousel_success(publisher):
    # Two child containers
    resp_mock.add(resp_mock.POST, f"{GRAPH}/123456789/media", json={"id": "child_1"})
    resp_mock.add(resp_mock.POST, f"{GRAPH}/123456789/media", json={"id": "child_2"})
    # Carousel container
    resp_mock.add(resp_mock.POST, f"{GRAPH}/123456789/media", json={"id": "carousel_1"})
    # Status check
    resp_mock.add(resp_mock.GET, f"{GRAPH}/carousel_1", json={"status_code": "FINISHED"})
    # Publish
    resp_mock.add(resp_mock.POST, f"{GRAPH}/123456789/media_publish", json={"id": "carousel_post_1"})

    result = publisher.publish_carousel(
        ["https://i.imgur.com/a.png", "https://i.imgur.com/b.png"],
        "Carousel caption",
    )

    assert result.success is True
    assert result.post_id == "carousel_post_1"


@resp_mock.activate
def test_publish_carousel_single_url_falls_back_to_single(publisher):
    resp_mock.add(resp_mock.POST, f"{GRAPH}/123456789/media", json=CONTAINER_RESP)
    resp_mock.add(resp_mock.GET, f"{GRAPH}/container_abc", json=FINISHED_RESP)
    resp_mock.add(resp_mock.POST, f"{GRAPH}/123456789/media_publish", json=PUBLISH_RESP)

    result = publisher.publish_carousel(["https://i.imgur.com/only.png"], "Caption")
    assert result.success is True


def test_publish_carousel_empty_list_fails(publisher):
    result = publisher.publish_carousel([], "Caption")
    assert result.success is False


@resp_mock.activate
def test_verify_credentials_true(publisher):
    resp_mock.add(resp_mock.GET, f"{GRAPH}/123456789", json=USER_RESP)
    assert publisher.verify_credentials() is True


@resp_mock.activate
def test_verify_credentials_false_on_api_error(publisher):
    resp_mock.add(resp_mock.GET, f"{GRAPH}/123456789", status=401)
    assert publisher.verify_credentials() is False


def test_verify_credentials_false_without_creds(publisher_no_creds):
    assert publisher_no_creds.verify_credentials() is False
