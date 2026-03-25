from pathlib import Path

from core.handlers.models import ConversionSettings
from core.profile_manager import ProfileManager


def test_builtin_profiles_listed(tmp_path):
    mgr = ProfileManager(profiles_dir=tmp_path / "profiles")
    names = mgr.list_profiles()
    assert "Balanced" in names
    assert "Fast H.264" in names


def test_save_load_delete_custom_profile(tmp_path):
    profiles_dir = tmp_path / "profiles"
    mgr = ProfileManager(profiles_dir=profiles_dir)
    s = ConversionSettings()
    s.video_crf = 22
    s.output_format = "mkv"
    assert mgr.save_profile("pytest_custom", s) is True
    loaded = mgr.load_profile("pytest_custom")
    assert loaded is not None
    assert loaded.video_crf == 22
    assert loaded.output_format == "mkv"
    assert mgr.delete_profile("pytest_custom") is True
    assert mgr.load_profile("pytest_custom") is None


def test_cannot_save_builtin_name(tmp_path):
    mgr = ProfileManager(profiles_dir=tmp_path / "profiles")
    s = ConversionSettings()
    assert mgr.save_profile("Balanced", s) is False


def test_get_profile_info_builtin(tmp_path):
    mgr = ProfileManager(profiles_dir=tmp_path / "profiles")
    info = mgr.get_profile_info("Balanced")
    assert info is not None
    assert info["builtin"] is True
    assert info["settings"]["format"] == "mp4"
