"""
Cross-platform QFont helpers.

Hard-coding Segoe UI / Consolas looks fine on Windows and falls back poorly
elsewhere. These helpers prefer the platform's usual UI / mono faces and keep
a short fallback chain so splash and log views stay readable on macOS and Linux.

Family-list helpers are pure Python (no Qt import) so unit tests can assert
OS selection without a display server.
"""

from __future__ import annotations

import platform
from typing import TYPE_CHECKING, List, Optional, Union

if TYPE_CHECKING:
    from PySide6.QtGui import QFont


def ui_font_families() -> List[str]:
    """Ordered UI font families for the current OS."""
    system = platform.system()
    if system == "Windows":
        return ["Segoe UI", "Tahoma", "Arial", "sans-serif"]
    if system == "Darwin":
        return [
            ".AppleSystemUIFont",
            "SF Pro Text",
            "Helvetica Neue",
            "Helvetica",
            "sans-serif",
        ]
    return ["Ubuntu", "Noto Sans", "DejaVu Sans", "Liberation Sans", "sans-serif"]


def mono_font_families() -> List[str]:
    """Ordered monospace font families for the current OS."""
    system = platform.system()
    if system == "Windows":
        return ["Consolas", "Cascadia Mono", "Courier New", "monospace"]
    if system == "Darwin":
        return ["Menlo", "Monaco", "SF Mono", "Courier New", "monospace"]
    return [
        "DejaVu Sans Mono",
        "Ubuntu Mono",
        "Noto Sans Mono",
        "Liberation Mono",
        "monospace",
    ]


def ui_font(
    point_size: int,
    weight: Optional[Union["QFont.Weight", int]] = None,
) -> "QFont":
    """QFont for general UI chrome (splash, labels) with OS-aware fallbacks."""
    from PySide6.QtGui import QFont

    if weight is None:
        weight = QFont.Weight.Normal

    font = QFont()
    font.setFamilies(ui_font_families())
    font.setPointSize(point_size)
    font.setWeight(weight)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    return font


def mono_font(point_size: int = 9) -> "QFont":
    """QFont for log / code views; prefers the system fixed font when available."""
    from PySide6.QtGui import QFont, QFontDatabase

    try:
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    except Exception:
        font = QFont()

    families = [f for f in font.families() if f]
    for name in mono_font_families():
        if name not in families:
            families.append(name)
    font.setFamilies(families or mono_font_families())
    font.setPointSize(point_size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setFixedPitch(True)
    return font
