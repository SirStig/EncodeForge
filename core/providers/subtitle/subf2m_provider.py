#!/usr/bin/env python3
"""
Subf2m Provider
Good for movies and TV shows - updated web scraping
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


class Subf2mProvider(BaseSubtitleProvider):
    """Subf2m provider for movies and TV shows"""
    
    def __init__(self):
        super().__init__()
        self.provider_name = "Subf2m"
    
    def search(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search Subf2m (subf2m.co) - improved scraping"""
        results = []
        
        try:
            metadata = self.extract_media_metadata(video_path)
            search_name = metadata['clean_name']
            season = metadata.get('season')
            episode = metadata.get('episode')
            year = metadata.get('year')
            
            if not search_name:
                return results
            
            # Build search queries
            search_queries = []
            if season and episode:
                search_queries.append(f"{search_name} S{season:02d}E{episode:02d}".replace(' ', '+'))
                search_queries.append(f"{search_name}".replace(' ', '+'))
            elif year:
                search_queries.append(f"{search_name} {year}".replace(' ', '+'))
                search_queries.append(search_name.replace(' ', '+'))
            else:
                search_queries.append(search_name.replace(' ', '+'))
            
            found_any = False
            
            for search_term in search_queries:
                if found_any:
                    break
                    
                try:
                    logger.info(f"Subf2m trying: '{search_term}'")
                    # Updated URL structure for subf2m.co
                    url = f"https://subf2m.co/subtitles/searchbytitle?query={search_term}&l="
                    
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Referer': 'https://subf2m.co/',
                        'DNT': '1'
                    }
                    
                    req = urllib.request.Request(url, headers=headers)
                    time.sleep(1)  # Respectful delay
                    
                    with urllib.request.urlopen(req, timeout=15) as response:
                        html = response.read().decode('utf-8', errors='ignore')
                    
                    # Parse with BeautifulSoup if available
                    if BS4_AVAILABLE:
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Find subtitle entries - subf2m uses <li> elements with subtitle info
                        subtitle_items = soup.find_all('li')
                        
                        for item in subtitle_items:
                            # Look for subtitle link
                            link = item.find('a', href=re.compile(r'/subtitles/'))
                            if not link:
                                continue
                            
                            title = link.get_text(strip=True)
                            subtitle_url = link.get('href', '')
                            
                            if not subtitle_url:
                                continue
                            
                            # Make absolute URL
                            if not subtitle_url.startswith('http'):
                                subtitle_url = f"https://subf2m.co{subtitle_url}"
                            
                            # Extract language if available
                            lang_span = item.find('span', class_='l')
                            found_lang = 'en'  # default
                            if lang_span:
                                lang_text = lang_span.get_text(strip=True).lower()
                                if 'english' in lang_text:
                                    found_lang = 'en'
                                elif 'spanish' in lang_text or 'español' in lang_text:
                                    found_lang = 'es'
                                elif 'french' in lang_text or 'français' in lang_text:
                                    found_lang = 'fr'
                                elif 'german' in lang_text or 'deutsch' in lang_text:
                                    found_lang = 'de'
                            
                            # Check if this language is requested
                            lang_requested = False
                            for req_lang in languages:
                                if req_lang.lower().startswith(found_lang) or found_lang.startswith(req_lang.lower()[:2]):
                                    lang_requested = True
                                    break
                            
                            if not lang_requested:
                                continue
                            
                            found_any = True
                            
                            results.append({
                                "provider": "Subf2m",
                                "file_name": f"{title}.srt",
                                "language": found_lang,
                                "downloads": 0,
                                "rating": 0.0,
                                "file_id": f"subf2m_{hash(subtitle_url)}",
                                "download_url": subtitle_url,
                                "movie_name": title.strip(),
                                "format": "srt"
                            })
                            
                            if len(results) >= 15:
                                break
                    else:
                        # Fallback regex parsing
                        title_pattern = r'<a[^>]*href="(/subtitles/[^"]+)"[^>]*>([^<]+)</a>'
                        matches = re.findall(title_pattern, html, re.IGNORECASE)
                        
                        if not matches:
                            logger.debug(f"Subf2m: No results for '{search_term}', trying next...")
                            continue
                        
                        found_any = True
                        logger.info(f"✅ Subf2m found {len(matches)} result(s)")
                        
                        for subtitle_path, title in matches[:15]:
                            for lang in languages:
                                results.append({
                                    "provider": "Subf2m",
                                    "file_name": f"{title}.{lang}.srt",
                                    "language": lang,
                                    "downloads": 0,
                                    "rating": 0.0,
                                    "file_id": f"subf2m_{subtitle_path}",
                                    "download_url": f"https://subf2m.co{subtitle_path}",
                                    "movie_name": title.strip(),
                                    "format": "srt"
                                })
                    
                    if found_any:
                        break
                        
                except urllib.error.HTTPError as e:
                    if e.code == 403:
                        logger.warning("Subf2m blocked request (403) - possible rate limiting")
                    else:
                        logger.debug(f"Subf2m HTTP {e.code} for '{search_term}'")
                    continue
                except Exception as e:
                    logger.debug(f"Subf2m error for '{search_term}': {e}")
                    continue
            
            logger.info(f"Subf2m found {len(results)} subtitle(s)")
            
        except Exception as e:
            logger.error(f"Error searching Subf2m: {e}", exc_info=True)
            
        return results
    
    def download(self, file_id: str, download_url: str, output_path: str) -> tuple:
        """Download from Subf2m - improved implementation"""
        try:
            if not download_url:
                return False, "Subf2m: No download URL provided"
            
            logger.info(f"Subf2m downloading from: {download_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': 'https://subf2m.co/',
                'DNT': '1'
            }
            
            # Step 1: Get subtitle page to find download link
            req = urllib.request.Request(download_url, headers=headers)
            time.sleep(1)
            
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='ignore')
            
            # Step 2: Find actual download link on the page
            actual_download_url = None
            
            if BS4_AVAILABLE:
                soup = BeautifulSoup(html, 'html.parser')
                # Look for download button/link
                download_link = soup.find('a', {'id': 'downloadButton'}) or \
                               soup.find('a', href=re.compile(r'/download/')) or \
                               soup.find('a', string=re.compile(r'download', re.I))
                
                if download_link:
                    actual_download_url = download_link.get('href', '')
            else:
                # Fallback regex
                download_patterns = [
                    r'href="(/download/[^"]+)"',
                    r'id="downloadButton"[^>]*href="([^"]+)"',
                    r'<a[^>]*href="([^"]*download[^"]*)"'
                ]
                
                for pattern in download_patterns:
                    matches = re.findall(pattern, html, re.IGNORECASE)
                    if matches:
                        actual_download_url = matches[0]
                        break
            
            if not actual_download_url:
                message = (
                    f"Subf2m: Could not find download link automatically.\n\n"
                    f"Manual download steps:\n"
                    f"1. Visit: {download_url}\n"
                    f"2. Click the download button\n"
                    f"3. Use 'External File' option to load the subtitle\n\n"
                    f"💡 Tip: Subf2m has great subtitles in many languages!"
                )
                logger.warning("⚠️ Subf2m requires manual download")
                return False, message
            
            # Make absolute URL
            if not actual_download_url.startswith('http'):
                actual_download_url = f"https://subf2m.co{actual_download_url}"
            
            logger.info(f"Subf2m actual download URL: {actual_download_url}")
            
            # Step 3: Download the file
            req2 = urllib.request.Request(actual_download_url, headers=headers)
            time.sleep(1)
            
            with urllib.request.urlopen(req2, timeout=30) as dl_response:
                content = dl_response.read()
                
                # Handle ZIP files
                if content[:4] == b'PK\x03\x04':
                    try:
                        with zipfile.ZipFile(BytesIO(content)) as zip_ref:
                            for name in zip_ref.namelist():
                                if name.lower().endswith(('.srt', '.ass', '.sub')):
                                    content = zip_ref.read(name)
                                    logger.info(f"Subf2m: Extracted {name} from ZIP")
                                    break
                    except Exception as e:
                        logger.warning(f"Subf2m: ZIP extraction failed: {e}")
                
                # Handle gzip
                elif content[:2] == b'\x1f\x8b':
                    try:
                        content = gzip.decompress(content)
                        logger.debug("Subf2m: Decompressed gzip content")
                    except Exception as e:
                        logger.debug(f"Subf2m: Gzip decompression failed: {e}")
                
                with open(output_path, 'wb') as f:
                    f.write(content)
                
                logger.info(f"✅ Downloaded from Subf2m: {output_path}")
                return True, output_path
                
        except urllib.error.HTTPError as e:
            error_msg = f"Subf2m HTTP error {e.code}: {e.reason}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Subf2m download error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

