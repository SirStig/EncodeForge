#!/usr/bin/env python3
"""
SubDivX Provider
Spanish subtitles - largest Spanish subtitle database (improved)
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


class SubDivXProvider(BaseSubtitleProvider):
    """SubDivX provider for Spanish subtitles"""
    
    def __init__(self):
        super().__init__()
        self.provider_name = "SubDivX"
    
    def search(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search SubDivX (Spanish subtitles)"""
        results = []
        
        try:
            if "spa" not in languages and "es" not in languages:
                logger.info("SubDivX skipped - no Spanish language requested")
                return results
            
            metadata = self.extract_media_metadata(video_path)
            search_name = metadata['clean_name']
            season = metadata.get('season')
            episode = metadata.get('episode')
            year = metadata.get('year')
            
            if not search_name:
                return results
            
            search_queries = []
            if season and episode:
                search_queries.append(f"{search_name} S{season:02d}E{episode:02d}")
                search_queries.append(f"{search_name} {season}x{episode:02d}")
                search_queries.append(f"{search_name} Temporada {season}")
                search_queries.append(search_name)
            elif year:
                search_queries.append(f"{search_name} {year}")
                search_queries.append(search_name)
            else:
                search_queries.append(search_name)
            
            found_any = False
            for search_term in search_queries:
                if found_any:
                    break
                    
                try:
                    logger.debug(f"SubDivX trying: '{search_term}'")
                    url = f"https://www.subdivx.com/index.php?buscar={urllib.parse.quote(search_term)}&accion=5&masdesc=&subtitulos=1&realiza_b=1"
                    
                    req = urllib.request.Request(url, headers=self.session_headers)
                    
                    with urllib.request.urlopen(req, timeout=10) as response:
                        html = response.read().decode('latin-1', errors='ignore')
                    
                    title_pattern = r'<a class="titulo_menu_izq"[^>]*>([^<]+)</a>'
                    download_pattern = r'<a[^>]*href="(/bajar\.php\?id=\d+&u=\d+)"'
                    
                    titles = re.findall(title_pattern, html)
                    downloads = re.findall(download_pattern, html)
                    
                    if not titles or not downloads:
                        logger.debug(f"SubDivX: No results for '{search_term}', trying next...")
                        continue
                    
                    found_any = True
                    logger.info(f"✅ SubDivX found {len(titles)} result(s)")
                    
                    for i, (title, download_url) in enumerate(zip(titles[:10], downloads[:10])):
                        results.append({
                            "provider": "SubDivX",
                            "file_name": f"{title}.srt",
                            "language": "spa",
                            "downloads": 0,
                            "rating": 0.0,
                            "file_id": f"subdivx_{i}_{download_url}",
                            "download_url": f"https://www.subdivx.com{download_url}",
                            "movie_name": title.strip(),
                            "format": "srt"
                        })
                    break
                    
                except urllib.error.URLError as e:
                    logger.debug(f"SubDivX network error for '{search_term}': {e}")
                    continue
                except Exception as e:
                    logger.debug(f"SubDivX error for '{search_term}': {e}")
                    continue
            
            logger.info(f"SubDivX found {len(results)} subtitle(s)")
            
        except Exception as e:
            logger.error(f"Error searching SubDivX: {e}", exc_info=True)
            
        return results
    
    def download(self, file_id: str, download_url: str, output_path: str) -> tuple:
        """Download from SubDivX - improved with better encoding and archive handling"""
        try:
            if not download_url:
                return False, "SubDivX: No download URL provided"
            
            logger.info(f"SubDivX downloading from: {download_url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
                'Referer': 'https://www.subdivx.com/',
                'DNT': '1'
            }
            
            req = urllib.request.Request(download_url, headers=headers)
            time.sleep(1)  # Respectful delay
            
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read()
                
                # Handle ZIP files (most common for SubDivX)
                if content[:4] == b'PK\x03\x04':
                    try:
                        with zipfile.ZipFile(BytesIO(content)) as zip_ref:
                            for name in zip_ref.namelist():
                                if name.lower().endswith(('.srt', '.ass', '.sub')):
                                    content = zip_ref.read(name)
                                    logger.info(f"SubDivX: Extracted {name} from ZIP")
                                    break
                    except Exception as e:
                        logger.warning(f"SubDivX: ZIP extraction failed: {e}")
                
                # Handle RAR files (SubDivX sometimes uses RAR)
                elif content[:4] == b'Rar!' or content[:7] == b'Rar!\x1a\x07\x00':
                    # RAR files require special handling - inform user
                    message = (
                        f"SubDivX: Downloaded file is in RAR format.\n\n"
                        f"RAR extraction requires additional software.\n"
                        f"Please:\n"
                        f"1. Visit: {download_url}\n"
                        f"2. Download and extract the RAR file manually\n"
                        f"3. Use 'External File' option to load the subtitle\n\n"
                        f"💡 Tip: Install WinRAR or 7-Zip to handle RAR files"
                    )
                    logger.warning("⚠️ SubDivX: RAR file requires manual extraction")
                    return False, message
                
                # Handle gzip
                elif content[:2] == b'\x1f\x8b':
                    try:
                        content = gzip.decompress(content)
                        logger.debug("SubDivX: Decompressed gzip content")
                    except Exception as e:
                        logger.debug(f"SubDivX: Gzip decompression failed: {e}")
                
                # Write to file (handle Latin-1 encoding for Spanish subtitles)
                try:
                    # Try to detect and convert encoding
                    try:
                        text = content.decode('latin-1')
                        content = text.encode('utf-8')
                        logger.debug("SubDivX: Converted from Latin-1 to UTF-8")
                    except:
                        pass  # Keep original if conversion fails
                    
                    with open(output_path, 'wb') as f:
                        f.write(content)
                    
                    logger.info(f"✅ Downloaded from SubDivX: {output_path}")
                    return True, output_path
                except Exception as e:
                    logger.error(f"SubDivX: File write error: {e}")
                    return False, f"SubDivX: Failed to write file: {str(e)}"
                
        except urllib.error.HTTPError as e:
            error_msg = f"SubDivX HTTP error {e.code}: {e.reason}"
            logger.error(error_msg)
            
            # SubDivX might require CAPTCHA or cookies
            if e.code == 403:
                error_msg += "\n\nSubDivX may require manual download due to anti-bot protection."
            
            return False, error_msg
        except Exception as e:
            error_msg = f"SubDivX download error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

