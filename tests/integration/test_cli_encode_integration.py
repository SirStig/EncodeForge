"""Integration: CLI encode dry-run + one real software encode via Core."""

import pytest
from click.testing import CliRunner


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
def test_cli_encode_dry_run_does_not_write_output(core_ffmpeg, synthetic_mp4, tmp_path, isolated_app_data):
    import cli

    out = tmp_path / "preview.mp4"
    runner = CliRunner()
    result = runner.invoke(cli.cli, [
        "encode", str(synthetic_mp4),
        "-o", str(out),
        "--dry-run",
        "--codec", "h264",
    ])
    assert result.exit_code == 0, result.output
    assert not out.exists()
    assert "would" in result.output.lower()


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
def test_cli_encode_one_file_software(core_ffmpeg, synthetic_mp4, tmp_path, isolated_app_data):
    import cli

    out = tmp_path / "encoded.mp4"
    runner = CliRunner()
    result = runner.invoke(cli.cli, [
        "encode", str(synthetic_mp4),
        "-o", str(out),
        "-y",
        "--codec", "h264",
        "--crf", "28",
        "--preset", "ultrafast",
        "--overwrite",
    ])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert out.stat().st_size > 1000
    assert "encoded" in result.output.lower() or "ok" in result.output.lower()
