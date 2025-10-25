#!/usr/bin/env python3
"""
Jimaku Provider
Modern anime subtitle search (multiple languages)
"""

import gzip
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List

from .base_provider import BaseSubtitleProvider

logger = logging.getLogger(__name__)


class JimakuProvider(BaseSubtitleProvider):
    """Jimaku provider for anime subtitles"""
    
    def __init__(self):
        super().__init__()
        self.provider_name = "Jimaku"
    
    def search(self, video_path: str, languages: List[str], anilist_url: str = "") -> List[Dict]:
        """Search Jimaku (jimaku.cc)"""
        results = []
        
        try:
            metadata = self.extract_media_metadata(video_path)
            anime_name = metadata['clean_name']
            season = metadata.get('season')
            episode = metadata.get('episode')
            
            if not anime_name:
                return results
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://jimaku.cc/'
            }
            
            search_strategies = []
            
            if anilist_url:
                anilist_match = re.search(r'anilist\.co/anime/(\d+)', anilist_url)
                if anilist_match:
                    anilist_id = anilist_match.group(1)
                    search_strategies.append({
                        'url': f"https://jimaku.cc/search?anilist_id={anilist_id}",
                        'desc': f"AniList ID {anilist_id}"
                    })
                else:
                    search_strategies.append({
                        'url': f"https://jimaku.cc/search?q={urllib.parse.quote(anilist_url)}",
                        'desc': f"AniList URL {anilist_url}"
                    })
            
            if season and episode:
                search_strategies.append({
                    'url': f"https://jimaku.cc/search?q={urllib.parse.quote(f'{anime_name} S{season:02d}E{episode:02d}')}",
                    'desc': f"'{anime_name}' S{season:02d}E{episode:02d}"
                })
            
            search_strategies.append({
                'url': f"https://jimaku.cc/search?q={urllib.parse.quote(anime_name)}",
                'desc': f"'{anime_name}'"
            })
            
            found_any = False
            for strategy in search_strategies:
                if found_any:
                    break
                    
                try:
                    logger.debug(f"Jimaku trying: {strategy['desc']}")
                    time.sleep(0.3)
                    req = urllib.request.Request(strategy['url'], headers=headers)
                    
                    with urllib.request.urlopen(req, timeout=15) as response:
                        html = response.read()
                        if html[:2] == b'\x1f\x8b':
                            html = gzip.decompress(html)
                        html = html.decode('utf-8', errors='ignore')
                    
                    entry_pattern = r'href="(/entries/[^"]+)"[^>]*>([^<]+)</a>'
                    entry_matches = re.findall(entry_pattern, html)
                    
                    if not entry_matches:
                        logger.debug(f"Jimaku: No results for {strategy['desc']}, trying next...")
                        continue
                    
                    found_any = True
                    logger.info(f"✅ Jimaku found {len(entry_matches)} result(s)")
                    
                    for entry_url, entry_name in entry_matches[:5]:
                        full_entry_url = f"https://jimaku.cc{entry_url}"
                        
                        for lang in languages:
                            results.append({
                                "provider": "Jimaku",
                                "file_name": f"{entry_name}.{lang}.srt",
                                "language": lang,
                                "downloads": 0,
                                "rating": 0.0,
                                "file_id": f"jimaku{entry_url}_{lang}",
                                "download_url": full_entry_url,
                                "movie_name": entry_name,
                                "format": "srt"
                            })
                    break
                    
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        logger.debug(f"Jimaku: 404 for {strategy['desc']}, trying next...")
                    elif e.code == 403:
                        logger.warning("Jimaku blocked request (HTTP 403) - may be rate limiting")
                    else:
                        logger.debug(f"Jimaku HTTP error {e.code} for {strategy['desc']}")
                    continue
                except Exception as e:
                    logger.debug(f"Jimaku error for {strategy['desc']}: {e}")
                    continue
            
            logger.info(f"Jimaku found {len(results)} subtitle(s)")
            
        except Exception as e:
            logger.debug(f"Error searching Jimaku: {e}", exc_info=True)
            
        return results
    
    def download(self, file_id: str, download_url: str, output_path: str) -> tuple:
        """Download from Jimaku (jimaku.cc)"""
        try:
            logger.info(f"Attempting to download from Jimaku: {file_id}")
            
            if not download_url:
                return False, "No download URL provided for Jimaku"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'cross-site',
                'Referer': 'https://jimaku.cc/',
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache'
            }
            
            time.sleep(0.3)
            req = urllib.request.Request(download_url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read()
                if html[:2] == b'\x1f\x8b':
                    html = gzip.decompress(html)
                html = html.decode('utf-8', errors='ignore')
            
            download_patterns = [
                r'href="(/api/download/[^"]+)"',
                r'href="(https://jimaku\.cc/api/download/[^"]+)"',
                r'data-download-url="([^"]+)"',
                r'data-download="([^"]+)"',
                r'href="(/entries/[^"]+/download)"',
                r'"download_url":"([^"]+)"',
                r'downloadUrl:\s*["\']([^"\']+)["\']'
            ]
            
            for pattern in download_patterns:
                matches = re.findall(pattern, html)
                if matches:
                    download_link = matches[0]
                    if not download_link.startswith('http'):
                        download_link = f"https://jimaku.cc{download_link}"
                    
                    logger.info(f"Found Jimaku download link: {download_link}")
                    
                    time.sleep(0.3)
                    req2 = urllib.request.Request(download_link, headers=headers)
                    with urllib.request.urlopen(req2, timeout=30) as dl_response:
                        content = dl_response.read()
                        if content[:2] == b'\x1f\x8b':
                            content = gzip.decompress(content)
                        
                        with open(output_path, 'wb') as f:
                            f.write(content)
                        
                        logger.info(f"✅ Downloaded from Jimaku: {output_path}")
                        return True, output_path
            
            message = (
                f"Jimaku automatic download failed.\n\n"
                f"Manual download steps:\n"
                f"1. Visit: {download_url}\n"
                f"2. Find and click the download button\n"
                f"3. Save the subtitle file\n"
                f"4. Use 'External File' option to apply\n\n"
                f"💡 Tip: Jimaku specializes in anime subtitles!"
            )
            logger.warning("⚠️ Jimaku requires manual download")
            return False, message
            
        except Exception as e:
            logger.error(f"Jimaku download error: {e}", exc_info=True)
            return False, f"Jimaku error: {str(e)}"

