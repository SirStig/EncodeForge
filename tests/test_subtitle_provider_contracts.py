"""
Contract tests for healthy subtitle providers + quarantine honesty.

Fixtures under tests/fixtures/subtitle/ stand in for live HTML/API responses
so CI never hits the network. Quarantined scrapers must not be queried.
"""

from __future__ import annotations

from pathlib import Path
from typing import List
from unittest.mock import MagicMock

from core.handlers.subtitle_handler import SubtitleHandler
from core.providers.subtitle.addic7ed_provider import Addic7edProvider
from core.providers.subtitle.opensubtitles_manager import OpenSubtitlesManager
from core.providers.subtitle.provider_status import (
    QUARANTINED_PROVIDERS,
    is_provider_quarantined,
    ui_provider_entries,
)
from core.providers.subtitle.subdl_provider import SubDLProvider
from core.subtitle_manager import SubtitleProviders

FIXTURES = Path(__file__).parent / "fixtures" / "subtitle"


def _load_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _load_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class _FakeHTTPResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


# --------------------------------------------------------------------------- #
# Quarantine / UI catalog
# --------------------------------------------------------------------------- #


class TestProviderQuarantine:
    def test_known_broken_scrapers_are_quarantined(self):
        assert QUARANTINED_PROVIDERS == frozenset({"Podnapisi", "SubDivX", "Jimaku"})
        for name in QUARANTINED_PROVIDERS:
            assert is_provider_quarantined(name) is True

    def test_healthy_providers_are_not_quarantined(self):
        for name in ("OpenSubtitles.com", "Addic7ed", "SubDL", "Subf2m", "YIFY"):
            assert is_provider_quarantined(name) is False

    def test_ui_entries_badge_unavailable(self):
        labels = {row["label"]: row for row in ui_provider_entries()}
        assert "All" in labels
        assert labels["Podnapisi (unavailable)"]["selectable"] is False
        assert labels["SubDivX (unavailable)"]["selectable"] is False
        assert labels["Jimaku (unavailable)"]["selectable"] is False
        assert labels["OpenSubtitles"]["available"] is True

    def test_default_search_skips_quarantined(self, monkeypatch, tmp_path):
        providers = SubtitleProviders()
        called: List[str] = []

        def _track(name):
            def _fn(*_a, **_k):
                called.append(name)
                return []

            return _fn

        monkeypatch.setattr(providers, "_search_opensubtitles", _track("OpenSubtitles.com"))
        monkeypatch.setattr(providers, "search_addic7ed", _track("Addic7ed"))
        monkeypatch.setattr(providers, "search_subdl", _track("SubDL"))
        monkeypatch.setattr(providers, "search_subf2m", _track("Subf2m"))
        monkeypatch.setattr(providers, "search_yifysubtitles", _track("YIFY"))
        monkeypatch.setattr(providers, "search_podnapisi", _track("Podnapisi"))
        monkeypatch.setattr(providers, "search_subdivx", _track("SubDivX"))
        monkeypatch.setattr(providers, "search_jimaku", _track("Jimaku"))

        video = tmp_path / "Movie.2020.1080p.mkv"
        video.write_bytes(b"\x00" * 64)
        providers.search_all_providers(str(video), ["eng"])

        assert "Podnapisi" not in called
        assert "SubDivX" not in called
        assert "Jimaku" not in called
        assert "OpenSubtitles.com" in called
        assert "Addic7ed" in called
        assert "SubDL" in called

    def test_explicit_jimaku_selection_still_blocked(self):
        providers = SubtitleProviders()
        providers.enabled_providers = ["Jimaku"]
        assert providers.is_provider_enabled("Jimaku") is False
        assert providers.is_provider_enabled("OpenSubtitles.com") is False


# --------------------------------------------------------------------------- #
# Empty search must not look like success
# --------------------------------------------------------------------------- #


