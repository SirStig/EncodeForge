"""
Shared rename pattern formatting for metadata-based file renaming.

Patterns use Python's format mini-language, e.g. {title}, S{season:02d}E{episode:02d}.
Unknown placeholders format to empty strings. season and episode are integers (default 0).
"""

from __future__ import annotations

import json
import logging
import re
from string import Formatter
from typing import Any, Dict, List, Optional, Tuple

from core import path_manager

logger = logging.getLogger(__name__)

SAMPLE_TV_METADATA: Dict[str, Any] = {
    "show_title": "Breaking Bad",
    "title": "Breaking Bad",
    "year": "2008",
    "show_year": "2008",
    "season": 1,
    "episode": 5,
    "episode_title": "Gray Matter",
    "episodeTitle": "Gray Matter",
    "episode_airdate": "2008-02-24",
    "quality": "1080p",
    "resolution": "1920x1080",
    "codec": "h264",
    "audio": "AAC",
    "group": "NTb",
    "network": "AMC",
    "rating": "8.5",
}

SAMPLE_MOVIE_METADATA: Dict[str, Any] = {
    "title": "Inception",
    "year": "2010",
    "show_title": "Inception",
    "show_year": "2010",
    "season": 0,
    "episode": 0,
    "episode_title": "",
    "episodeTitle": "",
    "quality": "1080p",
    "resolution": "1920x1080",
    "codec": "h264",
    "audio": "AC3",
    "group": "",
    "rating": "8.8",
}

PLACEHOLDER_DOCS: List[Tuple[str, str]] = [
    ("title", "Show or movie title (TV uses show title when available)"),
    ("show_title", "Series title from provider (alias for title on TV)"),
    ("year", "Release or first-air year string"),
    ("show_year", "Series year string from provider"),
    ("season", "Season number (int; use {season:02d} for zero padding)"),
    ("episode", "Episode number (int; use {episode:02d} for zero padding)"),
    ("episode_title", "Episode title"),
    ("episodeTitle", "Same as episode_title (alternate spelling)"),
    ("episode_airdate", "Episode air date (YYYY-MM-DD when available)"),
    ("airdate", "Alias of episode_airdate"),
    ("date", "Alias of episode_airdate"),
    ("quality", "Quality label e.g. 1080p (often from filename heuristics)"),
    ("resolution", "Resolution e.g. 1920x1080"),
    ("codec", "Video codec short name"),
    ("audio", "Audio codec short name"),
    ("group", "Release group tag when known"),
    ("network", "Network / service name when available"),
    ("rating", "Score or rating string when available"),
    ("overview", "Short plot text (avoid in filenames unless truncated)"),
]

BUILTIN_TEMPLATE_GROUPS: List[Tuple[str, List[Tuple[str, str]]]] = [
    (
        "TV & episodes",
        [
            ("Standard (default core)", "{title} - S{season:02d}E{episode:02d} - {episode_title}"),
            ("Compact SxxExx", "{title} - S{season:02d}E{episode:02d}"),
            ("Dots (scene-style)", "{title}.S{season:02d}E{episode:02d}.{episode_title}.1080p"),
            ("Season folder style", "{title} - Season {season:02d} - {episode:02d} - {episode_title}"),
            ("Anime bracket group", "[{group}] {title} - {episode:02d} - {episode_title}"),
            ("Kodi / Jellyfin", "{title} S{season:02d}E{episode:02d} {episode_title}"),
            ("Underscores", "{title}_S{season:02d}E{episode:02d}_{episode_title}"),
            ("Date aired", "{title}.{airdate}.S{season:02d}E{episode:02d}.{episode_title}"),
        ],
    ),
    (
        "Movies",
        [
            ("Title (year)", "{title} ({year})"),
            ("Title.year", "{title}.{year}"),
            ("Dots + quality", "{title}.{year}.1080p.WEB"),
            ("Folder style", "{title} ({year}) [{quality}]"),
        ],
    ),
    (
        "Minimal / mixed",
        [
            ("Title only", "{title}"),
            ("Title + year or episode", "{title}.{year}{season:02d}{episode:02d}"),
        ],
    ),
]


