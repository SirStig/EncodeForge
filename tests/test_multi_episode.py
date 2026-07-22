"""
Multi-episode file support (P5): "Show.S01E05E06.mkv" used to parse as just
episode 5, silently dropping the second episode. Covers the parser, the
pattern placeholder, and RenamingHandler.preview_rename's second-episode
title lookup end to end.
"""

from unittest.mock import MagicMock

import pytest


class TestMultiEpisodeParsing:
    @staticmethod
    def _provider():
        from core.providers.metadata.anidb_provider import AniDBProvider
        return AniDBProvider()

    @pytest.mark.parametrize("filename,episode,episode2", [
        ("Show.S01E05E06.1080p.mkv", 5, 6),
        ("Show.S01E05-E06.1080p.mkv", 5, 6),
        ("Show.S01E05.1080p.mkv", 5, None),
    ])
    def test_captures_second_episode_when_present(self, filename, episode, episode2):
        parsed = self._provider().parse_tv_filename(filename)
        assert parsed["episode"] == episode
        assert parsed.get("episode2") == episode2

    def test_hyphenated_quality_tag_is_not_misread_as_a_second_episode(self):
        """A bare "-1080" must never be read as episode 108 — only an
        explicit E/e marker counts as a second episode."""
        parsed = self._provider().parse_tv_filename("Show.S01E05-1080p.WEB.mkv")
        assert parsed["episode"] == 5
        assert parsed.get("episode2") is None


class TestMultiEpisodePatternFormatting:
    def test_episode_end_defaults_to_episode_for_single_episode_files(self):
        from core.rename_pattern import format_filename_stem

        stem = format_filename_stem(
            {"title": "Show", "season": 1, "episode": 5, "episode_title": "Ep"},
            "{title} - S{season:02d}E{episode:02d}-E{episode_end:02d}",
        )
        assert stem == "Show - S01E05-E05"

    def test_episode_end_reflects_the_second_episode_when_present(self):
        from core.rename_pattern import format_filename_stem

        stem = format_filename_stem(
            {"title": "Show", "season": 1, "episode": 5, "episode2": 6},
            "{title} - S{season:02d}E{episode:02d}-E{episode_end:02d}",
        )
        assert stem == "Show - S01E05-E06"


class TestMultiEpisodePreviewRename:
    def test_preview_rename_fetches_and_joins_both_episode_titles(self):
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler

        renamer = MagicMock()
        renamer.detect_media_type.return_value = "tv"
        renamer.parse_tv_filename.return_value = {"title": "Show", "season": 1, "episode": 5, "episode2": 6}

        def fake_search(title, season, episode, provider=None):
            titles = {5: "Part One", 6: "Part Two"}
            if episode in titles:
                return {"show_title": "Show", "season": 1, "episode": episode,
                        "episode_title": titles[episode], "source": "tvdb"}
            return None

        renamer.search_tv_show.side_effect = fake_search

        settings = ConversionSettings()
        settings.tvdb_api_key = "x"
        handler = RenamingHandler(settings, renamer)

        result = handler.preview_rename(["Show.S01E05E06.1080p.mkv"])
        assert result["status"] == "success"
        meta = result["metadata"][0]
        assert meta["episode2"] == 6
        assert meta["episode_title"] == "Part One & Part Two"

    def test_second_episode_lookup_failure_does_not_break_the_first(self):
        """If the second episode's title can't be found, the file still
        renames using what the first episode returned."""
        from core.handlers.models import ConversionSettings
        from core.handlers.renaming_handler import RenamingHandler

        renamer = MagicMock()
        renamer.detect_media_type.return_value = "tv"
        renamer.parse_tv_filename.return_value = {"title": "Show", "season": 1, "episode": 5, "episode2": 6}

        def fake_search(title, season, episode, provider=None):
            if episode == 5:
                return {"show_title": "Show", "season": 1, "episode": 5,
                        "episode_title": "Part One", "source": "tvdb"}
            return None  # episode 6 lookup fails

        renamer.search_tv_show.side_effect = fake_search

        settings = ConversionSettings()
        settings.tvdb_api_key = "x"
        handler = RenamingHandler(settings, renamer)

        result = handler.preview_rename(["Show.S01E05E06.1080p.mkv"])
        meta = result["metadata"][0]
        assert meta["episode2"] == 6
        assert meta["episode_title"] == "Part One"
