import os
from types import SimpleNamespace
from core.handlers.file_handler import FileHandler
from core.handlers.models import ConversionSettings


def test_scan_directory_finds_video_extensions(tmp_path):
    settings = ConversionSettings()
    handler = FileHandler(settings, SimpleNamespace(ffprobe_path="ffprobe"))
    (tmp_path / "a.mp4").write_bytes(b"0")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "b.mkv").write_bytes(b"0")
    (tmp_path / "skip.txt").write_text("no")
    result = handler.scan_directory(str(tmp_path), recursive=True)
    assert result["status"] == "success"
    assert result["count"] == 2
    paths = {os.path.basename(f["path"]) for f in result["files"]}
    assert paths == {"a.mp4", "b.mkv"}


def test_scan_directory_missing():
    settings = ConversionSettings()
    handler = FileHandler(settings, SimpleNamespace(ffprobe_path="ffprobe"))
    result = handler.scan_directory("/nonexistent/path/encodeforge", recursive=True)
    assert result["status"] == "error"
    assert result["files"] == []


def test_get_file_info_missing_file():
    settings = ConversionSettings()
    handler = FileHandler(settings, SimpleNamespace(ffprobe_path="ffprobe"))
    result = handler.get_file_info("/nonexistent/video.mp4")
    assert result["status"] == "error"
    assert result["duration"] == 0


def test_get_file_info_uses_ffprobe_json(tmp_path, monkeypatch):
    settings = ConversionSettings()
    handler = FileHandler(settings, SimpleNamespace(ffprobe_path="ffprobe"))
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")

    payload = '{"format":{"duration":"3.25","size":"999","format_name":"mov_mp4_m4a"}}'

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        assert "ffprobe" in cmd[0] or cmd[0] == "ffprobe"
        return SimpleNamespace(returncode=0, stdout=payload, stderr="")

    monkeypatch.setattr("core.handlers.file_handler.subprocess.run", fake_run)
    result = handler.get_file_info(str(media))
    assert result["status"] == "success"
    assert result["duration"] == 3.25
    assert result["format"] == "mov_mp4_m4a"
