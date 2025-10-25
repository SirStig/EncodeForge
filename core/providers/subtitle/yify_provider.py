#!/usr/bin/env python3
"""
YIFY Subtitles Provider
Supports movies only (not TV shows) - updated for yifysubtitles.ch
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


class YifyProvider(BaseSubtitleProvider):
    """YIFY Subtitles provider - movies only"""
    
    def __init__(self):
        super().__init__()
        self.provider_name = "YIFY"
    
    def search(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search YIFY Subtitles (yifysubtitles.ch) - improved scraping"""
        results = []
        
        try:
            metadata = self.extract_media_metadata(video_path)
            
            movie_name = metadata['clean_name']
            year = metadata.get('year')
            
            if not movie_name:
                return results
            
            # YIFY is best for movies
            if metadata['is_tv_show']:
                logger.debug("YIFY: TV show detected (YIFY specializes in movies)")
            
            # Try multiple search formats
            search_queries = []
            if year:
                search_queries.append(f"{movie_name} {year}")
            search_queries.append(movie_name)
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://yifysubtitles.ch/',
                'DNT': '1'
            }
            
            found_any = False
            for search_term in search_queries:
                if found_any:
                    break
                    
                logger.info(f"YIFY trying: '{search_term}'")
                search_query = urllib.parse.quote(search_term)
                url = f"https://yifysubtitles.ch/search?q={search_query}"
                
                try:
                    req = urllib.request.Request(url, headers=headers)
                    time.sleep(1)  # Respectful delay
                    
                    with urllib.request.urlopen(req, timeout=15) as response:
                        html = response.read().decode('utf-8', errors='ignore')
                    
                    # Parse with BeautifulSoup if available
                    if BS4_AVAILABLE:
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Find movie links - YIFY uses /movie-imdb/ URLs
                        movie_links = soup.find_all('a', href=re.compile(r'/movie-imdb/'))
                        
                        if not movie_links:
                            logger.debug(f"YIFY: No results for '{search_term}', trying next...")
                            continue
                        
                        found_any = True
                        logger.info(f"✅ YIFY found {len(movie_links)} movie(s)")
                        
                        for link in movie_links[:5]:  # Limit to top 5
                            movie_url = link.get('href', '')
                            movie_title = link.get_text(strip=True)
                            
                            # Skip if year doesn't match (if we have one)
                            if year and year not in movie_title:
                                continue
                            
                            # Make absolute URL
                            if not movie_url.startswith('http'):
                                movie_url = f"https://yifysubtitles.ch{movie_url}"
                            
                            # Create result for each requested language
                            for lang in languages:
                                lang_code = lang[:2] if len(lang) == 3 else lang
                                
                                results.append({
                                    "provider": "YIFY",
                                    "file_name": f"{movie_title}.{lang_code}.srt",
                                    "language": lang_code,
                                    "downloads": 0,
                                    "rating": 0.0,
                                    "file_id": f"yify_{hash(movie_url)}_{lang_code}",
                                    "download_url": movie_url,
                                    "movie_name": movie_title,
                                    "format": "srt"
                                })
                    else:
                        # Fallback regex parsing
                        movie_pattern = r'href="(/movie-imdb/[^"]+)"[^>]*>([^<]+)</a>'
                        matches = re.findall(movie_pattern, html)
                        
                        if not matches:
                            logger.debug(f"YIFY: No results for '{search_term}', trying next...")
                            continue
                        
                        found_any = True
                        logger.info(f"✅ YIFY found {len(matches)} movie(s)")
                        
                        for movie_url, movie_title in matches[:5]:
                            if year and year not in movie_title:
                                continue
                            
                            for lang in languages:
                                lang_code = lang[:2] if len(lang) == 3 else lang
                                
                                results.append({
                                    "provider": "YIFY",
                                    "file_name": f"{movie_title}.{lang_code}.srt",
                                    "language": lang_code,
                                    "downloads": 0,
                                    "rating": 0.0,
                                    "file_id": f"yify_{movie_url}_{lang_code}",
                                    "download_url": f"https://yifysubtitles.ch{movie_url}",
                                    "movie_name": movie_title,
                                    "format": "srt"
                                })
                    
                    if found_any:
                        break
                        
                except urllib.error.URLError as e:
                    logger.debug(f"YIFY network error for '{search_term}': {e}")
                    continue
                except Exception as e:
                    logger.debug(f"YIFY error for '{search_term}': {e}")
                    continue
            
            logger.info(f"YIFY found {len(results)} subtitle(s)")
            
        except Exception as e:
            logger.error(f"Error searching YIFY Subtitles: {e}", exc_info=True)
            
        return results
    
    def download(self, file_id: str, download_url: str, output_path: str) -> tuple:
        """Download from YIFY - improved implementation"""
        try:
            if not download_url:
                return False, "YIFY: No download URL provided"
            
            logger.info(f"YIFY downloading from: {download_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Referer': 'https://yifysubtitles.ch/',
                'DNT': '1'
            }
            
            # Extract language from file_id
            lang_code = file_id.split('_')[-1] if '_' in file_id else 'en'
            
            # Step 1: Get movie page to find subtitle links
            req = urllib.request.Request(download_url, headers=headers)
            time.sleep(1)
            
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='ignore')
            
            # Step 2: Find subtitle download link for the requested language
            actual_download_url = None
            
            if BS4_AVAILABLE:
                soup = BeautifulSoup(html, 'html.parser')
                
                # Find all subtitle rows
                subtitle_rows = soup.find_all('tr', class_='high-rating') or soup.find_all('tr')
                
                for row in subtitle_rows:
                    # Check if this row has the language we want
                    lang_cell = row.find('span', class_='sub-lang') or row.find('td', class_='flag-cell')
                    if lang_cell:
                        row_lang = lang_cell.get_text(strip=True).lower()
                        
                        # Match language
                        if lang_code.lower() in row_lang or row_lang[:2] == lang_code[:2]:
                            # Find download link in this row
                            download_link = row.find('a', href=re.compile(r'/subtitle/'))
                            if download_link:
                                actual_download_url = download_link.get('href', '')
                                break
            else:
                # Fallback regex - look for subtitle links
                # YIFY structure: /subtitle/movie-name.lang.srt
                pattern = rf'href="(/subtitle/[^"]*{lang_code}[^"]*)"'
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    actual_download_url = matches[0]
            
            if not actual_download_url:
                message = (
                    f"YIFY: Could not find {lang_code} subtitle automatically.\n\n"
                    f"Manual download steps:\n"
                    f"1. Visit: {download_url}\n"
                    f"2. Find the {lang_code.upper()} subtitle\n"
                    f"3. Click download button\n"
                    f"4. Use 'External File' option to load the subtitle\n\n"
                    f"💡 Tip: YIFY has high-quality movie subtitles!"
                )
                logger.warning("⚠️ YIFY requires manual download")
                return False, message
            
            # Make absolute URL
            if not actual_download_url.startswith('http'):
                actual_download_url = f"https://yifysubtitles.ch{actual_download_url}"
            
            logger.info(f"YIFY actual download URL: {actual_download_url}")
            
            # Step 3: Download the file
            req2 = urllib.request.Request(actual_download_url, headers=headers)
            time.sleep(1)
            
            with urllib.request.urlopen(req2, timeout=30) as dl_response:
                content = dl_response.read()
                
                # Handle ZIP files (YIFY often uses ZIP)
                if content[:4] == b'PK\x03\x04':
                    try:
                        with zipfile.ZipFile(BytesIO(content)) as zip_ref:
                            for name in zip_ref.namelist():
                                if name.lower().endswith(('.srt', '.ass', '.sub')):
                                    content = zip_ref.read(name)
                                    logger.info(f"YIFY: Extracted {name} from ZIP")
                                    break
                    except Exception as e:
                        logger.warning(f"YIFY: ZIP extraction failed: {e}")
                
                # Handle gzip
                elif content[:2] == b'\x1f\x8b':
                    try:
                        content = gzip.decompress(content)
                        logger.debug("YIFY: Decompressed gzip content")
                    except Exception as e:
                        logger.debug(f"YIFY: Gzip decompression failed: {e}")
                
                with open(output_path, 'wb') as f:
                    f.write(content)
                
                logger.info(f"✅ Downloaded from YIFY: {output_path}")
                return True, output_path
                
        except urllib.error.HTTPError as e:
            error_msg = f"YIFY HTTP error {e.code}: {e.reason}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"YIFY download error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

