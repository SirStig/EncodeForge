"""
Regression tests for defects found in the 0.5.0 codebase audit.

Each test pins behaviour that was previously broken. They are all pure-logic
tests: no network, no FFmpeg, no GUI, so they run in the default suite and in
CI in well under a second.
"""

import json
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# --------------------------------------------------------------------------- #
# utils/update_checker — pre-release versions could never compare as newer
# --------------------------------------------------------------------------- #

class TestVersionComparison:
    @pytest.mark.parametrize(
        "remote,current,expected",
        [
            ("v0.5.0-alpha-3", "0.5.0-alpha-2", True),
            ("v0.5.0-alpha-2", "0.5.0-alpha-2", False),
            ("v0.5.0-alpha-1", "0.5.0-alpha-2", False),
            # A final release is newer than any of its pre-releases.
            ("v0.5.0", "0.5.0-alpha-2", True),
            ("v0.5.0-alpha-2", "0.5.0", False),
            # Stage ordering: alpha < beta < rc < final
            ("v0.5.0-beta-1", "0.5.0-alpha-9", True),
            ("v0.5.0-rc-1", "0.5.0-beta-3", True),
            ("v0.5.1", "0.5.0-alpha-2", True),
            ("v0.4.9", "0.5.0-alpha-2", False),
        ],
    )
    def test_is_newer(self, remote, current, expected):
        from utils.update_checker import is_newer
        assert is_newer(remote, current) is expected

    def test_normalize_keeps_prerelease_segment(self):
        from utils.update_checker import normalize_version
        # Stripping this suffix made every shipped alpha compare equal to 0.5.0.
        assert normalize_version("v0.5.0-alpha-3") == "0.5.0-alpha-3"

    def test_fallback_ordering_without_packaging(self, monkeypatch):
        """The non-packaging code path must order pre-releases the same way."""
        import builtins
        import utils.update_checker as uc

        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name == "packaging.version":
                raise ImportError("blocked for test")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", blocked)
        assert uc.is_newer("v0.5.0-alpha-3", "0.5.0-alpha-2") is True
        assert uc.is_newer("v0.5.0-alpha-2", "0.5.0") is False


# --------------------------------------------------------------------------- #
# utils/settings_manager — one bad key discarded every later section
# --------------------------------------------------------------------------- #

class TestSettingsMigration:
    def test_unknown_key_does_not_discard_other_sections(self, isolated_app_data):
        """A field removed in a future release must not wipe the user's API keys."""
        from utils.settings_manager import SettingsManager
        import core.path_manager as path_manager

        settings_file = path_manager.get_settings_file()
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(json.dumps({
            "encoder": {"codec": "H.265", "crf": 18, "FIELD_REMOVED_IN_FUTURE": 123},
            "ui": {"theme": "light", "window_width": 1600},
            "conversion": {"tmdb_api_key": "KEY-TMDB", "tvdb_api_key": "KEY-TVDB"},
        }))

        SettingsManager._instance = None
        manager = SettingsManager()

        # The stale key is ignored rather than aborting the load...
        assert manager.encoder.codec == "H.265"
        assert manager.encoder.crf == 18
        # ...and every later section still loads. `conversion` is last, and it
        # holds all the API keys.
        assert manager.ui.theme == "light"
        assert manager.conversion.tmdb_api_key == "KEY-TMDB"
        assert manager.conversion.tvdb_api_key == "KEY-TVDB"

    def test_save_is_atomic_and_owner_only(self, isolated_app_data):
        import os
        from utils.settings_manager import SettingsManager

        SettingsManager._instance = None
        manager = SettingsManager()
        assert manager.save() is True

        settings_file = manager.settings_file
        assert settings_file.exists()
        # No temp file left behind
        assert not settings_file.with_name(settings_file.name + ".tmp").exists()

        if os.name != "nt":
            assert settings_file.stat().st_mode & 0o777 == 0o600

    def test_export_redacts_api_keys(self, isolated_app_data, tmp_path):
        from utils.settings_manager import SettingsManager

        SettingsManager._instance = None
        manager = SettingsManager()
        manager.conversion.tmdb_api_key = "SECRET"

        target = tmp_path / "export.json"
        assert manager.export_settings(target) is True
        assert json.loads(target.read_text())["conversion"]["tmdb_api_key"] == ""

        manager.export_settings(target, include_secrets=True)
        assert json.loads(target.read_text())["conversion"]["tmdb_api_key"] == "SECRET"


# --------------------------------------------------------------------------- #
# utils/download_manager — format detection and archive traversal
# --------------------------------------------------------------------------- #

class TestArchiveHandling:
    def test_format_detected_from_content_not_extension(self, tmp_path):
        """
        The FFmpeg installer saves to a generic temp name, so dispatching on the
        file extension made every Windows/Linux download fail to extract.
        """
        from utils.download_manager import DownloadManager

        archive = tmp_path / "ffmpeg_download.tmp"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("bin/ffmpeg", "binary")

        assert DownloadManager.detect_archive_format(archive) == "zip"

    def test_tar_xz_is_supported(self, tmp_path):
        """Linux FFmpeg builds ship as .tar.xz."""
        from utils.download_manager import DownloadManager

        archive = tmp_path / "download.tmp"
        with tarfile.open(archive, "w:xz") as tf:
            payload = tmp_path / "ffmpeg"
            payload.write_text("binary")
            tf.add(payload, arcname="ffmpeg")

        assert DownloadManager.detect_archive_format(archive) == "tar.xz"

        dest = tmp_path / "out"
        DownloadManager().extract_archive(archive, dest)
        assert (dest / "ffmpeg").exists()

    def test_zip_slip_is_rejected(self, tmp_path):
        from utils.download_manager import DownloadManager, UnsafeArchiveError

        archive = tmp_path / "evil.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../../escaped.txt", "pwned")

        dest = tmp_path / "out"
        with pytest.raises(UnsafeArchiveError):
            DownloadManager().extract_archive(archive, dest)

        assert not (tmp_path.parent / "escaped.txt").exists()

    def test_tar_slip_is_rejected(self, tmp_path):
        """tarfile performs no path validation of its own before Python 3.14."""
        from utils.download_manager import DownloadManager, UnsafeArchiveError

        payload = tmp_path / "payload.txt"
        payload.write_text("pwned")

        archive = tmp_path / "evil.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(payload, arcname="../../escaped.txt")

        dest = tmp_path / "out"
        with pytest.raises(UnsafeArchiveError):
            DownloadManager().extract_archive(archive, dest)

    def test_unknown_format_raises_clear_error(self, tmp_path):
        from utils.download_manager import DownloadError, DownloadManager

        blob = tmp_path / "mystery.bin"
        blob.write_bytes(b"not an archive at all, just bytes" * 4)

        with pytest.raises(DownloadError, match="Unsupported archive format"):
            DownloadManager().extract_archive(blob, tmp_path / "out")


# --------------------------------------------------------------------------- #
# utils/logging_config — rotation destroyed the log after the first rollover
# --------------------------------------------------------------------------- #

