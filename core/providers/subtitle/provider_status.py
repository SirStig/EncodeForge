"""
Honest availability for subtitle providers.

Podnapisi, SubDivX, and Jimaku scrape site layouts that have changed and
return empty results without a clear failure. They stay in the codebase for
a future rewrite but are quarantined: skipped by default searches and shown
as unavailable in the UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ProviderStatus:
    """Canonical provider identity + availability."""

    name: str
    ui_label: str
    available: bool
    reason: str = ""


# Display order matches the live Subtitles tab provider list.
PROVIDER_CATALOG: Tuple[ProviderStatus, ...] = (
    ProviderStatus("OpenSubtitles.com", "OpenSubtitles", True),
    ProviderStatus("Addic7ed", "Addic7ed", True),
    ProviderStatus("SubDL", "SubDL", True),
    ProviderStatus("Subf2m", "Subf2m", True),
    ProviderStatus("YIFY", "YIFY Subtitles", True),
    ProviderStatus(
        "Podnapisi",
        "Podnapisi",
        False,
        "Site layout changed; scraper quarantined until rewritten",
    ),
    ProviderStatus(
        "SubDivX",
        "SubDivX",
        False,
        "Site layout changed; scraper quarantined until rewritten",
    ),
    ProviderStatus(
        "Jimaku",
        "Jimaku",
        False,
        "Site layout changed; scraper quarantined until rewritten",
    ),
)

QUARANTINED_PROVIDERS = frozenset(p.name for p in PROVIDER_CATALOG if not p.available)

# UI / settings labels → canonical name used by SubtitleProviders.
_LABEL_ALIASES: Dict[str, str] = {
    "opensubtitles": "OpenSubtitles.com",
    "opensubtitles.com": "OpenSubtitles.com",
    "addic7ed": "Addic7ed",
    "subdl": "SubDL",
    "subf2m": "Subf2m",
    "yify": "YIFY",
    "yify subtitles": "YIFY",
    "podnapisi": "Podnapisi",
    "subdivx": "SubDivX",
    "jimaku": "Jimaku",
    "jimaku (japanese)": "Jimaku",
}


def canonicalize_provider_name(name: str) -> str:
    """Map a UI label or internal name to the catalog canonical name."""
    if not name:
        return ""
    key = name.strip().lower().replace(".com", "")
    if key == "opensubtitles":
        return "OpenSubtitles.com"
    return _LABEL_ALIASES.get(name.strip().lower(), name.strip())


def is_provider_quarantined(name: str) -> bool:
    """True when the provider is known-broken and must not be queried."""
    return canonicalize_provider_name(name) in QUARANTINED_PROVIDERS


def quarantine_reason(name: str) -> str:
    """Human-readable reason, or empty if the provider is available."""
    canonical = canonicalize_provider_name(name)
    for entry in PROVIDER_CATALOG:
        if entry.name == canonical:
            return entry.reason
    return ""


def available_provider_names() -> List[str]:
    return [p.name for p in PROVIDER_CATALOG if p.available]


def ui_provider_entries() -> List[Dict[str, object]]:
    """
    Rows for the Subtitles tab provider list.

    Each dict: label (display text), canonical, available, reason, selectable.
    """
    rows: List[Dict[str, object]] = [
        {
            "label": "All",
            "canonical": "All",
            "available": True,
            "reason": "",
            "selectable": True,
        }
    ]
    for entry in PROVIDER_CATALOG:
        if entry.available:
            label = entry.ui_label
        else:
            label = f"{entry.ui_label} (unavailable)"
        rows.append(
            {
                "label": label,
                "canonical": entry.name,
                "available": entry.available,
                "reason": entry.reason,
                "selectable": entry.available,
            }
        )
    return rows


def filter_enabled_against_quarantine(
    enabled: Optional[List[str]],
) -> Optional[List[str]]:
    """
    Drop quarantined names from a user selection.

    None means "all available providers" (quarantined still excluded by
    is_provider_enabled).
    """
    if enabled is None:
        return None
    kept = [
        name
        for name in enabled
        if str(name).strip().lower() == "all" or not is_provider_quarantined(str(name))
    ]
    return kept
