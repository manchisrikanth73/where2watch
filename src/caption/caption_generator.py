"""Generates captions, hashtags, and engagement questions via OpenAI."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.aggregator.models import LANGUAGE_DISPLAY, Release
from src.aggregator.platforms import get_platform_by_id, load_platforms
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are a social media content writer for an Indian OTT streaming page on Instagram. "
    "Your audience loves movies and web series across Netflix, Prime Video, Disney+ Hotstar, "
    "and regional platforms. Write engaging, conversational captions in English, using emojis "
    "naturally. Hashtags must be popular and relevant."
)


@dataclass
class GeneratedCaption:
    short_caption: str
    long_caption: str
    hashtags: list[str]
    engagement_question: str

    def hashtags_str(self) -> str:
        return " ".join(self.hashtags)

    def full_post(self) -> str:
        return f"{self.short_caption}\n\n{self.engagement_question}\n\n{self.hashtags_str()}"


def _releases_summary(releases: list[Release], platforms_map: dict) -> str:
    by_platform: dict[str, list[Release]] = {}
    for r in releases:
        by_platform.setdefault(r.platform, []).append(r)

    lines: list[str] = []
    for pid, items in by_platform.items():
        name = platforms_map[pid].display_name if pid in platforms_map else pid
        lines.append(f"\n{name}:")
        for r in items:
            lang = LANGUAGE_DISPLAY.get(r.language, r.language.upper())
            ct = r.content_type.value.title()
            lines.append(f"  • {r.title} ({ct}, {lang})")
    return "\n".join(lines)


class CaptionGenerator:
    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key)
        self.platforms_map = {p.id: p for p in load_platforms()}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=20))
    def _chat(self, user_prompt: str) -> dict:
        resp = self.client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=700,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        return json.loads(raw)  # type: ignore[no-any-return]

    def generate_daily(
        self,
        releases: list[Release],
        target_date: Optional[date] = None,
    ) -> GeneratedCaption:
        if target_date is None:
            target_date = date.today()

        date_str = target_date.strftime("%B %d, %Y")
        summary = _releases_summary(releases, self.platforms_map)
        platform_names = sorted(
            {self.platforms_map[r.platform].display_name for r in releases if r.platform in self.platforms_map}
        )

        prompt = (
            f"Today is {date_str}. Here are new OTT releases:\n{summary}\n\n"
            "Return JSON with these exact keys:\n"
            "- short_caption: 2-3 sentences with emojis, mention the date and top platforms\n"
            "- long_caption: 5-8 sentences highlighting specific titles and genres\n"
            "- hashtags: array of 20-25 hashtag strings (include platform names, content types, "
            "languages present, and general OTT tags)\n"
            "- engagement_question: one question to drive comments\n\n"
            f"Platforms present: {', '.join(platform_names)}"
        )

        try:
            data = self._chat(prompt)
        except Exception as exc:
            logger.error("Caption generation failed: %s", exc)
            data = {}

        return GeneratedCaption(
            short_caption=data.get(
                "short_caption",
                f"\U0001f3ac New OTT releases for {date_str}! Check out what's new across your favourite streaming platforms.",
            ),
            long_caption=data.get("long_caption", ""),
            hashtags=data.get(
                "hashtags",
                ["#OTTReleases", "#Netflix", "#PrimeVideo", "#StreamingNow", "#where2watch"],
            ),
            engagement_question=data.get(
                "engagement_question", "Which one are you watching tonight? \U0001f447"
            ),
        )

    def generate_weekly(self, releases: list[Release], week_label: str) -> GeneratedCaption:
        summary = _releases_summary(releases, self.platforms_map)
        prompt = (
            f"This is the {week_label} weekly OTT watchlist. Top releases:\n{summary}\n\n"
            "Return JSON:\n"
            "- short_caption: 2-3 sentences about the week's highlights\n"
            "- long_caption: 6-9 sentences covering platforms, genres, and languages\n"
            "- hashtags: 20-25 hashtag strings\n"
            "- engagement_question: a weekly engagement question"
        )
        try:
            data = self._chat(prompt)
        except Exception as exc:
            logger.error("Weekly caption failed: %s", exc)
            data = {}

        return GeneratedCaption(
            short_caption=data.get("short_caption", f"\U0001f5d3️ {week_label} OTT Watchlist is here!"),
            long_caption=data.get("long_caption", ""),
            hashtags=data.get("hashtags", ["#WeeklyWatchlist", "#OTTReleases", "#where2watch"]),
            engagement_question=data.get(
                "engagement_question", "What's your top pick this week? \U0001f447"
            ),
        )
