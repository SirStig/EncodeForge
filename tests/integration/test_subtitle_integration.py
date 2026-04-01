import os
import shutil
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.requires_ffmpeg
def test_apply_subtitle_external_embed_burn(core_ffmpeg, synthetic_mp4, minimal_srt):
    ext = core_ffmpeg.apply_subtitles(
        str(synthetic_mp4),
        [str(minimal_srt)],
        mode="external",
        language="eng",
    )
    assert ext["status"] == "success"
    assert Path(ext["output_path"]).exists()

    emb = core_ffmpeg.apply_subtitles(
        str(synthetic_mp4),
        [str(minimal_srt)],
        mode="embed",
        language="eng",
        output_path=str(synthetic_mp4.parent / "with_subs.mp4"),
    )
    assert emb["status"] == "success"
    assert Path(emb["output_path"]).exists()

    burn = core_ffmpeg.apply_subtitles(
        str(synthetic_mp4),
        [str(minimal_srt)],
        mode="burn-in",
        output_path=str(synthetic_mp4.parent / "burned.mp4"),
    )
    assert burn["status"] == "success"
    assert Path(burn["output_path"]).exists()


@pytest.mark.integration
@pytest.mark.requires_network
def test_search_subtitles_popular_movie_filename(core_ffmpeg, temp_sample_mp4, tmp_path):
    named = tmp_path / "The.Matrix.1999.1080p.BluRay.mp4"
    shutil.copy2(temp_sample_mp4, named)
    r = core_ffmpeg.search_subtitles(str(named), languages=["eng"])
    assert r["status"] == "success"
    if r.get("count", 0) == 0:
        pytest.skip("No subtitle hits from providers (quota, API, or catalog change)")
    assert len(r.get("subtitles", [])) >= 1


@pytest.mark.integration
@pytest.mark.requires_network
@pytest.mark.slow
def test_advanced_search_subtitles(core_ffmpeg, temp_sample_mp4, tmp_path):
    if os.environ.get("ENCODEFORGE_ADVANCED_SUBTITLE_SEARCH", "").strip() != "1":
        pytest.skip(
            "Advanced search calls every provider for each filename query variant; "
            "set ENCODEFORGE_ADVANCED_SUBTITLE_SEARCH=1 to run (can take several minutes)"
        )
    named = tmp_path / "Inception.2010.1080p.mkv"
    shutil.copy2(temp_sample_mp4, named)
    r = core_ffmpeg.advanced_search_subtitles(str(named), languages=["eng"])
    assert r["status"] == "success"


@pytest.mark.integration
@pytest.mark.requires_network
def test_subdl_search_and_download(core_ffmpeg, temp_sample_mp4, tmp_path):
    named = tmp_path / "The.Matrix.1999.1080p.BluRay.mp4"
    shutil.copy2(temp_sample_mp4, named)
    sp = core_ffmpeg.subtitle_providers
    hits = sp.subdl.search(str(named), ["eng"])
    if not hits:
        pytest.skip("SubDL returned no subtitles for this fixture")
    out = named.parent / f"{named.stem}.eng.srt"
    ok, res = sp.download_subtitle(
        hits[0]["file_id"],
        "SubDL",
        str(out),
        hits[0].get("download_url", "") or "",
    )
    assert ok, res
    assert out.exists()


@pytest.mark.integration
@pytest.mark.requires_network
@pytest.mark.slow
@pytest.mark.stress_subtitles
def test_download_subtitles_auto_best_stress(core_ffmpeg, temp_sample_mp4, tmp_path):
    if os.environ.get("ENCODEFORGE_STRESS_SUBTITLES", "").strip() != "1":
        pytest.skip("Set ENCODEFORGE_STRESS_SUBTITLES=1 to run full auto-download stress test")
    named = tmp_path / "Inception.2010.1080p.stress.mp4"
    shutil.copy2(temp_sample_mp4, named)
    r = core_ffmpeg.download_subtitles(str(named), languages=["eng"])
    assert r["status"] == "success"
    assert Path((r.get("subtitles_downloaded") or [{}])[0]["subtitle_path"]).exists()
