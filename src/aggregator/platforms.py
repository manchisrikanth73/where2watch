"""Platform definitions loaded from config/platforms.json."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Platform:
    id: str
    display_name: str
    tmdb_provider_id: int
    region: str
    color: str
    text_color: str
    languages: list[str]
    emoji: str = ""


_DEFAULT_CONFIG = Path(__file__).parent.parent.parent / "config" / "platforms.json"


def load_platforms(config_path: Optional[Path] = None) -> list[Platform]:
    path = config_path or _DEFAULT_CONFIG
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return [Platform(**p) for p in data["platforms"]]


def get_platform_by_id(
    platform_id: str,
    platforms: Optional[list[Platform]] = None,
) -> Optional[Platform]:
    if platforms is None:
        platforms = load_platforms()
    return next((p for p in platforms if p.id == platform_id), None)
