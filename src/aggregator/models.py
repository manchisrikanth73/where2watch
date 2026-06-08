"""Domain models for OTT releases."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class ContentType(str, Enum):
    MOVIE = "movie"
    SERIES = "series"
    DOCUMENTARY = "documentary"
    ANIME = "anime"


class Language(str, Enum):
    TELUGU = "te"
    HINDI = "hi"
    TAMIL = "ta"
    MALAYALAM = "ml"
    KANNADA = "kn"
    ENGLISH = "en"


LANGUAGE_DISPLAY: dict[str, str] = {
    "te": "Telugu",
    "hi": "Hindi",
    "ta": "Tamil",
    "ml": "Malayalam",
    "kn": "Kannada",
    "en": "English",
}

# TMDb genre IDs referenced in classification logic
GENRE_DOCUMENTARY = 99
GENRE_ANIMATION = 16


@dataclass
class Release:
    tmdb_id: int
    title: str
    original_title: str
    content_type: ContentType
    platform: str
    release_date: date
    language: str
    overview: str = ""
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    genres: list[str] = field(default_factory=list)
    genre_ids: list[int] = field(default_factory=list)
    runtime: Optional[int] = None
    rating: Optional[float] = None
    cast: list[str] = field(default_factory=list)
    poster_url: Optional[str] = None
    origin_country: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "tmdb_id": self.tmdb_id,
            "title": self.title,
            "original_title": self.original_title,
            "content_type": self.content_type.value,
            "platform": self.platform,
            "release_date": self.release_date.isoformat(),
            "language": self.language,
            "overview": self.overview,
            "poster_path": self.poster_path,
            "backdrop_path": self.backdrop_path,
            "genres": self.genres,
            "genre_ids": self.genre_ids,
            "runtime": self.runtime,
            "rating": self.rating,
            "cast": self.cast,
            "poster_url": self.poster_url,
            "origin_country": self.origin_country,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Release:
        return cls(
            tmdb_id=data["tmdb_id"],
            title=data["title"],
            original_title=data.get("original_title", data["title"]),
            content_type=ContentType(data["content_type"]),
            platform=data["platform"],
            release_date=date.fromisoformat(data["release_date"]),
            language=data.get("language", "en"),
            overview=data.get("overview", ""),
            poster_path=data.get("poster_path"),
            backdrop_path=data.get("backdrop_path"),
            genres=data.get("genres", []),
            genre_ids=data.get("genre_ids", []),
            runtime=data.get("runtime"),
            rating=data.get("rating"),
            cast=data.get("cast", []),
            poster_url=data.get("poster_url"),
            origin_country=data.get("origin_country", []),
        )
