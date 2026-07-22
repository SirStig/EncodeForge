"""
Tests for the manual match picker (app/dialogs/match_picker_dialog.py) and
its wiring into MetadataTab: a locked (manually-matched) row must survive a
bulk "Fetch Metadata" re-run instead of being silently overwritten.
"""

from unittest.mock import patch

import pytest

pyside6 = pytest.importorskip("PySide6")
from PySide6.QtCore import Qt, QThreadPool  # noqa: E402
from PySide6.QtWidgets import QTableWidgetItem  # noqa: E402

CANDIDATES = [
    {"source": "tvdb", "show_title": "Show", "year": "2020", "season": 1, "episode": 5, "episode_title": "Ep A"},
    {"source": "tmdb", "show_title": "Show (Alt)", "year": "2020", "season": 1, "episode": 5, "episode_title": "Ep B"},
]


def _pump(app, condition, timeout_s=2.0):
    import time
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.01)
    return False


class TestMatchPickerDialog:
    def test_search_populates_and_returns_the_selected_candidate(self, qapp, isolated_app_data):
        from app.dialogs.match_picker_dialog import MatchPickerDialog

        with patch(
            "core.encodeforge_core.EncodeForgeCore.search_rename_candidates",
            return_value=CANDIDATES,
        ):
            dlg = MatchPickerDialog(
                None, QThreadPool(),
                file_stem="Show.S01E05", media_type="tv",
                initial={"title": "Show", "season": 1, "episode": 5},
            )
            assert _pump(qapp, lambda: len(dlg._candidates) == 2)

        assert dlg.results_table.rowCount() == 2
        dlg.results_table.selectRow(1)
        dlg._accept_if_selected()

        picked = dlg.selected_metadata()
        assert picked is not None
        assert picked["show_title"] == "Show (Alt)"

    def test_no_candidates_leaves_selection_empty(self, qapp, isolated_app_data):
        from app.dialogs.match_picker_dialog import MatchPickerDialog

        with patch("core.encodeforge_core.EncodeForgeCore.search_rename_candidates", return_value=[]):
            dlg = MatchPickerDialog(None, QThreadPool(), file_stem="Unknown.Thing", media_type="tv")
            assert _pump(qapp, lambda: "No candidates" in dlg.status_label.text() or dlg._candidates)

        dlg._accept_if_selected()
        assert dlg.selected_metadata() is None


class TestMetadataTabMatchLock:
    @pytest.fixture
    def tab(self, qapp, isolated_app_data):
        from app.widgets.metadata_tab import MetadataTab
        return MetadataTab(QThreadPool())

    def test_manual_match_locks_the_row_against_bulk_refetch(self, tab, qapp, tmp_path):
        video = tmp_path / "Show.S01E05.1080p.mkv"
        video.write_text("DATA")
        tab._add_file_to_table(video)
        tab.file_table.selectRow(0)

        with patch(
            "core.encodeforge_core.EncodeForgeCore.search_rename_candidates",
            return_value=CANDIDATES,
        ):
            from app.dialogs.match_picker_dialog import MatchPickerDialog

            dlg = MatchPickerDialog(
                tab, tab.thread_pool, file_stem=video.stem, media_type="tv",
                initial={"title": "Show", "season": 1, "episode": 5},
            )
            assert _pump(qapp, lambda: len(dlg._candidates) == 2)
            dlg.results_table.selectRow(1)
            dlg._accept_if_selected()

        chosen = dlg.selected_metadata()
        assert chosen is not None

        # Simulate what _open_match_picker does once the dialog accepts, without
        # driving the modal exec() loop (headless tests can't click through it).
        pattern = "{title} - S{season:02d}E{episode:02d} - {episode_title}"
        tab.pattern_input.setText(pattern)
        item = QTableWidgetItem(f"locked: {chosen['show_title']}")
        item.setData(Qt.ItemDataRole.UserRole, chosen)
        item.setData(tab.LOCK_ROLE, True)
        tab.metadata_table.setRowCount(1)
        tab.metadata_table.setItem(0, 0, item)

        # A bulk fetch must skip this row (no worker submitted for it) —
        # verified by the cell's UserRole payload staying exactly `chosen`.
        tab._fetch_metadata()
        after = tab.metadata_table.item(0, 0)
        assert after.data(tab.LOCK_ROLE) is True
        assert after.data(Qt.ItemDataRole.UserRole) == chosen

        # And Apply Rename uses the locked metadata, not a fresh lookup.
        from PySide6.QtWidgets import QMessageBox
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            tab._apply_rename()
        assert (tmp_path / "Show (Alt) - S01E05 - Ep B.mkv").exists()
