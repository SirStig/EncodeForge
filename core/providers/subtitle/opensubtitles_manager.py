#!/usr/bin/env python3
"""
OpenSubtitles Manager - Handles subtitle download from OpenSubtitles.com API
"""

import json
import logging
import struct
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class OpenSubtitlesManager:
    """
    Manages subtitle downloads from OpenSubtitles.com
    Uses the OpenSubtitles REST API v1
    """
    
    API_URL = "https://api.opensubtitles.com/api/v1"
    USER_AGENT = "Encode Forge"  # MUST match registered Consumer name exactly
    
    CONSUMER_API_KEY = "N5GIH7h6rpgt9HpG9wqwtXqCoLM07Ot0"
    
    def __init__(self, api_key: str = "", username: str = "", password: str = ""):
        """
        Initialize OpenSubtitles manager.
        
        OpenSubtitles uses TWO-LEVEL authentication:
        
        1. CONSUMER API KEY (App-level - Developer registers):
           - Identifies Encode Forge as the consumer of the API
           - Limits: 40 requests/10s, 5 downloads/day per IP
        
        2. USER LOGIN (User-level - OPTIONAL):
           - Users can login with their OpenSubtitles username/password
           - Increases to 20 downloads/day per user account
           - No registration needed - uses existing OpenSubtitles account
        
        For open-source apps:
        - You register Consumer API key once (as developer)
        - Users optionally provide their username/password for higher limits
        
        Args:
            api_key: (DEPRECATED - use username/password instead)
            username: User's OpenSubtitles username (optional)
            password: User's OpenSubtitles password (optional)
        """
        self.consumer_api_key = self.CONSUMER_API_KEY or api_key.strip()
        self.username = username.strip() if username else ""
        self.password = password.strip() if password else ""
        self.user_token = None
        
        # Log initialization status
        if not self.consumer_api_key:
            logger.warning("⚠️ OpenSubtitles disabled - no Consumer API key")
            logger.warning("  Developer must register at: https://www.opensubtitles.com/en/consumers")
            logger.warning("  Set CONSUMER_API_KEY in opensubtitles_manager.py")
        else:
            logger.info("OpenSubtitles initialized with Consumer API key")
            if self.username and self.password:
                logger.info("  User login provided - attempting authentication...")
                logger.info("  Will get 20 downloads/day (instead of 5/day)")
            else:
                logger.info("  ✓ Basic access: 40 searches/10s, 5 downloads/day per IP")
                logger.info("  💡 Users can login for 20 downloads/day")
    
    
    def login(self) -> bool:
        """
        Login with user credentials to get JWT token for higher download limits.
        Returns True if successful, False otherwise.
        """
        if not self.username or not self.password:
            return False
        
        if not self.consumer_api_key:
            logger.error("Cannot login: Consumer API key required")
            return False
        
        try:
            url = f"{self.API_URL}/login"
            
            login_data = {
                "username": self.username,
                "password": self.password
            }
            
            headers = {
                "Content-Type": "application/json",
                "User-Agent": self.USER_AGENT,
                "Api-Key": self.consumer_api_key,
                "Accept": "application/json"
            }
            
            request = urllib.request.Request(
                url,
                data=json.dumps(login_data).encode('utf-8'),
                headers=headers,
                method="POST"
            )
            
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode())
            
            self.user_token = data.get("token")
            
            if self.user_token:
                logger.info(f"✅ Logged in as {self.username}")
                logger.info("  Now have 20 downloads/day (user quota)")
                return True
            else:
                logger.error("Login failed: No token received")
                return False
                
        except urllib.error.HTTPError as e:
            logger.error(f"Login failed: HTTP {e.code} {e.reason}")
            try:
                error_body = e.read().decode()
                error_data = json.loads(error_body)
                logger.error(f"Error: {error_data.get('message', error_body)}")
            except:
                pass
            return False
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    def calculate_file_hash(self, file_path: str) -> Optional[str]:
        """
        Calculate OpenSubtitles hash for a video file
        
        The hash is based on file size and first/last 64KB of the file
        """
        try:
            longlongformat = '<q'  # little-endian long long
            bytesize = struct.calcsize(longlongformat)
            
            with open(file_path, "rb") as f:
                filesize = Path(file_path).stat().st_size
                hash_value = filesize
                
                if filesize < 65536 * 2:
                    return None
                
                # Read first 64KB
                for _ in range(65536 // bytesize):
                    buffer = f.read(bytesize)
                    (l_value,) = struct.unpack(longlongformat, buffer)
                    hash_value += l_value
                    hash_value &= 0xFFFFFFFFFFFFFFFF  # 64-bit
                
                # Read last 64KB
                f.seek(max(0, filesize - 65536), 0)
                for _ in range(65536 // bytesize):
                    buffer = f.read(bytesize)
                    (l_value,) = struct.unpack(longlongformat, buffer)
                    hash_value += l_value
                    hash_value &= 0xFFFFFFFFFFFFFFFF
            
            return "%016x" % hash_value
        
        except Exception as e:
            logger.error(f"Error calculating hash: {e}")
            return None
    
    def search_subtitles(
        self,
        file_path: str,
        languages: Optional[List[str]] = None,
        limit: int = 5
    ) -> Tuple[bool, List[Dict]]:
        """
        Search for subtitles for a video file
        
        According to OpenSubtitles API docs:
        - API key is OPTIONAL for searching (search is free and unlimited)
        - API key is REQUIRED for downloading
        
        Args:
            file_path: Path to video file
            languages: List of language codes (e.g., ['en', 'es', 'eng', 'spa'])
            limit: Maximum number of results
            
        Returns:
            (success, list of subtitle dicts)
        """
        if languages is None:
            languages = ['en']
        
        # Consumer API key is REQUIRED
        if not self.consumer_api_key:
            logger.info("⚠️ OpenSubtitles skipped - no Consumer API key")
            logger.info("   Developer must register at: https://www.opensubtitles.com/en/consumers")
            return False, []
        
        # Try to login if user credentials provided (for higher limits)
        if self.username and self.password and not self.user_token:
            logger.info("Attempting user login for higher download limits...")
            self.login()
        
        try:
            # Calculate file hash
            file_hash = self.calculate_file_hash(file_path)
            
            if not file_hash:
                logger.error("Failed to calculate file hash - file may be too small or corrupted")
                return False, []
            
            file_size = Path(file_path).stat().st_size
            logger.info(f"Searching OpenSubtitles - File hash: {file_hash}, size: {file_size} bytes")
            
            # Convert language codes to OpenSubtitles format (2-letter ISO 639-1)
            # OpenSubtitles supports 60+ languages and uses 2-letter codes like 'en', 'es'
            # not 3-letter codes like 'eng', 'spa'
            converted_langs = []
            lang_conversion = {
                # Common languages (extensive mapping for 60+ languages)
                'eng': 'en', 'spa': 'es', 'fre': 'fr', 'fra': 'fr', 'ger': 'de', 'deu': 'de',
                'ita': 'it', 'por': 'pt', 'pob': 'pt', 'rus': 'ru', 'ara': 'ar',
                'chi': 'zh', 'zho': 'zh', 'jpn': 'ja', 'kor': 'ko', 'hin': 'hi',
                # Additional languages
                'dut': 'nl', 'nld': 'nl', 'pol': 'pl', 'tur': 'tr', 'swe': 'sv',
                'nor': 'no', 'dan': 'da', 'fin': 'fi', 'cze': 'cs', 'ces': 'cs',
                'gre': 'el', 'ell': 'el', 'heb': 'he', 'hun': 'hu', 'rum': 'ro',
                'ron': 'ro', 'tha': 'th', 'vie': 'vi', 'ind': 'id', 'may': 'ms',
                'per': 'fa', 'fas': 'fa', 'ukr': 'uk', 'bul': 'bg', 'hrv': 'hr',
                'srp': 'sr', 'slv': 'sl', 'lit': 'lt', 'lav': 'lv', 'est': 'et',
                'ice': 'is', 'isl': 'is', 'alb': 'sq', 'sqi': 'sq', 'mac': 'mk'
            }
            
            for lang in languages:
                if len(lang) == 3:
                    # Convert 3-letter to 2-letter
                    converted = lang_conversion.get(lang.lower(), lang[:2])
                    converted_langs.append(converted)
                else:
                    # Already 2-letter
                    converted_langs.append(lang.lower())
            
            # Remove duplicates
            converted_langs = list(dict.fromkeys(converted_langs))
            
            logger.info(f"Searching for languages: {', '.join(converted_langs)}")
            
            # Extract metadata from filename for query-based search
            from subtitle_manager import SubtitleProviders
            metadata_extractor = SubtitleProviders()
            metadata = metadata_extractor.extract_media_metadata(file_path)
            
            # Prepare search parameters - Try hash first, then query-based as fallback
            params = {
                "languages": ",".join(converted_langs)
            }
            
            # Add hash for exact matching
            if file_hash:
                params["moviehash"] = file_hash
            
            # Add query-based search (fallback if hash doesn't match)
            if metadata['clean_name']:
                params["query"] = metadata['clean_name']
                
                # For TV shows, add season/episode and REQUIRED type parameter
                if metadata['is_tv_show'] and metadata['season'] and metadata['episode']:
                    params["type"] = "episode"  # REQUIRED by OpenSubtitles API for TV shows
                    params["season_number"] = str(metadata['season'])
                    params["episode_number"] = str(metadata['episode'])
                    logger.info(f"Searching for: '{metadata['clean_name']}' S{metadata['season']:02d}E{metadata['episode']:02d} (type=episode)")
                elif metadata['is_movie']:
                    params["type"] = "movie"  # Specify movie type
                    logger.info(f"Searching for: '{metadata['clean_name']}' (type=movie)")
                else:
                    logger.info(f"Searching for: '{metadata['clean_name']}'")
                
                # Add year if available (helps with disambiguation)
                if metadata.get('year'):
                    params["year"] = str(metadata['year'])
            
            # Build URL
            url = f"{self.API_URL}/subtitles?{urllib.parse.urlencode(params)}"
            logger.debug(f"OpenSubtitles search URL: {url}")
            
            # Prepare headers - NO Content-Type for GET requests
            headers = {
                "User-Agent": self.USER_AGENT,
                "Accept": "application/json",
                "Api-Key": self.consumer_api_key  # Consumer API key (identifies app)
            }
            
            # Add user token if logged in (for user-specific quotas)
            if self.user_token:
                headers["Authorization"] = f"Bearer {self.user_token}"
                logger.debug("Using user authentication for higher limits")
            
            logger.info("Sending request to OpenSubtitles API...")
            
            # Make request (GET method, no body)
            request = urllib.request.Request(url, headers=headers, method='GET')
            
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode())
            
            logger.info(f"OpenSubtitles.com API response received: {len(str(data))} chars")
            
            # Parse results
            results = []
            
            if "data" in data:
                for item in data["data"][:limit]:
                    attributes = item.get("attributes", {})
                    files = attributes.get("files", [])
                    
                    if files:
                        file_info = files[0]
                        results.append({
                            "id": item.get("id"),
                            "language": attributes.get("language"),
                            "file_name": file_info.get("file_name"),
                            "file_id": file_info.get("file_id"),
                            "download_url": attributes.get("url"),
                            "downloads": attributes.get("download_count", 0),
                            "rating": attributes.get("ratings", 0),
                            "uploader": attributes.get("uploader", {}).get("name", "Unknown"),
                            "format": "srt"
                        })
            
            logger.info(f"✅ OpenSubtitles found {len(results)} subtitle(s) for {Path(file_path).name}")
            return True, results
        
        except urllib.error.HTTPError as e:
            logger.error(f"❌ OpenSubtitles HTTP Error: {e.code} {e.reason}")
            
            error_details = ""
            try:
                error_body = e.read().decode()
                error_data = json.loads(error_body)
                error_details = error_data.get("message", error_body)
                logger.error(f"Error details: {error_details}")
            except Exception:
                try:
                    error_body = e.read().decode() if hasattr(e, 'read') else str(e)
                    error_details = error_body[:200]
                    logger.error(f"Error body: {error_details}")
                except Exception:
                    pass
            
            # Provide specific error messages based on error code
            if e.code == 401 or e.code == 403:
                logger.error("=" * 80)
                logger.error("❌ OPENSUBTITLES AUTHENTICATION FAILED")
                logger.error("=" * 80)
                
                if "You cannot consume this service" in error_details:
                    logger.error("Consumer API key is INVALID, NOT APPROVED, or EXPIRED!")
                    logger.error("")
                    logger.error("📝 DEVELOPER ACTION REQUIRED:")
                    logger.error("   The Consumer API key needs to be registered/approved:")
                    logger.error("   1. Go to: https://www.opensubtitles.com/en/consumers")
                    logger.error("   2. Register 'EncodeForge v0.1' as Consumer App")
                    logger.error("   3. Wait for approval email (~24 hours)")
                    logger.error("   4. Copy Consumer API key and set in code")
                    logger.error("")
                    logger.error("⚠️ COMMON ISSUES:")
                    logger.error("   - Consumer app not registered yet")
                    logger.error("   - Consumer app waiting for approval")
                    logger.error("   - Consumer API key expired/revoked")
                    logger.error("   - User-Agent doesn't match registered app name")
                elif e.code == 401:
                    logger.error("API key is invalid or expired")
                    logger.error("Get a new key: https://www.opensubtitles.com/en/consumers")
                else:
                    logger.error(f"HTTP {e.code}: {e.reason}")
                    logger.error("Check your API key status at opensubtitles.com")
                
                logger.error("=" * 80)
            elif e.code == 429:
                logger.error("Rate limit exceeded - too many requests")
                logger.error("Note: Search should not be rate limited. This may be temporary.")
            elif e.code == 406:
                logger.error("Invalid request - check User-Agent format")
            else:
                logger.error(f"Unexpected error code {e.code}")
            
            return False, []
            
        except Exception as e:
            logger.error(f"❌ Unexpected error searching OpenSubtitles: {e}", exc_info=True)
            return False, []
    
    def download_subtitle(
        self,
        file_id: int,
        output_path: str
    ) -> Tuple[bool, str]:
        """
        Download a subtitle file
        
        According to OpenSubtitles API docs:
        - Downloading REQUIRES authentication (login) OR valid API key with download permissions
        - Downloads are rate limited (5 per day for anonymous, more for authenticated users)
        
        Args:
            file_id: OpenSubtitles file ID
            output_path: Where to save the subtitle
            
        Returns:
            (success, message)
        """
        # Check Consumer API key (REQUIRED)
        if not self.consumer_api_key:
            return False, "OpenSubtitles Consumer API key required. Developer must register app."
        
        try:
            # Note: API key provides 5 downloads per day
            # For higher limits (200/day), upgrade to VIP account on OpenSubtitles.com
            logger.info("Downloading subtitle with API key (5 downloads/day limit)")
            
            # Get download link
            url = f"{self.API_URL}/download"
            
            download_data = {
                "file_id": file_id
            }
            
            # Try to login if not already logged in
            if self.username and self.password and not self.user_token:
                self.login()
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": self.USER_AGENT,
                "Api-Key": self.consumer_api_key,  # Consumer API key (app-level)
                "Accept": "application/json"
            }
            
            # Add user token if available (for user quota instead of IP quota)
            if self.user_token:
                headers["Authorization"] = f"Bearer {self.user_token}"
            
            request = urllib.request.Request(
                url,
                data=json.dumps(download_data).encode('utf-8'),
                headers=headers,
                method="POST"
            )
            
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.loads(response.read().decode())
            
            download_url = data.get("link")
            
            if not download_url:
                return False, "No download link received"
            
            # Download the file
            logger.info(f"Downloading from: {download_url}")
            urllib.request.urlretrieve(download_url, output_path)
            
            logger.info(f"✅ Downloaded subtitle to {output_path}")
            return True, output_path
        
        except urllib.error.HTTPError as e:
            logger.error(f"❌ OpenSubtitles download HTTP Error: {e.code} {e.reason}")
            
            error_msg = f"Download failed: HTTP {e.code}"
            try:
                error_body = e.read().decode()
                error_data = json.loads(error_body)
                error_msg = error_data.get("message", error_body)
                logger.error(f"Error details: {error_msg}")
            except Exception:
                pass
            
            # Provide specific error messages
            if e.code == 401:
                error_msg = "Authentication required - please login or check API key"
            elif e.code == 403:
                error_msg = "Access forbidden - API key may not have download permissions or rate limit exceeded"
            elif e.code == 429:
                error_msg = "Rate limit exceeded - maximum downloads per day reached. Login for more downloads or wait 24h."
            elif e.code == 406:
                error_msg = "Invalid request format"
            
            return False, error_msg
            
        except Exception as e:
            logger.error(f"❌ Unexpected error downloading subtitle: {e}", exc_info=True)
            return False, f"Download error: {str(e)}"
    
    def download_subtitles_for_file(
        self,
        video_path: str,
        languages: Optional[List[str]] = None,
        auto_select: bool = True
    ) -> Tuple[bool, List[str]]:
        """
        Search and download subtitles for a video file
        
        Args:
            video_path: Path to video file
            languages: List of language codes
            auto_select: Automatically select best subtitle
            
        Returns:
            (success, list of downloaded subtitle paths)
        """
        if languages is None:
            languages = ['en']
        
        # Search for subtitles
        success, results = self.search_subtitles(video_path, languages)
        
        if not success or not results:
            return False, []
        
        downloaded_files = []
        
        # Download subtitles for each language
        for language in languages:
            # Find best subtitle for this language
            lang_results = [r for r in results if r["language"] == language]
            
            if not lang_results:
                continue
            
            # Sort by rating and downloads
            lang_results.sort(
                key=lambda x: (x["rating"], x["downloads"]),
                reverse=True
            )
            
            best_subtitle = lang_results[0]
            
            # Determine output path
            video_file = Path(video_path)
            output_path = video_file.parent / f"{video_file.stem}.{language}.srt"
            
            # Download
            success, message = self.download_subtitle(
                best_subtitle["file_id"],
                str(output_path)
            )
            
            if success:
                downloaded_files.append(str(output_path))
        
        if downloaded_files:
            return True, downloaded_files
        else:
            return False, []


def main():
    """Test the OpenSubtitles manager"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python opensubtitles_manager.py <video_file>")
        print("\nRequired environment variable:")
        print("  OPENSUBTITLES_API_KEY - Get your free API key from https://www.opensubtitles.com/en/consumers")
        return
    
    import os
    
    video_file = sys.argv[1]
    
    api_key = os.getenv("OPENSUBTITLES_API_KEY", "")
    
    if not api_key:
        print("❌ Error: OPENSUBTITLES_API_KEY environment variable is required")
        print("Get your free API key from: https://www.opensubtitles.com/en/consumers")
        return
    
    manager = OpenSubtitlesManager(api_key)
    
    # Search for subtitles
    print(f"\nSearching subtitles for: {Path(video_file).name}")
    print("Searching in multiple languages (en, es, fr, de, etc.)...")
    success, results = manager.search_subtitles(video_file, ["en", "es", "fr", "de"])
    
    if success and results:
        print(f"\n✅ Found {len(results)} subtitle(s):")
        
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['file_name']}")
            print(f"   Language: {result['language']}")
            print(f"   Downloads: {result['downloads']}")
            print(f"   Rating: {result['rating']}")
            print(f"   Uploader: {result['uploader']}")
    else:
        print("❌ No subtitles found")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

