#!/usr/bin/env python3
"""
Trakt Provider
Requires API key (free) - Good for movies and TV shows
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple

from .base_provider import BaseMetadataProvider

logger = logging.getLogger(__name__)


class TraktProvider(BaseMetadataProvider):
    """Trakt provider"""

    API_URL = "https://api.trakt.tv"

    def __init__(self, api_key: str = "", language_preference: str = "en"):
        super().__init__(api_key, language_preference=language_preference)
        logger.info(f"TraktProvider initialized (Language: {self.AVAILABLE_LANGUAGES.get(self.language_preference, self.language_preference)})")

    def validate_api_key(self) -> Tuple[bool, str]:
        """Validate Trakt API key"""
        if not self.api_key:
            return False, "No API key provided"
        
        try:
            headers = {
                "Content-Type": "application/json",
                "trakt-api-version": "2",
                "trakt-api-key": self.api_key
            }
            request = urllib.request.Request(f"{self.API_URL}/search/movie?query=test&limit=1", headers=headers)
            with urllib.request.urlopen(request, timeout=5) as response:
                return True, "Valid Trakt API key"
        except Exception as e:
            if "401" in str(e) or "403" in str(e):
                return False, "Invalid API key"
            return False, f"Error: {str(e)}"

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """Search movie using Trakt API"""
        if not self.api_key:
            return None
        
        try:
            self._rate_limit()
            
            params = {"query": title, "type": "movie", "limit": "1"}
            if year:
                params["years"] = str(year)
            
            url = f"{self.API_URL}/search/movie?{urllib.parse.urlencode(params)}"
            headers = {
                "Content-Type": "application/json",
                "trakt-api-version": "2",
                "trakt-api-key": self.api_key
            }
            
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data and len(data) > 0:
                movie = data[0].get("movie", {})
                
                return {
                    "title": movie.get("title", ""),
                    "year": str(movie.get("year", "")),
                    "overview": movie.get("overview", ""),
                    "rating": float(movie.get("rating", 0)),
                    "source": "trakt"
                }
        except Exception as e:
            logger.error(f"Trakt movie search error: {e}")
        
        return None

    def search_tv(self, title: str, season: int = 1, episode: int = 1) -> Optional[Dict]:
        """Search TV show using Trakt API"""
        if not self.api_key:
            return None
        
        try:
            self._rate_limit()
            
            # Search for show
            params = {"query": title, "type": "show", "limit": "1"}
            url = f"{self.API_URL}/search/show?{urllib.parse.urlencode(params)}"
            headers = {
                "Content-Type": "application/json",
                "trakt-api-version": "2",
                "trakt-api-key": self.api_key
            }
            
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data and len(data) > 0:
                show = data[0].get("show", {})
                
                return {
                    "show_title": show.get("title", ""),
                    "show_year": str(show.get("year", "")),
                    "season": season,
                    "episode": episode,
                    "episode_title": f"Episode {episode}",  # Trakt doesn't provide episode details easily
                    "overview": show.get("overview", ""),
                    "source": "trakt"
                }
        except Exception as e:
            logger.error(f"Trakt TV search error: {e}")
        
        return None

