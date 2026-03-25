from core.encodeforge_core import EncodeForgeCore
from core.handlers.models import ConversionSettings


def test_core_list_and_save_profile(isolated_app_data):
    core = EncodeForgeCore(ConversionSettings())
    listed = core.list_profiles()
    assert listed["status"] == "success"
    assert "Balanced" in listed["profiles"]

    custom = ConversionSettings()
    custom.video_crf = 24
    result = core.save_profile("pytest_core_profile", custom)
    assert result["status"] == "success"

    loaded = core.load_profile("pytest_core_profile")
    assert loaded["status"] == "success"
    prof = loaded["profile"]
    assert isinstance(prof, ConversionSettings)
    assert prof.video_crf == 24

    assert core.delete_profile("pytest_core_profile")["status"] == "success"


def test_core_get_file_info_delegates(isolated_app_data, monkeypatch):
    core = EncodeForgeCore(ConversionSettings())

    def fake_get(path: str):
        return {"status": "success", "duration": 1.0, "size": "1", "format": "mp4"}

    core._ensure_handlers_initialized()
    monkeypatch.setattr(core.file_handler, "get_file_info", fake_get)
    out = core.get_file_info("/fake/path.mp4")
    assert out["duration"] == 1.0
