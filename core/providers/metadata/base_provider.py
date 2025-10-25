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
            r'[Ss](\d+)[Ee](\d+)',  # S01E01
            r'(\d+)x(\d+)',  # 1x01
            r'[Ee]pisode\s*(\d+)',  # Episode 01
            r'\[(\d+)\]',  # [01]
        ]
        
        for pattern in tv_patterns:
            if re.search(pattern, filename):
                return "tv"
        
        # Movie year pattern
        if re.search(r'\(?\d{4}\)?', filename):
            return "movie"
        
        return "unknown"

    def parse_tv_filename(self, filename: str) -> Optional[Dict]:
        """
        Parse TV show filename to extract information
        
        Returns dict with: title, season, episode, or None
        """
        # Remove extension
        name = Path(filename).stem
        
        # Common TV patterns
        patterns = [
            r'(?P<title>.+?)[.\s_-]+[Ss](?P<season>\d+)[Ee](?P<episode>\d+)',
            r'(?P<title>.+?)[.\s_-]+(?P<season>\d+)x(?P<episode>\d+)',
            r'(?P<title>.+?)[.\s_-]+[Ee]pisode\s*(?P<episode>\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                result = match.groupdict()
                
                # Clean title
                title = result['title'].replace('.', ' ').replace('_', ' ').strip()
                title = re.sub(r'\s+', ' ', title)
                
                return {
                    "type": "tv",
                    "title": title,
                    "season": int(result.get('season', 1)),
                    "episode": int(result['episode']),
                    "original": filename
                }
        
        return None

    def parse_movie_filename(self, filename: str) -> Optional[Dict]:
        """
        Parse movie filename to extract information
        
        Returns dict with: title, year, or None
        """
        # Remove extension
        name = Path(filename).stem
        
        # Movie pattern with year
        pattern = r'(?P<title>.+?)[.\s_-]+\(?(?P<year>\d{4})\)?'
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