class TestNoSilentEmptySuccess:
    def test_search_subtitles_empty_status(self, monkeypatch, tmp_path):
        providers = SubtitleProviders()
        handler = SubtitleHandler(
            MagicMock(subtitle_languages=["eng"]),
            None,
            providers,
        )
        monkeypatch.setattr(providers, "search_all_providers", lambda *_a, **_k: [])
        video = tmp_path / "Empty.Show.S01E01.mkv"
        video.write_bytes(b"x")
        result = handler.search_subtitles(str(video), ["eng"])
        assert result["status"] == "empty"
        assert result["count"] == 0
        assert result["subtitles"] == []
        assert "No subtitles found" in result["message"]

    def test_download_subtitles_surfaces_empty_message(self, monkeypatch, tmp_path):
        handler = SubtitleHandler(
            MagicMock(subtitle_languages=["eng"]),
            None,
            SubtitleProviders(),
        )
        monkeypatch.setattr(
            handler,
            "search_subtitles",
            lambda *_a, **_k: {
                "status": "empty",
                "message": "No subtitles found from available providers.",
                "count": 0,
                "subtitles": [],
            },
        )
        video = tmp_path / "Empty.Show.S01E01.mkv"
        video.write_bytes(b"x")
        result = handler.download_subtitles(str(video), ["eng"])
        assert result["status"] == "error"
        assert "No subtitles found" in result["message"]
        assert result["subtitles_downloaded"] == []


# --------------------------------------------------------------------------- #
# OpenSubtitles API contract
# --------------------------------------------------------------------------- #


class TestOpenSubtitlesContract:
    def test_parses_fixture_response(self, monkeypatch, tmp_path):
        mgr = OpenSubtitlesManager(api_key="test-key")
        fixture = _load_bytes("opensubtitles_search.json")

        monkeypatch.setattr(mgr, "calculate_file_hash", lambda _p: "a" * 16)
        monkeypatch.setattr(
            "core.providers.subtitle.opensubtitles_manager.urllib.request.urlopen",
            lambda *_a, **_k: _FakeHTTPResponse(fixture),
        )

        video = tmp_path / "Breaking.Bad.S01E01.1080p.mkv"
        # Hash path needs a real size; search only uses the monkeypatched hash.
        video.write_bytes(b"\x00" * 200_000)

        success, results = mgr.search_subtitles(str(video), ["eng", "spa"])
        assert success is True
        assert len(results) == 2
        assert results[0]["file_id"] == 555001
        assert results[0]["file_name"] == "Breaking.Bad.S01E01.1080p.en.srt"
        assert results[0]["language"] == "en"
        assert results[1]["file_id"] == 555002


# --------------------------------------------------------------------------- #
# SubDL API contract
# --------------------------------------------------------------------------- #


class TestSubDLContract:
    def test_parses_fixture_response(self, monkeypatch, tmp_path):
        provider = SubDLProvider()
        fixture = _load_bytes("subdl_search.json")

        monkeypatch.setattr(
            "core.providers.subtitle.subdl_provider.urllib.request.urlopen",
            lambda *_a, **_k: _FakeHTTPResponse(fixture),
        )
        monkeypatch.setattr("core.providers.subtitle.subdl_provider.time.sleep", lambda _s: None)

        video = tmp_path / "Breaking.Bad.S01E01.1080p.mkv"
        video.write_bytes(b"x")
        results = provider.search(str(video), ["eng"])

        assert len(results) == 1  # French filtered out
        assert results[0]["provider"] == "SubDL"
        assert results[0]["file_id"] == "sd-1001"
        assert results[0]["language"] == "en"
        assert "Breaking.Bad" in results[0]["file_name"]


# --------------------------------------------------------------------------- #
# Addic7ed HTML contract
# --------------------------------------------------------------------------- #


class TestAddic7edContract:
    def test_parses_search_and_season_fixtures(self, monkeypatch, tmp_path):
        provider = Addic7edProvider()
        search_html = _load_bytes("addic7ed_search.html")
        season_html = _load_bytes("addic7ed_season.html")
        responses = iter([search_html, season_html])

        def _urlopen(_req, timeout=15):
            return _FakeHTTPResponse(next(responses))

        monkeypatch.setattr(
            "core.providers.subtitle.addic7ed_provider.urllib.request.urlopen",
            _urlopen,
        )
        monkeypatch.setattr("core.providers.subtitle.addic7ed_provider.time.sleep", lambda _s: None)

        video = tmp_path / "Breaking.Bad.S01E01.1080p.mkv"
        video.write_bytes(b"x")
        results = provider.search(str(video), ["eng"])

        assert len(results) == 1  # S01E02 and Spanish rows filtered
        assert results[0]["provider"] == "Addic7ed"
        assert results[0]["language"] == "eng"
        assert "S01E01" in results[0]["file_name"]
        assert results[0]["download_url"].endswith("/original/42/1")
