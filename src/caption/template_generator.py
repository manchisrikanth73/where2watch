"""
Template-based caption generator — no external API required.

Produces platform breakdowns, hashtags, and engagement questions
entirely from the structured Release data already fetched from TMDb.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from src.aggregator.models import ContentType, LANGUAGE_DISPLAY, Release
from src.aggregator.platforms import get_platform_by_id, load_platforms

# Rotated deterministically by date.day so output varies across the month
_DAILY_OPENERS = [
    "🎬 New OTT drops for {date}!",
    "📺 Fresh content alert — {date}!",
    "🍿 Your watchlist just got bigger! {date} drops are here.",
    "🎬 Lights, camera, stream! New releases for {date}.",
    "📱 Scroll to save — new OTT drops for {date}!",
    "🔥 New releases just landed for {date}.",
    "🎬 Stay in and stream! New OTT releases for {date}.",
]

_DAILY_QUESTIONS = [
    "Which one are you watching tonight? 👇",
    "Drop your pick in the comments! 👇",
    "Tag someone to watch this with! 👇",
    "Which platform are you watching on tonight? 👇",
    "Save this post and let us know which one you pick! 👇",
    "What's first on your list? Comment below! 👇",
    "Which title are you most excited about? 👇",
]

_WEEKLY_QUESTIONS = [
    "What's your top pick this week? 👇",
    "Which title are you binging this weekend? 👇",
    "Tag a friend to watch with! 👇",
    "Save this for the weekend — what are you watching? 👇",
    "Which platform wins this week? 👇",
]

_PLATFORM_HASHTAGS: dict[str, list[str]] = {
    "netflix":        ["#Netflix"],
    "prime_video":    ["#PrimeVideo", "#AmazonPrimeVideo"],
    "disney_hotstar": ["#DisneyPlusHotstar", "#Hotstar"],
    "aha":            ["#Aha", "#AhaVideo"],
    "zee5":           ["#ZEE5"],
    "sonyliv":        ["#SonyLIV"],
    "jiohotstar":     ["#JioHotstar", "#JioCinema"],
    "apple_tv":       ["#AppleTVPlus"],
    "hulu":           ["#Hulu"],
    "max":            ["#MaxStreaming"],
}

_LANGUAGE_HASHTAGS: dict[str, list[str]] = {
    "te": ["#TeluguMovies", "#Tollywood"],
    "hi": ["#HindiMovies", "#Bollywood"],
    "ta": ["#TamilMovies", "#Kollywood"],
    "ml": ["#MalayalamMovies", "#Mollywood"],
    "kn": ["#KannadaMovies", "#Sandalwood"],
    "en": ["#Hollywood", "#EnglishMovies"],
}

_GENRE_HASHTAGS: dict[str, str] = {
    "Action":      "#ActionMovies",
    "Drama":       "#Drama",
    "Comedy":      "#Comedy",
    "Thriller":    "#Thriller",
    "Horror":      "#Horror",
    "Romance":     "#Romance",
    "Science Fiction": "#SciFi",
    "Fantasy":     "#Fantasy",
    "Crime":       "#CrimeThrillers",
    "Animation":   "#Animation",
    "Documentary": "#Documentary",
    "Adventure":   "#Adventure",
    "Mystery":     "#Mystery",
}

_CONTENT_ICONS = {
    ContentType.MOVIE:        "🎬",
    ContentType.SERIES:       "📺",
    ContentType.DOCUMENTARY:  "🎙️",
    ContentType.ANIME:        "⛩️",
}

_BASE_TAGS = [
    "#OTTReleases", "#StreamingNow", "#where2watch",
    "#NewReleases", "#OTTUpdates", "#WatchNow", "#BingeWatch",
]


def _rotate(items: list, key: int) -> str:
    return items[key % len(items)]


def _platform_display(platform_id: str) -> str:
    p = get_platform_by_id(platform_id)
    return p.display_name if p else platform_id.replace("_", " ").title()


def _build_hashtags(releases: list[Release]) -> list[str]:
    tags: set[str] = set(_BASE_TAGS)

    for r in releases:
        for tag in _PLATFORM_HASHTAGS.get(r.platform, []):
            tags.add(tag)
        for tag in _LANGUAGE_HASHTAGS.get(r.language, []):
            tags.add(tag)
        for genre in r.genres:
            if genre in _GENRE_HASHTAGS:
                tags.add(_GENRE_HASHTAGS[genre])

    content_types = {r.content_type for r in releases}
    if ContentType.MOVIE in content_types:
        tags.add("#NewMovies")
    if ContentType.SERIES in content_types:
        tags.add("#WebSeries")
    if ContentType.DOCUMENTARY in content_types:
        tags.add("#Documentaries")
    if ContentType.ANIME in content_types:
        tags.add("#Anime")

    return sorted(tags)[:25]


def _platform_breakdown(releases: list[Release]) -> str:
    by_platform: dict[str, list[Release]] = {}
    for r in releases:
        by_platform.setdefault(r.platform, []).append(r)

    lines: list[str] = []
    for pid, items in by_platform.items():
        lines.append(f"\n{_platform_display(pid)}:")
        for r in items:
            icon = _CONTENT_ICONS.get(r.content_type, "🎬")
            lang = LANGUAGE_DISPLAY.get(r.language, r.language.upper())
            lines.append(f"  {icon} {r.title} ({lang})")
    return "\n".join(lines)


def _language_summary(releases: list[Release]) -> str:
    langs = {LANGUAGE_DISPLAY.get(r.language, r.language.upper()) for r in releases}
    if not langs:
        return ""
    if len(langs) == 1:
        return f"Today's highlight is {next(iter(langs))} content."
    lang_list = ", ".join(sorted(langs)[:-1]) + f" and {sorted(langs)[-1]}"
    return f"Content spanning {lang_list} — something for everyone!"


class TemplateCaptionGenerator:
    """Generates captions, hashtags and engagement questions from Release data — no API needed."""

    def generate_daily(
        self,
        releases: list[Release],
        target_date: Optional[date] = None,
    ) -> "GeneratedCaption":
        # Import here to avoid circular import
        from src.caption.caption_generator import GeneratedCaption

        if target_date is None:
            target_date = date.today()

        date_str = target_date.strftime("%B %d, %Y")
        platform_names = sorted({_platform_display(r.platform) for r in releases})
        platforms_text = (
            ", ".join(platform_names[:-1]) + f" and {platform_names[-1]}"
            if len(platform_names) > 1
            else (platform_names[0] if platform_names else "your favourite platforms")
        )

        opener = _rotate(_DAILY_OPENERS, target_date.day).format(date=date_str)
        short_caption = (
            f"{opener} {platforms_text} {'have' if len(platform_names) > 1 else 'has'} "
            f"new releases today. Check the full list below! 👇"
        )

        breakdown = _platform_breakdown(releases)
        lang_line = _language_summary(releases)
        long_caption = (
            f"Here's your complete OTT release guide for {date_str} 🎬\n"
            f"{breakdown}\n\n"
            f"{lang_line} Save this post and share with your friends. 🍿"
        )

        return GeneratedCaption(
            short_caption=short_caption,
            long_caption=long_caption,
            hashtags=_build_hashtags(releases),
            engagement_question=_rotate(_DAILY_QUESTIONS, target_date.day),
        )

    def generate_weekly(
        self,
        releases: list[Release],
        week_label: str,
    ) -> "GeneratedCaption":
        from src.caption.caption_generator import GeneratedCaption

        platform_names = sorted({_platform_display(r.platform) for r in releases})
        platforms_text = (
            ", ".join(platform_names[:-1]) + f" and {platform_names[-1]}"
            if len(platform_names) > 1
            else (platform_names[0] if platform_names else "streaming platforms")
        )

        short_caption = (
            f"🗓️ Weekly OTT Watchlist — {week_label}! "
            f"Catch up on all the top releases this week across {platforms_text}."
        )

        breakdown = _platform_breakdown(releases)
        lang_line = _language_summary(releases)
        long_caption = (
            f"Here's what dropped across streaming platforms this week ({week_label}) 🎬\n"
            f"{breakdown}\n\n"
            f"{lang_line} Save this for your weekend binge and tag someone to watch with! 🍿"
        )

        # Use a stable key for weekly (sum of char codes in week_label)
        key = sum(ord(c) for c in week_label)
        return GeneratedCaption(
            short_caption=short_caption,
            long_caption=long_caption,
            hashtags=_build_hashtags(releases) + ["#WeeklyWatchlist", "#WeekendWatch"],
            engagement_question=_rotate(_WEEKLY_QUESTIONS, key),
        )
