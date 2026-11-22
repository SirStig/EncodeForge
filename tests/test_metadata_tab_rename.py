"""
Tests for MetadataTab's Apply Rename / Undo — the GUI's own rename path.

This used to be a standalone Path.rename() loop with no collision guard, no
backup, and an in-memory-only undo. It now builds RenamePair objects and
funnels through core.rename_executor, the same path RenamingHandler (CLI)
uses. These tests exercise that GUI code directly (not mocked out) against
a real temp directory; only the QMessageBox confirmation prompt is stubbed
since there's no one to click it in a headless test run.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.gui

pyside6 = pytest.importorskip("PySide6")
from PySide6.QtCore import Qt, QThreadPool  # noqa: E402
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem  # noqa: E402


@pytest.fixture
def tab(qapp, isolated_app_data, qt_widget):
    from app.widgets.metadata_tab import MetadataTab
    return qt_widget(MetadataTab(QThreadPool()))


def test_metadata_tab_has_no_language_combo(tab):
    """P1-D: decorative Language combo never reached providers — removed."""
    assert not hasattr(tab, "language_combo")
    assert hasattr(tab, "provider_combo")
    assert hasattr(tab, "pattern_input")


def _seed_row(tab, file_path: Path, metadata: dict):
    tab._add_file_to_table(file_path)
    row = tab.file_table.rowCount() - 1
    tab.metadata_table.setRowCount(row + 1)
    item = QTableWidgetItem("preview")
    item.setData(Qt.ItemDataRole.UserRole, metadata)
    tab.metadata_table.setItem(row, 0, item)
    return row


class TestApplyRename:
    def test_apply_rename_moves_the_file_and_enables_undo(self, tab, tmp_path):
        video = tmp_path / "Show.S01E05.1080p.mkv"
        video.write_text("DATA")
        _seed_row(tab, video, {"title": "Show", "season": 1, "episode": 5, "episode_title": "Ep"})
        tab.pattern_input.setText("{title} - S{season:02d}E{episode:02d} - {episode_title}")

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            tab._apply_rename()

        renamed = tmp_path / "Show - S01E05 - Ep.mkv"
        assert renamed.exists()
        assert not video.exists()
        assert tab.undo_btn.isEnabled()

    def test_apply_rename_carries_sidecar_subtitle(self, tab, tmp_path):
        video = tmp_path / "Show.S01E05.1080p.mkv"
        video.write_text("VIDEO")
        srt = tmp_path / "Show.S01E05.1080p.srt"
        srt.write_text("SUBS")
        _seed_row(tab, video, {"title": "Show", "season": 1, "episode": 5, "episode_title": "Ep"})
        tab.pattern_input.setText("{title} - S{season:02d}E{episode:02d}")

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            tab._apply_rename()

        assert (tmp_path / "Show - S01E05.mkv").exists()
        assert (tmp_path / "Show - S01E05.srt").exists()
        assert (tmp_path / "Show - S01E05.srt").read_text() == "SUBS"

    def test_apply_rename_declined_confirmation_leaves_file_untouched(self, tab, tmp_path):
        video = tmp_path / "Show.S01E05.1080p.mkv"
        video.write_text("DATA")
        _seed_row(tab, video, {"title": "Show", "season": 1, "episode": 5, "episode_title": "Ep"})
        tab.pattern_input.setText("{title} - S{season:02d}E{episode:02d}")

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
            tab._apply_rename()

        assert video.exists()
        assert not tab.undo_btn.isEnabled()

    def test_two_rows_colliding_on_the_same_target_are_both_refused(self, tab, tmp_path):
        first = tmp_path / "Show.S01E05.1080p.mkv"
        second = tmp_path / "Show.S01E05.720p.mkv"
        first.write_text("FIRST")
        second.write_text("SECOND")
        meta = {"title": "Show", "season": 1, "episode": 5, "episode_title": "Ep"}
        _seed_row(tab, first, meta)
        _seed_row(tab, second, meta)
        tab.pattern_input.setText("{title} - S{season:02d}E{episode:02d}")

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            tab._apply_rename()

        # Neither file was renamed — the collision is caught before either moves.
        assert first.exists() and first.read_text() == "FIRST"
        assert second.exists() and second.read_text() == "SECOND"
        assert not (tmp_path / "Show - S01E05.mkv").exists()

    def test_undo_reverses_the_last_batch(self, tab, tmp_path):
        video = tmp_path / "Show.S01E05.1080p.mkv"
        video.write_text("DATA")
        _seed_row(tab, video, {"title": "Show", "season": 1, "episode": 5, "episode_title": "Ep"})
        tab.pattern_input.setText("{title} - S{season:02d}E{episode:02d}")

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            tab._apply_rename()
        assert not video.exists()

        tab._undo_rename()
        assert video.exists()
        assert video.read_text() == "DATA"

    def test_destination_root_and_action_from_settings_are_honoured(self, tab, tmp_path):
        from utils.settings_manager import get_settings_manager

        video = tmp_path / "src" / "Show.S01E05.1080p.mkv"
        video.parent.mkdir()
        video.write_text("DATA")
        dest_root = tmp_path / "library"

        sm = get_settings_manager()
        sm.renamer.destination_root = str(dest_root)
        sm.renamer.action = "copy"

        _seed_row(tab, video, {"title": "Show", "season": 1, "episode": 5})
        tab.pattern_input.setText("{title}/Season {season:02d}/{title} - S{season:02d}E{episode:02d}")

        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            tab._apply_rename()

        moved = dest_root / "Show" / "Season 01" / "Show - S01E05.mkv"
        assert moved.exists()
        assert moved.read_text() == "DATA"
        # action was "copy" — the original must still be there.
        assert video.exists()


class TestSettingsRefresh:
    """P1-C / H4: settings save must refresh Metadata tab providers + options."""

    def test_sync_filename_options_loads_renamer_settings(self, tab):
        from utils.settings_manager import get_settings_manager

        sm = get_settings_manager()
        sm.renamer.pattern = "{title} ({year})"
        sm.renamer.replace_spaces = True
        sm.renamer.lowercase = True
        sm.renamer.remove_special = True
        sm.renamer.preserve_extension = False

        tab.sync_filename_options()

        assert tab.pattern_input.text() == "{title} ({year})"
        assert tab.replace_spaces_check.isChecked() is True
        assert tab.lowercase_check.isChecked() is True
        assert tab.remove_special_check.isChecked() is True
        assert tab.preserve_extension_check.isChecked() is False

    def test_refresh_providers_adds_keyed_provider_after_key_saved(self, tab):
        from utils.settings_manager import get_settings_manager

        assert tab.provider_combo.findData("tmdb") < 0

        sm = get_settings_manager()
        sm.conversion.tmdb_api_key = "test-tmdb-key"
        tab.refresh_providers()

        assert tab.provider_combo.findData("tmdb") >= 0

    def test_on_settings_changed_refreshes_metadata_tab(
        self, qapp, isolated_app_data, qt_widget
    ):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from app.main_window import MainWindow
        from app.widgets.metadata_tab import MetadataTab
        from utils.settings_manager import get_settings_manager

        metadata_tab = qt_widget(MetadataTab(QThreadPool()))
        assert metadata_tab.provider_combo.findData("omdb") < 0
        assert metadata_tab.lowercase_check.isChecked() is False

        sm = get_settings_manager()
        sm.conversion.omdb_api_key = "test-omdb-key"
        sm.renamer.lowercase = True
        sm.renamer.replace_spaces = True
        sm.renamer.pattern = "{title} - {episode_title}"

        host = SimpleNamespace(
            threadpool=MagicMock(),
            subtitle_tab=None,
            metadata_tab=metadata_tab,
            _sync_metadata_api_keys=MagicMock(),
            _apply_statusbar_visibility=MagicMock(),
        )
        MainWindow._on_settings_changed(host)
        host._sync_metadata_api_keys.assert_called_once()
        host._apply_statusbar_visibility.assert_called_once()

        assert metadata_tab.provider_combo.findData("omdb") >= 0
        assert metadata_tab.lowercase_check.isChecked() is True
        assert metadata_tab.replace_spaces_check.isChecked() is True
        assert metadata_tab.pattern_input.text() == "{title} - {episode_title}"
