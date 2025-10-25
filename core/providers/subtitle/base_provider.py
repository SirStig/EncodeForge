#!/usr/bin/env python3
"""
Base Subtitle Provider Class
Contains common functionality for all subtitle providers
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseSubtitleProvider:
    """Base class for all subtitle providers"""
    
    def __init__(self):
        self.provider_name = "Base"
        self.session_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def extract_media_metadata(self, file_path: str) -> Dict:
        """
        Centralized metadata extraction service for consistent subtitle searching.
        Extracts all relevant metadata from media files including title, year, season, episode, etc.
        
        Args:
            file_path: Path to the video file
            
        Returns:
            Dict containing metadata
        """
        file_name = Path(file_path).stem
        metadata = {
            'original_name': file_name,
            'clean_name': file_name,
            'year': None,
            'season': None,
            'episode': None,
            'is_tv_show': False,
            'is_movie': False,
            'is_anime': False,
            'quality': None,
            'release_group': None,
            'search_queries': []
        }
        
        # Detect TV show pattern (S##E##)
        tv_match = re.search(r'[Ss](\d+)[Ee](\d+)', file_name)
        if tv_match:
            metadata['is_tv_show'] = True
            metadata['season'] = int(tv_match.group(1))
            metadata['episode'] = int(tv_match.group(2))
            # Extract show name (everything before S##E##)
            show_name = file_name[:tv_match.start()].strip('._- ')
            # Store this as the base clean name for TV shows
            metadata['clean_name'] = show_name
        
        # Detect year
        year_match = re.search(r'\b(19|20)\d{2}\b', file_name)
        if year_match:
            metadata['year'] = year_match.group(0)
        
        # Detect quality
        quality_match = re.search(r'\b(2160p|4K|1080p|720p|480p|360p)\b', file_name, re.IGNORECASE)
        if quality_match:
            metadata['quality'] = quality_match.group(0)
        
        # Detect release group
        group_match = re.search(r'[\[\(]([^\]\)]+)[\]\)]', file_name)
        if group_match:
            metadata['release_group'] = group_match.group(1)
        
        # Determine if movie (note: removed anime-specific detection as it's not needed)
        if metadata['year'] and not metadata['is_tv_show']:
            metadata['is_movie'] = True
        elif not metadata['is_tv_show']:
            # If no S##E## pattern and no year, assume movie
            metadata['is_movie'] = True
        
        # Clean the title - use the already extracted name for TV shows
        if metadata['is_tv_show']:
            # Already have clean name from TV extraction
            clean_name = metadata['clean_name']
        else:
            # For movies, clean from full filename
            clean_name = file_name
        
        # Remove brackets and their contents
        clean_name = re.sub(r'[\[\(]([^\]\)]+)[\]\)]', '', clean_name)
        # Remove quality/encoding info
        clean_name = re.sub(r'\b(2160p|4K|1080p|720p|480p|360p|BluRay|BDRip|WEB-DL|WEBRip|HDTV|DVDRip|x264|x265|HEVC|H\.264|H\.265|AAC|AC3|DTS|DD5\.1|10bit|8bit)\b', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\b(PROPER|REPACK|EXTENDED|UNRATED|Directors\.Cut|DC|INTERNAL)\b', '', clean_name, flags=re.IGNORECASE)
        
        # Remove year if present
        if metadata['year']:
            clean_name = clean_name.replace(metadata['year'], '')
        
        # Replace separators with spaces
        clean_name = re.sub(r'[._-]+', ' ', clean_name).strip()
        clean_name = re.sub(r'\s+', ' ', clean_name).strip()
        
        metadata['clean_name'] = clean_name
        
        # Generate alternative search queries
        queries = [clean_name]
        if metadata['year']:
            queries.append(f"{clean_name} {metadata['year']}")
        if metadata['is_tv_show']:
            queries.append(f"{clean_name} S{metadata['season']:02d}E{metadata['episode']:02d}")
            queries.append(f"{clean_name} {metadata['season']}x{metadata['episode']:02d}")
        
        # Try alternative without leading articles
        alt_clean = re.sub(r'^(The |A |An )', '', clean_name, flags=re.IGNORECASE)
        if alt_clean != clean_name:
            queries.append(alt_clean)
            if metadata['is_tv_show']:
                queries.append(f"{alt_clean} S{metadata['season']:02d}E{metadata['episode']:02d}")
        
        metadata['search_queries'] = list(dict.fromkeys(queries))
        
        logger.info(f"Extracted metadata: title='{metadata['clean_name']}', type={'TV' if metadata['is_tv_show'] else 'Movie'}, year={metadata['year']}, S={metadata.get('season')}, E={metadata.get('episode')}")
        
        return metadata
    
    def lang_code_to_name(self, lang_code: str) -> str:
        """Convert language code to full name"""
        lang_map = {
            "eng": "English", "en": "English",
            "spa": "Spanish", "es": "Spanish", "es-MX": "Spanish (LA)",
            "fre": "French", "fra": "French", "fr": "French",
            "ger": "German", "deu": "German", "de": "German",
            "ita": "Italian", "it": "Italian",
            "por": "Portuguese", "pt": "Portuguese (EU)",
            "pob": "Portuguese (BR)", "pt-BR": "Portuguese (BR)",
            "rus": "Russian", "ru": "Russian",
            "ara": "Arabic", "ar": "Arabic",
            "chi": "Chinese", "zh": "Chinese (Simp)", "zh-CN": "Chinese (Simp)",
            "zht": "Chinese (Trad)", "zh-TW": "Chinese (Trad)", "zho": "Chinese",
            "jpn": "Japanese", "ja": "Japanese",
            "kor": "Korean", "ko": "Korean",
            "hin": "Hindi", "hi": "Hindi",
            "tha": "Thai", "th": "Thai",
            "vie": "Vietnamese", "vi": "Vietnamese",
            "tur": "Turkish", "tr": "Turkish",
            "pol": "Polish", "pl": "Polish",
            "dut": "Dutch", "nld": "Dutch", "nl": "Dutch",
            "swe": "Swedish", "sv": "Swedish",
            "nor": "Norwegian", "no": "Norwegian", "nb": "Norwegian"
        }
        return lang_map.get(lang_code, lang_code.upper())
    
    def lang_name_to_code(self, lang_name: str) -> str:
        """Convert full language name to 3-letter ISO 639-2 code"""
        lang_map = {
            "english": "eng",
            "spanish": "spa",
            "spanish (eu)": "spa",
            "spanish (la)": "spa",
            "french": "fre",
            "german": "ger",
            "italian": "ita",
            "portuguese": "por",
            "portuguese (eu)": "por",
            "portuguese (br)": "pob",
            "portuguese (brazil)": "pob",
            "russian": "rus",
            "arabic": "ara",
            "chinese": "chi",
            "chinese (simplified)": "chi",
            "chinese (simp)": "chi",
            "chinese (traditional)": "zht",
            "chinese (trad)": "zht",
            "japanese": "jpn",
            "korean": "kor",
            "hindi": "hin",
            "thai": "tha",
            "vietnamese": "vie",
            "turkish": "tur",
            "polish": "pol",
            "dutch": "dut",
            "swedish": "swe",
            "norwegian": "nor"
        }
        return lang_map.get(lang_name.lower(), lang_name)
    
    def search(self, video_path: str, languages: List[str]) -> List[Dict]:
        """
        Search for subtitles (must be implemented by subclasses)
        
        Args:
            video_path: Path to video file
            languages: List of language codes
            
        Returns:
            List of subtitle results
        """
        raise NotImplementedError("Subclass must implement search()")
    
    def download(self, file_id: str, download_url: str, output_path: str) -> tuple:
        """
        Download subtitle (must be implemented by subclasses)
        
        Args:
            file_id: Subtitle file ID
            download_url: Download URL
            output_path: Where to save the subtitle
            
        Returns:
            (success: bool, message: str)
        """
        raise NotImplementedError("Subclass must implement download()")