def _templates_path():
    p = path_manager.get_base_dir() / "rename_templates.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_custom_templates() -> List[Tuple[str, str]]:
    path = _templates_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        raw = data.get("templates", [])
        out: List[Tuple[str, str]] = []
        for item in raw:
            if isinstance(item, dict):
                name = str(item.get("name", "")).strip()
                pat = str(item.get("pattern", "")).strip()
                if name and pat:
                    out.append((name, pat))
        return out
    except Exception as e:
        logger.warning("Could not load custom rename templates: %s", e)
        return []


def save_custom_templates(templates: List[Tuple[str, str]]) -> bool:
    path = _templates_path()
    try:
        payload = {
            "templates": [{"name": n, "pattern": p} for n, p in templates],
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as e:
        logger.error("Could not save custom rename templates: %s", e)
        return False


def _as_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_format_dict(metadata: Optional[Dict[str, Any]], file_stem: str = "") -> Dict[str, Any]:
    md = dict(metadata) if metadata else {}
    title = md.get("show_title") or md.get("title") or file_stem or "Unknown"
    show_title = md.get("show_title") or title
    year = md.get("year")
    if year is None or year == "":
        year = md.get("show_year", "")
    year = str(year) if year is not None else ""
    show_year = str(md.get("show_year", year) or "")
    season = _as_int(md.get("season"), 0)
    episode = _as_int(md.get("episode"), 0)
    ep_title = md.get("episode_title") or md.get("episodeTitle") or ""
    ep_title = str(ep_title) if ep_title is not None else ""
    air = str(md.get("episode_airdate") or md.get("airdate") or md.get("date") or "")

    return {
        "title": str(title),
        "show_title": str(show_title),
        "year": year,
        "show_year": show_year,
        "season": season,
        "episode": episode,
        "episode_title": ep_title,
        "episodeTitle": ep_title,
        "episode_airdate": air,
        "airdate": air,
        "date": air,
        "quality": str(md.get("quality", "") or ""),
        "resolution": str(md.get("resolution", "") or ""),
        "codec": str(md.get("codec", "") or ""),
        "audio": str(md.get("audio", "") or ""),
        "group": str(md.get("group", "") or ""),
        "network": str(md.get("network", "") or ""),
        "rating": str(md.get("rating", "") or ""),
        "overview": str(md.get("overview", "") or ""),
    }


class _RenameFormatMap(dict):
    def __missing__(self, key: str) -> Any:
        if key in ("season", "episode"):
            return 0
        return ""


def format_filename_stem(
    metadata: Optional[Dict[str, Any]],
    pattern: str,
    *,
    file_stem: str = "",
) -> Optional[str]:
    """
    Return filename stem (no extension) from metadata and pattern, or None on failure.
    """
    if not pattern or not str(pattern).strip():
        return None
    fmt_dict = build_format_dict(metadata, file_stem)
    try:
        result = Formatter().vformat(pattern, (), _RenameFormatMap(fmt_dict))
    except (ValueError, KeyError) as e:
        logger.error("Rename pattern format error: %s", e)
        return None
    result = result.strip()
    result = re.sub(r"\s+", " ", result)
    return result if result else None


def validate_pattern(pattern: str) -> Tuple[bool, str]:
    if not pattern or not pattern.strip():
        return False, "Pattern is empty."
    try:
        list(Formatter().parse(pattern))
    except ValueError as e:
        return False, f"Invalid pattern syntax: {e}"
    for sample in (SAMPLE_TV_METADATA, SAMPLE_MOVIE_METADATA):
        stem = format_filename_stem(sample, pattern, file_stem="Sample.File")
        if stem is None:
            return False, "Pattern could not be applied to sample metadata."
    return True, ""


def apply_filename_options(
    stem: str,
    *,
    replace_spaces: bool = False,
    lowercase: bool = False,
    remove_special: bool = False,
) -> str:
    out = stem
    if replace_spaces:
        out = out.replace(" ", ".")
    if lowercase:
        out = out.lower()
    if remove_special:
        out = "".join(c for c in out if c.isalnum() or c in ".-_ ")
    return out
