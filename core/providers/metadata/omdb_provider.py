#!/usr/bin/env python3
"""
OMDB Provider
Requires API key (free) - Good for movies and TV shows
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple

from .base_provider import BaseMetadataProvider

logger = logging.getLogger(__name__)


class OMDBProvider(BaseMetadataProvider):
    """OMDB (Open Movie Database) provider"""

    API_URL = "http://www.omdbapi.com/"

    def __init__(self, api_key: str = "", language_preference: str = "en"):
        super().__init__(api_key, language_preference=language_preference)
        logger.info(f"OMDBProvider initialized (Language: {self.AVAILABLE_LANGUAGES.get(self.language_preference, self.language_preference)})")

    def validate_api_key(self) -> Tuple[bool, str]:
        """Validate OMDB API key"""
        if not self.api_key:
            return False, "No API key provided"
        
        try:
            url = f"{self.API_URL}?apikey={self.api_key}&t=test"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                if data.get("Response") != "False" or "movie not found" in data.get("Error", "").lower():
                    return True, "Valid OMDB API key"
                if "invalid api key" in data.get("Error", "").lower():
                    return False, "Invalid API key"
        except Exception as e:
            return False, f"Error: {str(e)}"
        
        return False, "Unknown error"

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """Search movie using OMDB API"""
        if not self.api_key:
            return None
            
        try:
            params = {
                "apikey": self.api_key,
                "t": title,
                "type": "movie"
            }
            
            if year:
                params["y"] = str(year)
            
            url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data.get("Response") == "True":
                return {
                    "title": data.get("Title", ""),
                    "year": data.get("Year", ""),
                    "overview": data.get("Plot", ""),
                    "rating": float(data.get("imdbRating", 0)) if data.get("imdbRating") != "N/A" else 0,
                    "source": "omdb"
                }
        except Exception as e:
            logger.error(f"OMDB search error: {e}")
        
        return None

    def search_tv(self, title: str, season: int = 1, episode: int = 1) -> Optional[Dict]:
        """Search TV show using OMDB API"""
        if not self.api_key:
            return None
            
        try:
            params = {
                "apikey": self.api_key,
                "t": title,
                "type": "series"
            }
            
            url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data.get("Response") == "True":
                return {
                    "show_title": data.get("Title", ""),
                    "show_year": data.get("Year", "")[:4] if data.get("Year") else "",
                    "season": season,
                    "episode": episode,
                    "episode_title": f"Episode {episode}",
                    "overview": data.get("Plot", ""),
                    "source": "omdb"
                }
        except Exception as e:
            logger.error(f"OMDB TV search error: {e}")
        
        return None

