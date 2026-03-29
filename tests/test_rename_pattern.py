"""Tests for core.rename_pattern formatting and validation."""

from core.rename_pattern import (
    SAMPLE_TV_METADATA,
    apply_filename_options,
    build_format_dict,
    format_filename_stem,
    validate_pattern,
)


def test_format_tv_standard():
    pat = "{title} - S{season:02d}E{episode:02d} - {episode_title}"
    stem = format_filename_stem(SAMPLE_TV_METADATA, pat, file_stem="x")
    assert stem == "Breaking Bad - S01E05 - Gray Matter"


def test_format_movie_year():
    md = {"title": "Inception", "year": "2010"}
    stem = format_filename_stem(md, "{title} ({year})", file_stem="")
    assert stem == "Inception (2010)"


def test_build_format_dict_show_title_priority():
    d = build_format_dict({"show_title": "Show", "title": "Wrong"}, file_stem="stem")
    assert d["title"] == "Show"


def test_apply_filename_options():
    s = apply_filename_options("Hello World", replace_spaces=True, lowercase=True, remove_special=False)
    assert s == "hello.world"


def test_validate_pattern_ok():
    ok, msg = validate_pattern("{title} - S{season:02d}E{episode:02d}")
    assert ok and msg == ""


def test_validate_pattern_empty():
    ok, msg = validate_pattern("   ")
    assert not ok