def test_line_rotation_preserves_history(tmp_path):
    import logging
    from utils.logging_config import LineCountRotatingHandler

    log_file = tmp_path / "t.log"
    handler = LineCountRotatingHandler(str(log_file), maxLines=5, backupCount=3)
    handler.setFormatter(logging.Formatter("%(message)s"))

    logger = logging.getLogger("rotation_regression_test")
    logger.propagate = False
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    for i in range(12):
        logger.info("msg %d", i)
    handler.close()

    # Without the counter reset each backup held a single line and almost all
    # history was lost.
    backup = log_file.with_suffix(".log.1")
    assert backup.exists()
    assert len(backup.read_text().strip().splitlines()) == 5


# --------------------------------------------------------------------------- #
# core/handlers/conversion_handler — encoder selection
# --------------------------------------------------------------------------- #

class TestEncoderSelection:
    @staticmethod
    def _select(encoder_ids, is_10bit, **flags):
        from unittest.mock import MagicMock
        from core.handlers.conversion_handler import ConversionHandler
        from core.handlers.models import ConversionSettings

        settings = ConversionSettings()
        settings.use_nvenc = flags.get("nvenc", False)
        settings.use_amf = flags.get("amf", False)
        settings.use_vaapi = flags.get("vaapi", False)
        settings.use_qsv = flags.get("qsv", False)
        settings.use_videotoolbox = flags.get("vt", False)

        handler = ConversionHandler(settings, MagicMock())
        handler.ffmpeg_mgr.get_hwaccel_options.return_value = {
            "encode": [], "decode": [], "encoder_ids": encoder_ids,
        }
        return handler._select_best_encoder(is_10bit=is_10bit)

    def test_10bit_without_hevc_support_falls_back_to_h264(self):
        """
        A card with NVENC H.264 only must not be handed hevc_nvenc. The 8-bit
        conversion branch that handles this was previously unreachable.
        """
        result = self._select(["h264_nvenc"], is_10bit=True, nvenc=True)
        assert result["codec"] == "h264_nvenc"
        assert result["needs_conversion"] is True

    def test_10bit_uses_hevc_when_available(self):
        result = self._select(["h264_nvenc", "hevc_nvenc"], is_10bit=True, nvenc=True)
        assert result["codec"] == "hevc_nvenc"
        assert result["needs_conversion"] is False

    def test_vendor_selection_is_respected(self):
        result = self._select(["h264_amf", "hevc_amf"], is_10bit=False, amf=True)
        assert result["codec"] == "h264_amf"
        assert result["platform"] == "amd"

    def test_vaapi_selected_on_linux_path(self):
        result = self._select(["h264_vaapi", "hevc_vaapi"], is_10bit=False, vaapi=True)
        assert result["codec"] == "h264_vaapi"
        assert result["platform"] == "vaapi"

    def test_qsv_preferred_over_vaapi_when_both_enabled(self):
        result = self._select(
            ["h264_vaapi", "h264_qsv"], is_10bit=False, vaapi=True, qsv=True
        )
        assert result["codec"] == "h264_qsv"

    def test_disabled_hardware_falls_back_to_software(self):
        result = self._select(["h264_amf", "hevc_amf"], is_10bit=False)
        assert result["type"] == "software"

    def test_no_encoders_falls_back_to_software(self):
        result = self._select([], is_10bit=True, nvenc=True)
        assert result["type"] == "software"


def test_bitmap_subtitles_are_not_transcoded():
    """
    PGS/VobSub cannot be converted to text, and attempting it aborted the whole
    encode after it had already been running.
    """
    from unittest.mock import MagicMock
    from core.handlers.conversion_handler import ConversionHandler
    from core.handlers.models import ConversionSettings

    handler = ConversionHandler(ConversionSettings(), MagicMock())
    tracks = [
        {"index": 2, "codec": "subrip"},
        {"index": 3, "codec": "hdmv_pgs_subtitle"},
    ]

    args = handler._build_subtitle_args(tracks, "mov_text")
    assert "-map" in args and "0:2" in args      # text track carried over
    assert "0:3" not in args                      # bitmap track dropped
    assert args[args.index("-c:s") + 1] == "mov_text"

    # Matroska can carry both, so copy mode keeps everything.
    copy_args = handler._build_subtitle_args(tracks, "copy")
    assert "0:2" in copy_args and "0:3" in copy_args


# --------------------------------------------------------------------------- #
# utils/ffmpeg_manager — ffprobe path derivation + OS search roots
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "ffmpeg_path,expected",
    [
        # The Windows installer path contains "ffmpeg" in two directory
        # components; a naive str.replace corrupted all of them.
        (r"C:\Users\x\AppData\Local\ffmpeg\ffmpeg-7.1_build\bin\ffmpeg.exe",
         r"C:\Users\x\AppData\Local\ffmpeg\ffmpeg-7.1_build\bin\ffprobe.exe"),
        ("/opt/ffmpeg/bin/ffmpeg", "/opt/ffmpeg/bin/ffprobe"),
        ("/usr/bin/ffmpeg", "/usr/bin/ffprobe"),
        ("ffmpeg", "ffprobe"),
    ],
)
def test_ffprobe_path_derivation(ffmpeg_path, expected):
    from utils.ffmpeg_manager import FFmpegManager, derive_ffprobe_path

    assert derive_ffprobe_path(ffmpeg_path) == expected
    assert FFmpegManager._derive_ffprobe_path(ffmpeg_path) == expected


@pytest.mark.parametrize(
    "system,expected_fragment",
    [
        ("Windows", "EncodeForge/ffmpeg"),
        ("Windows", "C:/ffmpeg"),
        ("Darwin", "/opt/homebrew/bin"),
        ("Darwin", "/usr/local/bin"),
        ("Linux", "/usr/bin"),
        ("Linux", "/snap/bin"),
        ("Linux", ".local/bin"),
    ],
)
def test_common_search_paths_per_os(system, expected_fragment):
    from utils.ffmpeg_manager import common_search_paths_for_system

    paths = common_search_paths_for_system(system)
    assert any(expected_fragment in p for p in paths)


@pytest.mark.parametrize(
    "system,expected_fragment",
    [
        ("Windows", "ffmpeg"),
        ("Darwin", "homebrew"),
        ("Linux", "usr"),
    ],
)
def test_manager_common_paths_respect_os(monkeypatch, system, expected_fragment):
    import platform

    from utils.ffmpeg_manager import FFmpegManager

    FFmpegManager.reset_instance()
    monkeypatch.setattr(platform, "system", lambda: system)
    mgr = FFmpegManager()
    paths = [str(p).replace("\\", "/") for p in mgr._get_common_paths()]
    assert any(expected_fragment.lower() in p.lower() for p in paths)
    # Java embed runtime dir must never appear as a search root
    assert not any("FFMPEG_RUNTIME" in p for p in paths)
    FFmpegManager.reset_instance()


def test_download_urls_matrix_is_platform_aware():
    from utils.ffmpeg_manager import get_download_urls

    urls = get_download_urls()
    assert "supported" in urls
    assert "url" in urls
    assert "direct_binary" in urls
    if urls["supported"] and urls["system"] == "Darwin":
        assert urls["direct_binary"] is True
        assert "ffmpeg-darwin-" in urls["url"]
        assert urls["ffprobe_url"]


def test_java_embed_path_removed_from_unified_manager():
    """P2-A: FFMPEG_RUNTIME_DIR / Java bridge embed path must not exist."""
    import inspect

    import utils.ffmpeg_manager as ffmpeg_mod

    source = inspect.getsource(ffmpeg_mod)
    assert "FFMPEG_RUNTIME_DIR" not in source
    assert "_check_embedded_ffmpeg" not in source
    assert "JavaBridge" not in source


