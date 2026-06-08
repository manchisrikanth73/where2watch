"""Instagram / Facebook long-lived access token inspector and refresher.

Facebook long-lived tokens expire after 60 days.  This module handles:
  - Inspecting the current token to see how many days remain
  - Refreshing it before it expires (recommended: refresh when < 14 days remain)
  - Requires FACEBOOK_APP_ID + FACEBOOK_APP_SECRET (register a Facebook App at
    https://developers.facebook.com/apps/ — the same app that powers the
    Instagram Graph API integration)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

_GRAPH = "https://graph.facebook.com/v19.0"
_DEBUG_TOKEN_URL = "https://graph.facebook.com/debug_token"


@dataclass
class TokenInfo:
    is_valid: bool
    expires_at: Optional[datetime]
    days_remaining: Optional[int]
    error: Optional[str] = None

    @property
    def never_expires(self) -> bool:
        return self.is_valid and self.expires_at is None


class TokenRefresher:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.session = requests.Session()

    def _has_app_credentials(self) -> bool:
        return bool(self.settings.facebook_app_id and self.settings.facebook_app_secret)

    def inspect_token(self, token: Optional[str] = None) -> TokenInfo:
        """Query Facebook's /debug_token endpoint to check validity and expiry."""
        input_token = token or self.settings.instagram_access_token
        if not input_token:
            return TokenInfo(is_valid=False, expires_at=None, days_remaining=None,
                             error="No access token configured")

        if not self._has_app_credentials():
            return TokenInfo(is_valid=False, expires_at=None, days_remaining=None,
                             error="FACEBOOK_APP_ID and FACEBOOK_APP_SECRET are required")

        return self._call_debug_token(input_token)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30),
           reraise=True)
    def _call_debug_token(self, input_token: str) -> TokenInfo:
        app_token = f"{self.settings.facebook_app_id}|{self.settings.facebook_app_secret}"
        resp = self.session.get(
            _DEBUG_TOKEN_URL,
            params={"input_token": input_token, "access_token": app_token},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})

        if not data.get("is_valid", False):
            error_obj = data.get("error", {})
            msg = error_obj.get("message", "Token is invalid")
            return TokenInfo(is_valid=False, expires_at=None, days_remaining=None, error=msg)

        expires_at_ts = data.get("expires_at")
        if expires_at_ts and expires_at_ts != 0:
            expires_dt = datetime.fromtimestamp(expires_at_ts, tz=timezone.utc)
            now = datetime.now(tz=timezone.utc)
            days = max(0, (expires_dt - now).days)
            return TokenInfo(is_valid=True, expires_at=expires_dt, days_remaining=days)

        # Token that never expires (rare but possible for some app-level tokens)
        return TokenInfo(is_valid=True, expires_at=None, days_remaining=None)

    def needs_refresh(self, threshold_days: int = 14, token: Optional[str] = None) -> bool:
        """Return True when the token is invalid or expires within threshold_days."""
        info = self.inspect_token(token)
        if not info.is_valid:
            logger.warning("Token is invalid: %s", info.error)
            return True
        if info.never_expires:
            return False
        assert info.days_remaining is not None
        if info.days_remaining < threshold_days:
            logger.info(
                "Token expires in %d day(s) — below %d-day threshold, refresh needed",
                info.days_remaining,
                threshold_days,
            )
            return True
        logger.info("Token is healthy: %d day(s) remaining", info.days_remaining)
        return False

    def refresh(self, token: Optional[str] = None) -> str:
        """Exchange current token for a new 60-day long-lived token.

        Returns the new token string.  Raises on failure.
        """
        current_token = token or self.settings.instagram_access_token
        if not current_token:
            raise ValueError("No access token to refresh")
        if not self._has_app_credentials():
            raise ValueError("FACEBOOK_APP_ID and FACEBOOK_APP_SECRET are required for token refresh")

        return self._call_token_exchange(current_token)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=2, min=4, max=30),
           reraise=True)
    def _call_token_exchange(self, current_token: str) -> str:
        resp = self.session.get(
            f"{_GRAPH}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": self.settings.facebook_app_id,
                "client_secret": self.settings.facebook_app_secret,
                "fb_exchange_token": current_token,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        new_token = data.get("access_token")
        if not new_token:
            raise RuntimeError(f"Unexpected response from token exchange: {data}")

        expires_in = data.get("expires_in", 0)
        days = expires_in // 86400 if expires_in else 0
        logger.info("Token refreshed successfully — new token expires in ~%d days", days)
        return new_token  # type: ignore[return-value]
