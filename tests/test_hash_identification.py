"""
OSDB hash-based identification (P5) — a last-resort fallback for filenames
the S##E##/year parsers can't read anything from at all. Schema verified
against OpenSubtitles' real API docs (feature_details: feature_type, title,
parent_title, season_number, episode_number, year).
"""

import json
from unittest.mock import MagicMock, patch

import pytest


EPISODE_RESPONSE = {
    "data": [{
        "attributes": {
            "feature_details": {
                "feature_id": 88174,
                "feature_type": "Episode",
                "year": 2006,
                "title": "World's Greatest Couple",
                "movie_name": "How I Met Your Mother - S02E05 World's Greatest Couple",
                "imdb_id": 866188,
                "season_number": 2,
                "episode_number": 5,
                "parent_title": "How I Met Your Mother",
            }
        }
    }]
}

MOVIE_RESPONSE = {
    "data": [{
        "attributes": {
            "feature_details": {
                "feature_type": "Movie",
                "year": 2010,
                "title": "Inception",
                "imdb_id": 1375666,
            }
        }
    }]
}


def _mgr():
    from core.providers.subtitle.opensubtitles_manager import OpenSubtitlesManager
    mgr = OpenSubtitlesManager()
    mgr.consumer_api_key = "test-key"
    return mgr


def _mock_urlopen(payload):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


class TestIdentifyByHash:
    def test_episode_maps_parent_title_and_season_episode(self, tmp_path):
        video = tmp_path / "abc123.mkv"
        video.write_bytes(b"\x00" * (65536 * 2 + 10))

        mgr = _mgr()
        with patch.object(mgr, "calculate_file_hash", return_value="deadbeef"), \
             patch("urllib.request.urlopen", return_value=_mock_urlopen(EPISODE_RESPONSE)):
            result = mgr.identify_by_hash(str(video))

        assert result is not None
        assert result["show_title"] == "How I Met Your Mother"
        assert result["episode_title"] == "World's Greatest Couple"
        assert result["season"] == 2
        assert result["episode"] == 5
        assert result["year"] == "2006"

    def test_movie_maps_title_directly(self, tmp_path):
        video = tmp_path / "abc123.mkv"
        video.write_bytes(b"\x00" * (65536 * 2 + 10))

        mgr = _mgr()
        with patch.object(mgr, "calculate_file_hash", return_value="deadbeef"), \
             patch("urllib.request.urlopen", return_value=_mock_urlopen(MOVIE_RESPONSE)):
            result = mgr.identify_by_hash(str(video))

        assert result is not None
        assert result["title"] == "Inception"
        assert result["year"] == "2010"
        assert "season" not in result

    def test_no_consumer_key_returns_none_without_a_request(self, tmp_path):
        video = tmp_path / "abc123.mkv"
        video.write_bytes(b"\x00" * (65536 * 2 + 10))

        from core.providers.subtitle.opensubtitles_manager import OpenSubtitlesManager
        mgr = OpenSubtitlesManager()
        mgr.consumer_api_key = ""

        with patch("urllib.request.urlopen") as mock_urlopen:
            result = mgr.identify_by_hash(str(video))
        assert result is None
        mock_urlopen.assert_not_called()

    def test_file_too_small_to_hash_returns_none(self, tmp_path):
        video = tmp_path / "tiny.mkv"
        video.write_bytes(b"\x00" * 10)  # below the 128KB hash floor

        mgr = _mgr()
        result = mgr.identify_by_hash(str(video))
        assert result is None

    def test_network_failure_returns_none_not_an_exception(self, tmp_path):
        video = tmp_path / "abc123.mkv"
        video.write_bytes(b"\x00" * (65536 * 2 + 10))

        mgr = _mgr()
        with patch.object(mgr, "calculate_file_hash", return_value="deadbeef"), \
             patch("urllib.request.urlopen", side_effect=OSError("timed out")):
            result = mgr.identify_by_hash(str(video))
        assert result is None

    def test_no_data_in_response_returns_none(self, tmp_path):
        video = tmp_path / "abc123.mkv"
        video.write_bytes(b"\x00" * (65536 * 2 + 10))

        mgr = _mgr()
        with patch.object(mgr, "calculate_file_hash", return_value="deadbeef"), \
             patch("urllib.request.urlopen", return_value=_mock_urlopen({"data": []})):
            result = mgr.identify_by_hash(str(video))
        assert result is None


class TestRenamingHandlerHashFallback:
    def test_used_only_when_filename_and_folder_inference_both_fail(self, tmp_path):
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler

        garbage = tmp_path / "a1b2c3d4.mkv"
        garbage.write_text("DATA")

        handler = RenamingHandler(ConversionSettings(), renamer=None)

        with patch.object(handler, "_identify_by_hash", return_value={
            "title": "How I Met Your Mother", "season": 2, "episode": 5,
            "episode_title": "World's Greatest Couple",
        }), patch("subprocess.run", side_effect=OSError("no ffprobe in test env")):
            result = handler._extract_metadata_from_file(str(garbage))

        assert result is not None
        assert result["title"] == "How I Met Your Mother"
        assert result["season"] == 2
        assert result["episode"] == 5

    def test_not_consulted_when_filename_already_parsed(self, tmp_path):
        """The hash lookup is a last resort — a normal S##E## filename
        must never trigger a network call."""
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler

        video = tmp_path / "Show.S01E05.mkv"
        video.write_text("DATA")

        handler = RenamingHandler(ConversionSettings(), renamer=None)

        with patch.object(handler, "_identify_by_hash") as mock_hash, \
             patch("subprocess.run", side_effect=OSError("no ffprobe in test env")):
            result = handler._extract_metadata_from_file(str(video))

        mock_hash.assert_not_called()
        assert result is not None
        assert result["season"] == 1
        assert result["episode"] == 5
