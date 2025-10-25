#!/usr/bin/env python3
"""
Podnapisi Provider
Supports all movies, TV shows, and languages - updated scraping
"""

import gzip
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from io import BytesIO
from typing import Dict, List

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from .base_provider import BaseSubtitleProvider

logger = logging.getLogger(__name__)


class PodnapisiProvider(BaseSubtitleProvider):
    """Podnapisi.NET provider"""
    
    def __init__(self):
        super().__init__()
        self.provider_name = "Podnapisi"
    
    def search(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search Podnapisi.NET - improved scraping"""
        results = []
        
        try:
            metadata = self.extract_media_metadata(video_path)
            search_name = metadata['clean_name']
            season = metadata.get('season')
            episode = metadata.get('episode')
            year = metadata.get('year')
            
            if not search_name:
                return results
            
            # Convert language codes to Podnapisi format (2-letter)
            podnapisi_langs = []
            for lang in languages:
                if len(lang) == 3:
                    podnapisi_langs.append(lang[:2].upper())
                else:
                    podnapisi_langs.append(lang.upper())
            
            search_queries = []
            if season and episode:
                search_queries.append(f"{search_name} S{season:02d}E{episode:02d}")
                search_queries.append(f"{search_name} {season}x{episode:02d}")
                search_queries.append(search_name)
            elif year:
                search_queries.append(f"{search_name} {year}")
                search_queries.append(search_name)
            else:
                search_queries.append(search_name)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://podnapisi.net/',
                'DNT': '1'
            }
            
            found_any = False
            for search_term in search_queries:
                if found_any:
                    break
                    
                try:
                    logger.info(f"Podnapisi trying: '{search_term}'")
                    # Updated URL for current Podnapisi structure
                    url = f"https://podnapisi.net/en/ppodnapisi/search?sK={urllib.parse.quote(search_term)}"
                    
                    req = urllib.request.Request(url, headers=headers)
                    time.sleep(1)  # Respectful delay
                    
                    with urllib.request.urlopen(req, timeout=15) as response:
                        html = response.read().decode('utf-8', errors='ignore')
                    
                    # Parse with BeautifulSoup if available
                    if BS4_AVAILABLE:
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Podnapisi uses table rows for results
                        subtitle_rows = soup.find_all('tr', class_=re.compile(r'subtitle-entry'))
                        
                        if not subtitle_rows:
                            # Try alternative selectors
                            subtitle_rows = soup.find_all('tr', attrs={'data-id': True})
                        
                        if not subtitle_rows:
                            logger.debug(f"Podnapisi: No results for '{search_term}', trying next...")
                            continue
                        
                        found_any = True
                        logger.info(f"✅ Podnapisi found {len(subtitle_rows)} result(s)")
                        
                        for row in subtitle_rows[:20]:
                            try:
                                # Find title/download link
                                title_link = row.find('a', href=re.compile(r'/subtitles/'))
                                if not title_link:
                                    continue
                                
                                title = title_link.get_text(strip=True)
                                subtitle_url = title_link.get('href', '')
                                
                                # Find language
                                lang_img = row.find('img', alt=True)
                                row_lang = 'en'
                                if lang_img:
                                    lang_alt = lang_img.get('alt', '').upper()
                                    if lang_alt[:2] in podnapisi_langs:
                                        row_lang = lang_alt[:2].lower()
                                    else:
                                        continue  # Skip if not requested language
                                
                                # Make absolute URL
                                if not subtitle_url.startswith('http'):
                                    subtitle_url = f"https://podnapisi.net{subtitle_url}"
                                
                                # Extract subtitle ID for download
                                subtitle_id = row.get('data-id') or re.search(r'/(\d+)/', subtitle_url)
                                if isinstance(subtitle_id, re.Match):
                                    subtitle_id = subtitle_id.group(1)
                                
                                results.append({
                                    "provider": "Podnapisi",
                                    "file_name": f"{title}.srt",
                                    "language": row_lang,
                                    "downloads": 0,
                                    "rating": 0.0,
                                    "file_id": f"podnapisi_{subtitle_id}",
                                    "download_url": subtitle_url,
                                    "movie_name": title,
                                    "format": "srt"
                                })
                            except Exception as e:
                                logger.debug(f"Error parsing Podnapisi row: {e}")
                                continue
                    else:
                        # Fallback regex parsing
                        subtitle_pattern = r'<a href="(/[^"]+/download)"[^>]*>.*?<span[^>]*>([^<]+)</span>'
                        matches = re.findall(subtitle_pattern, html, re.DOTALL)
                        
                        if not matches:
                            logger.debug(f"Podnapisi: No results for '{search_term}', trying next...")
                            continue
                        
                        found_any = True
                        logger.info(f"✅ Podnapisi found {len(matches)} result(s)")
                        
                        for download_url, title in matches[:15]:
                            for lang in languages:
                                full_download_url = download_url if download_url.startswith('http') else f"https://podnapisi.net{download_url}"
                                results.append({
                                    "provider": "Podnapisi",
                                    "file_name": f"{title}.srt",
                                    "language": lang[:2] if len(lang) == 3 else lang,
                                    "downloads": 0,
                                    "rating": 0.0,
                                    "file_id": f"podnapisi_{hash(download_url)}",
                                    "download_url": full_download_url,
                                    "movie_name": title,
                                    "format": "srt"
                                })
                    
                    if found_any:
                        break
                        
                except urllib.error.HTTPError as e:
                    if e.code == 415:
                        logger.debug(f"Podnapisi: HTTP 415 for '{search_term}'")
                    elif e.code == 403:
                        logger.warning("Podnapisi blocked request (HTTP 403) - may be rate limiting")
                        time.sleep(2)
                    else:
                        logger.debug(f"Podnapisi HTTP {e.code} for '{search_term}'")
                    continue
                except Exception as e:
                    logger.debug(f"Podnapisi error for '{search_term}': {e}")
                    continue
            
            logger.info(f"Podnapisi found {len(results)} subtitle(s)")
            
        except Exception as e:
            logger.debug(f"Error searching Podnapisi: {e}", exc_info=True)
            
        return results
    
    def download(self, file_id: str, download_url: str, output_path: str) -> tuple:
        """Download from Podnapisi - improved with ZIP handling"""
        try:
            if not download_url:
                return False, "No download URL provided for Podnapisi"
            
            logger.info(f"Podnapisi downloading from: {download_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Referer': 'https://podnapisi.net/',
                'DNT': '1'
            }
            
            # Extract subtitle ID from file_id if available
            subtitle_id = file_id.replace('podnapisi_', '') if 'podnapisi_' in file_id else None
            
            # Try to construct download URL if we have subtitle ID
            if subtitle_id and subtitle_id.isdigit():
                download_url = f"https://podnapisi.net/en/subtitles/{subtitle_id}/download"
            
            req = urllib.request.Request(download_url, headers=headers)
            time.sleep(1)
            
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read()
                
                # Handle gzip compression
                if content[:2] == b'\x1f\x8b':
                    try:
                        content = gzip.decompress(content)
                        logger.debug("Podnapisi: Decompressed gzip content")
                    except Exception as e:
                        logger.debug(f"Podnapisi: Gzip decompression failed: {e}")
                
                # Handle ZIP files
                elif content[:4] == b'PK\x03\x04':
                    try:
                        with zipfile.ZipFile(BytesIO(content)) as zip_ref:
                            for name in zip_ref.namelist():
                                if name.lower().endswith(('.srt', '.ass', '.sub')):
                                    content = zip_ref.read(name)
                                    logger.info(f"Podnapisi: Extracted {name} from ZIP")
                                    break
                    except Exception as e:
                        logger.warning(f"Podnapisi: ZIP extraction failed: {e}")
                
                with open(output_path, 'wb') as f:
                    f.write(content)
                
                logger.info(f"✅ Downloaded from Podnapisi: {output_path}")
                return True, output_path
                
        except urllib.error.HTTPError as e:
            error_msg = f"Podnapisi HTTP error {e.code}: {e.reason}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Podnapisi download failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

