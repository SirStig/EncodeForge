from __future__ import annotations

from pathlib import Path

from utils.design_tokens import DesignTokens, default_tokens


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _theme_base_path() -> Path:
    return _project_root() / "resources" / "styles" / "theme_base.css"


def _splash_path() -> Path:
    return _project_root() / "resources" / "styles" / "splash_screen.css"


def apply_token_placeholders(css: str, tokens: DesignTokens) -> str:
    """Replace ``__token_name__`` placeholders with values from the token set."""
    out = css
    for key, value in tokens.as_mapping().items():
        out = out.replace(f"__{key}__", value)
    return out


def build_app_stylesheet(tokens: DesignTokens) -> str:
    """Compose the flat-dark app stylesheet from theme_base.css + chrome overlay."""
    base_path = _theme_base_path()
    with open(base_path, "r", encoding="utf-8") as f:
        base = f.read()
    t = tokens
    check_svg = (_project_root() / "resources" / "icons" / "check.svg").as_posix()
    overlay = f"""
/* token overlay — main chrome, dialogs, control density */
QWidget#central_root {{
    background-color: {t.bg_base};
}}

QLabel#sidebar_app_title {{
    font-size: 13px;
    font-weight: 600;
    color: {t.text_primary};
    padding: {t.space_xs} 2px {t.space_sm} 2px;
    letter-spacing: 0.2px;
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
    padding: 1px;
    color: {t.text_secondary};
    min-width: 22px;
    max-width: 22px;
    min-height: 22px;
    max-height: 22px;
    icon-size: 12px;
}}

QToolButton#titlebar_control:hover {{
    background: {t.bg_hover};
    border: 1px solid transparent;
    color: {t.text_primary};
}}

QToolButton#titlebar_menu {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {t.radius_sm};
    padding: 0px;
    color: {t.text_secondary};
    min-width: 22px;
    max-width: 22px;
    min-height: 22px;
    max-height: 22px;
    icon-size: 12px;
}}

QToolButton#titlebar_menu:hover {{
    background: {t.bg_hover};
    color: {t.text_primary};
}}

QToolButton#titlebar_menu::menu-indicator {{
    image: none;
    width: 0px;
}}

QLabel#titlebar_title {{
    font-size: {t.font_compact};
    font-weight: 500;
    color: {t.text_secondary};
    padding: 0 {t.space_sm};
}}

QStatusBar#app_bottom_bar {{
    background: {t.bg_elevated2};
    border-top: 1px solid {t.border_subtle};
    color: {t.text_muted};
    font-size: {t.font_small};
    padding: 2px {t.space_md};
    min-height: {t.bottom_bar_height};
}}

QDialog, QMessageBox {{
    background: {t.bg_elevated};
    border: 1px solid {t.border_strong};
    border-radius: {t.radius_md};
}}

QDialog QLabel#title_label {{
    font-size: 15px;
    font-weight: 600;
    color: {t.text_primary};
    padding: {t.space_sm} {t.space_md};
}}

QDialog QLabel#subtitle_label {{
    font-size: 12px;
    color: {t.text_secondary};
    padding: {t.space_xs} {t.space_md};
}}

QPushButton {{
    min-height: {t.control_min_height};
    padding: 3px 12px;
}}

QComboBox {{
    min-height: {t.control_min_height};
    padding: 2px 26px 2px 9px;
}}

QComboBox::drop-down {{
    width: 20px;
}}

QComboBox QAbstractItemView::item {{
    padding: 4px 10px;
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
    padding: 5px 14px;
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
    border-radius: 3px;
    background: {t.bg_elevated};
    border: 1.5px solid {t.border_muted};
}}

QCheckBox::indicator:hover {{
    border-color: {t.accent_hover};
}}

QCheckBox::indicator:checked {{
    background: {t.accent};
    border-color: {t.accent};
    image: url({check_svg});
}}

QCheckBox::indicator:disabled {{
    background: {t.bg_sidebar};
    border-color: {t.border_subtle};
}}

QToolButton#statusbar_indicator {{
    background: transparent;
    border: none;
    border-radius: 2px;
    padding: 0px 5px;
    margin: 0px;
    font-size: 10px;
    font-weight: 400;
    color: {t.text_muted};
}}

QToolButton#statusbar_indicator:hover {{
    background: rgba(255, 255, 255, 0.05);
    color: {t.text_secondary};
}}

QToolButton#statusbar_indicator[status="ok"] {{
    color: {t.status_ok};
}}

QToolButton#statusbar_indicator[status="warn"] {{
    color: {t.status_warn};
}}

QTabBar::tab {{
    min-width: 70px;
}}

QHeaderView::section {{
    padding: 3px 6px;
    font-size: 9px;
}}

QFrame#update_toast QLabel#update_toast_title {{
    font-size: 13px;
    font-weight: 600;
    color: {t.text_primary};
}}

QFrame#update_toast QLabel#update_toast_subtitle {{
    font-size: {t.font_ui_size};
    color: {t.text_secondary};
}}
"""
    return apply_token_placeholders(base, tokens).rstrip() + "\n" + overlay


def build_splash_stylesheet(tokens: DesignTokens | None = None) -> str:
    """Splash CSS with the same token set as the main app theme."""
    t = tokens if tokens is not None else default_tokens()
    path = _splash_path()
    with open(path, "r", encoding="utf-8") as f:
        return apply_token_placeholders(f.read(), t)
