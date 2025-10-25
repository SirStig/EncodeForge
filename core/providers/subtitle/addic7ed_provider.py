#!/usr/bin/env python3
"""
Addic7ed Provider
Supports TV shows, movies, and anime
"""

import gzip
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("BeautifulSoup4 not available, Addic7ed provider will use regex fallback")

from .base_provider import BaseSubtitleProvider

logger = logging.getLogger(__name__)


class Addic7edProvider(BaseSubtitleProvider):
    """Addic7ed provider for TV shows and movies"""
    
    def __init__(self):
        super().__init__()
        self.provider_name = "Addic7ed"
    
    def search(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search Addic7ed (addic7ed.com) - improved web scraping"""
        results = []
        
        try:
            metadata = self.extract_media_metadata(video_path)
            search_name = metadata['clean_name']
            season = metadata.get('season')
            episode = metadata.get('episode')
            
            if season and episode:
                logger.info(f"Addic7ed search: '{search_name}' S{season:02d}E{episode:02d}")
            else:
                logger.info(f"Addic7ed search: '{search_name}'")
            
            # Try multiple search strategies
            search_queries = [search_name]
            if search_name.lower().startswith('the '):
                search_queries.append(search_name[4:])
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Referer': 'https://www.addic7ed.com/'
            }
            
            show_found = False
            show_id = None
            found_show_name = None
            
            # Step 1: Search for the show
            for search_query in search_queries:
                if show_found:
                    break
                    
                try:
                    logger.debug(f"Addic7ed trying: '{search_query}'")
                    search_url = f"https://www.addic7ed.com/search.php?search={urllib.parse.quote(search_query)}&Submit=Search"
                    
                    time.sleep(1)  # Respectful delay
                    req = urllib.request.Request(search_url, headers=headers)
                    
                    with urllib.request.urlopen(req, timeout=15) as response:
                        html = response.read()
                        if html[:2] == b'\x1f\x8b':
                            html = gzip.decompress(html)
                        html = html.decode('utf-8', errors='ignore')
                    
                    # Parse with BeautifulSoup if available, otherwise regex
                    if BS4_AVAILABLE:
                        soup = BeautifulSoup(html, 'html.parser')
                        # Look for show links - updated pattern for current site
                        show_links = soup.find_all('a', href=re.compile(r'/show/\d+'))
                        
                        if show_links:
                            for link in show_links:
                                link_text = link.get_text(strip=True)
                                href = link.get('href', '')
                                
                                # Extract show ID
                                show_id_match = re.search(r'/show/(\d+)', href)
                                if show_id_match:
                                    search_lower = search_query.lower()
                                    link_lower = link_text.lower()
                                    
                                    # Exact or close match
                                    if search_lower == link_lower or search_lower in link_lower or link_lower in search_lower:
                                        show_id = show_id_match.group(1)
                                        found_show_name = link_text
                                        show_found = True
                                        logger.info(f"✅ Addic7ed found show: {found_show_name} (ID: {show_id})")
                                        break
                    else:
                        # Fallback regex parsing
                        show_pattern = r'<a href="(/show/(\d+))"[^>]*>([^<]+)</a>'
                        show_matches = re.findall(show_pattern, html, re.IGNORECASE)
                        
                        if show_matches:
                            for show_url, sid, sname in show_matches:
                                search_lower = search_query.lower()
                                sname_lower = sname.lower()
                                
                                if search_lower == sname_lower or search_lower in sname_lower or sname_lower in search_lower:
                                    show_id = sid
                                    found_show_name = sname
                                    show_found = True
                                    logger.info(f"✅ Addic7ed found show: {found_show_name} (ID: {show_id})")
                                    break
                                    
                except urllib.error.HTTPError as e:
                    if e.code == 403:
                        logger.warning("Addic7ed blocked request (403) - rate limiting")
                        time.sleep(2)
                    elif e.code == 503:
                        logger.warning("Addic7ed temporarily unavailable (503)")
                    else:
                        logger.warning(f"Addic7ed HTTP error: {e.code}")
                    continue
                except Exception as e:
                    logger.debug(f"Addic7ed search failed for '{search_query}': {e}")
                    continue
            
            if not show_found:
                logger.info("Addic7ed: No matching show found")
                return results
            
            # Step 2: Get subtitles for specific episode (if TV show)
            if season and episode and show_id:
                try:
                    # Navigate to season/episode page
                    episode_url = f"https://www.addic7ed.com/show/{show_id}"
                    time.sleep(1)
                    req2 = urllib.request.Request(episode_url, headers=headers)
                    
                    with urllib.request.urlopen(req2, timeout=15) as response2:
                        show_html = response2.read()
                        if show_html[:2] == b'\x1f\x8b':
                            show_html = gzip.decompress(show_html)
                        show_html = show_html.decode('utf-8', errors='ignore')
                    
                    # Parse subtitles table
                    if BS4_AVAILABLE:
                        soup = BeautifulSoup(show_html, 'html.parser')
                        
                        # Find subtitle entries - Addic7ed uses table rows with class 'epeven' or 'epodd'
                        subtitle_rows = soup.find_all('tr', class_=re.compile(r'ep(even|odd)'))
                        
                        for row in subtitle_rows[:20]:
                            # Find language cell
                            lang_cell = row.find('td', class_='language')
                            if not lang_cell:
                                continue
                            
                            language_name = lang_cell.get_text(strip=True)
                            lang_code = self.lang_name_to_code(language_name)
                            
                            if lang_code not in languages:
                                continue
                            
                            # Find download link
                            download_link = row.find('a', href=re.compile(r'/(original|updated)/\d+/\d+'))
                            if not download_link:
                                continue
                            
                            download_path = download_link.get('href', '')
                            download_url = f"https://www.addic7ed.com{download_path}"
                            
                            # Extract version/release info
                            version_cell = row.find('td', class_='NewsTitle')
                            version = version_cell.get_text(strip=True) if version_cell else "Unknown"
                            
                            file_name = f"{found_show_name}.S{season:02d}E{episode:02d}.{version}.{lang_code}.srt"
                            movie_name = f"{found_show_name} S{season:02d}E{episode:02d}"
                            file_id = f"addic7ed_{show_id}_S{season:02d}E{episode:02d}_{lang_code}_{hash(download_url)}"
                            
                            results.append({
                                "provider": "Addic7ed",
                                "file_name": file_name,
                                "language": lang_code,
                                "downloads": 0,
                                "rating": 0.0,
                                "file_id": file_id,
                                "download_url": download_url,
                                "movie_name": movie_name,
                                "format": "srt",
                                "release": version
                            })
                    else:
                        # Fallback regex parsing
                        lang_pattern = r'class="language">([^<]+)</td>.*?<a href="(/(?:original|updated)/\d+/\d+)"'
                        lang_matches = re.findall(lang_pattern, show_html, re.DOTALL)
                        
                        for language_name, download_path in lang_matches[:20]:
                            lang_code = self.lang_name_to_code(language_name.strip())
                            
                            if lang_code in languages:
                                download_url = f"https://www.addic7ed.com{download_path}"
                                
                                file_name = f"{found_show_name}.S{season:02d}E{episode:02d}.{lang_code}.srt"
                                movie_name = f"{found_show_name} S{season:02d}E{episode:02d}"
                                file_id = f"addic7ed_{show_id}_S{season:02d}E{episode:02d}_{lang_code}"
                                
                                results.append({
                                    "provider": "Addic7ed",
                                    "file_name": file_name,
                                    "language": lang_code,
                                    "downloads": 0,
                                    "rating": 0.0,
                                    "file_id": file_id,
                                    "download_url": download_url,
                                    "movie_name": movie_name,
                                    "format": "srt"
                                })
                    
                    logger.info(f"Addic7ed found {len(results)} subtitle(s)")
                    
                except Exception as e:
                    logger.error(f"Addic7ed episode parsing failed: {e}", exc_info=True)
            
        except Exception as e:
            logger.error(f"Error searching Addic7ed: {e}", exc_info=True)
            
        return results
    
    def download(self, file_id: str, download_url: str, output_path: str) -> tuple:
        """Download from Addic7ed (web scraping with anti-bot handling)"""
        try:
            logger.info(f"Attempting to download from Addic7ed: {file_id}")
            
            parts = file_id.replace("addic7ed_", "").rsplit("_", 1)
            if len(parts) != 2:
                return False, "Invalid Addic7ed file_id format"
            
            show_episode = parts[0]
            language = parts[1]
            
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
                'Sec-Fetch-Site': 'none',
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache'
            }
            
            search_url = f"https://www.addic7ed.com/search.php?search={urllib.parse.quote(show_episode)}"
            time.sleep(0.5)
            req = urllib.request.Request(search_url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read()
                if html[:2] == b'\x1f\x8b':
                    html = gzip.decompress(html)
                html = html.decode('utf-8', errors='ignore')
            
            download_patterns = [
                r'href="(/original/[^"]+)"',
                r'href="(/updated/[^"]+)"',
                r'href="(\/downloadexport\.php\?[^"]+)"'
            ]
            
            for pattern in download_patterns:
                matches = re.findall(pattern, html)
                if matches:
                    download_path = matches[0]
                    download_link = f"https://www.addic7ed.com{download_path}"
                    
                    time.sleep(0.5)
                    req2 = urllib.request.Request(download_link, headers=headers)
                    with urllib.request.urlopen(req2, timeout=15) as dl_response:
                        content = dl_response.read()
                        if content[:2] == b'\x1f\x8b':
                            content = gzip.decompress(content)
                        
                        with open(output_path, 'wb') as f:
                            f.write(content)
                        
                        logger.info(f"✅ Downloaded from Addic7ed: {output_path}")
                        return True, output_path
            
            # Manual download fallback
            message = (
                f"Addic7ed automatic download failed (anti-bot protection).\n\n"
                f"Manual download steps:\n"
                f"1. Visit: {search_url}\n"
                f"2. Find your episode: {show_episode}\n"
                f"3. Select language: {language}\n"
                f"4. Click download button\n"
                f"5. Use 'External File' option to apply\n\n"
                f"💡 Tip: Addic7ed has excellent TV show subtitles!"
            )
            logger.warning("⚠️ Addic7ed requires manual download")
            return False, message
            
        except Exception as e:
            logger.error(f"Addic7ed download error: {e}", exc_info=True)
            return False, f"Addic7ed error: {str(e)}"

