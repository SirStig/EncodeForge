from core.metadata_grabber import MetadataGrabber
from core.subtitle_manager import SubtitleProviders


def test_metadata_grabber_provider_flags(isolated_app_data):
    g = MetadataGrabber()
    avail = g.get_available_providers()
    assert avail["anidb"] is True
    assert avail["tmdb"] is False
    g2 = MetadataGrabber(tmdb_key="secret")
    assert g2.get_available_providers()["tmdb"] is True


def test_detect_media_type_and_parse_tv(isolated_app_data):
    g = MetadataGrabber()
    assert g.detect_media_type("My.Show.S01E02.1080p.mkv") == "tv"
    parsed = g.parse_tv_filename("My.Show.S01E02.1080p.mkv")
    assert parsed is not None
    assert parsed["season"] == 1
    assert parsed["episode"] == 2


def test_subtitle_hash_small_file_returns_none(tmp_path):
    sp = SubtitleProviders()
    tiny = tmp_path / "small.bin"
    tiny.write_bytes(b"\x00" * 1000)
    assert sp.calculate_hash(str(tiny)) is None


def test_extract_media_metadata_nonexistent():
    sp = SubtitleProviders()
    meta = sp.extract_media_metadata("/no/such/file.mp4")
    assert isinstance(meta, dict)
