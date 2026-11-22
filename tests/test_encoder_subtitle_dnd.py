"""
P2-C: live Encoder + Subtitle tables accept drag-and-drop (Metadata already did).
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.gui

pytest.importorskip("PySide6")
from PySide6.QtCore import QThreadPool, QUrl  # noqa: E402
from PySide6.QtWidgets import QAbstractItemView  # noqa: E402


@pytest.fixture
def encoder_tab(qapp, isolated_app_data, qt_widget):
    from app.widgets.encoder_tab import EncoderTab

    return qt_widget(EncoderTab(QThreadPool()))


@pytest.fixture
def subtitle_tab(qapp, isolated_app_data, qt_widget, monkeypatch):
    from app.widgets.subtitle_tab import SubtitleTab

    # Avoid probing Whisper during construction in headless CI.
    monkeypatch.setattr(SubtitleTab, "_update_whisper_status", lambda self: None)
    return qt_widget(SubtitleTab(QThreadPool()))


def _mime_urls(paths):
    mime = MagicMock()
    mime.hasUrls.return_value = True
    mime.urls.return_value = [QUrl.fromLocalFile(str(p)) for p in paths]
    return mime


def _drop_urls(widget, paths):
    enter = MagicMock()
    enter.mimeData.return_value = _mime_urls(paths)
    widget._drag_enter_event(enter)
    enter.acceptProposedAction.assert_called()

    drop = MagicMock()
    drop.mimeData.return_value = _mime_urls(paths)
    widget._drop_event(drop)
    drop.acceptProposedAction.assert_called()


class TestEncoderSubtitleDragDrop:
    def test_encoder_table_accepts_drops(self, encoder_tab):
        assert encoder_tab.files_table.acceptDrops()
        assert (
            encoder_tab.files_table.dragDropMode()
            == QAbstractItemView.DragDropMode.DropOnly
        )

    def test_subtitle_table_accepts_drops(self, subtitle_tab):
        assert subtitle_tab.file_table.acceptDrops()
        assert (
            subtitle_tab.file_table.dragDropMode()
            == QAbstractItemView.DragDropMode.DropOnly
        )

    def test_encoder_drop_adds_video(self, encoder_tab, tmp_path):
        video = tmp_path / "clip.mkv"
        video.write_bytes(b"x")
        before = encoder_tab.files_table.rowCount()
        _drop_urls(encoder_tab, [video])
        assert encoder_tab.files_table.rowCount() == before + 1

    def test_subtitle_drop_adds_video(self, subtitle_tab, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"x")
        before = subtitle_tab.file_table.rowCount()
        _drop_urls(subtitle_tab, [video])
        assert subtitle_tab.file_table.rowCount() == before + 1

    def test_encoder_drop_adds_folder_videos(self, encoder_tab, tmp_path):
        folder = tmp_path / "batch"
        folder.mkdir()
        (folder / "a.mkv").write_bytes(b"a")
        (folder / "b.avi").write_bytes(b"b")
        (folder / "notes.txt").write_text("skip")
        before = encoder_tab.files_table.rowCount()
        _drop_urls(encoder_tab, [folder])
        assert encoder_tab.files_table.rowCount() == before + 2