def test_core_ffmpeg_manager_is_thin_facade():
    """core.ffmpeg_manager must re-export the utils singleton, not a second class."""
    import core.ffmpeg_manager as core_ff
    import utils.ffmpeg_manager as utils_ff

    assert core_ff.FFmpegManager is utils_ff.FFmpegManager
    assert core_ff.get_ffmpeg_manager is utils_ff.get_ffmpeg_manager
    assert core_ff.derive_ffprobe_path is utils_ff.derive_ffprobe_path


# --------------------------------------------------------------------------- #
# Subtitle provider language handling
# --------------------------------------------------------------------------- #

class TestLanguageMatching:
    @pytest.mark.parametrize(
        "requested,found",
        [
            ("spa", "es"),      # Subf2m dropped all Spanish
            ("ger", "de"),      # ...and all German
            ("ger", "DE"),      # Podnapisi flag alt text
            ("eng", "en"),
            ("eng", "English (US)"),
            ("por", "Portuguese (Brazilian)"),
            ("chi", "zh"),
            ("dut", "nl"),
            ("cze", "cs"),
            ("gre", "el"),
        ],
    )
    def test_equivalent_codes_match(self, requested, found):
        from core.providers.subtitle.base_provider import languages_match
        assert languages_match(requested, found) is True

    @pytest.mark.parametrize(
        "requested,found",
        [
            ("en", "slovenian"),   # YIFY substring test matched this
            ("en", "french"),
            ("it", "british english"),
            ("ar", "hungarian"),
            ("es", "en"),
        ],
    )
    def test_different_languages_do_not_match(self, requested, found):
        from core.providers.subtitle.base_provider import languages_match
        assert languages_match(requested, found) is False

    def test_three_letter_codes_normalise_correctly(self):
        from core.providers.subtitle.base_provider import to_iso639_1
        # Truncating to two characters produced 'GE', which is not a language.
        assert to_iso639_1("ger") == "de"
        assert to_iso639_1("chi") == "zh"
        assert to_iso639_1("dut") == "nl"


class TestSubtitleContentValidation:
    @pytest.mark.parametrize("payload", [
        b"1\r\n00:00:01,000 --> 00:00:04,000\r\nHola\r\n\r\n",
        b"[Script Info]\r\nTitle: x\r\n[Events]\r\nDialogue: 0,0:00:01.00",
        b"WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nHello\n",
    ])
    def test_real_subtitles_accepted(self, payload):
        from core.providers.subtitle.base_provider import looks_like_subtitle
        assert looks_like_subtitle(payload) is True

    @pytest.mark.parametrize("payload", [
        b"PK\x03\x04" + b"\x00" * 40,                        # undextracted zip
        b"<!DOCTYPE html>\n<html><head><title>Just a moment",  # Cloudflare page
        b"Rar!\x1a\x07\x00" + b"\x00" * 40,
        b"\x1f\x8b\x08" + b"\x00" * 40,
        b"",
    ])
    def test_non_subtitles_rejected(self, payload):
        from core.providers.subtitle.base_provider import looks_like_subtitle
        assert looks_like_subtitle(payload) is False


# --------------------------------------------------------------------------- #
# Filename parsing and sanitisation
# --------------------------------------------------------------------------- #

class TestFilenameParsing:
    @staticmethod
    def _provider():
        from core.providers.metadata.base_provider import BaseMetadataProvider

        class _Concrete(BaseMetadataProvider):
            def search_movie(self, *a, **k): return None
            def search_tv(self, *a, **k): return None
            def search_tv_show(self, *a, **k): return None

        return _Concrete()

    def test_resolution_is_not_parsed_as_season_episode(self):
        provider = self._provider()
        # "1920x1080" previously produced season 1920, episode 1080.
        assert provider.detect_media_type("Interstellar.2014.1920x1080.mkv") == "movie"

    def test_real_season_episode_still_parses(self):
        provider = self._provider()
        parsed = provider.parse_tv_filename("Firefly.1x02.The.Train.Job.mkv")
        assert (parsed["season"], parsed["episode"]) == (1, 2)

    def test_bracket_numbered_anime_parses(self):
        """These classified as TV but had no matching parse pattern."""
        provider = self._provider()
        parsed = provider.parse_tv_filename("[SubsPlease] Frieren - [12] (1080p).mkv")
        assert parsed is not None
        assert parsed["episode"] == 12
        assert "SubsPlease" not in parsed["title"]

    @pytest.mark.parametrize("filename,title,year", [
        ("Blade.Runner.2049.2017.2160p.mkv", "Blade Runner 2049", 2017),
        ("Interstellar.2014.1920x1080.mkv", "Interstellar", 2014),
        ("The.Matrix.1999.mkv", "The Matrix", 1999),
        ("2012.2009.1080p.mkv", "2012", 2009),
    ])
    def test_release_year_is_the_last_year_token(self, filename, title, year):
        parsed = self._provider().parse_movie_filename(filename)
        assert parsed["title"] == title
        assert parsed["year"] == year


class TestFilenameSanitisation:
    @staticmethod
    def _sanitize(name):
        from core.rename_pattern import sanitize_filename
        return sanitize_filename(name)

    def test_long_names_are_truncated_to_filesystem_limit(self):
        result = self._sanitize("A" * 400)
        assert len(result.encode("utf-8")) <= 255

    def test_multibyte_names_truncate_on_character_boundary(self):
        result = self._sanitize("日本語" * 200)
        assert len(result.encode("utf-8")) <= 255
        result.encode("utf-8").decode("utf-8")  # must not raise

    def test_leading_dot_does_not_create_hidden_file(self):
        assert not self._sanitize("....hidden").startswith(".")

    def test_control_characters_removed(self):
        assert self._sanitize("bad\x00null\x1fctrl") == "badnullctrl"


class TestSubfolderSanitisation:
    """core.rename_pattern.sanitize_filename(..., allow_subfolders=True) — P2 library layout."""

    def test_allows_forward_slash_as_folder_separator(self):
        from core.rename_pattern import sanitize_filename
        result = sanitize_filename("Show/Season 01/Show - S01E01", allow_subfolders=True)
        assert result == "Show/Season 01/Show - S01E01"

    def test_rejects_directory_traversal_segments(self):
        """
        A pattern is built from provider metadata (title, episode_title, …);
        it must never be able to walk a formatted path out of the
        destination root via a stray '..' segment.
        """
        from core.rename_pattern import sanitize_filename
        result = sanitize_filename("../../etc/Show", allow_subfolders=True)
        assert ".." not in result.split("/")
        assert "etc" in result.split("/")

    def test_without_allow_subfolders_slash_is_stripped_like_any_invalid_char(self):
        from core.rename_pattern import sanitize_filename
        result = sanitize_filename("Show/Season 01", allow_subfolders=False)
        assert "/" not in result


