"""
Tests for the `encode` CLI command.

EncodeForgeCore is mocked so these stay off the integration marker and
exercise CLI option wiring, confirmation, and output reporting.
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


def _ok_result(output_path="out.mp4", encoder="libx264", dry_run=False):
    return {
        "status": "success",
        "message": "ok",
        "output_path": output_path,
        "encoder": encoder,
        "dry_run": dry_run,
    }


def _patch_core(return_value=None):
    """Patch EncodeForgeCore; return (CoreCls, instance) context helpers."""
    instance = MagicMock()
    instance.convert_file.return_value = return_value or _ok_result()
    return instance


class TestCliEncode:
    def test_dry_run_sets_flag_and_skips_confirm(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"\x00" * 64)
        out = tmp_path / "encoded.mp4"

        instance = _patch_core(_ok_result(str(out), dry_run=True))
        with patch("core.encodeforge_core.EncodeForgeCore", return_value=instance) as CoreCls:
            result = _invoke(runner, [
                "encode", str(video),
                "-o", str(out),
                "--dry-run",
            ])

        assert result.exit_code == 0, result.output
        settings = CoreCls.call_args.kwargs["settings"]
        assert settings.dry_run is True
        assert instance.convert_file.call_count == 1
        assert "would encode" in result.output.lower() or "would" in result.output.lower()
        assert video.exists()

    def test_real_run_with_yes_invokes_convert(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"\x00" * 64)
        out = tmp_path / "done.mp4"

        instance = _patch_core(_ok_result(str(out)))
        with patch("core.encodeforge_core.EncodeForgeCore", return_value=instance) as CoreCls:
            result = _invoke(runner, [
                "encode", str(video),
                "-o", str(out),
                "-y",
                "--codec", "h265",
                "--crf", "20",
                "--preset", "fast",
            ])

        assert result.exit_code == 0, result.output
        settings = CoreCls.call_args.kwargs["settings"]
        assert settings.video_codec_fallback == "libx265"
        assert settings.video_crf == 20
        assert settings.video_preset == "fast"
        assert settings.dry_run is False
        assert instance.convert_file.call_count == 1
        call_kwargs = instance.convert_file.call_args
        assert call_kwargs[0][0] == str(video)
        assert call_kwargs[1].get("output_path") == str(out) or (
            len(call_kwargs[0]) > 1 and call_kwargs[0][1] == str(out)
        )
        assert "ok" in result.output
        assert str(out) in result.output

    def test_without_yes_and_no_input_aborts(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"\x00" * 64)

        instance = _patch_core()
        with patch("core.encodeforge_core.EncodeForgeCore", return_value=instance):
            result = _invoke(runner, ["encode", str(video)])

        assert result.exit_code != 0
        assert instance.convert_file.call_count == 0
        assert "Cancelled" in result.output or "Aborted" in result.output

    def test_no_video_files_found_exits_nonzero(self, isolated_app_data, runner, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = _invoke(runner, ["encode", str(empty_dir), "-y"])
        assert result.exit_code != 0
        assert "No video files found" in result.output

    def test_software_default_and_hw_flags(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"\x00" * 64)

        instance = _patch_core()
        with patch("core.encodeforge_core.EncodeForgeCore", return_value=instance) as CoreCls:
            result = _invoke(runner, ["encode", str(video), "-y"])
            assert result.exit_code == 0, result.output
            settings = CoreCls.call_args.kwargs["settings"]
            assert settings.use_nvenc is False
            assert settings.use_qsv is False
            assert settings.use_amf is False
            assert settings.video_codec_fallback == "libx264"

            result2 = _invoke(runner, ["encode", str(video), "-y", "--use-nvenc", "--codec", "h265"])
            assert result2.exit_code == 0, result2.output
            settings2 = CoreCls.call_args.kwargs["settings"]
            assert settings2.use_nvenc is True
            assert settings2.video_codec_fallback == "libx265"
            assert settings2.nvenc_codec == "hevc_nvenc"

    def test_convert_failure_exits_nonzero(self, isolated_app_data, runner, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"\x00" * 64)

        instance = _patch_core({"status": "error", "message": "boom"})
        with patch("core.encodeforge_core.EncodeForgeCore", return_value=instance):
            result = _invoke(runner, ["encode", str(video), "-y"])

        assert result.exit_code == 1
        assert "boom" in result.output

    def test_batch_rejects_file_output(self, isolated_app_data, runner, tmp_path):
        (tmp_path / "a.mp4").write_bytes(b"\x00" * 32)
        (tmp_path / "b.mp4").write_bytes(b"\x00" * 32)

        result = _invoke(runner, [
            "encode", str(tmp_path),
            "-o", str(tmp_path / "single.mp4"),
            "-y",
        ])
        assert result.exit_code == 1
        assert "directory" in result.output.lower()
