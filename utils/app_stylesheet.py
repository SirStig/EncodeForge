from __future__ import annotations

from pathlib import Path

from utils.design_tokens import DesignTokens


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _theme_base_path() -> Path:
    return _project_root() / "resources" / "styles" / "theme_base.css"


def build_app_stylesheet(tokens: DesignTokens) -> str:
    base_path = _theme_base_path()
    with open(base_path, "r", encoding="utf-8") as f:
        base = f.read()
    t = tokens
    overlay = f"""
/* token overlay — main chrome, dialogs, control density */
QWidget#central_root {{
    background-color: {t.bg_base};
}}

QLabel#sidebar_app_title {{
    font-size: 13px;
    font-weight: 700;
    color: {t.text_primary};
    padding: {t.space_xs} 2px {t.space_sm} 2px;
    letter-spacing: 0.3px;
}}

QFrame#app_title_bar {{
    background-color: {t.bg_elevated};
    border: none;
    border-bottom: 1px solid {t.border_subtle};
    min-height: {t.title_bar_height};
    max-height: {t.title_bar_height};
}}

QToolButton#titlebar_control {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {t.radius_sm};
    padding: {t.space_xs} {t.space_sm};
    color: {t.text_secondary};
}}

QToolButton#titlebar_control:hover {{
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.08);
    color: {t.text_primary};
}}

QLabel#titlebar_title {{
    font-size: {t.font_compact};
    font-weight: 600;
    color: {t.text_primary};
    padding: 0 {t.space_sm};
}}

QStatusBar#app_bottom_bar {{
    background: {t.bg_elevated2};
    border-top: 1px solid rgba(255,255,255,0.07);
    color: {t.text_muted};
    font-size: {t.font_small};
    padding: 2px {t.space_md};
    min-height: {t.bottom_bar_height};
}}

QDialog, QMessageBox {{
    background: {t.bg_elevated};
    border: 1px solid {t.border_subtle};
    border-radius: {t.radius_lg};
}}

QDialog QLabel#title_label {{
    font-size: 16px;
    font-weight: 600;
    color: {t.text_primary};
    padding: {t.space_sm} {t.space_md};
}}

QDialog QLabel#subtitle_label {{
    font-size: 13px;
    color: {t.text_secondary};
    padding: {t.space_xs} {t.space_md};
}}

QPushButton {{
    min-height: {t.control_min_height};
    padding: 3px 12px;
}}

QPushButton:pressed {{
    padding-top: 4px;
    padding-bottom: 2px;
    padding-left: 12px;
    padding-right: 12px;
}}

QComboBox {{
    min-height: {t.control_min_height};
    padding: 2px 26px 2px 9px;
}}

QComboBox::drop-down {{
    width: 20px;
}}

QComboBox QAbstractItemView::item {{
    padding: 5px 10px;
    min-height: 20px;
    font-size: {t.font_compact};
}}

QLineEdit {{
    min-height: {t.control_min_height};
    padding: 2px 9px;
}}

QSpinBox {{
    min-height: {t.control_min_height};
    padding: 2px 9px;
}}

QSpinBox::up-button, QSpinBox::down-button {{
    width: 16px;
    margin: 1px;
}}

QWidget#encoder_toolbar QComboBox,
QWidget#encoder_toolbar QPushButton {{
    font-size: {t.font_compact};
}}

QWidget#tab_toolbar_strip QComboBox,
QWidget#tab_toolbar_strip QPushButton {{
    font-size: {t.font_compact};
}}

QFrame#sidebar QToolButton {{
    padding: 4px 8px;
    min-height: 24px;
    max-height: 28px;
    font-size: {t.font_compact};
}}

QTabBar::tab {{
    padding: 4px 14px;
    font-size: {t.font_compact};
}}

QToolBar {{
    padding: 3px 8px;
    spacing: 4px;
}}

QCheckBox {{
    font-size: {t.font_compact};
    spacing: 6px;
}}

QCheckBox::indicator {{
    width: 15px;
    height: 15px;
}}

QHeaderView::section {{
    padding: 3px 6px;
    font-size: 9px;
}}

QFrame#update_toast QLabel#update_toast_title {{
    font-size: 13px;
    font-weight: 700;
    color: {t.text_primary};
}}

QFrame#update_toast QLabel#update_toast_subtitle {{
    font-size: {t.font_ui_size};
    color: {t.text_secondary};
}}
"""
    return base.rstrip() + "\n" + overlay
