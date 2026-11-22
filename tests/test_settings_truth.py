"""
P3-A: Settings truth — no cosmetic-only toggles for unimplemented features.

Theme Light/Auto, app language, toolbar, and two_pass are hidden until wired.
Show status bar must toggle the main-window status bar.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.gui

pyside6 = pytest.importorskip("PySide6")
from PySide6.QtWidgets import QCheckBox  # noqa: E402


@pytest.fixture
def settings_panel(qapp, isolated_app_data, qt_widget):
    from app.dialogs.settings_dialog import SettingsPanel

    return qt_widget(SettingsPanel(show_action_bar=False))


class TestCosmeticControlsHidden:
    def test_no_language_or_theme_or_toolbar_or_two_pass_controls(self, settings_panel):
        assert not hasattr(settings_panel, "language_combo")
        assert not hasattr(settings_panel, "theme_combo")
        assert not hasattr(settings_panel, "show_toolbar_check")
        assert not hasattr(settings_panel, "two_pass_check")

    def test_statusbar_toggle_exists(self, settings_panel):
        assert isinstance(settings_panel.show_statusbar_check, QCheckBox)

    def test_save_forces_dark_theme_and_persists_statusbar(
        self, settings_panel, isolated_app_data
    ):
        from utils.settings_manager import SettingsManager

        settings_panel.settings.ui.theme = "light"
        settings_panel.show_statusbar_check.setChecked(False)
        settings_panel.save_to_disk(notify=False)

        SettingsManager._instance = None
        reloaded = SettingsManager()
        assert reloaded.ui.theme == "dark"
        assert reloaded.ui.show_statusbar is False


class TestStatusbarVisibility:
    def test_apply_statusbar_visibility_honours_setting(self, isolated_app_data):
        from app.main_window import MainWindow
        from utils.settings_manager import SettingsManager

        sm = SettingsManager()
        sm.ui.show_statusbar = False
        sm.save()

        statusbar = MagicMock()
        host = SimpleNamespace(statusbar=statusbar)
        MainWindow._apply_statusbar_visibility(host)
        statusbar.setVisible.assert_called_once_with(False)

        sm.ui.show_statusbar = True
        sm.save()
        statusbar.reset_mock()
        MainWindow._apply_statusbar_visibility(host)
        statusbar.setVisible.assert_called_once_with(True)

    def test_on_settings_changed_applies_statusbar(self, isolated_app_data):
        from app.main_window import MainWindow
        from utils.settings_manager import SettingsManager

        sm = SettingsManager()
        sm.ui.show_statusbar = False
        sm.save()

        host = SimpleNamespace(
            threadpool=MagicMock(),
            subtitle_tab=None,
            metadata_tab=None,
            _sync_metadata_api_keys=MagicMock(),
            _apply_statusbar_visibility=MagicMock(),
        )
        MainWindow._on_settings_changed(host)
        host._apply_statusbar_visibility.assert_called_once()
        host._sync_metadata_api_keys.assert_called_once()
