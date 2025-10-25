#!/usr/bin/env python3
"""
Jikan Provider (MyAnimeList Mirror)
No API key required - Good for anime
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Dict, Optional

from .base_provider import BaseMetadataProvider

logger = logging.getLogger(__name__)


class JikanProvider(BaseMetadataProvider):
    """Jikan API (MyAnimeList mirror) provider"""

    API_URL = "https://api.jikan.moe/v4"

    def __init__(self, language_preference: str = "en"):
        super().__init__(language_preference=language_preference)
        logger.info(f"JikanProvider initialized (Language: {self.AVAILABLE_LANGUAGES.get(self.language_preference, self.language_preference)})")

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """Search anime movie using Jikan API"""
        try:
            self._rate_limit(0.5)  # Jikan has stricter rate limits
            
            params = {"q": title, "limit": "1", "type": "movie"}
            url = f"{self.API_URL}/anime?{urllib.parse.urlencode(params)}"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data.get("data") and len(data["data"]) > 0:
                anime = data["data"][0]
                
                # Get available titles
                available_titles = {}
                if anime.get("title_english"):
                    available_titles["en"] = anime["title_english"]
                if anime.get("title"):
                    available_titles["x-jat"] = anime["title"]  # Jikan's title is usually Romaji
                if anime.get("title_japanese"):
                    available_titles["ja"] = anime["title_japanese"]
                
                # Get preferred title
                preferred_title = self.get_preferred_title(available_titles, anime.get("title", ""))
                
                return {
                    "title": preferred_title,
                    "year": str(anime.get("year", "")) if anime.get("year") else "",
                    "overview": anime.get("synopsis", "")[:200] + "..." if anime.get("synopsis") else "",
                    "rating": float(anime.get("score", 0)) if anime.get("score") else 0,
                    "source": "jikan"
                }
        except Exception as e:
            logger.error(f"Jikan movie search error: {e}")
        
        return None

    def search_tv(self, title: str, season: int = 1, episode: int = 1) -> Optional[Dict]:
        """Search anime using Jikan API with per-episode details"""
        try:
            self._rate_limit(0.5)  # Jikan has stricter rate limits
            
            # Step 1: Search for anime to get MAL ID
            params = {"q": title, "limit": "1", "type": "tv"}
            url = f"{self.API_URL}/anime?{urllib.parse.urlencode(params)}"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data.get("data") and len(data["data"]) > 0:
                anime = data["data"][0]
                anime_id = anime.get("mal_id")
                
                # Step 2: Fetch specific episode details
                episode_title = f"Episode {episode}"  # Default
                episode_synopsis = ""
                
                if anime_id:
                    try:
                        self._rate_limit(0.5)  # Additional rate limit for episode call
                        episode_url = f"{self.API_URL}/anime/{anime_id}/episodes/{episode}"
                        
                        with urllib.request.urlopen(episode_url, timeout=10) as ep_response:
                            ep_data = json.loads(ep_response.read().decode())
                        
                        if ep_data.get("data"):
                            episode_info = ep_data["data"]
                            
                            # Get available episode titles
                            available_episode_titles = []
                            if episode_info.get("title"):
                                available_episode_titles.append(episode_info["title"])
                            if episode_info.get("title_romanji"):
                                available_episode_titles.append(episode_info["title_romanji"])
                            
                            # Get preferred episode title
                            episode_title = self.get_preferred_episode_title(available_episode_titles, f"Episode {episode}")
                            episode_synopsis = episode_info.get("synopsis", "")
                            
                            logger.info(f"Jikan: Found episode title '{episode_title}' for {title} E{episode}")
                    except Exception as ep_err:
                        logger.warning(f"Jikan: Could not fetch episode {episode} details: {ep_err}")
                
                # Get available titles for the show
                available_titles = {}
                if anime.get("title_english"):
                    available_titles["en"] = anime["title_english"]
                if anime.get("title"):
                    available_titles["x-jat"] = anime["title"]  # Jikan's title is usually Romaji
                if anime.get("title_japanese"):
                    available_titles["ja"] = anime["title_japanese"]
                
                # Get preferred title
                preferred_title = self.get_preferred_title(available_titles, anime.get("title", ""))
                
                return {
                    "show_title": preferred_title,
                    "show_title_english": anime.get("title_english", ""),
                    "show_title_romaji": anime.get("title", ""),
                    "show_year": str(anime.get("year", "")) if anime.get("year") else "",
                    "season": season,
                    "episode": episode,
                    "episode_title": episode_title,
                    "overview": episode_synopsis or anime.get("synopsis", "")[:300] if anime.get("synopsis") else "",
                    "genres": [genre["name"] for genre in anime.get("genres", [])],
                    "rating": str(anime.get("score", "")) if anime.get("score") else "",
                    "total_episodes": anime.get("episodes"),
                    "status": anime.get("status", "").lower() if anime.get("status") else "",
                    "type": anime.get("type", ""),
                    "studios": [studio["name"] for studio in anime.get("studios", [])],
                    "poster_url": anime.get("images", {}).get("jpg", {}).get("large_image_url", ""),
                    "source": "jikan"
                }
        except Exception as e:
            logger.error(f"Jikan search error: {e}")
        
        return None

