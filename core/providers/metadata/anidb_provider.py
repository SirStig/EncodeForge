#!/usr/bin/env python3
"""
AniDB Provider
No API key required (uses HTTP API) - Best for comprehensive anime metadata
Note: AniDB has strict rate limiting (1 request per 2 seconds)

IMPORTANT: This provider requires client registration with AniDB.
See: https://wiki.anidb.net/HTTP_API_Definition for registration details.
Without registration, all API calls will fail with "client version missing or invalid" error.
"""

import gzip
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

from .base_provider import BaseMetadataProvider

logger = logging.getLogger(__name__)


class AniDBProvider(BaseMetadataProvider):
    """AniDB (anime database) provider using HTTP API"""

    API_URL = "http://api.anidb.net:9001/httpapi"
    TITLES_URL = "http://anidb.net/api/anime-titles.xml.gz"
    # Registered AniDB client credentials
    # See: https://wiki.anidb.net/HTTP_API_Definition
    CLIENT = "encodeforge"  # Registered client name
    CLIENT_VER = 1
    
    # AniDB requires minimum 2 second delay between requests
    last_request_time = 0
    MIN_DELAY = 3.0  # Increased to 3 seconds for safety
    
    # Cache for anime titles database
    _titles_cache: Optional[Dict[int, List[str]]] = None
    _cache_file: Optional[Path] = None

    def __init__(self, language_preference: str = "en"):
        super().__init__(language_preference=language_preference)
        # Set up cache directory
        from path_manager import get_cache_dir
        cache_dir = get_cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        AniDBProvider._cache_file = cache_dir / "anidb-titles.xml"
        logger.info("AniDBProvider initialized (HTTP API with title database)")
        logger.info(f"AniDB client 'encodeforge' v1 is registered and ready to use (Language: {self.AVAILABLE_LANGUAGES.get(self.language_preference, self.language_preference)})")
    
    def is_anime(self, title: str) -> bool:
        """
        Check if title is likely anime
        Note: AniDB is anime-only, so this is a heuristic check
        """
        # AniDB is anime-only database, so return True by default
        # This could be enhanced with more sophisticated detection if needed
        return True
    
    def _check_client_registration(self) -> bool:
        """
        Check if the AniDB client is properly registered
        Returns True if registered, False otherwise
        """
        # Client is now registered with AniDB
        return True

    def _anidb_rate_limit(self):
        """Enforce AniDB's strict rate limit (3 seconds for safety)"""
        current_time = time.time()
        time_since_last = current_time - AniDBProvider.last_request_time
        
        if time_since_last < self.MIN_DELAY:
            sleep_time = self.MIN_DELAY - time_since_last
            logger.debug(f"AniDB rate limit: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        
        AniDBProvider.last_request_time = time.time()
    
    def _download_titles_database(self) -> bool:
        """Download and cache AniDB's anime titles database"""
        try:
            if not AniDBProvider._cache_file:
                return False
            
            # Check if cache exists and is recent (update weekly)
            if AniDBProvider._cache_file.exists():
                cache_age = time.time() - AniDBProvider._cache_file.stat().st_mtime
                if cache_age < 7 * 24 * 3600:  # 7 days
                    logger.debug("Using cached AniDB titles database")
                    return True
            
            logger.info("Downloading AniDB anime titles database...")
            request = urllib.request.Request(self.TITLES_URL)
            request.add_header("User-Agent", "EncodeForge/1.0")
            
            with urllib.request.urlopen(request, timeout=30) as response:
                compressed_data = response.read()
            
            # Decompress gzip data
            xml_data = gzip.decompress(compressed_data)
            
            # Save to cache
            AniDBProvider._cache_file.write_bytes(xml_data)
            logger.info(f"AniDB titles database cached to {AniDBProvider._cache_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download AniDB titles database: {e}")
            return False
    
    def _load_titles_cache(self) -> Dict[int, List[str]]:
        """Load and parse the titles database into memory"""
        if AniDBProvider._titles_cache is not None:
            return AniDBProvider._titles_cache
        
        try:
            if not AniDBProvider._cache_file:
                return {}
            
            if not AniDBProvider._cache_file.exists():
                if not self._download_titles_database():
                    return {}
            
            logger.debug("Loading AniDB titles database...")
            tree = ET.parse(AniDBProvider._cache_file)
            root = tree.getroot()
            
            # Build a dictionary: {aid: [list of titles]}
            titles_db: Dict[int, List[str]] = {}
            for anime in root.findall("anime"):
                aid_str = anime.get("aid")
                if not aid_str:
                    continue
                    
                aid = int(aid_str)
                titles: List[str] = []
                
                for title in anime.findall("title"):
                    title_text = title.text
                    if title_text:
                        titles.append(title_text.lower())
                
                if titles:
                    titles_db[aid] = titles
            
            AniDBProvider._titles_cache = titles_db
            logger.info(f"Loaded {len(titles_db)} anime from AniDB database")
            return titles_db
            
        except Exception as e:
            logger.error(f"Failed to load AniDB titles cache: {e}")
            return {}
    
    def _search_anime_id(self, title: str) -> Optional[int]:
        """Search for anime ID by title using fuzzy matching"""
        titles_db = self._load_titles_cache()
        if not titles_db:
            return None
        
        search_title = title.lower().strip()
        
        # Clean up common patterns
        search_title = re.sub(r'\s*-\s*s\d+e\d+.*', '', search_title, flags=re.IGNORECASE)
        search_title = re.sub(r'\s*season\s+\d+.*', '', search_title, flags=re.IGNORECASE)
        search_title = re.sub(r'\s*\(\d{4}\).*', '', search_title)
        search_title = search_title.strip()
        
        logger.debug(f"Searching AniDB for: '{search_title}'")
        
        # First pass: exact match
        for aid, titles in titles_db.items():
            for anime_title in titles:
                if anime_title == search_title:
                    logger.info(f"AniDB exact match found: AID={aid}")
                    return aid
        
        # Second pass: starts with
        for aid, titles in titles_db.items():
            for anime_title in titles:
                if anime_title.startswith(search_title) or search_title.startswith(anime_title):
                    logger.info(f"AniDB partial match found: AID={aid}")
                    return aid
        
        # Third pass: contains (fuzzy)
        search_words = set(search_title.split())
        best_match = None
        best_score = 0
        
        for aid, titles in titles_db.items():
            for anime_title in titles:
                title_words = set(anime_title.split())
                # Calculate word overlap
                common_words = search_words & title_words
                if len(common_words) > 0:
                    score = len(common_words) / max(len(search_words), len(title_words))
                    if score > best_score and score > 0.5:  # At least 50% overlap
                        best_score = score
                        best_match = aid
        
        if best_match:
            logger.info(f"AniDB fuzzy match found: AID={best_match} (score: {best_score:.2f})")
            return best_match
        
        logger.debug(f"No AniDB match found for '{title}'")
        return None

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[Dict]:
        """Search anime movie using AniDB HTTP API"""
        try:
            # Check if client is registered
            if not self._check_client_registration():
                logger.error("AniDB client not registered. Please register your client at: https://wiki.anidb.net/HTTP_API_Definition")
                return None
            
            # Search for anime ID using title
            aid = self._search_anime_id(title)
            if not aid:
                logger.debug(f"AniDB: No match found for movie '{title}'")
                return None
            
            # Fetch anime details by ID
            return self.get_anime_by_id(aid, episode=1)
            
        except Exception as e:
            logger.error(f"AniDB movie search error: {e}")
        
        return None

    def search_tv(self, title: str, season: int = 1, episode: int = 1) -> Optional[Dict]:
        """
        Search anime using AniDB HTTP API
        Note: AniDB uses absolute episode numbering, not season/episode
        """
        try:
            # Check if client is registered
            if not self._check_client_registration():
                logger.error("AniDB client not registered. Please register your client at: https://wiki.anidb.net/HTTP_API_Definition")
                return None
            
            # Search for anime ID using title
            aid = self._search_anime_id(title)
            if not aid:
                logger.debug(f"AniDB: No match found for '{title}'")
                return None
            
            # AniDB uses absolute episode numbering (no seasons)
            # If season > 1, try to calculate absolute episode number
            absolute_episode = episode
            if season > 1:
                # Estimate: assume 12-13 episodes per season
                absolute_episode = ((season - 1) * 12) + episode
                logger.debug(f"AniDB: Converting S{season:02d}E{episode:02d} to absolute episode {absolute_episode}")
            
            # Fetch anime details by ID
            result = self.get_anime_by_id(aid, episode=absolute_episode)
            
            # Update the result to use the original season/episode numbers
            if result:
                result["season"] = season
                result["episode"] = episode
            
            return result
            
        except Exception as e:
            logger.error(f"AniDB search error: {e}")
        
        return None

    def get_anime_by_id(self, aid: int, episode: int = 1) -> Optional[Dict]:
        """
        Fetch anime details by AniDB ID (AID)
        This is the primary way to use AniDB's HTTP API
        """
        try:
            # Check if client is registered
            if not self._check_client_registration():
                logger.error("AniDB client not registered. Please register your client at: https://wiki.anidb.net/HTTP_API_Definition")
                return None
            
            self._anidb_rate_limit()
            
            params = {
                "request": "anime",
                "client": self.CLIENT,
                "clientver": self.CLIENT_VER,
                "protover": "1",
                "aid": aid
            }
            
            url = f"{self.API_URL}?{urllib.parse.urlencode(params)}"
            
            request = urllib.request.Request(url)
            request.add_header("User-Agent", f"EncodeForge/{self.CLIENT_VER}")
            request.add_header("Accept-Encoding", "gzip")
            
            try:
                with urllib.request.urlopen(request, timeout=15) as response:
                    raw_data = response.read()
            except urllib.error.HTTPError as e:
                logger.error(f"AniDB HTTP error {e.code}: {e.reason}")
                return None
            except urllib.error.URLError as e:
                logger.error(f"AniDB URL error: {e.reason}")
                return None
            
            # Check if response is gzip-compressed (starts with 0x1f 0x8b)
            if raw_data[:2] == b'\x1f\x8b':
                logger.debug("AniDB response is gzip-compressed, decompressing...")
                xml_data = gzip.decompress(raw_data).decode('utf-8')
            else:
                xml_data = raw_data.decode('utf-8')
            
            # Parse XML response
            root = ET.fromstring(xml_data)
            
            if root.tag == "error":
                error_text = root.text or "Unknown error"
                if "banned" in error_text.lower():
                    logger.warning(f"AniDB client temporarily banned. This usually resolves after a few hours. Error: {error_text}")
                    logger.info("AniDB: Falling back to other providers. Try again later or contact AniDB support if the issue persists.")
                else:
                    logger.error(f"AniDB error: {error_text}")
                return None
            
            # Check for specific error conditions in the response
            if root.tag == "anime" and len(root) == 0:
                logger.debug(f"AniDB: No anime data found for AID {aid}")
                return None
            
            # Extract anime info with language preference support
            titles = root.find("titles")
            available_titles = {}
            english_title = ""
            romaji_title = ""
            
            if titles is not None:
                for title_elem in titles.findall("title"):
                    lang = title_elem.get("{http://www.w3.org/XML/1998/namespace}lang", "")
                    title_type = title_elem.get("type", "")
                    title_text = title_elem.text or ""
                    
                    if title_text and title_type in ["main", "official"]:
                        # Prefer main titles, but also include official titles
                        if lang not in available_titles or title_type == "main":
                            available_titles[lang] = title_text
                        
                        if lang == "en":
                            english_title = title_text
                        elif lang == "x-jat":
                            romaji_title = title_text
            
            # Get preferred title based on language preference
            preferred_title = self.get_preferred_title(available_titles, romaji_title or english_title)
            
            # Get episode info
            episodes = root.find("episodes")
            episode_title = f"Episode {episode}"
            episode_synopsis = ""
            
            if episodes is not None:
                for ep in episodes.findall("episode"):
                    ep_no = ep.find("epno")
                    if ep_no is not None and ep_no.text:
                        try:
                            if int(ep_no.text) == episode:
                                # Found matching episode - collect all available titles
                                episode_titles = ep.findall("title")
                                available_episode_titles = []
                                
                                if episode_titles:
                                    for title_elem in episode_titles:
                                        title_text = title_elem.text
                                        if title_text and title_text.strip():
                                            available_episode_titles.append(title_text.strip())
                                
                                # Get preferred episode title based on language preference
                                episode_title = self.get_preferred_episode_title(available_episode_titles, f"Episode {episode}")
                                
                                summary = ep.find("summary")
                                if summary is not None and summary.text:
                                    episode_synopsis = summary.text
                                break
                        except ValueError:
                            continue
            
            # Get year
            start_date = root.find("startdate")
            year = start_date.text[:4] if start_date is not None and start_date.text else ""
            
            # Get description
            description = root.find("description")
            overview = description.text[:300] if description is not None and description.text else ""
            
            # Get ratings
            ratings = root.find("ratings")
            rating = ""
            if ratings is not None:
                permanent = ratings.find("permanent")
                if permanent is not None:
                    rating = permanent.text or ""
            
            # Get episode count
            ep_count = root.find("episodecount")
            total_episodes = int(ep_count.text) if ep_count is not None and ep_count.text else None
            
            return {
                "show_title": preferred_title,
                "show_title_english": english_title,
                "show_title_romaji": romaji_title,
                "show_year": year,
                "season": 1,  # AniDB doesn't use seasons
                "episode": episode,
                "episode_title": episode_title,
                "overview": episode_synopsis or overview,
                "rating": rating,
                "total_episodes": total_episodes,
                "source": "anidb"
            }
            
        except Exception as e:
            logger.error(f"AniDB get_anime_by_id error: {e}")
        
        return None

