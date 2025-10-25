#!/usr/bin/env python3
"""
TVDB (The Television Database) Provider
Requires API key (free) - Best for TV shows
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple

from .base_provider import BaseMetadataProvider

logger = logging.getLogger(__name__)


class TVDBProvider(BaseMetadataProvider):
    """The Television Database (TVDB) provider"""

    API_URL = "https://api4.thetvdb.com/v4"

    def __init__(self, api_key: str = "", language_preference: str = "en"):
        super().__init__(api_key, language_preference=language_preference)
        self.token = None
        logger.info(f"TVDBProvider initialized (Language: {self.AVAILABLE_LANGUAGES.get(self.language_preference, self.language_preference)})")

    def login(self) -> bool:
        """Login to TVDB and get JWT token"""
        if not self.api_key:
            return False
        
        try:
            login_data = json.dumps({"apikey": self.api_key}).encode('utf-8')
            request = urllib.request.Request(
                f"{self.API_URL}/login",
                data=login_data,
                headers={"Content-Type": "application/json"}
            )
            
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode())
                self.token = data.get("data", {}).get("token")
                return self.token is not None
        except Exception as e:
            logger.error(f"TVDB login error: {e}")
            return False

    def validate_api_key(self) -> Tuple[bool, str]:
        """Validate TVDB API key"""
        if not self.api_key:
            return False, "No API key provided"
        
        if self.login():
            return True, "Valid TVDB API key"
        return False, "Invalid TVDB API key"

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """TVDB doesn't support movies, return None"""
        return None

    def search_tv(self, title: str, season: int = 1, episode: int = 1) -> Optional[Dict]:
        """Search TV show using TVDB"""
        if not self.token and not self.login():
            return None
        
        try:
            # Search for series
            search_url = f"{self.API_URL}/search/series?name={urllib.parse.quote(title)}"
            headers = {"Authorization": f"Bearer {self.token}"}
            
            request = urllib.request.Request(search_url, headers=headers)
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data.get("data"):
                series = data["data"][0]
                series_id = series["id"]
                
                # Get episode info
                episode_url = f"{self.API_URL}/series/{series_id}/episodes/default?season={season}&episodeNumber={episode}"
                request = urllib.request.Request(episode_url, headers=headers)
                
                with urllib.request.urlopen(request, timeout=10) as ep_response:
                    episode_data = json.loads(ep_response.read().decode())
                
                if episode_data.get("data", {}).get("episodes"):
                    ep = episode_data["data"]["episodes"][0]
                    return {
                        "show_title": series.get("name", ""),
                        "show_year": series.get("firstAired", "")[:4] if series.get("firstAired") else "",
                        "season": season,
                        "episode": episode,
                        "episode_title": ep.get("name", ""),
                        "overview": ep.get("overview", ""),
                        "source": "tvdb"
                    }
        except Exception as e:
            logger.error(f"TVDB search error: {e}")
        
        return None

