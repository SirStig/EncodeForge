#!/usr/bin/env python3
"""
Base Provider for Metadata
Common interface and utilities for all metadata providers
"""

import logging
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class BaseMetadataProvider(ABC):
    """Abstract base class for all metadata providers."""

    # Language preference constants
    LANGUAGE_PREFERENCE_ENGLISH = "en"
    LANGUAGE_PREFERENCE_ROMANJI = "x-jat"  # AniDB uses this for romanized Japanese
    LANGUAGE_PREFERENCE_JAPANESE = "ja"
    LANGUAGE_PREFERENCE_ORIGINAL = "original"  # Use original language
    
    # Available language preferences
    AVAILABLE_LANGUAGES = {
        LANGUAGE_PREFERENCE_ENGLISH: "English",
        LANGUAGE_PREFERENCE_ROMANJI: "Romanized Japanese (Romaji)",
        LANGUAGE_PREFERENCE_JAPANESE: "Japanese",
        LANGUAGE_PREFERENCE_ORIGINAL: "Original Language"
    }

    def __init__(self, api_key: str = "", language_preference: str = LANGUAGE_PREFERENCE_ENGLISH):
        self.api_key = api_key
        self.language_preference = language_preference
        self.last_request_time = 0

    @abstractmethod
    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """
        Search for movie metadata.
        Each concrete provider must implement this.
        
        Returns dict with: title, year, overview, rating, source
        """
        pass

    @abstractmethod
    def search_tv(self, title: str, season: int = 1, episode: int = 1) -> Optional[Dict]:
        """
        Search for TV show metadata.
        Each concrete provider must implement this.
        
        Returns dict with: show_title, show_year, season, episode, episode_title, overview, source
        """
        pass

    def validate_api_key(self) -> Tuple[bool, str]:
        """
        Validate API key.
        Override in subclasses if API key validation is needed.
        """
        if not self.api_key:
            return False, "No API key provided"
        return True, "API key present (validation not implemented)"

    def _rate_limit(self, min_interval: float = 0.25):
        """Simple rate limiting to avoid hammering APIs"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < min_interval:
            time.sleep(min_interval - time_since_last)
        self.last_request_time = time.time()

    def detect_media_type(self, filename: str) -> str:
        """
        Detect if file is a movie or TV show
        
        Returns: "movie", "tv", or "unknown"
        """
        # TV show patterns
        tv_patterns = [
            r'[Ss](\d{1,2})[Ee](\d{1,3})',  # S01E01
            # 1x01 — bounded and separator-anchored so "1920x1080" is read as a
            # resolution rather than season 1920 episode 1080.
            r'(?:^|[.\s_\-\[])(\d{1,2})x(\d{1,3})(?:$|[.\s_\-\]])',
            r'[Ee]pisode\s*(\d{1,3})',  # Episode 01
            r'\[(\d{1,3})\]',  # [01]
        ]
        
        for pattern in tv_patterns:
            if re.search(pattern, filename):
                return "tv"
        
        # Movie year pattern — match 1900-2099 not followed by resolution suffixes
        if re.search(r'(?<!\d)((?:19|20)\d{2})(?!\d)(?![px])', filename, re.IGNORECASE):
            return "movie"
        
        return "unknown"

    def parse_tv_filename(self, filename: str) -> Optional[Dict]:
        """
        Parse TV show filename to extract information
        
        Returns dict with: title, season, episode, or None
        """
        # Remove extension
        name = Path(filename).stem
        
        # Common TV patterns. The primary S##E## pattern optionally captures a
        # second episode number — "S01E01E02" or "S01E01-E02" — for a double
        # episode released as one file; without it, "E02" was simply left
        # dangling in the filename and silently dropped. The 'E'/'e' is
        # required (not just a bare "-02") so a hyphenated quality tag like
        # "S01E05-1080p" can't be misread as episode 108.
        patterns = [
            r'(?P<title>.+?)[.\s_-]+[Ss](?P<season>\d{1,2})[Ee](?P<episode>\d{1,3})'
            r'(?:[-_]?[Ee](?P<episode2>\d{1,3}))?',
            r'(?P<title>.+?)[.\s_-]+(?P<season>\d{1,2})x(?P<episode>\d{1,3})(?:$|[.\s_\-\]])',
            r'(?P<title>.+?)[.\s_-]+[Ee]pisode\s*(?P<episode>\d{1,3})',
            # Release-group bracket numbering, e.g. "[SubsPlease] Frieren - [12]".
            # detect_media_type() already classified these as TV, but there was
            # no matching parse pattern, so every such file failed to rename.
            r'(?P<title>.+?)[\s_-]*\[(?P<episode>\d{1,3})\]',
        ]

        for pattern in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                result = match.groupdict()

                # Clean title
                title = result['title'].replace('.', ' ').replace('_', ' ').strip()
                title = re.sub(r'\s+', ' ', title)
                # Strip a leading release-group tag: "[SubsPlease] Frieren"
                title = re.sub(r'^\[[^\]]+\]\s*', '', title).strip(' -_')

                # `.get('season', 1)` cannot defend against a pattern that
                # matched but has no season group — it yields None, not the
                # default — so fall back explicitly.
                season = result.get('season')
                episode2 = result.get('episode2')

                parsed = {
                    "type": "tv",
                    "title": title,
                    "season": int(season) if season else 1,
                    "episode": int(result['episode']),
                    "original": filename
                }
                if episode2:
                    parsed["episode2"] = int(episode2)
                return parsed

        return None

    def parse_movie_filename(self, filename: str) -> Optional[Dict]:
        """
        Parse movie filename to extract information
        
        Returns dict with: title, year, or None
        """
        # Remove extension
        name = Path(filename).stem
        
        # Find every plausible release year, then take the LAST one: a title can
        # itself contain a year-like number ("Blade Runner 2049"), and the
        # release year always follows the title.
        #
        # (?![xX]\d) rejects the leading half of a resolution such as 1920x1080,
        # which otherwise parses as the year 1920.
        year_pattern = r'(?<!\d)((?:19|20)\d{2})(?!\d)(?![xX]\d)'
        year_matches = list(re.finditer(year_pattern, name))

        if year_matches:
            last = year_matches[-1]
            title = name[:last.start()].rstrip(' .()_-')
            if title:
                title = title.replace('.', ' ').replace('_', ' ').strip()
                title = re.sub(r'\s+', ' ', title)
                return {
                    "type": "movie",
                    "title": title,
                    "year": int(last.group(1)),
                    "original": filename,
                }

        pattern = r'(?P<title>.+?)[.\s_-]+\(?(?P<year>(?:19|20)\d{2})\)?(?!\d)'
        match = re.search(pattern, name)
        
        if match:
            result = match.groupdict()
            
            # Clean title
            title = result['title'].replace('.', ' ').replace('_', ' ').strip()
            title = re.sub(r'\s+', ' ', title)
            
            return {
                "type": "movie",
                "title": title,
                "year": int(result['year']),
                "original": filename
            }
        
        # Try without year
        title = name.replace('.', ' ').replace('_', ' ').strip()
        title = re.sub(r'\s+', ' ', title)
        
        return {
            "type": "movie",
            "title": title,
            "year": None,
            "original": filename
        }

    def is_anime(self, title: str) -> bool:
        """Check if title is likely anime"""
        anime_keywords = [
            'anime', 'naruto', 'attack on titan', 'bleach', 'one piece', 
            'dragon ball', 'demon slayer', 'jujutsu kaisen', 'my hero academia',
            'one punch man', 'death note', 'fullmetal', 'sword art online',
            'ghibli', 'pokemon', 'evangelion', 'akira', 'spirited away', 
            'your name', 'weathering with you'
        ]
        return any(word in title.lower() for word in anime_keywords)
    
    def set_language_preference(self, language: str):
        """Set the language preference for this provider"""
        if language in self.AVAILABLE_LANGUAGES:
            self.language_preference = language
        else:
            logger.warning(f"Unknown language preference: {language}, using English")
            self.language_preference = self.LANGUAGE_PREFERENCE_ENGLISH
    
    def get_preferred_title(self, titles: Dict[str, str], fallback: str = "") -> str:
        """
        Get the preferred title based on language preference
        
        Args:
            titles: Dictionary mapping language codes to titles
            fallback: Fallback title if no preferred language found
            
        Returns:
            The preferred title or fallback
        """
        if not titles:
            return fallback
        
        # Try to get the preferred language
        if self.language_preference in titles:
            return titles[self.language_preference]
        
        # If original language requested, return the first available title
        if self.language_preference == self.LANGUAGE_PREFERENCE_ORIGINAL:
            return next(iter(titles.values()))
        
        # Fallback to English if available
        if self.LANGUAGE_PREFERENCE_ENGLISH in titles:
            return titles[self.LANGUAGE_PREFERENCE_ENGLISH]
        
        # Fallback to any available title
        return next(iter(titles.values()))
    
    def get_preferred_episode_title(self, episode_titles: List[str], fallback: str = "") -> str:
        """
        Get the preferred episode title based on language preference
        
        Args:
            episode_titles: List of episode titles in different languages
            fallback: Fallback title if no preferred language found
            
        Returns:
            The preferred episode title or fallback
        """
        if not episode_titles:
            return fallback
        
        # For episode titles, we'll use a simple heuristic:
        # English titles typically don't contain non-ASCII characters
        if self.language_preference == self.LANGUAGE_PREFERENCE_ENGLISH:
            for title in episode_titles:
                if title and not any(ord(char) > 127 for char in title):
                    return title.strip()
        
        # Return the first non-empty title
        for title in episode_titles:
            if title and title.strip():
                return title.strip()
        
        return fallback