class TestEnglishTitlePreference:
    @staticmethod
    def _handler():
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler
        return RenamingHandler(ConversionSettings(), None)

    @pytest.mark.parametrize("titles,expected", [
        # Substring matching on particles ('no', 'wa', 'ni', 'to') classified
        # these English titles as Japanese.
        (["The Night Of", "Yoru no Monogatari"], "The Night Of"),
        (["Doctor Who", "Watashi no Sensei"], "Doctor Who"),
        (["Kekkon Shiawase", "My Happy Marriage"], "My Happy Marriage"),
        (["鋼の錬金術師", "Fullmetal Alchemist"], "Fullmetal Alchemist"),
    ])
    def test_prefers_the_english_title(self, titles, expected):
        results = [{"source": "tvdb", "show_title": t} for t in titles]
        chosen = self._handler()._prefer_english_title(results)
        assert chosen["show_title"] == expected


# --------------------------------------------------------------------------- #
# core/rename_pattern — positional placeholders crashed the settings dialog
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("pattern", ["{0} - {title}", "{} - {title}"])
def test_positional_placeholders_rejected_not_raised(pattern):
    from core.rename_pattern import validate_pattern
    valid, message = validate_pattern(pattern)
    assert valid is False
    assert "positional" in message.lower()


def test_valid_pattern_accepted():
    from core.rename_pattern import validate_pattern
    valid, _ = validate_pattern("{title} - S{season:02d}E{episode:02d}")
    assert valid is True


# --------------------------------------------------------------------------- #
# core/rename_executor — the single safe path every renamer (GUI/CLI/backend)
# now funnels through; a collision or overwrite must never destroy a file.
# --------------------------------------------------------------------------- #

class TestRenameSafety:
    def test_collision_is_caught_before_either_file_moves(self, tmp_path):
        """
        Path.rename overwrites silently on POSIX, so a 1080p and a 720p of
        the same episode used to destroy one another mid-batch. Both are
        now rejected up front instead of letting iteration order pick a
        silent winner.
        """
        from core.rename_executor import RenamePair, execute_renames

        first = tmp_path / "Show.S01E05.1080p.mkv"
        second = tmp_path / "Show.S01E05.720p.mkv"
        first.write_text("FIRST")
        second.write_text("SECOND")
        target = tmp_path / "Show - S01E05.mkv"

        result = execute_renames(
            [RenamePair(source=first, dest=target), RenamePair(source=second, dest=target)]
        )

        assert result["renamed"] == 0
        assert all(not r["success"] for r in result["results"])
        assert all("collide" in r["message"].lower() for r in result["results"])
        assert not target.exists()

        # Both payloads survive, under their original names.
        contents = {p.name: p.read_text() for p in tmp_path.iterdir() if p.is_file()}
        assert contents == {"Show.S01E05.1080p.mkv": "FIRST", "Show.S01E05.720p.mkv": "SECOND"}

    def test_pre_existing_target_outside_batch_is_not_overwritten(self, tmp_path):
        """A target that already exists on disk (not part of this batch's own
        collisions) must be refused just as firmly as an in-batch collision."""
        from core.rename_executor import RenamePair, execute_renames

        source = tmp_path / "Show.S01E05.mkv"
        source.write_text("NEW")
        target = tmp_path / "Show - S01E05.mkv"
        target.write_text("EXISTING")

        result = execute_renames([RenamePair(source=source, dest=target)])

        assert result["renamed"] == 0
        assert result["results"][0]["success"] is False
        assert "overwrite" in result["results"][0]["message"].lower()
        assert target.read_text() == "EXISTING"
        assert source.exists() and source.read_text() == "NEW"

    def test_rename_files_refuses_empty_formatted_name(self, tmp_path):
        """
        An empty formatted stem (e.g. a pattern of only dots, which the
        hidden-file guard strips entirely) must never produce a bare
        extension — RenamingHandler.rename_files has to catch this before
        it reaches the filesystem, not just core.rename_executor.
        """
        from unittest.mock import MagicMock, patch
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler

        target = tmp_path / "Show.S01E05.mkv"
        target.write_text("DATA")

        settings = ConversionSettings()
        settings.renaming_pattern_tv = "..."  # sanitizes to an empty stem
        renamer = MagicMock()
        renamer.detect_media_type.return_value = "tv"
        handler = RenamingHandler(settings, renamer=renamer)

        with patch.object(handler, "preview_rename", return_value={
            "status": "success",
            "metadata": [{"title": "x", "season": 1, "episode": 5}],
            "providers": ["Test"],
            "errors": [""],
        }):
            result = handler.rename_files([str(target)])

        assert result["results"][0]["success"] is False
        assert "format" in result["results"][0]["message"].lower()
        assert target.exists()
        assert target.read_text() == "DATA"


# --------------------------------------------------------------------------- #
# core/profile_manager — profile names were used unsanitised as paths
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name", ["../../settings", "../escape", "sub/dir", "a\\b"])
def test_profile_names_cannot_escape_directory(isolated_app_data, name):
    from core.handlers.models import ConversionSettings
    from core.profile_manager import ProfileManager

    manager = ProfileManager()
    assert manager.save_profile(name, ConversionSettings()) is False
    assert manager.delete_profile(name) is False


def test_normal_profile_names_still_work(isolated_app_data):
    from core.handlers.models import ConversionSettings
    from core.profile_manager import ProfileManager

    manager = ProfileManager()
    settings = ConversionSettings()
    settings.video_crf = 21

    assert manager.save_profile("My Profile", settings) is True
    loaded = manager.load_profile("My Profile")
    assert loaded is not None
    assert loaded.video_crf == 21


# --------------------------------------------------------------------------- #
# utils/workers — progress_callback injection and cancellation
# --------------------------------------------------------------------------- #

class TestWorkerBehaviour:
    def test_zero_arg_callable_does_not_get_progress_callback(self):
        """
        Injecting it unconditionally made every API-key "Test" button raise
        TypeError, so a valid key was indistinguishable from an invalid one.
        """
        from utils.workers import Worker

        def validate():
            return (True, "Valid")

        assert Worker(validate).kwargs == {}

    def test_callable_accepting_progress_gets_it(self):
        from utils.workers import Worker

        def job(progress_callback=None):
            return "ok"

        assert "progress_callback" in Worker(job).kwargs

    def test_kwargs_catchall_gets_it(self):
        from utils.workers import Worker

        def job(**kwargs):
            return "ok"

        assert "progress_callback" in Worker(job).kwargs

    def test_cancelled_worker_never_runs_its_function(self):
        """Queued runnables kept executing after Stop was pressed."""
        from utils.workers import Worker

        calls = []

        def job(progress_callback=None):
            calls.append(1)

        worker = Worker(job)
        worker.stop()
        worker.run()

        assert calls == []


@pytest.mark.parametrize("backend,expected", [
    # (nvenc, amf, vaapi, qsv, videotoolbox)
    ("NVENC (NVIDIA)", (True, False, False, False, False)),
    ("AMF (AMD)", (False, True, False, False, False)),
    ("VAAPI (Linux)", (False, False, True, False, False)),
    ("QSV (Intel)", (False, False, False, True, False)),
    ("VideoToolbox (Apple)", (False, False, False, False, True)),
    ("Auto", (True, True, True, True, True)),
    ("None", (False, False, False, False, False)),
])
def test_hardware_backend_selection(backend, expected):
    """Every backend used to map to NVENC regardless of what the user picked."""
    from core.handlers.models import ConversionSettings
    from utils.workers import merge_encoder_ui_into_conversion_settings

    settings = merge_encoder_ui_into_conversion_settings(
        ConversionSettings(), {"hw_accel": True, "hw_accel_backend": backend}
    )
    actual = (
        settings.use_nvenc,
        settings.use_amf,
        settings.use_vaapi,
        settings.use_qsv,
        settings.use_videotoolbox,
    )
    assert actual == expected


