#!/usr/bin/env python3
"""
Metadata Grabber - FileBot-style renaming with database integration
Orchestrates multiple metadata providers for movies, TV shows, and anime
"""

import logging
import platform
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

from core.providers.metadata import (
    AniDBProvider,
    JikanProvider,
    KitsuProvider,
    OMDBProvider,
    TMDBProvider,
    TraktProvider,
    TVDBProvider,
    TVmazeProvider,
)

logger = logging.getLogger(__name__)


class MetadataGrabber:
    """
    Handles media metadata retrieval with multiple database providers
    
    FREE Providers (No API Key):
    - AniDB (Anime)
    - Kitsu (Anime)
    - Jikan/MyAnimeList (Anime - read-only)
    - TVmaze (TV Shows)
    
    API Key Providers (Free Keys):
    - TMDB (Movies & TV)
    - TVDB (TV Shows)
    - OMDB (Movies & TV)
    - Trakt (Movies & TV)
    """
    
    def __init__(self, 
                 tmdb_key: str = "", 
                 tvdb_key: str = "", 
                 omdb_key: str = "",
                 trakt_key: str = "",
                 fanart_key: str = "",
                 mal_client_id: str = ""):
        """Initialize with API keys"""
        # Initialize providers with API keys
        self.tmdb = TMDBProvider(tmdb_key) if tmdb_key else None
        self.tvdb = TVDBProvider(tvdb_key) if tvdb_key else None
        self.omdb = OMDBProvider(omdb_key) if omdb_key else None
        self.trakt = TraktProvider(trakt_key) if trakt_key else None
        
        # Initialize free providers (no API key)
        self.anidb = AniDBProvider()
        self.tvmaze = TVmazeProvider()
        self.kitsu = KitsuProvider()
        self.jikan = JikanProvider()
        
        # Store keys for validation
        self.tmdb_key = tmdb_key
        self.tvdb_key = tvdb_key
        self.omdb_key = omdb_key
        self.trakt_key = trakt_key
        self.fanart_key = fanart_key
        self.mal_client_id = mal_client_id
    
    def get_available_providers(self) -> Dict[str, bool]:
        """
        Get list of available providers based on configured API keys
        
        Returns:
            Dict mapping provider name to availability status
        """
        return {
            # Always available (no key needed)
            "anidb": True,
            "kitsu": True,
            "jikan": True,
            "tvmaze": True,
            
            # Require API keys
            "tmdb": bool(self.tmdb_key),
            "tvdb": bool(self.tvdb_key),
            "omdb": bool(self.omdb_key),
            "trakt": bool(self.trakt_key),
            "fanart": bool(self.fanart_key),
            "mal": bool(self.mal_client_id),
        }
    
    def validate_tmdb_key(self) -> Tuple[bool, str]:
        """Validate TMDB API key"""
        if self.tmdb:
            return self.tmdb.validate_api_key()
        return False, "TMDB provider not initialized"
    
    def validate_tvdb_key(self) -> Tuple[bool, str]:
        """Validate TVDB API key"""
        if self.tvdb:
            return self.tvdb.validate_api_key()
        return False, "TVDB provider not initialized"
    
    def validate_omdb_key(self) -> Tuple[bool, str]:
        """Validate OMDB API key"""
        if self.omdb:
            return self.omdb.validate_api_key()
        return False, "OMDB provider not initialized"
    
    def validate_trakt_key(self) -> Tuple[bool, str]:
        """Validate Trakt API key"""
        if self.trakt:
            return self.trakt.validate_api_key()
        return False, "Trakt provider not initialized"
    
    def detect_media_type(self, filename: str) -> str:
        """
        Detect if file is a movie or TV show
        
        Returns: "movie", "tv", or "unknown"
        """
        return self.anidb.detect_media_type(filename)
    
    def parse_tv_filename(self, filename: str) -> Optional[Dict]:
        """
        Parse TV show filename to extract information
        
        Returns dict with: title, season, episode, or None
        """
        return self.anidb.parse_tv_filename(filename)
    
    def parse_movie_filename(self, filename: str) -> Optional[Dict]:
        """
        Parse movie filename to extract information
        
        Returns dict with: title, year, or None
        """
        return self.anidb.parse_movie_filename(filename)
    
    def search_tv_show(self, title: str, season: int = 1, episode: int = 1, provider: str = "auto") -> Optional[Dict]:
        """
        Search for TV show - tries multiple providers
        
        Args:
            title: Show title to search
            season: Season number
            episode: Episode number
            provider: Specific provider to use, or "auto" for automatic selection
        
        Provider Priority:
            - Anime: AniDB, Kitsu, Jikan -> TMDB
            - TV: TVDB, TVmaze, Trakt -> TMDB -> OMDB
        """
        # Detect if anime
        is_anime = self.anidb.is_anime(title)
        
        # Try specific provider if requested
        if provider != "auto":
            if provider == "tvdb" and self.tvdb:
                return self.tvdb.search_tv(title, season, episode)
            elif provider == "tvmaze":
                return self.tvmaze.search_tv(title, season, episode)
            elif provider == "anidb":
                return self.anidb.search_tv(title, season, episode)
            elif provider == "kitsu":
                return self.kitsu.search_tv(title, season, episode)
            elif provider == "jikan":
                return self.jikan.search_tv(title, season, episode)
            elif provider == "trakt" and self.trakt:
                return self.trakt.search_tv(title, season, episode)
            elif provider == "omdb" and self.omdb:
                return self.omdb.search_tv(title, season, episode)
            elif provider == "tmdb" and self.tmdb:
                pass  # Fall through to TMDB below
        
        # Auto mode - try providers based on content type
        if is_anime:
            # Try anime providers first (all free)
            for provider_obj in [self.anidb, self.kitsu, self.jikan]:
                try:
                    result = provider_obj.search_tv(title, season, episode)
                    if result:
                        return result
                except Exception as e:
                    logger.error(f"Error with anime provider: {e}")
        
        # Try general TV show providers
        # TVDB (requires key)
        if self.tvdb:
            result = self.tvdb.search_tv(title, season, episode)
            if result:
                return result
        
        # TVmaze (free, no key)
        result = self.tvmaze.search_tv(title, season, episode)
        if result:
            return result
        
        # Trakt (requires key)
        if self.trakt:
            result = self.trakt.search_tv(title, season, episode)
            if result:
                return result
        
        # Try TMDB
        if self.tmdb:
            result = self.tmdb.search_tv(title, season, episode)
            if result:
                return result
        
        # Last resort: OMDB
        if self.omdb:
            result = self.omdb.search_tv(title, season, episode)
            if result:
                return result
        
        logger.warning(f"No results found for TV show: {title}")
        return None
    
    def search_movie(self, title: str, year: Optional[int] = None, provider: str = "auto") -> Optional[Dict]:
        """
        Search for movie information using multiple providers
        
        Args:
            title: Movie title to search
            year: Release year (optional, helps accuracy)
            provider: Specific provider to use, or "auto" for automatic selection
        
        Provider Priority:
            - Anime Movies: AniDB, Kitsu, Jikan -> TMDB
            - Regular Movies: TMDB, Trakt, OMDB
        
        Returns dict with movie information or None
        """
        # Detect if anime movie
        is_anime = self.anidb.is_anime(title)
        
        # Try specific provider if requested
        if provider != "auto":
            if provider == "anidb":
                return self.anidb.search_movie(title, year)
            elif provider == "kitsu":
                return self.kitsu.search_movie(title, year)
            elif provider == "jikan":
                return self.jikan.search_movie(title, year)
            elif provider == "tmdb" and self.tmdb:
                pass  # Fall through to TMDB below
            elif provider == "trakt" and self.trakt:
                return self.trakt.search_movie(title, year)
            elif provider == "omdb" and self.omdb:
                return self.omdb.search_movie(title, year)
        
        # Auto mode - try providers based on content type
        if is_anime:
            # Try anime providers first (all free)
            for provider_obj in [self.anidb, self.kitsu, self.jikan]:
                try:
                    result = provider_obj.search_movie(title, year)
                    if result:
                        return result
                except Exception as e:
                    logger.error(f"Error with anime movie provider: {e}")
        
        # Try TMDB first (best quality for regular movies)
        if self.tmdb:
            result = self.tmdb.search_movie(title, year)
            if result:
                return result
        
        # Try Trakt
        if self.trakt:
            result = self.trakt.search_movie(title, year)
            if result:
                return result
        
        # Try OMDB
        if self.omdb:
            result = self.omdb.search_movie(title, year)
            if result:
                return result
        
        logger.warning(f"No results found for movie: {title}")
        return None
    
    def format_filename(self, info: Dict, pattern: str) -> str:
        """
        Format filename using a pattern
        
        Pattern tokens:
            {title} - Show/Movie title
            {year} - Year
            {season} - Season number (padded)
            {episode} - Episode number (padded)
            {episodeTitle} - Episode title
            {S} - Season (S01)
            {E} - Episode (E01)
        
        Example patterns:
            TV: "{title} - S{season}E{episode} - {episodeTitle}"
            Movie: "{title} ({year})"
        """
        # Start with pattern
        result = pattern
        
        # Replace tokens
        replacements = {
            "{title}": info.get("show_title", info.get("title", "")),
            "{year}": str(info.get("year", info.get("show_year", ""))),
            "{season}": f"{info.get('season', 1):02d}",
            "{episode}": f"{info.get('episode', 1):02d}",
            "{episodeTitle}": info.get("episode_title", ""),
            "{S}": f"S{info.get('season', 1):02d}",
            "{E}": f"E{info.get('episode', 1):02d}",
        }
        
        for token, value in replacements.items():
            result = result.replace(token, value)
        
        # Clean up multiple spaces
        result = re.sub(r'\s+', ' ', result).strip()
        
        # Remove invalid filename characters (cross-platform)
        result = self._sanitize_filename(result)
        
        return result
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for cross-platform compatibility"""
        # Remove or replace invalid characters based on platform
        system = platform.system().lower()
        
        if system == "windows":
            # Windows invalid characters
            invalid_chars = r'[<>:"/\\|?*]'
        else:
            # Unix/Linux/macOS - only forward slash and null character
            invalid_chars = r'[/\x00]'
        
        result = re.sub(invalid_chars, '', filename)
        
        # Additional platform-specific handling
        if system == "windows":
            # Remove trailing dots and spaces (Windows doesn't like them)
            result = result.rstrip('. ')
            # Windows reserved names
            reserved_names = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
            if result.upper() in reserved_names:
                result = result + "_"
        
        return result
    
    def rename_file(
        self,
        file_path: str,
        pattern: str,
        auto_detect: bool = True,
        dry_run: bool = False
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Rename a media file
        
        Args:
            file_path: Path to file
            pattern: Naming pattern
            auto_detect: Automatically detect and search for metadata
            dry_run: Don't actually rename, just show what would happen
            
        Returns:
            (success, message, new_path)
        """
        path = Path(file_path)
        
        if not path.exists():
            return False, f"File not found: {file_path}", None
        
        # Detect media type
        media_type = self.detect_media_type(path.name)
        
        info = None
        
        if auto_detect:
            if media_type == "tv":
                parsed = self.parse_tv_filename(path.name)
                if parsed:
                    info = self.search_tv_show(
                        parsed["title"],
                        parsed["season"],
                        parsed["episode"]
                    )
            elif media_type == "movie":
                parsed = self.parse_movie_filename(path.name)
                if parsed:
                    info = self.search_movie(parsed["title"], parsed.get("year"))
        
        if not info:
            return False, "Could not find metadata for file", None
        
        # Format new filename
        new_name = self.format_filename(info, pattern)
        new_path = path.parent / f"{new_name}{path.suffix}"
        
        if dry_run:
            return True, f"Would rename to: {new_path.name}", str(new_path)
        
        # Perform rename
        try:
            path.rename(new_path)
            return True, f"Renamed successfully to: {new_path.name}", str(new_path)
        except Exception as e:
            return False, f"Rename failed: {str(e)}", None


def main():
    """Test the metadata grabber"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python metadata_grabber.py <filename>")
        return
    
    filename = sys.argv[1]
    grabber = MetadataGrabber()
    
    # Test parsing
    print(f"Testing: {filename}")
    print(f"Media type: {grabber.detect_media_type(filename)}")
    
    tv_info = grabber.parse_tv_filename(filename)
    if tv_info:
        print(f"TV Show parsed: {tv_info}")
        result = grabber.search_tv_show(tv_info['title'], tv_info['season'], tv_info['episode'])
        if result:
            print(f"Search result: {result}")
    
    movie_info = grabber.parse_movie_filename(filename)
    if movie_info:
        print(f"Movie parsed: {movie_info}")
        result = grabber.search_movie(movie_info['title'], movie_info.get('year'))
        if result:
            print(f"Search result: {result}")


if __name__ == "__main__":
    try:
        from utils.logging_config import setup_logging
        setup_logging()
    except ImportError:
        logging.basicConfig(level=logging.INFO)
    main()

