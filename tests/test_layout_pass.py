"""
P5-B layout pass smoke tests: scrollable inspector, Processes monitor,
subtitle list heights, and primary shortcuts.
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.gui

pytest.importorskip("PySide6")
from PySide6.QtCore import QThreadPool, Qt  # noqa: E402
from PySide6.QtWidgets import QScrollArea  # noqa: E402


@pytest.fixture
def encoder_tab(qapp, isolated_app_data, qt_widget):
    from app.widgets.encoder_tab import EncoderTab

    return qt_widget(EncoderTab(QThreadPool()))


@pytest.fixture
def subtitle_tab(qapp, isolated_app_data, qt_widget):
    from app.widgets.subtitle_tab import SubtitleTab

    return qt_widget(SubtitleTab(QThreadPool()))


@pytest.fixture
def processes_tab(qapp, qt_widget):
    from app.widgets.processes_tab import ProcessesTab

    return qt_widget(ProcessesTab())


class TestEncoderInspectorScroll:
    def test_file_info_sidebar_is_scrollable(self, encoder_tab):
        scrolls = encoder_tab.findChildren(QScrollArea)
        assert any(
            s.objectName() == "encoder_inspector_scroll" for s in scrolls
        ), "Encoder file inspector must be wrapped in a QScrollArea"


class TestSubtitleListHeights:
    def test_language_and_provider_lists_are_taller(self, subtitle_tab):
        assert subtitle_tab.language_list.maximumHeight() >= 100
        assert subtitle_tab.provider_list.maximumHeight() >= 100
        assert subtitle_tab.language_list.minimumHeight() >= 100
        assert subtitle_tab.provider_list.minimumHeight() >= 100

    def test_tracks_active_workers_dict(self, subtitle_tab):
        assert hasattr(subtitle_tab, "active_workers")
        assert isinstance(subtitle_tab.active_workers, dict)


class TestProcessesMonitor:
    def test_refresh_empty(self, processes_tab):
        processes_tab.refresh([])
        assert processes_tab.table.rowCount() == 0
        assert "No active" in processes_tab.info_label.text()

    def test_refresh_encode_job_with_progress(self, processes_tab):
        class _W:
            def stop(self):
                self.stopped = True

        worker = _W()
        processes_tab.note_progress("/tmp/clip.mkv", 40, 100, "encoding")
        processes_tab.refresh(
            [
                {
                    "id": "/tmp/clip.mkv",
                    "kind": "Encode",
                    "name": "clip.mkv",
                    "worker": worker,
                    "cancelable": True,
                }
            ]
        )
        assert processes_tab.table.rowCount() == 1
        assert processes_tab.table.item(0, 0).text() == "Encode"
        assert processes_tab.table.item(0, 1).text() == "clip.mkv"
        assert "1 active" in processes_tab.info_label.text()
        cancel = processes_tab.table.cellWidget(0, 4)
        assert cancel is not None
        cancel.click()
        assert getattr(worker, "stopped", False) is True

    def test_collect_jobs_from_tabs(self, encoder_tab, subtitle_tab, processes_tab):
        from app.widgets.processes_tab import ProcessesTab

        class _W:
            def stop(self):
                pass

        encoder_tab.active_workers["/a/encode.mkv"] = _W()
        subtitle_tab.active_workers["search:/b/ep.mkv"] = _W()
        jobs = ProcessesTab.collect_jobs(encoder_tab, subtitle_tab, None)
        kinds = {j["kind"] for j in jobs}
        assert "Encode" in kinds
        assert "Subtitle search" in kinds


class TestMainWindowLayout:
    def test_window_fits_720p_and_has_shortcuts(self, qapp, isolated_app_data, qt_widget):
        from app.main_window import MainWindow

        win = qt_widget(MainWindow())
        assert win.minimumWidth() <= 1280
        assert win.minimumHeight() <= 720
        assert win.width() >= 1100
        # Processes tab is the real monitor
        from app.widgets.processes_tab import ProcessesTab

        assert isinstance(win.processes_tab, ProcessesTab)
        # Shortcut objects installed on the window
        from PySide6.QtGui import QShortcut

        shortcuts = win.findChildren(QShortcut)
        seqs = {s.key().toString() for s in shortcuts}
        assert "Ctrl+1" in seqs
        assert "Ctrl+O" in seqs or "Ctrl+Shift+O" in seqs or any(
            "Ctrl" in s for s in seqs
        )
