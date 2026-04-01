import pytest

from core.metadata_grabber import MetadataGrabber


@pytest.mark.integration
@pytest.mark.requires_network
def test_tvmaze_tv_search_breaking_bad():
    g = MetadataGrabber()
    r = g.search_tv_show("Breaking Bad", 1, 1, provider="tvmaze")
    assert r is not None
    title = (r.get("show_title") or r.get("title") or "").lower()
    assert "breaking" in title


@pytest.mark.integration
@pytest.mark.requires_network
def test_metadata_grabber_auto_tv_falls_back_to_free_provider():
    g = MetadataGrabber()
    r = g.search_tv_show("The Simpsons", 1, 1, provider="auto")
    assert r is not None
    blob = (r.get("show_title") or r.get("title") or "").lower()
    assert "simpson" in blob


@pytest.mark.integration
@pytest.mark.requires_network
def test_search_movie_jikan_anime():
    g = MetadataGrabber()
    r = g.search_movie("Cowboy Bebop: The Movie", 2001, provider="jikan")
    if r is None:
        pytest.skip("Jikan did not return a movie match (rate limit or API change)")
    label = (r.get("title") or r.get("show_title") or "").lower()
    assert "bebop" in label or "cowboy" in label
