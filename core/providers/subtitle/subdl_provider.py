#!/usr/bin/env python3
"""
SubDL Provider
Good for movies and TV shows with free API
Updated to use latest API structure with web scraping fallback
"""

import gzip
import json
import logging
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
    logging.getLogger(__name__).warning("BeautifulSoup not available for SubDL web scraping fallback")

from .base_provider import BaseSubtitleProvider

logger = logging.getLogger(__name__)


class SubDLProvider(BaseSubtitleProvider):
    """SubDL provider with free API"""
    
    def __init__(self):
        super().__init__()
        self.provider_name = "SubDL"
        # SubDL provides free API keys without login (no rate limits on free keys)
        # This key was obtained from their website and works without authentication
        self.api_key = "0kzwwW12CndUyeuPru5DtdRwpIXfH9H9"
    
    def search(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search SubDL (subdl.com) - improved API integration"""
        results = []
        
        try:
            metadata = self.extract_media_metadata(video_path)
            search_term = metadata['clean_name']
            season = metadata.get('season')
            episode = metadata.get('episode')
            year = metadata.get('year')
            
            if not search_term:
                return results
            
            # Convert language codes to 2-letter format for SubDL
            subdl_languages = []
            for lang in languages:
                if len(lang) == 3:
                    if lang.lower() == 'eng':
                        subdl_languages.append('en')
                    elif lang.lower() == 'spa':
                        subdl_languages.append('es')
                    elif lang.lower() == 'fre':
                        subdl_languages.append('fr')
                    elif lang.lower() == 'ger':
                        subdl_languages.append('de')
                    elif lang.lower() == 'por':
                        subdl_languages.append('pt')
                    elif lang.lower() == 'ita':
                        subdl_languages.append('it')
                    else:
                        subdl_languages.append(lang[:2].lower())
                else:
                    subdl_languages.append(lang.lower())
            
            # Build search queries
            searches = []
            
            # Try with season/episode in parameters (best for TV shows)
            if season and episode:
                url = f"https://api.subdl.com/api/v1/subtitles"
                params = {
                    'api_key': self.api_key,
                    'film_name': search_term,
                    'type': 'tv',
                    'season_number': str(season),
                    'episode_number': str(episode),
                    'languages': ','.join(subdl_languages)
                }
                query_string = urllib.parse.urlencode(params)
                searches.append({
                    'url': f"{url}?{query_string}",
                    'desc': f"'{search_term}' S{season:02d}E{episode:02d} (TV type)"
                })
                
                # Also try with episode in the name
                search_with_ep = f"{search_term} S{season:02d}E{episode:02d}"
                params2 = {
                    'api_key': self.api_key,
                    'film_name': search_with_ep,
                    'languages': ','.join(subdl_languages)
                }
                query_string2 = urllib.parse.urlencode(params2)
                searches.append({
                    'url': f"{url}?{query_string2}",
                    'desc': f"'{search_with_ep}' (in name)"
                })
            else:
                # Movie search
                url = f"https://api.subdl.com/api/v1/subtitles"
                params = {
                    'api_key': self.api_key,
                    'film_name': search_term,
                    'type': 'movie',
                    'languages': ','.join(subdl_languages)
                }
                if year:
                    params['year'] = year
                query_string = urllib.parse.urlencode(params)
                searches.append({
                    'url': f"{url}?{query_string}",
                    'desc': f"'{search_term}' (movie)"
                })
                
                # Also try without specifying type
                params_general = {
                    'api_key': self.api_key,
                    'film_name': search_term,
                    'languages': ','.join(subdl_languages)
                }
                query_string_general = urllib.parse.urlencode(params_general)
                searches.append({
                    'url': f"{url}?{query_string_general}",
                    'desc': f"'{search_term}' (general)"
                })
            
            data = None
            successful_search = None
            
            for search in searches:
                try:
                    logger.info(f"SubDL search attempt: {search['desc']}")
                    logger.debug(f"SubDL URL: {search['url']}")
                    
                    headers = {
                        'User-Agent': self.session_headers['User-Agent'],
                        'Accept': 'application/json'
                    }
                    
                    req = urllib.request.Request(search['url'], headers=headers)
                    time.sleep(0.5)  # Respectful delay
                    
                    with urllib.request.urlopen(req, timeout=10) as response:
                        response_text = response.read().decode('utf-8')
                        logger.debug(f"SubDL response (first 500 chars): {response_text[:500]}")
                        data = json.loads(response_text)
                        
                        logger.debug(f"SubDL response keys: {data.keys() if isinstance(data, dict) else 'not a dict'}")
                        
                        if isinstance(data, dict):
                            # Check for success and subtitles
                            if data.get('status') and data.get('subtitles'):
                                if len(data['subtitles']) > 0:
                                    logger.info(f"✅ SubDL found {len(data['subtitles'])} results")
                                    successful_search = search['desc']
                                    break
                            elif 'subtitles' in data and len(data.get('subtitles', [])) > 0:
                                logger.info(f"✅ SubDL found {len(data['subtitles'])} results (no status field)")
                                successful_search = search['desc']
                                break
                            else:
                                logger.info(f"SubDL: No results for this search")
                                data = None
                        else:
                            logger.warning(f"SubDL returned unexpected format: {type(data)}")
                            data = None
                            
                except urllib.error.HTTPError as e:
                    logger.warning(f"SubDL HTTP error {e.code}: {e.reason}")
                    if e.code == 403:
                        logger.info("SubDL API returned 403, will try web scraping fallback")
                    continue
                except Exception as e:
                    logger.warning(f"SubDL search failed: {e}")
                    continue
            
            # If API failed (403 or no results), try web scraping fallback
            if (not data or not data.get('subtitles')) and BS4_AVAILABLE:
                logger.info("SubDL API search failed, trying web scraping fallback...")
                results = self._search_web_fallback(search_term, season, episode, subdl_languages)
                if results:
                    return results
            
            if not data or not data.get('subtitles'):
                logger.info("SubDL: No results found after all search strategies")
                return results
            
            logger.info(f"Processing {len(data['subtitles'])} SubDL results")
            
            # Parse results
            for item in data['subtitles'][:30]:  # Increased limit
                try:
                    lang_code = item.get('lang', '').lower()
                    
                    # Check if this language was requested
                    if lang_code not in subdl_languages:
                        continue
                    
                    # Extract subtitle info
                    file_name = item.get('release_name') or item.get('name', 'Unknown')
                    sd_id = item.get('sd_id') or item.get('id', '')
                    download_url = item.get('url', '')
                    
                    # Get ratings/downloads
                    downloads = int(item.get('download_count', 0) or item.get('downloads', 0))
                    rating = float(item.get('hi_count', 0) or item.get('rating', 0))
                    
                    results.append({
                        "provider": "SubDL",
                        "file_name": file_name,
                        "language": lang_code,
                        "downloads": downloads,
                        "rating": rating,
                        "file_id": str(sd_id),
                        "download_url": download_url,
                        "movie_name": item.get('name', search_term),
                        "format": "srt"
                    })
                except Exception as e:
                    logger.warning(f"Error parsing SubDL item: {e}")
                    continue
            
            logger.info(f"SubDL found {len(results)} matching subtitle(s)")
            
        except Exception as e:
            logger.error(f"Error searching SubDL: {e}", exc_info=True)
            
        return results
    
    def _search_web_fallback(self, search_term: str, season, episode, languages: List[str]) -> List[Dict]:
        """Web scraping fallback when API returns 403"""
        results = []
        
        if not BS4_AVAILABLE:
            return results
        
        try:
            # Build search URL
            query = search_term.replace(' ', '-').lower()
            if season and episode:
                search_url = f"https://subdl.com/subtitle/{query}/english"
            else:
                search_url = f"https://subdl.com/subtitle/{query}/english"
            
            logger.info(f"SubDL web scraping: {search_url}")
            
            headers = {
                'User-Agent': self.session_headers['User-Agent'],
                'Accept': 'text/html,application/xhtml+xml',
                'Accept-Language': 'en-US,en;q=0.9'
            }
            
            req = urllib.request.Request(search_url, headers=headers)
            time.sleep(1.0)  # Be respectful
            
            with urllib.request.urlopen(req, timeout=15) as response:
                html = response.read().decode('utf-8', errors='ignore')
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find subtitle entries
            subtitle_entries = soup.find_all('div', class_='item') or soup.find_all('a', class_='subtitle-entry')
            
            for entry in subtitle_entries[:20]:
                try:
                    # Extract subtitle info from web page
                    name_elem = entry.find('h5') or entry.find('span', class_='title') or entry.find('a')
                    if not name_elem:
                        continue
                    
                    file_name = name_elem.get_text(strip=True)
                    
                    # Get download link
                    link_elem = entry.find('a', href=True)
                    if link_elem:
                        download_url = link_elem['href']
                        if not download_url.startswith('http'):
                            download_url = 'https://subdl.com' + download_url
                    else:
                        download_url = ''
                    
                    # Extract file ID from URL
                    file_id = download_url.split('/')[-1] if download_url else ''
                    
                    # Try to extract language
                    lang_elem = entry.find('span', class_='language') or entry.find('span', class_='lang')
                    lang_code = 'en'  # default
                    if lang_elem:
                        lang_text = lang_elem.get_text(strip=True).lower()
                        if 'spanish' in lang_text or 'español' in lang_text:
                            lang_code = 'es'
                        elif 'french' in lang_text or 'français' in lang_text:
                            lang_code = 'fr'
                        elif 'german' in lang_text or 'deutsch' in lang_text:
                            lang_code = 'de'
                    
                    # Filter by season/episode if TV show
                    if season and episode:
                        se_pattern = f"s{season:02d}e{episode:02d}"
                        if se_pattern not in file_name.lower():
                            continue
                    
                    results.append({
                        "provider": "SubDL",
                        "file_name": file_name,
                        "language": lang_code,
                        "downloads": 0,
                        "rating": 0,
                        "file_id": file_id,
                        "download_url": download_url,
                        "movie_name": search_term,
                        "format": "srt"
                    })
                    
                except Exception as e:
                    logger.debug(f"Error parsing SubDL web entry: {e}")
                    continue
            
            logger.info(f"SubDL web scraping found {len(results)} subtitle(s)")
            
        except Exception as e:
            logger.warning(f"SubDL web scraping failed: {e}")
        
        return results
    
    def download(self, file_id: str, download_url: str, output_path: str) -> tuple:
        """Download from SubDL - improved with ZIP handling"""
        try:
            logger.info(f"SubDL download: file_id={file_id}")
            
            # Try to get download URL from API if not provided
            if not download_url and file_id:
                api_url = f"https://api.subdl.com/api/v1/subtitles/{file_id}"
                headers = {
                    'User-Agent': self.session_headers['User-Agent'],
                    'Accept': 'application/json'
                }
                req = urllib.request.Request(api_url, headers=headers)
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode('utf-8'))
                    
                    if isinstance(data, dict):
                        download_url = data.get('download_url') or data.get('url', '')
            
            if not download_url:
                return False, "SubDL: No download URL available"
            
            logger.info(f"SubDL downloading from: {download_url}")
            
            # Download the file
            headers = {
                'User-Agent': self.session_headers['User-Agent'],
                'Accept': '*/*',
                'Referer': 'https://subdl.com/'
            }
            req2 = urllib.request.Request(download_url, headers=headers)
            time.sleep(0.5)
            
            with urllib.request.urlopen(req2, timeout=30) as dl_response:
                content = dl_response.read()
                
                # Handle different compression formats
                if download_url.endswith('.gz') or content[:2] == b'\x1f\x8b':
                    try:
                        content = gzip.decompress(content)
                        logger.debug("SubDL: Decompressed gzip content")
                    except Exception as e:
                        logger.debug(f"SubDL: Not gzipped or decompression failed: {e}")
                
                # Handle ZIP files (common for SubDL)
                elif download_url.endswith('.zip') or content[:4] == b'PK\x03\x04':
                    try:
                        with zipfile.ZipFile(BytesIO(content)) as zip_ref:
                            # Find first .srt or .ass file
                            for name in zip_ref.namelist():
                                if name.lower().endswith(('.srt', '.ass', '.sub')):
                                    content = zip_ref.read(name)
                                    logger.info(f"SubDL: Extracted {name} from ZIP")
                                    break
                    except Exception as e:
                        logger.warning(f"SubDL: ZIP extraction failed: {e}")
                        # Continue with raw content
                
                # Write to output file
                with open(output_path, 'wb') as f:
                    f.write(content)
                
                logger.info(f"✅ Downloaded from SubDL: {output_path}")
                return True, output_path
                    
        except urllib.error.HTTPError as e:
            error_msg = f"SubDL HTTP error {e.code}: {e.reason}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"SubDL download failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

