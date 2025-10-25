#!/usr/bin/env python3
"""
Kitsunekko Provider
Excellent for anime (English and Japanese subtitles)
"""

import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List

from .base_provider import BaseSubtitleProvider

logger = logging.getLogger(__name__)


class KitsunekkoProvider(BaseSubtitleProvider):
    """Kitsunekko provider for anime subtitles"""
    
    def __init__(self):
        super().__init__()
        self.provider_name = "Kitsunekko"
    
    def search(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search Kitsunekko (kitsunekko.net)"""
        results = []
        
        try:
            supported_langs = []
            for lang in languages:
                if lang in ["jpn", "ja", "eng", "en"]:
                    supported_langs.append(lang)
            
            if not supported_langs:
                logger.info("Kitsunekko skipped - English or Japanese not requested")
                return results
            
            file_name = Path(video_path).stem
            
            anime_name = re.sub(r'\[.*?\]', '', file_name)
            anime_name = re.sub(r'\d+p', '', anime_name)
            anime_name = re.sub(r'[._-]+', ' ', anime_name).strip()
            
            episode_match = re.search(r'(?:E|Episode|Ep\.?)\s*(\d+)', anime_name, re.IGNORECASE)
            if not episode_match:
                episode_match = re.search(r'\s(\d+)\s', anime_name)
            
            episode_num = episode_match.group(1) if episode_match else "01"
            
            logger.info(f"Searching Kitsunekko for anime: {anime_name} (Episode {episode_num})")
            
            for lang in supported_langs:
                if lang in ["jpn", "ja"]:
                    lang_code = "jpn"
                    lang_dir = "japanese"
                else:
                    lang_code = "eng"
                    lang_dir = "english"
                
                results.append({
                    "provider": "Kitsunekko",
                    "file_name": f"{anime_name}.E{episode_num}.{lang_code}.ass",
                    "language": lang_code,
                    "downloads": 0,
                    "rating": 0.0,
                    "file_id": f"kitsunekko_{anime_name}_{episode_num}_{lang_code}",
                    "download_url": f"https://kitsunekko.net/dirlist.php?dir=subtitles%2F{lang_dir}%2F",
                    "movie_name": anime_name,
                    "format": "ass"
                })
            
            logger.info(f"Kitsunekko prepared {len(results)} placeholder result(s)")
            
        except Exception as e:
            logger.error(f"Error searching Kitsunekko: {e}")
            
        return results
    
    def download(self, file_id: str, download_url: str, output_path: str) -> tuple:
        """Download from Kitsunekko"""
        try:
            logger.info(f"Attempting to download from Kitsunekko: {file_id}")
            
            parts = file_id.replace("kitsunekko_", "").rsplit("_", 2)
            if len(parts) >= 2:
                anime_name = "_".join(parts[:-2]) if len(parts) > 2 else parts[0]
                lang_code = parts[-1] if len(parts) >= 3 else "jpn"
            else:
                anime_name = file_id.replace("kitsunekko_", "").rsplit("_", 1)[0]
                lang_code = "jpn"
            
            lang_dir = "japanese" if lang_code in ["jpn", "ja"] else "english"
            search_url = f"https://kitsunekko.net/dirlist.php?dir=subtitles%2F{lang_dir}%2F" + urllib.parse.quote(anime_name)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Referer': 'https://kitsunekko.net/'
            }
            
            req = urllib.request.Request(search_url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode('utf-8', errors='ignore')
            
            subtitle_patterns = [
                r'href="([^"]+\.ass)"',
                r'href="([^"]+\.srt)"',
                r'<a href="(/dirlist\.php[^"]+\.(?:ass|srt))"'
            ]
            
            for pattern in subtitle_patterns:
                matches = re.findall(pattern, html)
                if matches:
                    download_link = matches[0]
                    if not download_link.startswith('http'):
                        if download_link.startswith('/'):
                            download_link = f"https://kitsunekko.net{download_link}"
                        else:
                            download_link = f"https://kitsunekko.net/subtitles/japanese/{download_link}"
                    
                    logger.info(f"Found Kitsunekko download link: {download_link}")
                    
                    req2 = urllib.request.Request(download_link, headers=headers)
                    with urllib.request.urlopen(req2, timeout=30) as dl_response:
                        content = dl_response.read()
                        
                        with open(output_path, 'wb') as f:
                            f.write(content)
                        
                        logger.info(f"✅ Downloaded from Kitsunekko: {output_path}")
                        return True, output_path
            
            message = (
                f"Kitsunekko subtitle located but automatic download unavailable.\n"
                f"Please visit: https://kitsunekko.net/dirlist.php?dir=subtitles%2F{lang_dir}%2F\n"
                f"Search for your anime and download manually.\n"
                f"Note: Kitsunekko has both English and Japanese subtitle directories."
            )
            logger.warning("⚠️ Kitsunekko automatic download not available")
            return False, message
            
        except Exception as e:
            logger.error(f"Kitsunekko download error: {e}")
            return False, f"Kitsunekko error: {str(e)}"

