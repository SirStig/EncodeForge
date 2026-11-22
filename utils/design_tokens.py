from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DesignTokens:
    """Single source of truth for the flat-dark desktop theme."""

    # Surfaces
    bg_base: str
    bg_elevated: str
    bg_elevated2: str
    bg_sidebar: str
    bg_control: str
    bg_hover: str
    bg_pressed: str
    bg_input: str
    bg_danger_hover: str

    # Borders
    border_subtle: str
    border_strong: str
    border_muted: str
    border_danger: str
    border_danger_hover: str

    # Accent (steel blue — media-tool, not purple/glow)
    accent: str
    accent_hover: str
    accent_pressed: str
    accent_soft: str
    accent_soft_border: str
    accent_selection: str
    accent_selection_strong: str
    accent_border: str

    # Text
    text_primary: str
    text_secondary: str
    text_muted: str
    text_disabled: str
    text_on_accent: str
    text_danger: str

    # Status
    success: str
    warning: str
    error: str
    status_ok: str
    status_warn: str

    # Radii / spacing / type / chrome
    radius_sm: str
    radius_md: str
    radius_lg: str
    space_xs: str
    space_sm: str
    space_md: str
    space_lg: str
    font_ui_size: str
    font_small: str
    font_compact: str
    control_min_height: str
    title_bar_height: str
    bottom_bar_height: str

    def as_mapping(self) -> dict[str, str]:
        return asdict(self)


THEME_NAME = "flat_dark"


def default_tokens() -> DesignTokens:
    """Flat dark palette for EncodeForge desktop chrome."""
    return DesignTokens(
        bg_base="#1a1a1a",
        bg_elevated="#252526",
        bg_elevated2="#111111",
        bg_sidebar="#1e1e1e",
        bg_control="#2d2d2d",
        bg_hover="#37373d",
        bg_pressed="#252526",
        bg_input="#1e1e1e",
        bg_danger_hover="#3a2626",
        border_subtle="#2e2e2e",
        border_strong="#3e3e42",
        border_muted="#4e4e52",
        border_danger="#6e3e3e",
        border_danger_hover="#8e4e4e",
        accent="#3b82f6",
        accent_hover="#60a5fa",
        accent_pressed="#2563eb",
        accent_soft="rgba(59,130,246,0.25)",
        accent_soft_border="rgba(59,130,246,0.20)",
        accent_selection="rgba(59,130,246,0.22)",
        accent_selection_strong="rgba(59,130,246,0.40)",
        accent_border="rgba(59,130,246,0.50)",
        text_primary="#cccccc",
        text_secondary="#9d9d9d",
        text_muted="#6e6e6e",
        text_disabled="#4e4e52",
        text_on_accent="#ffffff",
        text_danger="#f47272",
        success="#4ade80",
        warning="#fbbf24",
        error="#f87171",
        status_ok="#7a9e7a",
        status_warn="#9e8a6a",
        radius_sm="3px",
        radius_md="4px",
        radius_lg="6px",
        space_xs="4px",
        space_sm="8px",
        space_md="12px",
        space_lg="16px",
        font_ui_size="12px",
        font_small="11px",
        font_compact="11px",
        control_min_height="24px",
        title_bar_height="30px",
        bottom_bar_height="24px",
    )
