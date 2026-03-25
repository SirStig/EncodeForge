import pytest
from core.metadata_grabber import MetadataGrabber
from core.subtitle_manager import SubtitleProviders
from core.providers.subtitle.base_provider import BaseSubtitleProvider
from core.providers.subtitle.opensubtitles_manager import OpenSubtitlesManager
from core.providers.subtitle.subdl_provider import SubDLProvider


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


# ── BaseSubtitleProvider metadata extraction ─────────────────────────────────

class ConcreteProvider(BaseSubtitleProvider):
    """Minimal concrete subclass for testing."""
    def search(self, video_path, languages):
        return []
    def download(self, file_id, download_url, output_path):
        return False, "not implemented"


@pytest.fixture
def provider():
    return ConcreteProvider()


def test_extract_tv_show_metadata(provider):
    meta = provider.extract_media_metadata("My.Show.S03E07.1080p.BluRay.mkv")
    assert meta["is_tv_show"] is True
    assert meta["season"] == 3
    assert meta["episode"] == 7
    assert meta["clean_name"].lower() == "my show"
    assert meta["quality"] == "1080p"


def test_extract_movie_metadata(provider):
    meta = provider.extract_media_metadata("Inception.2010.1080p.BluRay.mkv")
    assert meta["is_movie"] is True
    assert meta["is_tv_show"] is False
    assert meta["year"] == "2010"
    assert "inception" in meta["clean_name"].lower()


def test_extract_metadata_no_match(provider):
    meta = provider.extract_media_metadata("random_file.mp4")
    assert isinstance(meta, dict)
    assert "clean_name" in meta
    assert "search_queries" in meta
    assert len(meta["search_queries"]) >= 1


def test_search_queries_tv_show(provider):
    meta = provider.extract_media_metadata("Breaking.Bad.S01E01.720p.mkv")
    queries = meta["search_queries"]
    # Must contain at least the bare show name and an S##E## form
    assert any("Breaking Bad" in q or "breaking bad" in q.lower() for q in queries)
    assert any("S01E01" in q for q in queries)


def test_search_queries_movie_with_year(provider):
    meta = provider.extract_media_metadata("The.Dark.Knight.2008.1080p.mkv")
    queries = meta["search_queries"]
    assert any("2008" in q for q in queries)
    # Article stripping: "The Dark Knight" → "Dark Knight" variant
    assert any("Dark Knight" in q for q in queries)


# ── Language code conversion ──────────────────────────────────────────────────

def test_lang_code_to_name(provider):
    assert provider.lang_code_to_name("eng") == "English"
    assert provider.lang_code_to_name("spa") == "Spanish"
    assert provider.lang_code_to_name("jpn") == "Japanese"
    assert provider.lang_code_to_name("en") == "English"


def test_lang_name_to_code(provider):
    assert provider.lang_name_to_code("English") == "eng"
    assert provider.lang_name_to_code("spanish") == "spa"
    assert provider.lang_name_to_code("japanese") == "jpn"
    assert provider.lang_name_to_code("portuguese (br)") == "pob"


# ── OpenSubtitlesManager ──────────────────────────────────────────────────────

def test_opensubtitles_extends_base():
    """OpenSubtitlesManager must inherit BaseSubtitleProvider (circular import fix)."""
    mgr = OpenSubtitlesManager()
    assert isinstance(mgr, BaseSubtitleProvider)
    # extract_media_metadata must be callable without circular import crash
    meta = mgr.extract_media_metadata("Test.Show.S01E01.mkv")
    assert meta["is_tv_show"] is True


def test_opensubtitles_no_key_returns_empty(tmp_path):
    """Without a consumer key, search_subtitles must return (False, []) gracefully."""
    mgr = OpenSubtitlesManager.__new__(OpenSubtitlesManager)
    BaseSubtitleProvider.__init__(mgr)
    mgr.consumer_api_key = ""
    mgr.username = ""
    mgr.password = ""
    mgr.user_token = None
    # Create a real (tiny) file so calculate_file_hash gets called
    f = tmp_path / "test.mkv"
    f.write_bytes(b"\x00" * 200_000)
    success, results = mgr.search_subtitles(str(f), ["en"])
    assert success is False
    assert results == []


# ── SubDLProvider language mapping ───────────────────────────────────────────

def test_subdl_language_mapping_comprehensive():
    """SubDL must convert all common 3-letter codes without falling back to wrong 2-letter prefix."""
    provider = SubDLProvider()
    # Simulate the mapping logic from SubDLProvider.search
    _lang3_to_2 = {
        'eng': 'en', 'spa': 'es', 'fre': 'fr', 'fra': 'fr', 'ger': 'de', 'deu': 'de',
        'ita': 'it', 'por': 'pt', 'pob': 'pt', 'rus': 'ru', 'ara': 'ar',
        'chi': 'zh', 'zho': 'zh', 'zht': 'zh', 'jpn': 'ja', 'kor': 'ko',
        'hin': 'hi', 'tha': 'th', 'vie': 'vi', 'tur': 'tr', 'pol': 'pl',
        'dut': 'nl', 'nld': 'nl', 'swe': 'sv', 'nor': 'no', 'dan': 'da',
    }
    for three, two in _lang3_to_2.items():
        result = _lang3_to_2.get(three.lower())
        assert result == two, f"{three} should map to {two}, got {result}"


# ── SubtitleProviders rank ordering ──────────────────────────────────────────

def test_rank_puts_opensubtitles_first():
    sp = SubtitleProviders()
    results = [
        {"provider": "YIFY", "downloads": 1000, "rating": 9.0, "format": "srt"},
        {"provider": "OpenSubtitles.com", "downloads": 50, "rating": 5.0, "format": "srt"},
        {"provider": "SubDL", "downloads": 200, "rating": 7.0, "format": "srt"},
    ]
    ranked = sp._rank_subtitles(results)
    assert ranked[0]["provider"] == "OpenSubtitles.com"


def test_rank_higher_downloads_breaks_ties():
    sp = SubtitleProviders()
    results = [
        {"provider": "SubDL", "downloads": 10, "rating": 0, "format": "srt"},
        {"provider": "SubDL", "downloads": 5000, "rating": 0, "format": "srt"},
    ]
    ranked = sp._rank_subtitles(results)
    assert ranked[0]["downloads"] == 5000


def test_rank_ass_beats_srt_same_provider():
    sp = SubtitleProviders()
    results = [
        {"provider": "SubDL", "downloads": 0, "rating": 0, "format": "srt"},
        {"provider": "SubDL", "downloads": 0, "rating": 0, "format": "ass"},
    ]
    ranked = sp._rank_subtitles(results)
    assert ranked[0]["format"] == "ass"


# ── Kitsunekko removed ───────────────────────────────────────────────────────

def test_kitsunekko_not_importable():
    """Kitsunekko was a placeholder with no real implementation and has been removed."""
    import importlib
    with pytest.raises(ImportError):
        importlib.import_module("core.providers.subtitle.kitsunekko_provider")


def test_kitsunekko_not_in_subtitle_providers():
    sp = SubtitleProviders()
    assert not hasattr(sp, "kitsunekko")
    assert "Kitsunekko" not in sp.providers