def test_hardware_disabled_clears_all_backends():
    from core.handlers.models import ConversionSettings
    from utils.workers import merge_encoder_ui_into_conversion_settings

    settings = merge_encoder_ui_into_conversion_settings(
        ConversionSettings(), {"hw_accel": False, "hw_accel_backend": "AMF (AMD)"}
    )
    assert not any([
        settings.use_nvenc,
        settings.use_amf,
        settings.use_vaapi,
        settings.use_qsv,
        settings.use_videotoolbox,
    ])


# --------------------------------------------------------------------------- #
# Subtitle provider selection was built by the UI and then dropped
# --------------------------------------------------------------------------- #

class TestProviderSelection:
    def test_no_restriction_by_default(self):
        from core.subtitle_manager import SubtitleProviders
        providers = SubtitleProviders()
        assert providers.is_provider_enabled("OpenSubtitles.com") is True
        # Quarantined scrapers stay listed for honesty but are never queried.
        assert providers.is_provider_enabled("Jimaku") is False
        assert providers.is_provider_enabled("Podnapisi") is False
        assert providers.is_provider_enabled("SubDivX") is False

    def test_restriction_is_honoured(self):
        from core.subtitle_manager import SubtitleProviders
        providers = SubtitleProviders()
        providers.enabled_providers = ["SubDL"]

        assert providers.is_provider_enabled("SubDL") is True
        assert providers.is_provider_enabled("OpenSubtitles.com") is False
        assert providers.is_provider_enabled("Addic7ed") is False

    def test_ui_label_matches_internal_name(self):
        """The UI says "OpenSubtitles"; the manager calls it "OpenSubtitles.com"."""
        from core.subtitle_manager import SubtitleProviders
        providers = SubtitleProviders()
        providers.enabled_providers = ["OpenSubtitles"]
        assert providers.is_provider_enabled("OpenSubtitles.com") is True


# --------------------------------------------------------------------------- #
# Notifications — the method every call site used did not exist
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("kind", ["success", "error", "warning", "info", "unrecognised"])
def test_show_notification_exists_and_never_raises(kind, monkeypatch):
    """
    Five call sites used show_notification(); the class defined no such method,
    so each raised AttributeError inside a Qt slot — including on the subtitle
    failure path, which is exactly where users end up.
    """
    from utils.notifications import get_notification_manager

    manager = get_notification_manager()
    assert hasattr(manager, "show_notification")

    # Don't touch the real desktop backend: it rate-limits and would emit
    # unrelated tracebacks from the dispatch thread.
    sent = []

    async def _capture(title, message):
        sent.append((title, message))

    monkeypatch.setattr(manager, "notify_success", _capture)
    monkeypatch.setattr(manager, "notify_error", _capture)
    monkeypatch.setattr(manager, "notify_warning", _capture)

    # Advisory only: a failure here must never take down the calling slot.
    manager.show_notification(title="t", message="m", notification_type=kind)


def test_show_notification_survives_a_broken_backend(monkeypatch):
    from utils.notifications import get_notification_manager

    manager = get_notification_manager()
    monkeypatch.setattr(
        manager, "_ensure_loop", lambda: (_ for _ in ()).throw(RuntimeError("no loop"))
    )
    # Must not propagate.
    manager.show_notification(title="t", message="m", notification_type="error")


# --------------------------------------------------------------------------- #
# Imports that pointed at a pre-refactor package layout
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("module_path", [
    "core.providers.subtitle.whisper_manager",
    "core.path_manager",
])
def test_refactored_module_paths_are_importable(module_path):
    """
    subtitle_handler imported `subtitle_providers.whisper_manager` and
    conversion_handler imported `path_manager`; neither top-level package
    exists, so Whisper-via-handler and crash recovery were silently dead.
    """
    import importlib
    assert importlib.import_module(module_path) is not None


@pytest.mark.parametrize("dead_module", ["subtitle_providers", "path_manager"])
def test_old_toplevel_module_paths_are_gone(dead_module):
    import importlib
    with pytest.raises(ImportError):
        importlib.import_module(dead_module)


# --------------------------------------------------------------------------- #
# Version consistency
# --------------------------------------------------------------------------- #

class TestVersionConsistency:
    """app/__init__.py is the single source of truth for the version."""

    def test_settings_stamp_matches_app_version(self, isolated_app_data):
        from app import __version__
        from utils.settings_manager import SettingsManager

        SettingsManager._instance = None
        assert SettingsManager().to_dict()["version"] == __version__

    def test_setup_py_reads_the_same_version(self):
        from app import __version__

        setup_py = (Path(__file__).parent.parent / "setup.py").read_text(encoding="utf-8")
        # setup.py must derive the version, not repeat it.
        assert 'version="0.' not in setup_py, "setup.py hardcodes a version string"
        assert "version=version" in setup_py

        init_py = (Path(__file__).parent.parent / "app" / "__init__.py").read_text(encoding="utf-8")
        assert f'__version__ = "{__version__}"' in init_py

    def test_changelog_documents_the_current_version(self):
        from app import __version__

        changelog = (Path(__file__).parent.parent / "CHANGELOG.md").read_text(encoding="utf-8")
        assert f"## [{__version__}]" in changelog, (
            f"CHANGELOG.md has no section for {__version__}"
        )


# --------------------------------------------------------------------------- #
# C1 — GUI "auto"/"all" must expand like CLI "automatic"
# --------------------------------------------------------------------------- #

@pytest.mark.audit_c1
class TestProviderTokenNormalization:
    """GUI/settings emit auto/all; handler used to only expand automatic."""

    @pytest.mark.parametrize("token", ["auto", "all", "automatic", "Auto", " ALL "])
    def test_normalize_selected_provider_maps_expand_all_tokens(self, token):
        from core.handlers.renaming_handler import normalize_selected_provider

        assert normalize_selected_provider(token) == "automatic"

    def test_normalize_leaves_specific_provider(self):
        from core.handlers.renaming_handler import normalize_selected_provider

        assert normalize_selected_provider("tmdb") == "tmdb"
        assert normalize_selected_provider("TVDB") == "tvdb"

    @pytest.mark.parametrize("token", ["auto", "all", "automatic"])
    def test_selected_provider_auto_expands_to_multiple_providers(self, token):
        """Regression for C1: GUI default provider=\"auto\" must try free
        providers, not treat the literal token as a provider id."""
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler

        renamer = MagicMock()
        renamer.detect_media_type.return_value = "tv"
        renamer.parse_tv_filename.return_value = {
            "title": "Show",
            "season": 1,
            "episode": 1,
        }

        def fake_search(title, season, episode, provider=None):
            return {
                "show_title": "Show",
                "season": season,
                "episode": episode,
                "episode_title": f"via-{provider}",
                "source": provider,
            }

        renamer.search_tv_show.side_effect = fake_search

        handler = RenamingHandler(ConversionSettings(), renamer)
        result = handler.preview_rename(
            ["Show.S01E01.mkv"],
            settings_dict={"selected_provider": token},
        )

        assert result["status"] == "success"
        providers_called = [
            call.kwargs.get("provider") for call in renamer.search_tv_show.call_args_list
        ]
        # Must not treat the expand-all token as a single provider id.
        assert token.lower() not in providers_called
        assert "auto" not in providers_called
        assert "all" not in providers_called
        assert "automatic" not in providers_called
        # Free providers (no API key) are always attempted when expanding.
        assert "tvmaze" in providers_called
        assert "anidb" in providers_called
        assert len(providers_called) > 1

    def test_specific_provider_does_not_expand(self):
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler

        renamer = MagicMock()
        renamer.detect_media_type.return_value = "tv"
        renamer.parse_tv_filename.return_value = {
            "title": "Show",
            "season": 1,
            "episode": 1,
        }
        renamer.search_tv_show.return_value = {
            "show_title": "Show",
            "season": 1,
            "episode": 1,
            "episode_title": "Only",
            "source": "tvmaze",
        }

        handler = RenamingHandler(ConversionSettings(), renamer)
        handler.preview_rename(
            ["Show.S01E01.mkv"],
            settings_dict={"selected_provider": "tvmaze"},
        )

        providers_called = [
            call.kwargs.get("provider") for call in renamer.search_tv_show.call_args_list
        ]
        assert providers_called == ["tvmaze"]

    def test_worker_maps_gui_auto_to_automatic(self):
        from utils.workers import _renamer_preview_settings_from_ui

        d = _renamer_preview_settings_from_ui({"provider": "auto"})
        assert d["selected_provider"] == "automatic"


