"""
Smoke tests for Encoder and Subtitle tabs.

These only construct the live widgets and assert critical controls exist —
no encoding, downloads, or Whisper. Keeps GUI regressions visible in the
unit CI matrix (see P3-D / audit plan).
"""

from pathlib import Path

import pytest

pytestmark = pytest.mark.gui

pytest.importorskip("PySide6")
from PySide6.QtCore import QThreadPool  # noqa: E402


@pytest.fixture
def encoder_tab(qapp, isolated_app_data, qt_widget):
    from app.widgets.encoder_tab import EncoderTab

    return qt_widget(EncoderTab(QThreadPool()))


@pytest.fixture
def subtitle_tab(qapp, isolated_app_data, qt_widget):
    from app.widgets.subtitle_tab import SubtitleTab

    return qt_widget(SubtitleTab(QThreadPool()))


class TestEncoderTabSmoke:
    def test_constructs_with_core_controls(self, encoder_tab):
        assert encoder_tab.files_table is not None
        assert encoder_tab.files_table.columnCount() >= 1
        assert encoder_tab.add_files_btn is not None
        assert encoder_tab.start_btn is not None
        assert encoder_tab.format_combo.count() >= 1
        assert encoder_tab.codec_combo.count() >= 1
        assert encoder_tab.hw_accel_check is not None

    def test_add_file_row_updates_table(self, encoder_tab, tmp_path):
        video = tmp_path / "clip.mkv"
        video.write_bytes(b"not-a-real-video")
        encoder_tab._add_file_to_table(video)
        assert encoder_tab.files_table.rowCount() == 1
        name_item = encoder_tab.files_table.item(0, 1)
        assert name_item is not None
        assert "clip.mkv" in name_item.text()


class TestSubtitleTabSmoke:
    def test_constructs_with_core_controls(self, subtitle_tab):
        assert subtitle_tab.file_table is not None
        assert subtitle_tab.add_files_btn is not None
        assert subtitle_tab.search_btn is not None
        assert subtitle_tab.apply_btn is not None
        assert subtitle_tab.provider_list.count() >= 1
        assert subtitle_tab.whisper_status is not None

    def test_add_file_row_updates_table(self, subtitle_tab, tmp_path):
        video = tmp_path / "episode.mkv"
        video.write_bytes(b"not-a-real-video")
        subtitle_tab._add_file_to_table(Path(video))
        assert subtitle_tab.file_table.rowCount() == 1
        item = subtitle_tab.file_table.item(0, 0)
        assert item is not None
        assert "episode.mkv" in item.text()
