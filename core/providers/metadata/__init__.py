"""
Metadata Providers Package
Modular metadata provider implementations for movies, TV shows, and anime
"""

from .anidb_provider import AniDBProvider
from .base_provider import BaseMetadataProvider
from .jikan_provider import JikanProvider
from .kitsu_provider import KitsuProvider
from .omdb_provider import OMDBProvider
from .tmdb_provider import TMDBProvider
from .trakt_provider import TraktProvider
from .tvdb_provider import TVDBProvider
from .tvmaze_provider import TVmazeProvider

__all__ = [
    'BaseMetadataProvider',
    'TMDBProvider',
    'TVDBProvider',
    'AniDBProvider',
    'TVmazeProvider',
    'KitsuProvider',
    'JikanProvider',
    'TraktProvider',
    'OMDBProvider'
]

