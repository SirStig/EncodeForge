import shutil
from pathlib import Path

import pytest

from core.encodeforge_core import EncodeForgeCore
from core.handlers.models import ConversionSettings


@pytest.fixture
def software_conversion_settings(isolated_app_data) -> ConversionSettings:
    s = ConversionSettings()
    s.use_nvenc = False
    s.use_amf = False
    s.use_qsv = False
    s.use_videotoolbox = False
    s.video_codec_fallback = "libx264"
    s.audio_codec = "aac"
    s.overwrite_existing = True
    return s


@pytest.fixture
def core_ffmpeg(isolated_app_data, software_conversion_settings) -> EncodeForgeCore:
    core = EncodeForgeCore(software_conversion_settings)
    st = core.check_ffmpeg()
    if not st.get("ffmpeg_available"):
        pytest.skip("FFmpeg/FFprobe not available on PATH")
    return core


@pytest.fixture(scope="session")
def session_cached_sample_mp4():
    from tests.support.media_assets import ensure_downloaded_sample_mp4

    try:
        return ensure_downloaded_sample_mp4()
    except Exception as exc:
        pytest.skip(f"Sample MP4 download failed (network or URL): {exc}")


@pytest.fixture
def temp_sample_mp4(tmp_path: Path, session_cached_sample_mp4: Path) -> Path:
    dest = tmp_path / "sample_clip.mp4"
    shutil.copy2(session_cached_sample_mp4, dest)
    return dest


@pytest.fixture
def synthetic_mp4(tmp_path: Path, core_ffmpeg: EncodeForgeCore) -> Path:
    from tests.support.media_assets import synthesize_test_mp4

    out = tmp_path / "synthetic.mp4"
    ffmpeg = str(core_ffmpeg.ffmpeg_mgr.get_ffmpeg_path() or "ffmpeg")
    return synthesize_test_mp4(out, duration=4.0, ffmpeg_bin=ffmpeg)


@pytest.fixture
def minimal_srt(tmp_path: Path) -> Path:
    p = tmp_path / "track.srt"
    p.write_text(
        "1\n"
        "00:00:00,000 --> 00:00:02,000\n"
        "EncodeForge test subtitle\n",
        encoding="utf-8",
    )
    return p