# --------------------------------------------------------------------------- #
# C2 — Runtime API keys must rebuild provider instances
# --------------------------------------------------------------------------- #

@pytest.mark.audit_c2
class TestMetadataProviderKeyReinit:
    """Setting TMDB/OMDB/etc. after an empty start must enable searches."""

    def test_configure_keys_builds_providers_after_empty_start(self):
        from core.metadata_grabber import MetadataGrabber
        from core.providers.metadata import OMDBProvider, TMDBProvider, TraktProvider, TVDBProvider

        grabber = MetadataGrabber()
        assert grabber.tmdb is None
        assert grabber.tvdb is None
        assert grabber.omdb is None
        assert grabber.trakt is None
        assert grabber.get_available_providers()["tmdb"] is False

        grabber.configure_keys(
            tmdb_key="tmdb-secret",
            tvdb_key="tvdb-secret",
            omdb_key="omdb-secret",
            trakt_key="trakt-secret",
        )

        assert isinstance(grabber.tmdb, TMDBProvider)
        assert isinstance(grabber.tvdb, TVDBProvider)
        assert isinstance(grabber.omdb, OMDBProvider)
        assert isinstance(grabber.trakt, TraktProvider)
        assert grabber.tmdb.api_key == "tmdb-secret"
        assert grabber.get_available_providers()["tmdb"] is True
        assert grabber.get_available_providers()["omdb"] is True

    def test_configure_keys_clears_provider_when_key_removed(self):
        from core.metadata_grabber import MetadataGrabber

        grabber = MetadataGrabber(tmdb_key="was-set")
        assert grabber.tmdb is not None

        grabber.configure_keys(tmdb_key="")
        assert grabber.tmdb is None
        assert grabber.tmdb_key == ""
        assert grabber.get_available_providers()["tmdb"] is False

    def test_configure_keys_leaves_omitted_providers_unchanged(self):
        from core.metadata_grabber import MetadataGrabber

        grabber = MetadataGrabber(tmdb_key="keep-me", omdb_key="")
        assert grabber.tmdb is not None
        assert grabber.omdb is None

        grabber.configure_keys(omdb_key="now-set")
        assert grabber.tmdb is not None
        assert grabber.tmdb_key == "keep-me"
        assert grabber.omdb is not None
        assert grabber.omdb_key == "now-set"

    def test_core_configure_metadata_keys_after_empty_start(self):
        from core.encodeforge_core import EncodeForgeCore
        from core.handlers.models import ConversionSettings

        core = EncodeForgeCore(ConversionSettings())
        assert core.renamer.tmdb is None
        assert core.renamer.omdb is None

        core.configure_metadata_keys(tmdb_key="tmdb-live", omdb_key="omdb-live")
        assert core.settings.tmdb_api_key == "tmdb-live"
        assert core.settings.omdb_api_key == "omdb-live"
        assert core.renamer.tmdb is not None
        assert core.renamer.omdb is not None
        assert core.renamer.tmdb.api_key == "tmdb-live"

    def test_preview_rename_rebuilds_providers_from_settings_dict(self):
        """Regression for C2: keys in settings_dict must not only update strings."""
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler
        from core.metadata_grabber import MetadataGrabber

        grabber = MetadataGrabber()  # empty start — keyed providers are None
        assert grabber.tmdb is None

        handler = RenamingHandler(ConversionSettings(), grabber)
        grabber.detect_media_type = MagicMock(return_value="movie")
        grabber.parse_movie_filename = MagicMock(
            return_value={"title": "Inception", "year": 2010}
        )

        searched = {}

        def fake_search_movie(title, year=None, provider=None):
            searched["called"] = True
            searched["has_tmdb_instance"] = grabber.tmdb is not None
            return {
                "title": "Inception",
                "year": 2010,
                "source": "tmdb",
            }

        grabber.search_movie = fake_search_movie
        # Avoid FFprobe / hash fallbacks touching the filesystem.
        handler._extract_metadata_from_file = MagicMock(return_value=None)
        handler._infer_from_folder_context = MagicMock(return_value=None)
        handler._identify_by_hash = MagicMock(return_value=None)

        result = handler.preview_rename(
            ["Inception.2010.mkv"],
            settings_dict={
                "selected_provider": "tmdb",
                "tmdb_api_key": "runtime-tmdb-key",
            },
        )

        assert result["status"] == "success"
        assert grabber.tmdb is not None
        assert grabber.tmdb_key == "runtime-tmdb-key"
        assert grabber.tmdb.api_key == "runtime-tmdb-key"
        assert searched.get("called") is True
        assert searched.get("has_tmdb_instance") is True

    def test_string_only_key_assignment_was_insufficient(self):
        """Document the pre-fix failure mode: string update without rebuild."""
        from core.metadata_grabber import MetadataGrabber

        grabber = MetadataGrabber()
        grabber.tmdb_key = "late-key"  # old preview_rename behaviour
        assert grabber.tmdb is None  # provider still missing
        assert grabber.search_movie("Inception", 2010, provider="tmdb") is None

        grabber.configure_keys(tmdb_key="late-key")
        assert grabber.tmdb is not None


# --------------------------------------------------------------------------- #
# P1-B — Keyless-first free metadata providers
# --------------------------------------------------------------------------- #

