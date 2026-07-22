"""
Tests for the `rename` CLI command.

core.encodeforge_core / RenamingHandler / rename_executor are all real —
only the network-touching metadata lookup (RenamingHandler.preview_rename)
is mocked, so these exercise the actual filesystem behaviour end to end.
"""

from unittest.mock import patch

import pytest
from click.testing import CliRunner

FAKE_PREVIEW = {
    "status": "success",
    "metadata": [{"title": "Show", "season": 1, "episode": 5, "episode_title": "Ep"}],
    "providers": ["Test"],
    "errors": [""],
}


@pytest.fixture
def runner():
    return CliRunner()


def _invoke(runner, args):
    import cli
    return runner.invoke(cli.cli, args)


class TestCliRename:
    def test_dry_run_does_not_touch_the_file(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "Show.S01E05.1080p.mkv"
        video.write_text("DATA")

        with patch("core.handlers.renaming_handler.RenamingHandler.preview_rename", return_value=FAKE_PREVIEW):
            result = _invoke(runner, [
                "rename", str(video),
                "--pattern", "{title} - S{season:02d}E{episode:02d} - {episode_title}",
                "--dry-run", "-y",
            ])

        assert result.exit_code == 0, result.output
        assert video.exists()
        assert video.read_text() == "DATA"
        assert "Would rename" in result.output

    def test_real_run_renames_and_writes_backup(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "Show.S01E05.1080p.mkv"
        video.write_text("DATA")

        with patch("core.handlers.renaming_handler.RenamingHandler.preview_rename", return_value=FAKE_PREVIEW):
            result = _invoke(runner, [
                "rename", str(video),
                "--pattern", "{title} - S{season:02d}E{episode:02d} - {episode_title}",
                "-y",
            ])

        assert result.exit_code == 0, result.output
        assert not video.exists()
        renamed = tmp_path / "Show - S01E05 - Ep.mkv"
        assert renamed.exists()
        assert renamed.read_text() == "DATA"
        assert "Backup written" in result.output

    def test_without_yes_and_no_input_aborts_without_renaming(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "Show.S01E05.1080p.mkv"
        video.write_text("DATA")

        with patch("core.handlers.renaming_handler.RenamingHandler.preview_rename", return_value=FAKE_PREVIEW):
            result = _invoke(runner, ["rename", str(video), "--pattern", "{title}"])

        assert result.exit_code != 0
        assert video.exists()
        assert video.read_text() == "DATA"

    def test_no_video_files_found_exits_nonzero(self, isolated_app_data, runner, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = _invoke(runner, ["rename", str(empty_dir), "-y"])
        assert result.exit_code != 0
        assert "No video files found" in result.output

    def test_destination_root_moves_into_subfolders(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "src" / "Show.S01E05.1080p.mkv"
        video.parent.mkdir()
        video.write_text("DATA")
        dest_root = tmp_path / "library"

        with patch("core.handlers.renaming_handler.RenamingHandler.preview_rename", return_value=FAKE_PREVIEW):
            result = _invoke(runner, [
                "rename", str(video),
                "--pattern", "{title}/Season {season:02d}/{title} - S{season:02d}E{episode:02d}",
                "--destination", str(dest_root),
                "-y",
            ])

        assert result.exit_code == 0, result.output
        moved = dest_root / "Show" / "Season 01" / "Show - S01E05.mkv"
        assert moved.exists()
        assert moved.read_text() == "DATA"
        assert not video.exists()

    def test_sidecar_subtitle_is_carried_along(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "Show.S01E05.1080p.mkv"
        video.write_text("VIDEO")
        srt = tmp_path / "Show.S01E05.1080p.srt"
        srt.write_text("SUBS")

        with patch("core.handlers.renaming_handler.RenamingHandler.preview_rename", return_value=FAKE_PREVIEW):
            result = _invoke(runner, [
                "rename", str(video),
                "--pattern", "{title} - S{season:02d}E{episode:02d}",
                "-y",
            ])

        assert result.exit_code == 0, result.output
        assert (tmp_path / "Show - S01E05.mkv").exists()
        assert (tmp_path / "Show - S01E05.srt").exists()
        assert (tmp_path / "Show - S01E05.srt").read_text() == "SUBS"
        assert "companion file" in result.output
