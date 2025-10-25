#!/usr/bin/env python3
"""
TMDB (The Movie Database) Provider
Requires API key (free) - Best for movies and TV shows
"""

import json
import logging
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple

from .base_provider import BaseMetadataProvider

logger = logging.getLogger(__name__)


class TMDBProvider(BaseMetadataProvider):
    """The Movie Database (TMDB) provider"""

    API_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str = "", language_preference: str = "en"):
        super().__init__(api_key, language_preference=language_preference)
        logger.info(f"TMDBProvider initialized (Language: {self.AVAILABLE_LANGUAGES.get(self.language_preference, self.language_preference)})")

    def validate_api_key(self) -> Tuple[bool, str]:
        """Validate TMDB API key"""
        if not self.api_key:
            return False, "No API key provided"
        
        try:
            url = f"{self.API_URL}/configuration?api_key={self.api_key}"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                if data.get("images"):
                    return True, "Valid TMDB API key"
        except Exception as e:
            return False, f"Invalid: {str(e)}"
        
        return False, "Unknown error"

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """Search movie using TMDB"""
        if not self.api_key:
            return None

        try:
            self._rate_limit()
            search_url = f"{self.API_URL}/search/movie"
            params = {
                "api_key": self.api_key,
                "query": title
            }
            
            if year:
                params["year"] = str(year)
            
            url = f"{search_url}?{urllib.parse.urlencode(params)}"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data.get("results"):
                movie = data["results"][0]
                
                # TMDB provides titles in the requested language
                # For language preference consistency, we'll use the title as-is
                movie_title = movie.get("title", "")
                
                return {
                    "title": movie_title,
                    "year": movie.get("release_date", "")[:4] if movie.get("release_date") else "",
                    "overview": movie.get("overview", ""),
                    "rating": movie.get("vote_average", 0),
                    "source": "tmdb"
                }
        except Exception as e:
            logger.error(f"Error searching TMDB movie: {e}")
        
        return None

    def search_tv(self, title: str, season: int = 1, episode: int = 1) -> Optional[Dict]:
        """Search TV show using TMDB"""
        if not self.api_key:
            return None

        try:
            self._rate_limit()
            search_url = f"{self.API_URL}/search/tv"
            params = {
                "api_key": self.api_key,
                "query": title
            }
            
            url = f"{search_url}?{urllib.parse.urlencode(params)}"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
            
            if data.get("results"):
                show = data["results"][0]
                show_id = show["id"]
                
                # Get episode details
                episode_url = f"{self.API_URL}/tv/{show_id}/season/{season}/episode/{episode}"
                episode_params = {"api_key": self.api_key}
                episode_full_url = f"{episode_url}?{urllib.parse.urlencode(episode_params)}"
                
                try:
                    with urllib.request.urlopen(episode_full_url, timeout=10) as ep_response:
                        episode_data = json.loads(ep_response.read().decode())
                    
                    # TMDB provides titles in the requested language
                    show_title = show.get("name", "")
                    episode_title = episode_data.get("name", "")
                    
                    return {
                        "show_title": show_title,
                        "show_year": show.get("first_air_date", "")[:4] if show.get("first_air_date") else "",
                        "season": season,
                        "episode": episode,
                        "episode_title": episode_title,
                        "episode_airdate": episode_data.get("air_date", ""),
                        "episode_runtime": episode_data.get("runtime"),  # in minutes
                        "overview": episode_data.get("overview", ""),
                        "genres": [genre["name"] for genre in show.get("genre_ids", [])] if "genre_ids" in show else [],
                        "rating": str(show.get("vote_average", "")) if show.get("vote_average") else "",
                        "popularity": str(show.get("popularity", "")) if show.get("popularity") else "",
                        "poster_url": f"https://image.tmdb.org/t/p/w500{show['poster_path']}" if show.get("poster_path") else "",
                        "backdrop_url": f"https://image.tmdb.org/t/p/w1280{show['backdrop_path']}" if show.get("backdrop_path") else "",
                        "episode_still_url": f"https://image.tmdb.org/t/p/w500{episode_data['still_path']}" if episode_data.get("still_path") else "",
                        "source": "tmdb"
                    }
                except Exception as e:
                    logger.error(f"Error fetching TMDB episode details: {e}")
                    # Return show info without episode details
                    show_title = show.get("name", "")
                    return {
                        "show_title": show_title,
                        "show_year": show.get("first_air_date", "")[:4] if show.get("first_air_date") else "",
                        "season": season,
                        "episode": episode,
                        "episode_title": "",
                        "overview": "",
                        "rating": str(show.get("vote_average", "")) if show.get("vote_average") else "",
                        "poster_url": f"https://image.tmdb.org/t/p/w500{show['poster_path']}" if show.get("poster_path") else "",
                        "source": "tmdb"
                    }
        except Exception as e:
            logger.error(f"Error searching TMDB TV show: {e}")
        
        return None

