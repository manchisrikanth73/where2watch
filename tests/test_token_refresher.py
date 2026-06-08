"""Tests for TokenRefresher — Facebook/Instagram long-lived token management."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.config import Settings
from src.publisher.token_refresher import TokenInfo, TokenRefresher


@pytest.fixture
def settings():
    return Settings(
        TMDB_API_KEY="tmdb_key",
        INSTAGRAM_ACCESS_TOKEN="test_instagram_token",
        FACEBOOK_APP_ID="123456789",
        FACEBOOK_APP_SECRET="app_secret_abc",
    )


@pytest.fixture
def refresher(settings):
    return TokenRefresher(settings=settings)


def _mock_debug_response(valid: bool, expires_at: int | None = None, error_msg: str = "") -> MagicMock:
    """Build a mock response for the /debug_token endpoint."""
    data: dict = {"is_valid": valid}
    if expires_at is not None:
        data["expires_at"] = expires_at
    if error_msg:
        data["error"] = {"message": error_msg}

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"data": data}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _mock_exchange_response(new_token: str, expires_in: int = 5184000) -> MagicMock:
    """Build a mock response for the fb_exchange_token endpoint."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"access_token": new_token, "expires_in": expires_in}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ── inspect_token ──────────────────────────────────────────────────────────────

def test_inspect_token_valid_with_expiry(refresher):
    future_ts = int(time.time()) + 30 * 86400  # 30 days from now
    with patch.object(refresher.session, "get", return_value=_mock_debug_response(True, future_ts)):
        info = refresher.inspect_token()

    assert info.is_valid is True
    assert info.days_remaining is not None
    assert 29 <= info.days_remaining <= 30
    assert info.error is None


def test_inspect_token_never_expires(refresher):
    with patch.object(refresher.session, "get", return_value=_mock_debug_response(True, expires_at=0)):
        info = refresher.inspect_token()

    assert info.is_valid is True
    assert info.never_expires is True
    assert info.days_remaining is None


def test_inspect_token_invalid(refresher):
    with patch.object(
        refresher.session, "get",
        return_value=_mock_debug_response(False, error_msg="Token expired"),
    ):
        info = refresher.inspect_token()

    assert info.is_valid is False
    assert info.error == "Token expired"


def test_inspect_token_no_app_credentials():
    settings = Settings(
        TMDB_API_KEY="tmdb_key",
        INSTAGRAM_ACCESS_TOKEN="tok",
        # no FACEBOOK_APP_ID / FACEBOOK_APP_SECRET
    )
    refresher = TokenRefresher(settings=settings)
    info = refresher.inspect_token()
    assert info.is_valid is False
    assert "FACEBOOK_APP_ID" in (info.error or "")


def test_inspect_token_no_access_token():
    settings = Settings(
        TMDB_API_KEY="tmdb_key",
        FACEBOOK_APP_ID="123",
        FACEBOOK_APP_SECRET="secret",
    )
    refresher = TokenRefresher(settings=settings)
    info = refresher.inspect_token()
    assert info.is_valid is False
    assert "No access token" in (info.error or "")


def test_inspect_token_http_error_retries(refresher):
    bad_resp = MagicMock()
    bad_resp.raise_for_status.side_effect = requests.HTTPError("503")

    with patch.object(refresher.session, "get", return_value=bad_resp):
        # reraise=True means the original HTTPError bubbles up after all retries
        with pytest.raises(requests.HTTPError):
            refresher._call_debug_token("some_token")


# ── needs_refresh ──────────────────────────────────────────────────────────────

def test_needs_refresh_true_when_expiring_soon(refresher):
    soon_ts = int(time.time()) + 5 * 86400  # 5 days
    with patch.object(refresher.session, "get", return_value=_mock_debug_response(True, soon_ts)):
        assert refresher.needs_refresh(threshold_days=14) is True


def test_needs_refresh_false_when_healthy(refresher):
    far_ts = int(time.time()) + 50 * 86400  # 50 days
    with patch.object(refresher.session, "get", return_value=_mock_debug_response(True, far_ts)):
        assert refresher.needs_refresh(threshold_days=14) is False


def test_needs_refresh_true_when_token_invalid(refresher):
    with patch.object(
        refresher.session, "get",
        return_value=_mock_debug_response(False, error_msg="Expired"),
    ):
        assert refresher.needs_refresh() is True


def test_needs_refresh_false_for_never_expires(refresher):
    with patch.object(refresher.session, "get", return_value=_mock_debug_response(True, expires_at=0)):
        assert refresher.needs_refresh() is False


# ── refresh ────────────────────────────────────────────────────────────────────

def test_refresh_returns_new_token(refresher):
    with patch.object(
        refresher.session, "get",
        return_value=_mock_exchange_response("new_token_xyz"),
    ):
        token = refresher.refresh()

    assert token == "new_token_xyz"


def test_refresh_raises_on_empty_token_in_response(refresher):
    bad = MagicMock()
    bad.json.return_value = {}  # no access_token key
    bad.raise_for_status = MagicMock()

    with patch.object(refresher.session, "get", return_value=bad):
        # reraise=True means RuntimeError bubbles up after all retries
        with pytest.raises(RuntimeError, match="Unexpected response"):
            refresher._call_token_exchange("current_token")


def test_refresh_raises_when_no_credentials():
    settings = Settings(TMDB_API_KEY="tmdb_key", INSTAGRAM_ACCESS_TOKEN="tok")
    refresher = TokenRefresher(settings=settings)
    with pytest.raises(ValueError, match="FACEBOOK_APP_ID"):
        refresher.refresh()


def test_refresh_raises_when_no_token():
    settings = Settings(
        TMDB_API_KEY="tmdb_key",
        FACEBOOK_APP_ID="123",
        FACEBOOK_APP_SECRET="secret",
    )
    refresher = TokenRefresher(settings=settings)
    with pytest.raises(ValueError, match="No access token"):
        refresher.refresh()


def test_refresh_http_error_raises(refresher):
    bad = MagicMock()
    bad.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")

    with patch.object(refresher.session, "get", return_value=bad):
        # reraise=True means HTTPError bubbles up after all retries
        with pytest.raises(requests.HTTPError):
            refresher._call_token_exchange("current_token")


# ── TokenInfo helpers ──────────────────────────────────────────────────────────

def test_token_info_never_expires_property():
    info = TokenInfo(is_valid=True, expires_at=None, days_remaining=None)
    assert info.never_expires is True


def test_token_info_not_never_expires_when_has_date():
    info = TokenInfo(
        is_valid=True,
        expires_at=datetime(2025, 12, 31, tzinfo=timezone.utc),
        days_remaining=30,
    )
    assert info.never_expires is False


def test_token_info_invalid_not_never_expires():
    info = TokenInfo(is_valid=False, expires_at=None, days_remaining=None, error="bad")
    assert info.never_expires is False
