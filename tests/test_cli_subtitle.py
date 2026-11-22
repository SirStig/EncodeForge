"""
Tests for the `subtitle` CLI command.

Uses the same settings-merge path as the GUI (`subtitle_core_from_settings` /
`build_subtitle_settings_dict`). Network / Whisper work is mocked so these
exercise CLI wiring and exit codes only.
"""

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


def _invoke(runner, args):
    import cli
    return runner.invoke(cli.cli, args)


class TestCliSubtitle:
    def test_no_video_files_found_exits_nonzero(self, isolated_app_data, runner, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = _invoke(runner, ["subtitle", str(empty_dir)])
        assert result.exit_code != 0
        assert "No video files found" in result.output

    def test_download_uses_shared_settings_merge(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "Show.S01E01.mkv"
        video.write_text("DATA")
        fake_core = MagicMock()
        fake_core.download_subtitles.return_value = {
            "status": "success",
            "message": "Downloaded 1 subtitle(s)",
            "subtitles_downloaded": [{"subtitle_path": str(tmp_path / "Show.S01E01.eng.srt")}],
        }
        captured = {}

        def capture_build(subtitle_settings):
            captured.update(subtitle_settings)
            return fake_core

        with patch("utils.settings_manager.subtitle_core_from_settings", side_effect=capture_build):
            result = _invoke(runner, [
                "subtitle", str(video),
                "--language", "en",
                "--provider", "opensubtitles",
            ])

        assert result.exit_code == 0, result.output
        assert "ok" in result.output
        assert captured.get("languages") == ["eng"]
        assert captured.get("providers") == ["opensubtitles"]
        fake_core.download_subtitles.assert_called_once_with(
            str(video), languages=["eng"]
        )

    def test_generate_flag_calls_whisper_path(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "movie.mp4"
        video.write_text("DATA")
        fake_core = MagicMock()
        fake_core.generate_subtitles.return_value = {
            "status": "success",
            "message": "Generated with base",
            "subtitle": {"path": str(tmp_path / "movie.eng.srt")},
        }

        with patch("utils.settings_manager.subtitle_core_from_settings", return_value=fake_core):
            result = _invoke(runner, [
                "subtitle", str(video),
                "--generate",
                "--model", "base",
                "-l", "eng",
            ])

        assert result.exit_code == 0, result.output
        fake_core.generate_subtitles.assert_called_once()
        fake_core.download_subtitles.assert_not_called()
        call_kwargs = fake_core.generate_subtitles.call_args
        assert call_kwargs[0][0] == str(video)
        assert call_kwargs[1].get("language") == "eng" or (
            len(call_kwargs[0]) > 1 and call_kwargs[0][1] == "eng"
        )
        assert "ok" in result.output

    def test_download_failure_exits_nonzero(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "lonely.mkv"
        video.write_text("DATA")
        fake_core = MagicMock()
        fake_core.download_subtitles.return_value = {
            "status": "error",
            "message": "No subtitles found",
            "subtitles_downloaded": [],
        }

        with patch("utils.settings_manager.subtitle_core_from_settings", return_value=fake_core):
            result = _invoke(runner, ["subtitle", str(video)])

        assert result.exit_code == 1
        assert "fail" in result.output
        assert "No subtitles found" in result.output

    def test_defaults_come_from_saved_subtitle_settings(self, isolated_app_data, runner, tmp_path):
        from utils.settings_manager import get_settings_manager

        sm = get_settings_manager()
        sm.subtitle.whisper_model = "small"
        sm.subtitle.language = "Spanish"
        sm.subtitle.providers = ["SubDL", "Addic7ed"]
        sm.save()

        video = tmp_path / "clip.mkv"
        video.write_text("DATA")
        fake_core = MagicMock()
        fake_core.generate_subtitles.return_value = {
            "status": "success",
            "message": "ok",
            "subtitle": {"path": str(tmp_path / "clip.spa.srt")},
        }

        captured = {}

        def capture_build(subtitle_settings):
            captured.update(subtitle_settings)
            return fake_core

        with patch("utils.settings_manager.subtitle_core_from_settings", side_effect=capture_build):
            result = _invoke(runner, ["subtitle", str(video), "--generate"])

        assert result.exit_code == 0, result.output
        assert captured.get("whisper_model") == "small"
        assert captured.get("languages") == ["spa"]
        assert [p.lower() for p in captured.get("providers", [])] == ["subdl", "addic7ed"]

    def test_model_flag_overrides_saved_whisper_model(self, isolated_app_data, runner, tmp_path):
        from utils.settings_manager import get_settings_manager

        sm = get_settings_manager()
        sm.subtitle.whisper_model = "medium"
        sm.save()

        video = tmp_path / "clip.mkv"
        video.write_text("DATA")
        fake_core = MagicMock()
        fake_core.generate_subtitles.return_value = {
            "status": "success",
            "message": "ok",
            "subtitle": {},
        }
        captured = {}

        def capture_build(subtitle_settings):
            captured.update(subtitle_settings)
            return fake_core

        with patch("utils.settings_manager.subtitle_core_from_settings", side_effect=capture_build):
            result = _invoke(runner, [
                "subtitle", str(video), "--generate", "--model", "tiny",
            ])

        assert result.exit_code == 0, result.output
        assert captured.get("whisper_model") == "tiny"
