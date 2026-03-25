from dataclasses import asdict, fields

from core.handlers.models import ConversionSettings
from utils.settings_manager import SettingsManager, _conversion_from_dict


def test_conversion_settings_defaults():
    s = ConversionSettings()
    assert s.ffmpeg_path == "ffmpeg"
    assert s.output_format == "mp4"
    assert "eng" in s.subtitle_languages


def test_conversion_from_dict_filters_unknown_keys():
    data = {"video_crf": 19, "not_a_real_field": "x", "dry_run": True}
    s = _conversion_from_dict(data)
    assert s.video_crf == 19
    assert s.dry_run is True
    assert not hasattr(s, "not_a_real_field")


def test_settings_manager_roundtrip(isolated_app_data):
    sm = SettingsManager()
    sm.application.log_level = "DEBUG"
    sm.conversion.video_crf = 21
    assert sm.save() is True

    SettingsManager._instance = None
    sm2 = SettingsManager()
    assert sm2.application.log_level == "DEBUG"
    assert sm2.conversion.video_crf == 21


def test_get_merged_conversion_settings_ffmpeg_paths(isolated_app_data):
    sm = SettingsManager()
    sm.application.ffmpeg_path = "/custom/ffmpeg"
    sm.application.ffprobe_path = "/custom/ffprobe"
    merged = sm.get_merged_conversion_settings()
    assert merged.ffmpeg_path == "/custom/ffmpeg"
    assert merged.ffprobe_path == "/custom/ffprobe"


def test_settings_to_dict_contains_all_sections(isolated_app_data):
    sm = SettingsManager()
    d = sm.to_dict()
    for key in ("encoder", "subtitle", "renamer", "ui", "application", "conversion", "version"):
        assert key in d
    conv_keys = {f.name for f in fields(ConversionSettings)}
    assert conv_keys >= {"video_crf", "output_format"}
