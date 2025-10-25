#!/usr/bin/env python3
"""
TVmaze Provider
No API key required - Good for TV shows
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Dict, Optional

from .base_provider import BaseMetadataProvider

logger = logging.getLogger(__name__)


class TVmazeProvider(BaseMetadataProvider):
    """TVmaze provider (no key required)"""

    API_URL = "https://api.tvmaze.com"

    def __init__(self, language_preference: str = "en"):
        super().__init__(language_preference=language_preference)
        logger.info(f"TVmazeProvider initialized (Language: {self.AVAILABLE_LANGUAGES.get(self.language_preference, self.language_preference)})")

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """TVmaze doesn't support movies, return None"""
        return None

    def search_tv(self, title: str, season: int = 1, episode: int = 1) -> Optional[Dict]:
        """Search TV show using TVmaze API (no key required)"""
        try:
            self._rate_limit()
            
            # Search for show
            search_url = f"{self.API_URL}/singlesearch/shows"
            params = {"q": title}
            url = f"{search_url}?{urllib.parse.urlencode(params)}"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                show = json.loads(response.read().decode())
            
            if show and show.get("id"):
                show_id = show["id"]
                
                # Get episode info
                episode_url = f"{self.API_URL}/shows/{show_id}/episodebynumber?season={season}&number={episode}"
                
                try:
                    with urllib.request.urlopen(episode_url, timeout=10) as ep_response:
                        episode_data = json.loads(ep_response.read().decode())
                    
                    # Clean HTML from summary
                    summary = episode_data.get("summary", "")
                    if summary:
                        summary = summary.replace("<p>", "").replace("</p>", "").replace("<br>", " ").replace("<br/>", " ")
                        summary = summary.replace("<i>", "").replace("</i>", "").replace("<b>", "").replace("</b>", "")
                    
                    # TVmaze typically provides titles in original language
                    # For language preference, we'll use the show name as-is
                    show_title = show.get("name", "")
                    
                    return {
                        "show_title": show_title,
                        "show_year": show.get("premiered", "")[:4] if show.get("premiered") else "",
                        "season": season,
                        "episode": episode,
                        "episode_title": episode_data.get("name", ""),
                        "episode_airdate": episode_data.get("airdate", ""),
                        "episode_runtime": episode_data.get("runtime"),  # in minutes
                        "overview": summary,
                        "genres": show.get("genres", []),
                        "network": show.get("network", {}).get("name", "") if show.get("network") else "",
                        "status": show.get("status", "").lower(),
                        "rating": str(show.get("rating", {}).get("average", "")) if show.get("rating") else "",
                        "poster_url": show.get("image", {}).get("original", "") if show.get("image") else "",
                        "episode_image_url": episode_data.get("image", {}).get("original", "") if episode_data.get("image") else "",
                        "source": "tvmaze"
                    }
                except Exception as e:
                    logger.error(f"TVmaze episode error: {e}")
                    # Return show info without episode details
                    show_title = show.get("name", "")
                    return {
                        "show_title": show_title,
                        "show_year": show.get("premiered", "")[:4] if show.get("premiered") else "",
                        "season": season,
                        "episode": episode,
                        "episode_title": "",
                        "overview": "",
                        "genres": show.get("genres", []),
                        "network": show.get("network", {}).get("name", "") if show.get("network") else "",
                        "status": show.get("status", "").lower(),
                        "poster_url": show.get("image", {}).get("original", "") if show.get("image") else "",
                        "source": "tvmaze"
                    }
        except Exception as e:
            logger.error(f"TVmaze search error: {e}")
        
        return None

