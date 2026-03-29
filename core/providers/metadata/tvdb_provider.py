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
        """Search TV show using TVDB v4 API"""
        if not self.token and not self.login():
            return None

        try:
            headers = {"Authorization": f"Bearer {self.token}"}

            # v4 search endpoint
            search_url = f"{self.API_URL}/search?query={urllib.parse.quote(title)}&type=series"
            request = urllib.request.Request(search_url, headers=headers)
            with urllib.request.urlopen(request, timeout=10) as response:
                data = json.loads(response.read().decode())

            results = data.get("data") or []
            if not results:
                return None

            series = results[0]
            # v4 search returns tvdb_id for the numeric ID
            series_id = series.get("tvdb_id") or series.get("id")
            if not series_id:
                return None

            show_title = series.get("name", "")
            show_year = str(series.get("year", ""))

            # Fetch episodes for the requested season
            ep_url = f"{self.API_URL}/series/{series_id}/episodes/official?season={season}&page=0"
            request = urllib.request.Request(ep_url, headers=headers)

            episode_title = ""
            episode_airdate = ""
            overview = ""
            try:
                with urllib.request.urlopen(request, timeout=10) as ep_response:
                    ep_data = json.loads(ep_response.read().decode())

                episodes = (ep_data.get("data") or {}).get("episodes") or []
                ep = next((e for e in episodes if e.get("number") == episode), None)
                if ep:
                    episode_title = ep.get("name", "")
                    episode_airdate = ep.get("aired", "")
                    overview = ep.get("overview", "")
            except Exception as e:
                logger.error(f"TVDB episode detail error: {e}")

            return {
                "show_title": show_title,
                "show_year": show_year,
                "season": season,
                "episode": episode,
                "episode_title": episode_title,
                "episode_airdate": episode_airdate,
                "overview": overview,
                "source": "tvdb",
            }
        except Exception as e:
            logger.error(f"TVDB search error: {e}")

        return None