class TestKeylessFirstMetadataProviders:
    """Default auto path must work with empty API keys via free providers."""

    def test_tv_auto_providers_are_keyless_first(self):
        from core.metadata_grabber import KEYED_PROVIDERS, TV_AUTO_PROVIDERS

        free = [p for p in TV_AUTO_PROVIDERS if p not in KEYED_PROVIDERS]
        keyed = [p for p in TV_AUTO_PROVIDERS if p in KEYED_PROVIDERS]
        assert free == ["tvmaze", "anidb", "kitsu", "jikan"]
        assert keyed == ["tvdb", "tmdb", "trakt", "omdb"]
        # Every free provider appears before every keyed one.
        assert max(TV_AUTO_PROVIDERS.index(p) for p in free) < min(
            TV_AUTO_PROVIDERS.index(p) for p in keyed
        )

    def test_movie_auto_providers_include_free_before_keyed(self):
        from core.metadata_grabber import KEYED_PROVIDERS, MOVIE_AUTO_PROVIDERS

        free = [p for p in MOVIE_AUTO_PROVIDERS if p not in KEYED_PROVIDERS]
        keyed = [p for p in MOVIE_AUTO_PROVIDERS if p in KEYED_PROVIDERS]
        assert free == ["anidb", "kitsu", "jikan"]
        assert keyed == ["tmdb", "omdb", "trakt"]
        assert max(MOVIE_AUTO_PROVIDERS.index(p) for p in free) < min(
            MOVIE_AUTO_PROVIDERS.index(p) for p in keyed
        )

    def test_tv_auto_with_empty_keys_only_calls_free_providers(self):
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler
        from core.metadata_grabber import KEYED_PROVIDERS, TV_AUTO_PROVIDERS

        renamer = MagicMock()
        renamer.detect_media_type.return_value = "tv"
        renamer.parse_tv_filename.return_value = {
            "title": "Show",
            "season": 1,
            "episode": 1,
        }
        renamer.search_tv_show.side_effect = lambda *a, provider=None, **k: {
            "show_title": "Show",
            "season": 1,
            "episode": 1,
            "episode_title": f"via-{provider}",
            "source": provider,
        }

        settings = ConversionSettings()  # all API keys empty
        handler = RenamingHandler(settings, renamer)
        handler._extract_metadata_from_file = MagicMock(return_value=None)
        handler._infer_from_folder_context = MagicMock(return_value=None)
        handler._identify_by_hash = MagicMock(return_value=None)

        result = handler.preview_rename(
            ["Show.S01E01.mkv"],
            settings_dict={"selected_provider": "auto"},
        )

        assert result["status"] == "success"
        providers_called = [
            call.kwargs.get("provider") for call in renamer.search_tv_show.call_args_list
        ]
        assert providers_called == [p for p in TV_AUTO_PROVIDERS if p not in KEYED_PROVIDERS]
        assert "tvmaze" in providers_called
        assert "tmdb" not in providers_called
        assert "trakt" not in providers_called
        assert "omdb" not in providers_called
        assert result["metadata"][0].get("episode_title") or result["metadata"][0].get(
            "show_title"
        )

    def test_tv_trakt_and_omdb_branches_run_when_keys_present(self):
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler

        renamer = MagicMock()
        renamer.detect_media_type.return_value = "tv"
        renamer.parse_tv_filename.return_value = {
            "title": "Show",
            "season": 1,
            "episode": 1,
        }
        called = []

        def fake_search(title, season, episode, provider=None):
            called.append(provider)
            return {
                "show_title": "Show",
                "season": season,
                "episode": episode,
                "episode_title": f"via-{provider}",
                "source": provider,
            }

        renamer.search_tv_show.side_effect = fake_search

        settings = ConversionSettings(
            tmdb_api_key="",
            tvdb_api_key="",
            omdb_api_key="omdb-key",
            trakt_api_key="trakt-key",
        )
        handler = RenamingHandler(settings, renamer)
        handler._extract_metadata_from_file = MagicMock(return_value=None)
        handler._infer_from_folder_context = MagicMock(return_value=None)
        handler._identify_by_hash = MagicMock(return_value=None)

        handler.preview_rename(
            ["Show.S01E01.mkv"],
            settings_dict={"selected_provider": "automatic"},
        )

        assert "trakt" in called
        assert "omdb" in called
        assert "tvmaze" in called

    def test_movie_auto_with_empty_keys_uses_free_providers(self):
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler
        from core.metadata_grabber import KEYED_PROVIDERS, MOVIE_AUTO_PROVIDERS

        renamer = MagicMock()
        renamer.detect_media_type.return_value = "movie"
        renamer.parse_movie_filename.return_value = {
            "title": "Cowboy Bebop",
            "year": 2001,
        }
        renamer.search_movie.side_effect = lambda title, year=None, provider=None: {
            "title": "Cowboy Bebop: The Movie",
            "year": 2001,
            "source": provider,
        }

        handler = RenamingHandler(ConversionSettings(), renamer)
        handler._extract_metadata_from_file = MagicMock(return_value=None)
        handler._infer_from_folder_context = MagicMock(return_value=None)
        handler._identify_by_hash = MagicMock(return_value=None)

        result = handler.preview_rename(
            ["Cowboy.Bebop.2001.mkv"],
            settings_dict={"selected_provider": "auto"},
        )

        assert result["status"] == "success"
        providers_called = [
            call.kwargs.get("provider") for call in renamer.search_movie.call_args_list
        ]
        assert providers_called == [
            p for p in MOVIE_AUTO_PROVIDERS if p not in KEYED_PROVIDERS
        ]
        assert "anidb" in providers_called
        assert "kitsu" in providers_called
        assert "jikan" in providers_called
        assert "tmdb" not in providers_called
        assert result["metadata"][0].get("title")

    def test_movie_auto_includes_keyed_when_keys_present(self):
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler
        from core.metadata_grabber import MOVIE_AUTO_PROVIDERS

        renamer = MagicMock()
        renamer.detect_media_type.return_value = "movie"
        renamer.parse_movie_filename.return_value = {
            "title": "Inception",
            "year": 2010,
        }
        renamer.search_movie.side_effect = lambda title, year=None, provider=None: {
            "title": "Inception",
            "year": 2010,
            "source": provider,
        }

        settings = ConversionSettings(
            tmdb_api_key="tmdb-key",
            omdb_api_key="omdb-key",
            trakt_api_key="trakt-key",
        )
        handler = RenamingHandler(settings, renamer)
        handler._extract_metadata_from_file = MagicMock(return_value=None)
        handler._infer_from_folder_context = MagicMock(return_value=None)
        handler._identify_by_hash = MagicMock(return_value=None)

        handler.preview_rename(
            ["Inception.2010.mkv"],
            settings_dict={"selected_provider": "automatic"},
        )

        providers_called = [
            call.kwargs.get("provider") for call in renamer.search_movie.call_args_list
        ]
        assert providers_called == list(MOVIE_AUTO_PROVIDERS)

    def test_grabber_auto_soft_skips_missing_keys(self):
        from core.metadata_grabber import MetadataGrabber

        grabber = MetadataGrabber()  # no keys
        assert grabber.tmdb is None
        assert grabber.omdb is None
        assert grabber.trakt is None
        assert grabber.tvdb is None

        grabber.tvmaze.search_tv = MagicMock(
            return_value={"show_title": "Free Show", "source": "tvmaze"}
        )
        grabber.anidb.search_tv = MagicMock(return_value=None)
        grabber.kitsu.search_tv = MagicMock(return_value=None)
        grabber.jikan.search_tv = MagicMock(return_value=None)

        result = grabber.search_tv_show("Free Show", 1, 1, provider="auto")
        assert result is not None
        assert result["source"] == "tvmaze"
        grabber.tvmaze.search_tv.assert_called_once()

    def test_grabber_movie_auto_reaches_free_providers(self):
        from core.metadata_grabber import MetadataGrabber

        grabber = MetadataGrabber()
        grabber.anidb.search_movie = MagicMock(return_value=None)
        grabber.kitsu.search_movie = MagicMock(return_value=None)
        grabber.jikan.search_movie = MagicMock(
            return_value={"title": "Anime Film", "source": "jikan"}
        )

        result = grabber.search_movie("Anime Film", 2001, provider="auto")
        assert result is not None
        assert result["source"] == "jikan"
        grabber.anidb.search_movie.assert_called_once()
        grabber.kitsu.search_movie.assert_called_once()
        grabber.jikan.search_movie.assert_called_once()


