from pathlib import Path

import pytest

from tests.support.media_assets import trim_video


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.requires_whisper
def test_check_whisper_status(core_ffmpeg):
    st = core_ffmpeg.check_whisper()
    assert st["status"] == "success"
    if not st.get("whisper_available"):
        pytest.skip("faster-whisper not installed")
    if not st.get("installed_models"):
        pytest.skip("No Whisper models cached — download one in app settings or run download test")


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.requires_whisper
def test_generate_subtitles_short_clip(core_ffmpeg, session_cached_sample_mp4, tmp_path):
    st = core_ffmpeg.check_whisper()
    if not st.get("whisper_available") or not st.get("installed_models"):
        pytest.skip("Whisper or cached models unavailable")

    ffmpeg = str(core_ffmpeg.ffmpeg_mgr.get_ffmpeg_path() or "ffmpeg")
    clip = tmp_path / "whisper_clip.mp4"
    trim_video(session_cached_sample_mp4, clip, 6.0, ffmpeg_bin=ffmpeg)

    core_ffmpeg.settings.whisper_model = st["installed_models"][0]
    r = core_ffmpeg.generate_subtitles(str(clip), language="eng")
    assert r["status"] == "success", r.get("message", r)
    sub = r.get("subtitle") or {}
    path = sub.get("file_path")
    assert path
    assert Path(path).exists()
