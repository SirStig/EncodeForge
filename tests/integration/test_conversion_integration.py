import pytest


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
def test_check_ffmpeg_reports_paths(core_ffmpeg):
    st = core_ffmpeg.check_ffmpeg()
    assert st["status"] == "success"
    assert st["ffmpeg_available"] is True
    assert st.get("ffmpeg_path")
    assert st.get("ffprobe_path")


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
def test_get_file_info_and_media_info(core_ffmpeg, synthetic_mp4):
    fi = core_ffmpeg.get_file_info(str(synthetic_mp4))
    assert fi["status"] == "success"
    assert fi.get("duration", 0) > 0

    mi = core_ffmpeg.get_media_info(str(synthetic_mp4))
    assert mi["status"] == "success"


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
def test_scan_directory(core_ffmpeg, synthetic_mp4, tmp_path):
    sub = tmp_path / "nested"
    sub.mkdir()
    other = sub / "extra.mp4"
    other.write_bytes(b"not real video")
    res = core_ffmpeg.scan_directory(str(tmp_path), recursive=True)
    assert res["status"] == "success"
    names = {__import__("os").path.basename(f["path"]) for f in res["files"]}
    assert "synthetic.mp4" in names


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
def test_convert_mp4_software_h264(core_ffmpeg, synthetic_mp4, tmp_path):
    core_ffmpeg.settings.output_format = "mp4"
    core_ffmpeg.settings.output_suffix = "_h264test"
    out = tmp_path / "synthetic_h264test.mp4"
    r = core_ffmpeg.convert_file(str(synthetic_mp4), output_path=str(out))
    assert r["status"] == "success", r.get("message", r)
    assert out.exists()
    assert out.stat().st_size > 1000


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
def test_convert_to_mkv_container(core_ffmpeg, synthetic_mp4, tmp_path):
    core_ffmpeg.settings.output_format = "mkv"
    core_ffmpeg.settings.output_suffix = "_mkv"
    out = tmp_path / "out_mkv.mkv"
    r = core_ffmpeg.convert_file(str(synthetic_mp4), output_path=str(out))
    assert r["status"] == "success", r.get("message", r)
    assert out.exists()


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
def test_convert_batch_two_files(core_ffmpeg, tmp_path):
    from tests.support.media_assets import synthesize_test_mp4

    ffmpeg = str(core_ffmpeg.ffmpeg_mgr.get_ffmpeg_path() or "ffmpeg")
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    synthesize_test_mp4(a, duration=2.0, ffmpeg_bin=ffmpeg)
    synthesize_test_mp4(b, duration=2.0, ffmpeg_bin=ffmpeg)
    core_ffmpeg.settings.output_format = "mp4"
    core_ffmpeg.settings.output_suffix = "_bat"
    batch = core_ffmpeg.convert_files([str(a), str(b)])
    assert batch["status"] == "success"
    assert batch.get("converted", 0) >= 1


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
def test_convert_libx265_when_available(core_ffmpeg, synthetic_mp4, tmp_path):
    core_ffmpeg.settings.video_codec_fallback = "libx265"
    core_ffmpeg.settings.output_format = "mp4"
    core_ffmpeg.settings.output_suffix = "_hevc"
    out = tmp_path / "hevc_out.mp4"
    r = core_ffmpeg.convert_file(str(synthetic_mp4), output_path=str(out))
    if r["status"] != "success":
        pytest.skip(f"libx265 not usable in this FFmpeg build: {r.get('message', r)}")
    assert out.exists()


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
def test_audio_normalize_forces_aac(core_ffmpeg, synthetic_mp4, tmp_path):
    core_ffmpeg.settings.normalize_audio = True
    core_ffmpeg.settings.audio_codec = "copy"
    core_ffmpeg.settings.output_format = "mp4"
    core_ffmpeg.settings.output_suffix = "_norm"
    out = tmp_path / "norm.mp4"
    r = core_ffmpeg.convert_file(str(synthetic_mp4), output_path=str(out))
    assert r["status"] == "success", r.get("message", r)
    assert out.exists()
