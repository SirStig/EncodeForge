from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DesignTokens:
    bg_base: str
    bg_elevated: str
    bg_elevated2: str
    border_subtle: str
    border_strong: str
    accent: str
    accent_soft: str
    text_primary: str
    text_secondary: str
    text_muted: str
    radius_sm: str
    radius_md: str
    radius_lg: str
    space_xs: str
    space_sm: str
    space_md: str
    space_lg: str
    font_ui_size: str
    font_small: str
    control_min_height: str
    title_bar_height: str
    bottom_bar_height: str
    font_compact: str


def default_tokens() -> DesignTokens:
    return DesignTokens(
        bg_base="#141416",
        bg_elevated="#1e1e22",
        bg_elevated2="#111114",
        border_subtle="rgba(255,255,255,0.10)",
        border_strong="rgba(255,255,255,0.14)",
        accent="#6366f1",
        accent_soft="rgba(99,102,241,0.35)",
        text_primary="rgba(255,255,255,0.92)",
        text_secondary="rgba(255,255,255,0.65)",
        text_muted="rgba(255,255,255,0.55)",
        radius_sm="6px",
        radius_md="8px",
        radius_lg="12px",
        space_xs="4px",
        space_sm="8px",
        space_md="12px",
        space_lg="16px",
        font_ui_size="12px",
        font_small="11px",
        control_min_height="24px",
        title_bar_height="34px",
        bottom_bar_height="24px",
        font_compact="11px",
    )