# --------------------------------------------------------------------------- #
# P2-C — SubtitleHandler shares Core Whisper; dead dual-UI removed
# --------------------------------------------------------------------------- #

class TestSubtitleWhisperSharedViaCore:
    def test_handler_uses_parent_core_whisper_mgr(self, isolated_app_data):
        """Passing Core into SubtitleHandler must not spawn a second WhisperManager."""
        from core.encodeforge_core import EncodeForgeCore
        from core.handlers.subtitle_handler import SubtitleHandler

        sentinel = object()
        core = EncodeForgeCore()
        core._handlers_initialized = True  # skip full handler init for this unit test
        core._whisper_checked = True
        core._whisper_mgr = sentinel

        handler = SubtitleHandler(core.settings, core, None)
        assert handler._lazy_load is False
        assert handler._core is core
        assert handler.whisper_mgr is sentinel

    def test_handler_init_does_not_probe_core_whisper(self, isolated_app_data):
        """Parent-core detection must not invoke Core.whisper_mgr during __init__."""
        from core.encodeforge_core import EncodeForgeCore
        from core.handlers.subtitle_handler import SubtitleHandler

        core = EncodeForgeCore()
        core._handlers_initialized = True
        assert core._whisper_checked is False

        handler = SubtitleHandler(core.settings, core, None)
        assert core._whisper_checked is False
        assert handler._whisper_mgr is None
        assert handler._core is core

    def test_ensure_handlers_passes_self_not_none(self, isolated_app_data, monkeypatch):
        from core.encodeforge_core import EncodeForgeCore
        from core.handlers.subtitle_handler import SubtitleHandler

        captured = {}

        def fake_init(self, settings, core_or_whisper_mgr, subtitle_providers):
            captured["arg"] = core_or_whisper_mgr
            self.settings = settings
            self._core = core_or_whisper_mgr
            self._whisper_mgr = None
            self._lazy_load = False
            self.subtitle_providers = subtitle_providers

        monkeypatch.setattr(SubtitleHandler, "__init__", fake_init)

        core = EncodeForgeCore()
        # Force handler construction (also builds other handlers; stub heavy deps).
        monkeypatch.setattr(core, "ffmpeg_mgr", MagicMock())
        monkeypatch.setattr(core, "renamer", MagicMock())
        monkeypatch.setattr(core, "subtitle_providers", MagicMock())
        core._ensure_handlers_initialized()
        assert captured["arg"] is core


class TestSubtitleDeadDualUiRemoved:
    def test_unmounted_panel_builders_are_gone(self):
        # Read source so this assertion does not require a display/PySide import.
        src = Path(__file__).resolve().parents[1] / "app" / "widgets" / "subtitle_tab.py"
        text = src.read_text(encoding="utf-8")
        for name in (
            "_create_file_panel",
            "_create_settings_panel",
            "_connect_signals",
            "_start_processing",
            "_process_file",
            "_load_preview",
            "_clear_all",
            "_stop_processing",
        ):
            assert f"def {name}" not in text, name
        assert "enableDragDrop(self._drag_enter_event, self._drop_event)" in text



# --------------------------------------------------------------------------- #
# P2-E — no bundled OpenSubtitles / SubDL API keys in source
# --------------------------------------------------------------------------- #

class TestSubtitleSecretsHygiene:
    def test_opensubtitles_source_has_no_plaintext_default(self):
        from pathlib import Path

        src = Path("core/providers/subtitle/opensubtitles_manager.py").read_text(
            encoding="utf-8"
        )
        assert "CONSUMER_API_KEY" not in src
        # Historical leaked key must not reappear.
        assert "N5GIH7h6rpgt9HpG9wqwtXqCoLM07Ot0" not in src

    def test_subdl_source_has_no_plaintext_default(self):
        from pathlib import Path

        src = Path("core/providers/subtitle/subdl_provider.py").read_text(
            encoding="utf-8"
        )
        assert "0kzwwW12CndUyeuPru5DtdRwpIXfH9H9" not in src

    def test_opensubtitles_empty_without_settings_or_env(self, monkeypatch):
        from core.providers.subtitle.opensubtitles_manager import OpenSubtitlesManager

        monkeypatch.delenv("ENCODEFORGE_OPENSUBTITLES_KEY", raising=False)
        mgr = OpenSubtitlesManager()
        assert mgr.consumer_api_key == ""

    def test_opensubtitles_prefers_arg_then_env(self, monkeypatch):
        from core.providers.subtitle.opensubtitles_manager import OpenSubtitlesManager

        monkeypatch.setenv("ENCODEFORGE_OPENSUBTITLES_KEY", "env-os-key")
        assert OpenSubtitlesManager().consumer_api_key == "env-os-key"
        assert OpenSubtitlesManager(api_key="user-os-key").consumer_api_key == "user-os-key"

    def test_subdl_empty_without_settings_or_env(self, monkeypatch):
        from core.providers.subtitle.subdl_provider import SubDLProvider

        monkeypatch.delenv("ENCODEFORGE_SUBDL_KEY", raising=False)
        assert SubDLProvider().api_key == ""

    def test_subdl_prefers_arg_then_env(self, monkeypatch):
        from core.providers.subtitle.subdl_provider import SubDLProvider

        monkeypatch.setenv("ENCODEFORGE_SUBDL_KEY", "env-subdl-key")
        assert SubDLProvider().api_key == "env-subdl-key"
        assert SubDLProvider(api_key="user-subdl-key").api_key == "user-subdl-key"

    def test_core_wires_subtitle_keys_from_settings(self, monkeypatch, isolated_app_data):
        from core.encodeforge_core import EncodeForgeCore
        from core.handlers.models import ConversionSettings

        monkeypatch.delenv("ENCODEFORGE_OPENSUBTITLES_KEY", raising=False)
        monkeypatch.delenv("ENCODEFORGE_SUBDL_KEY", raising=False)
        settings = ConversionSettings(
            opensubtitles_api_key="os-from-settings",
            subdl_api_key="subdl-from-settings",
        )
        core = EncodeForgeCore(settings=settings)
        assert core.subtitle_providers.opensubtitles.consumer_api_key == "os-from-settings"
        assert core.subtitle_providers.subdl.api_key == "subdl-from-settings"

    def test_export_redacts_subtitle_api_keys(self, isolated_app_data, tmp_path):
        from utils.settings_manager import SettingsManager

        SettingsManager._instance = None
        manager = SettingsManager()
        manager.conversion.opensubtitles_api_key = "OS-SECRET"
        manager.conversion.subdl_api_key = "SUBDL-SECRET"

        target = tmp_path / "export-subs.json"
        assert manager.export_settings(target) is True
        data = json.loads(target.read_text())
        assert data["conversion"]["opensubtitles_api_key"] == ""
        assert data["conversion"]["subdl_api_key"] == ""
