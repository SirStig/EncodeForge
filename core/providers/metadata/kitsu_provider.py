#!/usr/bin/env python3
"""
Kitsu Provider
No API key required - Good for anime
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Dict, Optional

from .base_provider import BaseMetadataProvider

logger = logging.getLogger(__name__)


class KitsuProvider(BaseMetadataProvider):
    """Kitsu (anime database) provider"""

    API_URL = "https://kitsu.io/api/edge"

    def __init__(self, language_preference: str = "en"):
        super().__init__(language_preference=language_preference)
        logger.info(f"KitsuProvider initialized (Language: {self.AVAILABLE_LANGUAGES.get(self.language_preference, self.language_preference)})")

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """Search anime movie using Kitsu API"""
        try:
            self._rate_limit()
            
            params = {"filter[text]": title, "filter[subtype]": "movie", "page[limit]": "1"}
            url = f"{self.API_URL}/anime?{urllib.parse.urlencode(params)}"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data.get("data") and len(data["data"]) > 0:
                anime = data["data"][0]["attributes"]
                
                # Get available titles
                titles = anime.get("titles", {})
                available_titles = {}
                if titles.get("en"):
                    available_titles["en"] = titles["en"]
                if titles.get("en_jp"):
                    available_titles["x-jat"] = titles["en_jp"]
                if titles.get("ja_jp"):
                    available_titles["ja"] = titles["ja_jp"]
                
                # Get preferred title
                preferred_title = self.get_preferred_title(available_titles, anime.get("canonicalTitle", ""))
                
                return {
                    "title": preferred_title,
                    "year": anime.get("startDate", "")[:4] if anime.get("startDate") else "",
                    "overview": anime.get("synopsis", "")[:200] + "..." if anime.get("synopsis") else "",
                    "rating": float(anime.get("averageRating", 0)) / 10.0 if anime.get("averageRating") else 0,
                    "source": "kitsu"
                }
        except Exception as e:
            logger.error(f"Kitsu movie search error: {e}")
        
        return None

    def search_tv(self, title: str, season: int = 1, episode: int = 1) -> Optional[Dict]:
        """Search anime using Kitsu API with per-episode details"""
        try:
            self._rate_limit()
            
            # Step 1: Search for anime to get Kitsu ID
            params = {"filter[text]": title, "page[limit]": "1"}
            url = f"{self.API_URL}/anime?{urllib.parse.urlencode(params)}"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data.get("data") and len(data["data"]) > 0:
                anime_data = data["data"][0]
                anime = anime_data["attributes"]
                anime_id = anime_data["id"]
                
                # Step 2: Fetch episodes for this anime
                episode_title = f"Episode {episode}"  # Default
                episode_synopsis = ""
                
                if anime_id:
                    try:
                        self._rate_limit(0.3)  # Rate limit for episode call
                        # Fetch episodes, filter by episode number
                        episodes_params = {
                            "filter[mediaId]": anime_id,
                            "filter[number]": episode,
                            "page[limit]": "1"
                        }
                        episodes_url = f"{self.API_URL}/episodes?{urllib.parse.urlencode(episodes_params)}"
                        
                        with urllib.request.urlopen(episodes_url, timeout=10) as ep_response:
                            ep_data = json.loads(ep_response.read().decode())
                        
                        if ep_data.get("data") and len(ep_data["data"]) > 0:
                            episode_info = ep_data["data"][0]["attributes"]
                            
                            # Get available episode titles
                            ep_titles = episode_info.get("titles", {})
                            available_episode_titles = []
                            if ep_titles.get("en"):
                                available_episode_titles.append(ep_titles["en"])
                            if ep_titles.get("en_jp"):
                                available_episode_titles.append(ep_titles["en_jp"])
                            if ep_titles.get("ja_jp"):
                                available_episode_titles.append(ep_titles["ja_jp"])
                            
                            # Get preferred episode title
                            episode_title = self.get_preferred_episode_title(available_episode_titles, f"Episode {episode}")
                            episode_synopsis = episode_info.get("synopsis", "")
                            
                            logger.info(f"Kitsu: Found episode title '{episode_title}' for {title} E{episode}")
                    except Exception as ep_err:
                        logger.warning(f"Kitsu: Could not fetch episode {episode} details: {ep_err}")
                
                # Get available titles for the show
                titles = anime.get("titles", {})
                available_titles = {}
                if titles.get("en"):
                    available_titles["en"] = titles["en"]
                if titles.get("en_jp"):
                    available_titles["x-jat"] = titles["en_jp"]
                if titles.get("ja_jp"):
                    available_titles["ja"] = titles["ja_jp"]
                
                # Get preferred title
                preferred_title = self.get_preferred_title(available_titles, anime.get("canonicalTitle", ""))
                
                return {
                    "show_title": preferred_title,
                    "show_title_english": titles.get("en", ""),
                    "show_title_romaji": titles.get("en_jp", ""),
                    "show_year": anime.get("startDate", "")[:4] if anime.get("startDate") else "",
                    "season": season,
                    "episode": episode,
                    "episode_title": episode_title,
                    "overview": episode_synopsis or (anime.get("synopsis", "")[:300] if anime.get("synopsis") else ""),
                    "genres": [],  # Would need additional API call
                    "rating": str(anime.get("averageRating", "")) if anime.get("averageRating") else "",
                    "total_episodes": anime.get("episodeCount"),
                    "episode_runtime": anime.get("episodeLength"),  # in minutes
                    "status": anime.get("status", "").lower() if anime.get("status") else "",
                    "age_rating": anime.get("ageRating", ""),
                    "poster_url": anime.get("posterImage", {}).get("large", "") if anime.get("posterImage") else "",
                    "cover_url": anime.get("coverImage", {}).get("original", "") if anime.get("coverImage") else "",
                    "source": "kitsu"
                }
        except Exception as e:
            logger.error(f"Kitsu search error: {e}")
        
        return None

