"""P4-C: cross-platform font family helpers."""

from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    "system,expected",
    [
        ("Windows", "Segoe UI"),
        ("Darwin", "SF Pro Text"),
        ("Linux", "Ubuntu"),
    ],
)
def test_ui_font_families_prefer_platform_face(monkeypatch, system, expected):
    import platform

    import utils.platform_fonts as fonts

    monkeypatch.setattr(platform, "system", lambda: system)
    families = fonts.ui_font_families()
    assert expected in families
    assert families[-1] == "sans-serif"


@pytest.mark.parametrize(
    "system,expected",
    [
        ("Windows", "Consolas"),
        ("Darwin", "Menlo"),
        ("Linux", "DejaVu Sans Mono"),
    ],
)
def test_mono_font_families_prefer_platform_face(monkeypatch, system, expected):
    import platform

    import utils.platform_fonts as fonts

    monkeypatch.setattr(platform, "system", lambda: system)
    families = fonts.mono_font_families()
    assert expected in families
    assert families[-1] == "monospace"


def test_ui_and_mono_fonts_construct_qfont():
    """Needs a working Qt Gui stack; skip on headless hosts missing libEGL."""
    try:
        from PySide6.QtGui import QFont
    except ImportError as exc:
        pytest.skip(f"PySide6 QtGui unavailable: {exc}")

    from utils.platform_fonts import mono_font, ui_font

    ui = ui_font(12, QFont.Weight.Bold)
    assert ui.pointSize() == 12
    assert ui.families()

    mono = mono_font(9)
    assert mono.pointSize() == 9
    assert mono.fixedPitch() is True
    assert mono.families()
