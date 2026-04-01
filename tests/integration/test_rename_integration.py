import shutil
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.requires_network
def test_preview_rename_tv_episode(core_ffmpeg, temp_sample_mp4, tmp_path):
    tv = tmp_path / "Breaking.Bad.S01E01.Pilot.1080p.mkv"
    shutil.copy2(temp_sample_mp4, tv)
    prev = core_ffmpeg.preview_rename([str(tv)])
    assert prev["status"] == "success"
    meta = prev.get("metadata") or []
    assert len(meta) == 1
    first = meta[0]
    if not first:
        pytest.skip("TVmaze/metadata did not return a match for this filename")
    show = (first.get("show_title") or first.get("title") or "").lower()
    assert "breaking" in show or "bad" in show


@pytest.mark.integration
@pytest.mark.requires_network
def test_rename_files_dry_run(core_ffmpeg, temp_sample_mp4, tmp_path):
    tv = tmp_path / "Breaking.Bad.S01E01.Pilot.1080p.mkv"
    shutil.copy2(temp_sample_mp4, tv)
    r = core_ffmpeg.rename_files([str(tv)], dry_run=True)
    if r["status"] != "success":
        pytest.skip(f"Rename preview/metadata unavailable: {r.get('message', r)}")
    assert tv.exists()
    res = (r.get("results") or [{}])[0]
    assert res.get("success") is True
    assert "would rename" in (res.get("message") or "").lower()
