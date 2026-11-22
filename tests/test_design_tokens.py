"""Design system: single token set drives theme CSS."""

from __future__ import annotations

from utils.app_stylesheet import (
    apply_token_placeholders,
    build_app_stylesheet,
    build_splash_stylesheet,
)
from utils.design_tokens import THEME_NAME, default_tokens


def test_default_tokens_are_flat_dark_not_purple():
    t = default_tokens()
    assert THEME_NAME == "flat_dark"
    assert t.accent.lower() == "#3b82f6"
    assert "99,102,241" not in t.accent_soft  # old indigo soft
    assert t.bg_base.startswith("#")


def test_theme_base_placeholders_fully_substituted():
    css = build_app_stylesheet(default_tokens())
    assert "__accent__" not in css
    assert "__bg_base__" not in css
    assert "#3b82f6" in css
    assert "section_card" in css
    assert "glass_card" not in css
    assert "#6366f1" not in css


def test_splash_stylesheet_uses_same_accent():
    css = build_splash_stylesheet(default_tokens())
    assert "__accent__" not in css
    assert default_tokens().accent in css


def test_apply_token_placeholders_roundtrip():
    sample = "color: __accent__; bg: __bg_base__;"
    out = apply_token_placeholders(sample, default_tokens())
    assert out == f"color: {default_tokens().accent}; bg: {default_tokens().bg_base};"
