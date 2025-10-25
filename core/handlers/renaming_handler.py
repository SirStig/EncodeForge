#!/usr/bin/env python3
"""
Renaming Handler - Media file renaming operations
"""

import logging
import platform
import re
from pathlib import Path
from typing import Dict, List, Optional

from .models import ConversionSettings

logger = logging.getLogger(__name__)


class RenamingHandler:
    """Handles media file renaming with metadata lookups"""
    
    def __init__(self, settings: ConversionSettings, renamer):
        self.settings = settings
        self.renamer = renamer
    
    def _extract_metadata_from_file(self, file_path: str) -> Optional[Dict]:
        """
        Extract any useful metadata from video file for searching providers
        Returns dict with show name, episode title, or other searchable info
        """
        try:
            import json
            import re
            import subprocess
            
            path = Path(file_path)
            filename = path.stem
            
            # Step 1: Try FFprobe to get embedded metadata
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                file_path
            ]
            
            embedded_info = {}
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    data = json.loads(result.stdout)
                    format_tags = data.get('format', {}).get('tags', {})
                    
                    # Extract any useful embedded metadata
                    embedded_title = format_tags.get('title')
                    embedded_show = format_tags.get('show') or format_tags.get('series')
                    embedded_episode_name = format_tags.get('episode_id')
                    
                    # Parse S##E## from embedded title if present
                    embedded_season = format_tags.get('season_number') or format_tags.get('season')
                    embedded_episode = format_tags.get('episode_sort') or format_tags.get('episode')
                    
                    # Check if embedded title contains S##E## pattern
                    if embedded_title and not embedded_season:
                        se_match = re.search(r'[Ss](\d+)[Ee](\d+)', embedded_title)
                        if se_match:
                            embedded_season = int(se_match.group(1))
                            embedded_episode = int(se_match.group(2))
                            # Remove S##E## from title to get the real title/episode name
                            embedded_title = embedded_title[:se_match.start()].strip('-_ ') + embedded_title[se_match.end():].strip('-_ ')
                    
                    embedded_info = {
                        'embedded_title': embedded_title,
                        'embedded_show': embedded_show,
                        'embedded_episode_name': embedded_episode_name,
                        'season': embedded_season,
                        'episode': embedded_episode,
                    }
                    logger.info(f"  FFprobe found: {embedded_info}")
            except Exception as e:
                logger.warning(f"FFprobe extraction failed: {e}")
            
            # Step 2: Try standard S##E## pattern parsing
            season_episode_patterns = [
                r'[Ss](\d+)[Ee](\d+)',  # S01E02
                r'(\d+)[xX](\d+)',       # 1x02
                r'[Ss]eason\s*(\d+).*?[Ee]pisode\s*(\d+)',  # Season 1 Episode 2
            ]
            
            show_name = None
            season = embedded_info.get('season')
            episode = embedded_info.get('episode')
            episode_title = None
            
            for pattern in season_episode_patterns:
                match = re.search(pattern, filename)
                if match:
                    # Extract show name (everything before S##E##)
                    show_name = filename[:match.start()].strip('._- ')
                    show_name = re.sub(r'\s+', ' ', show_name)
                    show_name = re.sub(r'[._]', ' ', show_name)
                    
                    # Extract season/episode numbers
                    if not season:
                        season = int(match.group(1))
                    if not episode:
                        episode = int(match.group(2))
                    
                    # Extract episode title (everything after S##E##)
                    episode_title = filename[match.end():].strip('._- ')
                    episode_title = re.sub(r'\s+', ' ', episode_title)
                    episode_title = re.sub(r'[._]', ' ', episode_title)
                    # Remove common quality tags
                    episode_title = re.sub(r'\b(720p|1080p|2160p|4K|HEVC|x264|x265|WEB-?DL|BluRay|BDRip)\b', '', episode_title, flags=re.IGNORECASE)
                    episode_title = episode_title.strip('._- ')
                    
                    logger.info(f"  Parsed: Show='{show_name}', S{season}E{episode}, Episode='{episode_title}'")
                    break
            
            # Step 3: If no S##E##, try to infer from folder/siblings
            if not show_name:
                folder_info = self._infer_from_folder_context(file_path)
                if folder_info:
                    show_name = folder_info.get('title')
                    # ONLY use folder inference for season/episode if we don't already have them from FFprobe
                    if not season:
                        season = folder_info.get('season')
                    if not episode:
                        episode = folder_info.get('episode')
                    # Try to extract episode title from filename
                    episode_title = filename
                    # Clean up common artifacts
                    episode_title = re.sub(r'\b(720p|1080p|2160p|4K|HEVC|x264|x265|WEB-?DL|BluRay|BDRip)\b', '', episode_title, flags=re.IGNORECASE)
                    episode_title = episode_title.strip('._- ')
            
            # Use embedded info as fallback
            if not show_name:
                show_name = embedded_info.get('embedded_show') or embedded_info.get('embedded_title')
            if not episode_title:
                episode_title = embedded_info.get('embedded_episode_name')
            
            # Return whatever we found
            if show_name or season or episode or episode_title:
                result = {
                    'title': show_name,
                    'season': int(season) if season else None,
                    'episode': int(episode) if episode else None,
                    'episode_title': episode_title
                }
                logger.info(f"  Final extracted metadata: {result}")
                return result
            
            logger.info(f"  Could not extract usable metadata from: {file_path}")
            return None
            
        except Exception as e:
            logger.error(f"Error extracting metadata from file: {e}")
            return None
    
    def _infer_from_folder_context(self, file_path: str) -> Optional[Dict]:
        """
        Try to infer show name, episode number, and episode title from folder structure and sibling files
        Used when file itself doesn't have S##E## pattern
        """
        try:
            import os
            import re
            
            path = Path(file_path)
            folder = path.parent
            filename = path.stem
            
            # Get all video files in same folder
            video_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm'}
            sibling_files = []
            
            try:
                for f in os.listdir(folder):
                    if Path(f).suffix.lower() in video_extensions:
                        sibling_files.append(f)
            except Exception as e:
                logger.warning(f"Could not list folder: {e}")
                return None
            
            # Sort files to determine position
            sibling_files.sort()
            
            # Look for files with S##E## pattern to infer show name
            show_name = None
            season = None
            
            for sibling in sibling_files:
                match = re.search(r'(.*?)[._\-\s]*[Ss](\d+)[Ee](\d+)', sibling)
                if match:
                    candidate_show = match.group(1).strip('._- ')
                    candidate_show = re.sub(r'[._]', ' ', candidate_show)
                    candidate_show = re.sub(r'\s+', ' ', candidate_show)
                    
                    # Use this as the show name
                    if not show_name:
                        show_name = candidate_show
                        season = int(match.group(2))
                        logger.info(f"  Inferred show from sibling file: {show_name} Season {season}")
                        break
            
            # Extract episode title from current filename by removing show name
            episode_title = filename
            if show_name:
                # Remove show name from filename to get episode title
                episode_title = filename.replace(show_name, '').strip('._- ')
                # Clean up
                episode_title = re.sub(r'\s+', ' ', episode_title)
                episode_title = re.sub(r'[._]', ' ', episode_title)
                episode_title = re.sub(r'\b(720p|1080p|2160p|4K|HEVC|x264|x265|WEB-?DL|BluRay|BDRip)\b', '', episode_title, flags=re.IGNORECASE)
                episode_title = episode_title.strip('._- ')
            
            # If we found a show name, try to determine episode number
            if show_name and season:
                # Try to find this file in the sorted list
                try:
                    file_index = sibling_files.index(path.name)
                    
                    # Count how many episodes we've seen before this one
                    episode_num = 1
                    for i, sibling in enumerate(sibling_files):
                        if i < file_index:
                            # Check if it's from the same show
                            if show_name.lower().replace(' ', '') in sibling.lower().replace(' ', '').replace('_', '').replace('.', ''):
                                match = re.search(r'[Ss](\d+)[Ee](\d+)', sibling)
                                if match and int(match.group(1)) == season:
                                    episode_num = int(match.group(2)) + 1
                    
                    logger.info(f"  Inferred: E{episode_num:02d}, Episode title: '{episode_title}'")
                    return {
                        'title': show_name,
                        'season': season,
                        'episode': episode_num,
                        'episode_title': episode_title if episode_title else None
                    }
                except ValueError:
                    pass
            
            # Fallback: Try to extract show name from folder name
            folder_name = folder.name
            # Remove common folder patterns
            folder_name = re.sub(r'[Ss]eason\s*\d+', '', folder_name, flags=re.IGNORECASE)
            folder_name = re.sub(r'[Ss]\d+', '', folder_name)
            folder_name = folder_name.strip('._- ')
            
            if folder_name:
                logger.info(f"  Using folder name as show hint: {folder_name}")
                # Try to match filename against folder name
                cleaned_filename = filename.lower().replace(' ', '').replace('_', '').replace('.', '')
                if folder_name.lower().replace(' ', '') in cleaned_filename:
                    # Extract episode title by removing show name
                    episode_title = filename.replace(folder_name, '').strip('._- ')
                    episode_title = re.sub(r'\s+', ' ', episode_title)
                    episode_title = re.sub(r'[._]', ' ', episode_title)
                    
                    # Assume first episode of season 1 if we can't determine more
                    return {
                        'title': folder_name,
                        'season': 1,
                        'episode': 1,
                        'episode_title': episode_title if episode_title else None
                    }
            
            logger.info("  Could not infer metadata from folder context")
            return None
            
        except Exception as e:
            logger.error(f"Error inferring from folder context: {e}")
            return None
    
    def _prefer_english_title(self, results_list: List[Dict]) -> Optional[Dict]:
        """
        Given multiple provider results, prefer English titles over Japanese/Romaji
        
        Strategy:
        1. Prioritize results from AniDB/Kitsu (they return English titles)
        2. Detect common Japanese romaji patterns
        3. Prefer titles without Japanese words
        """
        if not results_list:
            return None
        
        # Common Japanese romaji words that indicate it's not an English title
        japanese_indicators = [
            'watashi', 'no', 'wa', 'ga', 'wo', 'ni', 'de', 'to', 'kara', 'made',
            'shiawase', 'kekkon', 'shoujo', 'shounen', 'sensei', 'sama', 'chan', 'kun',
            'anime', 'manga', 'otaku', 'kawaii', 'sugoi', 'desu', 'masu', 'です', 'ます'
        ]
        
        # First pass: Look for results from providers known to give English titles
        preferred_sources = ['anidb', 'kitsu', 'jikan/mal', 'tmdb']
        for result in results_list:
            source = result.get('source', '').lower()
            title = result.get('show_title', '') or result.get('title', '')
            
            if source in preferred_sources and title:
                # Check if title contains Japanese romaji words
                title_lower = title.lower()
                has_japanese = any(word in title_lower for word in japanese_indicators)
                
                if not has_japanese:
                    logger.info(f"  Preferring English title from {source}: {title}")
                    return result
        
        # Second pass: Find any title without Japanese indicators
        for result in results_list:
            title = result.get('show_title', '') or result.get('title', '')
            if title:
                title_lower = title.lower()
                has_japanese = any(word in title_lower for word in japanese_indicators)
                
                if not has_japanese:
                    logger.info(f"  Selecting non-Japanese title: {title}")
                    return result
        
        # Fallback: return first result
        logger.info("  All titles appear to be Japanese, using first result")
        return results_list[0]
    
    def preview_rename(self, file_paths: List[str], settings_dict: Optional[Dict] = None) -> Dict:
        """
        Preview how files would be renamed
        
        Now uses parallel processing for faster metadata lookups across multiple files.
        
        TODO: FUTURE ENHANCEMENT - Use file hashes and embedded metadata
        Currently uses filename parsing only. Future improvements:
        1. Extract embedded metadata (title, show, season, episode) from video file using FFprobe
        2. Calculate file hashes (MD5/SHA1) for database lookups
        3. Combine multiple data sources:
           - Filename parsing (current method)
           - Embedded video metadata (title, show, season/episode tags)
           - File hash lookups (AniDB hash, OpenSubtitles hash)
           - File size and duration matching
        4. Implement confidence scoring to pick best match across providers
        5. Fall back to filename parsing if no embedded data available
        
        This would dramatically improve matching for files with weird/incorrect names
        like "My Happy Marriage Ordeal" that don't match the actual show name.
        """
        try:
            logger.info(f"=== Preview Rename for {len(file_paths)} file(s) ===")
            
            # Get selected provider (no media type override - let auto-detection work)
            selected_provider = "automatic"
            
            # Update settings if provided
            if settings_dict:
                if "tmdb_api_key" in settings_dict:
                    self.settings.tmdb_api_key = settings_dict["tmdb_api_key"]
                    self.renamer.tmdb_key = settings_dict["tmdb_api_key"]
                if "tvdb_api_key" in settings_dict:
                    self.settings.tvdb_api_key = settings_dict["tvdb_api_key"]
                    self.renamer.tvdb_key = settings_dict["tvdb_api_key"]
                if "omdb_api_key" in settings_dict:
                    self.settings.omdb_api_key = settings_dict.get("omdb_api_key", "")
                    self.renamer.omdb_key = settings_dict.get("omdb_api_key", "")
                if "trakt_api_key" in settings_dict:
                    self.settings.trakt_api_key = settings_dict.get("trakt_api_key", "")
                    self.renamer.trakt_key = settings_dict.get("trakt_api_key", "")
                if "selected_provider" in settings_dict:
                    selected_provider = settings_dict["selected_provider"]
            
            logger.info(f"Selected Provider: {selected_provider}")
            
            # Log provider status
            has_tmdb = bool(self.settings.tmdb_api_key and self.settings.tmdb_api_key.strip())
            has_tvdb = bool(self.settings.tvdb_api_key and self.settings.tvdb_api_key.strip())
            has_omdb = bool(getattr(self.settings, 'omdb_api_key', None) and self.settings.omdb_api_key.strip())
            has_trakt = bool(getattr(self.settings, 'trakt_api_key', None) and self.settings.trakt_api_key.strip())
            logger.info(f"Providers: TMDB={'✓' if has_tmdb else '✗'}, TVDB={'✓' if has_tvdb else '✗'}, OMDB={'✓' if has_omdb else '✗'}, Trakt={'✓' if has_trakt else '✗'}, AniDB=✓, Kitsu=✓, Jikan=✓, TVmaze=✓")
            
            # Use parallel processing for metadata lookups
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from resource_manager import get_resource_manager
            
            # Get optimal worker count for metadata operations
            rm = get_resource_manager()
            max_workers = rm.get_optimal_worker_count("metadata")
            logger.info(f"Using {max_workers} parallel workers for metadata lookups")
            
            suggested_metadata = []  # Store raw metadata for each file
            providers = []
            errors = []
            provider_metadata = {}  # Store metadata per provider for comparison (not formatted strings)
            
            # Process files in parallel
            def process_single_file(file_path):
                """Process a single file and return its metadata"""
                try:
                    path = Path(file_path)
                    logger.info(f"Processing: {path.name}")
                    
                    # Auto-detect media type from filename
                    media_type = self.renamer.detect_media_type(path.name)
                    
                    logger.info(f"  Media type: {media_type}")
                    
                    info = None
                    new_name = None
                    provider = None
                    error = None
                    
                    if media_type == "unknown":
                        # Try extracting metadata from file using FFprobe for unknown types
                        logger.info("  Unknown media type, trying FFprobe metadata extraction...")
                        parsed = self._extract_metadata_from_file(file_path)
                        if parsed:
                            media_type = "tv"  # Assume TV if we can extract S##E## from file
                        else:
                            error = "❌ ERROR: Could not detect media type from filename or file metadata."
                    
                    if media_type == "tv" or media_type == "anime":
                        parsed = self.renamer.parse_tv_filename(path.name)
                        if not parsed:
                            # Try extracting metadata from file using FFprobe
                            logger.info("  Filename parsing failed, trying FFprobe metadata extraction...")
                            parsed = self._extract_metadata_from_file(file_path)
                        
                        if not parsed:
                            error = "❌ ERROR: Could not parse TV show information from filename or file metadata."
                        else:
                            # Log what we extracted for searching
                            search_query = f"Title: '{parsed.get('title')}'"
                            if parsed.get('season') and parsed.get('episode'):
                                search_query += f", S{parsed['season']:02d}E{parsed['episode']:02d}"
                            if parsed.get('episode_title'):
                                search_query += f", Episode: '{parsed['episode_title']}'"
                            logger.info(f"  Search query: {search_query}")
                            
                            # Search based on selected provider
                            providers_to_try = []
                            
                            if selected_provider == "automatic":
                                # Try ALL providers - anime could be misdetected as TV
                                # Order: Try anime providers first (usually better metadata), then general TV
                                providers_to_try = ["anidb", "kitsu", "jikan/mal", "tmdb", "tvdb", "tvmaze", "omdb"]
                            else:
                                # Use specific provider
                                providers_to_try = [selected_provider]
                            
                            # Try ALL providers and store results from each
                            all_provider_info = []  # Store all results with provider names
                            # Track which providers we tried for THIS file (for alignment)
                            file_provider_results = {}
                            
                            for prov in providers_to_try:
                                prov_info = None
                                prov_name = None
                                    
                                try:
                                    # Extract search parameters (use defaults if not available)
                                    title = parsed.get("title")
                                    season = parsed.get("season", 1)  # Default to S01 if not found
                                    episode = parsed.get("episode", 1)  # Default to E01 if not found
                                    episode_title = parsed.get("episode_title")  # May be None
                                    
                                    # TODO: Future - use episode_title for enhanced matching
                                    # Episode titles can help identify exact episodes when S##E## is uncertain
                                    
                                    if prov == "tmdb" and self.settings.tmdb_api_key:
                                        prov_info = self.renamer.search_tv_show(
                                            title,
                                            season,
                                            episode
                                        )
                                        if prov_info:
                                            prov_name = "TMDB"
                                    elif prov == "tvdb" and self.settings.tvdb_api_key:
                                        prov_info = self.renamer.search_tv_show(
                                            title,
                                            season,
                                            episode,
                                            provider="tvdb"
                                        )
                                        if prov_info:
                                            prov_name = "TVDB"
                                    elif prov == "anidb":
                                        prov_info = self.renamer.search_tv_show(
                                            title,
                                            season,
                                            episode,
                                            provider="anidb"
                                        )
                                        if prov_info:
                                            prov_name = "AniDB"
                                    elif prov == "kitsu":
                                        prov_info = self.renamer.search_tv_show(
                                            title,
                                            season,
                                            episode,
                                            provider="kitsu"
                                        )
                                        if prov_info:
                                            prov_name = "Kitsu"
                                    elif prov == "jikan/mal" or prov == "jikan":
                                        prov_info = self.renamer.search_tv_show(
                                            title,
                                            season,
                                            episode,
                                            provider="jikan"
                                        )
                                        if prov_info:
                                            prov_name = "Jikan/MAL"
                                    elif prov == "tvmaze":
                                        prov_info = self.renamer.search_tv_show(
                                            title,
                                            season,
                                            episode,
                                            provider="tvmaze"
                                        )
                                        if prov_info:
                                            prov_name = "TVmaze"
                                    
                                    # Store raw metadata from this provider (don't format yet - Java will do that)
                                    if prov_info and prov_name:
                                        # Store raw metadata (Java will format it)
                                        all_provider_info.append({
                                            'info': prov_info,
                                            'provider': prov_name
                                        })
                                        file_provider_results[prov_name] = prov_info
                                        
                                        logger.info(f"  Found match via {prov_name}: {prov_info.get('show_title', 'Unknown')} S{prov_info.get('season', 0):02d}E{prov_info.get('episode', 0):02d} - {prov_info.get('episode_title', 'N/A')}")
                                    elif prov_name:
                                        # Provider was tried but failed - track it as empty
                                        file_provider_results[prov_name] = {}
                                except Exception as e:
                                    logger.error(f"{prov} lookup failed: {e}")
                                    # Track failed provider with empty result
                                    if prov == "tmdb":
                                        file_provider_results["TMDB"] = {}
                                    elif prov == "tvdb":
                                        file_provider_results["TVDB"] = {}
                                    elif prov == "anidb":
                                        file_provider_results["AniDB"] = {}
                                    elif prov == "kitsu":
                                        file_provider_results["Kitsu"] = {}
                                    elif prov == "jikan/mal" or prov == "jikan":
                                        file_provider_results["Jikan/MAL"] = {}
                                    elif prov == "tvmaze":
                                        file_provider_results["TVmaze"] = {}
                            
                            # Store results from ALL providers for THIS file (including empty ones for alignment)
                            for prov_name, prov_info in file_provider_results.items():
                                if prov_name not in provider_metadata:
                                    provider_metadata[prov_name] = []
                                provider_metadata[prov_name].append(prov_info if prov_info else {})
                            
                            # After trying all providers, prefer English title
                            if all_provider_info:
                                # Extract just the info dicts for preference function
                                info_dicts = [item['info'] for item in all_provider_info]
                                preferred_info = self._prefer_english_title(info_dicts)
                                
                                # Find the matching provider item
                                for item in all_provider_info:
                                    if item['info'] == preferred_info:
                                        info = item['info']
                                        provider = item['provider']
                                        logger.info(f"  ✓ Selected result from {provider}: {info.get('show_title', 'Unknown')} S{info.get('season', 0):02d}E{info.get('episode', 0):02d}")
                                        break
                            
                            if not info:
                                # Don't show error, just leave blank
                                season_str = f"S{parsed['season']:02d}" if parsed.get('season') else "S??"
                                episode_str = f"E{parsed['episode']:02d}" if parsed.get('episode') else "E??"
                                logger.info(f"  No metadata found for '{parsed.get('title', 'Unknown')}' {season_str}{episode_str}")
                    
                    elif media_type == "movie":
                        parsed = self.renamer.parse_movie_filename(path.name)
                        if not parsed:
                            error = "❌ ERROR: Could not parse movie information."
                        else:
                            # Search based on selected provider
                            providers_to_try = []
                            
                            if selected_provider == "automatic":
                                # Try all available providers for best match
                                providers_to_try = ["tmdb", "omdb", "trakt"]
                            else:
                                # Use specific provider
                                providers_to_try = [selected_provider]
                            
                            # Try ALL providers and store results from each
                            all_provider_info = []  # Store all results with provider names
                            # Track which providers we tried for THIS file (for alignment)
                            file_provider_results = {}
                            
                            for prov in providers_to_try:
                                prov_info = None
                                prov_name = None
                                    
                                try:
                                    if prov == "tmdb" and self.settings.tmdb_api_key:
                                        prov_info = self.renamer.search_movie(
                                            parsed["title"],
                                            parsed.get("year")
                                        )
                                        if prov_info:
                                            prov_name = "TMDB"
                                    elif prov == "omdb" and getattr(self.settings, 'omdb_api_key', None):
                                        prov_info = self.renamer.search_movie(
                                            parsed["title"],
                                            parsed.get("year"),
                                            provider="omdb"
                                        )
                                        if prov_info:
                                            prov_name = "OMDB"
                                    elif prov == "trakt" and getattr(self.settings, 'trakt_api_key', None):
                                        prov_info = self.renamer.search_movie(
                                            parsed["title"],
                                            parsed.get("year"),
                                            provider="trakt"
                                        )
                                        if prov_info:
                                            prov_name = "Trakt"
                                    
                                    # Store result from this provider
                                    if prov_info and prov_name:
                                        # Store raw metadata (Java will format it)
                                        all_provider_info.append({
                                            'info': prov_info,
                                            'provider': prov_name
                                        })
                                        file_provider_results[prov_name] = prov_info
                                        
                                        logger.info(f"  Found match via {prov_name}: {prov_info.get('title', 'Unknown')} ({prov_info.get('year', 'N/A')})")
                                    elif prov_name:
                                        # Provider was tried but failed - track it as empty
                                        file_provider_results[prov_name] = {}
                                except Exception as e:
                                    logger.error(f"{prov} movie lookup failed: {e}")
                                    # Track failed provider with empty result
                                    if prov == "tmdb":
                                        file_provider_results["TMDB"] = {}
                                    elif prov == "omdb":
                                        file_provider_results["OMDB"] = {}
                                    elif prov == "trakt":
                                        file_provider_results["Trakt"] = {}
                            
                            # Store results from ALL providers for THIS file (including empty ones for alignment)
                            for prov_name, prov_info in file_provider_results.items():
                                if prov_name not in provider_metadata:
                                    provider_metadata[prov_name] = []
                                provider_metadata[prov_name].append(prov_info if prov_info else {})
                            
                            # After trying all providers, prefer English title
                            if all_provider_info:
                                
                                # Extract just the info dicts for preference function
                                info_dicts = [item['info'] for item in all_provider_info]
                                preferred_info = self._prefer_english_title(info_dicts)
                                
                                # Find the matching provider item
                                for item in all_provider_info:
                                    if item['info'] == preferred_info:
                                        info = item['info']
                                        provider = item['provider']
                                        logger.info(f"  ✓ Selected result from {provider}: {info.get('title', 'Unknown')} ({info.get('year', 'N/A')})")
                                        break
                            
                            if not info:
                                # Don't show error, just leave blank
                                year_str = f" ({parsed.get('year')})" if parsed.get('year') else ""
                                logger.info(f"  No metadata found for movie '{parsed['title']}'{year_str}")
                
                    # Store raw metadata (not formatted name) - Java will format using user's pattern
                    suggested_metadata.append(info if info else {})
                    providers.append(provider if provider else "None")
                    errors.append(error if error else "")
                    
                    if info:
                        logger.info(f"  ✓ Metadata found [via {provider}]")
                    elif error:
                        logger.warning(f"  {error}")
                    else:
                        logger.info("  No metadata found - leaving blank")
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}", exc_info=True)
                    suggested_metadata.append({})
                    providers.append("Error")
                    errors.append(str(e))
            
            # Actually process the files using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all files for parallel processing
                future_to_file = {executor.submit(process_single_file, fp): fp for fp in file_paths}
                
                # Collect results as they complete
                for future in as_completed(future_to_file):
                    file_path = future_to_file[future]
                    try:
                        # The function already appends to the shared lists
                        future.result()
                    except Exception as e:
                        logger.error(f"Error processing {file_path}: {e}", exc_info=True)
                        suggested_metadata.append({})
                        providers.append("Error")
                        errors.append(str(e))
            
            logger.info(f"=== Preview Complete: {len(suggested_metadata)} file(s) processed ===")
            logger.info(f"Provider results: {list(provider_metadata.keys())}")
            
            return {
                "status": "success",
                "metadata": suggested_metadata,  # Raw metadata for each file (Java will format)
                "providers": providers,
                "errors": errors,
                "provider_metadata": provider_metadata  # Per-provider metadata for comparison
            }
        except Exception as e:
            logger.error(f"Error in preview_rename: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Failed to preview rename: {str(e)}",
                "metadata": [],
                "providers": [],
                "errors": []
            }
    
    def rename_files(self, file_paths: List[str], dry_run: bool = False, create_backup: bool = False) -> Dict:
        """
        Rename media files using metadata
        
        Args:
            file_paths: List of file paths to rename
            dry_run: If True, don't actually rename files
            create_backup: If True, create a backup list of original filenames
        
        Returns:
            Dict with status, renamed count, total count, and results
        """
        import json
        import os
        from datetime import datetime
        
        logger.info(f"=== Starting file renaming for {len(file_paths)} files ===")
        logger.info(f"Dry run: {dry_run}, Create backup: {create_backup}")
        
        results = []
        backup_data = []
        
        # First, get metadata for all files (reuse preview logic)
        preview_result = self.preview_rename(file_paths)
        if preview_result["status"] != "success":
            return {
                "status": "error",
                "message": "Failed to get metadata for files",
                "renamed": 0,
                "total": len(file_paths),
                "results": []
            }
        
        metadata_list = preview_result["metadata"]
        
        for i, file_path in enumerate(file_paths):
            try:
                logger.info(f"Processing file {i+1}/{len(file_paths)}: {os.path.basename(file_path)}")
                
                path = Path(file_path)
                if not path.exists():
                    logger.error(f"File not found: {file_path}")
                    results.append({
                        "original": file_path,
                        "new_path": None,
                        "success": False,
                        "message": f"File not found: {file_path}"
                    })
                    continue
                
                # Get metadata for this file
                metadata = metadata_list[i] if i < len(metadata_list) else {}
                
                if not metadata:
                    logger.warning(f"No metadata available for: {os.path.basename(file_path)}")
                    results.append({
                        "original": file_path,
                        "new_path": None,
                        "success": False,
                        "message": "No metadata found for file"
                    })
                    continue
                
                # Determine pattern based on media type
                media_type = self.renamer.detect_media_type(path.name)
                pattern = self.settings.renaming_pattern_tv
                if media_type == "movie":
                    pattern = self.settings.renaming_pattern_movie
                
                logger.info(f"Using pattern: {pattern}")
                
                # Format new filename using metadata
                new_name = self._format_filename_from_metadata(metadata, pattern)
                if not new_name:
                    logger.error(f"Failed to format filename for: {os.path.basename(file_path)}")
                    results.append({
                        "original": file_path,
                        "new_path": None,
                        "success": False,
                        "message": "Failed to format new filename"
                    })
                    continue
                
                # Ensure new filename has the same extension
                new_path = path.parent / f"{new_name}{path.suffix}"
                
                # Check if file already has the correct name
                if path.name == new_path.name:
                    logger.info(f"File already has correct name: {path.name}")
                    results.append({
                        "original": file_path,
                        "new_path": str(new_path),
                        "success": True,
                        "message": f"File already correctly named: {path.name}"
                    })
                    continue
                
                # Check if target file already exists
                if new_path.exists() and new_path != path:
                    logger.warning(f"Target file already exists: {new_path.name}")
                    results.append({
                        "original": file_path,
                        "new_path": str(new_path),
                        "success": False,
                        "message": f"Target file already exists: {new_path.name}"
                    })
                    continue
                
                # Store backup information
                if create_backup:
                    backup_data.append({
                        "original_path": str(path),
                        "original_name": path.name,
                        "new_path": str(new_path),
                        "new_name": new_path.name,
                        "timestamp": datetime.now().isoformat()
                    })
                
                if dry_run:
                    logger.info(f"DRY RUN: Would rename '{path.name}' to '{new_path.name}'")
                    results.append({
                        "original": file_path,
                        "new_path": str(new_path),
                        "success": True,
                        "message": f"Would rename to: {new_path.name}"
                    })
                else:
                    # Perform the actual rename
                    try:
                        logger.info(f"Renaming '{path.name}' to '{new_path.name}'")
                        path.rename(new_path)
                        logger.info(f"✅ Successfully renamed to: {new_path.name}")
                        results.append({
                            "original": file_path,
                            "new_path": str(new_path),
                            "success": True,
                            "message": f"Renamed to: {new_path.name}"
                        })
                    except Exception as e:
                        logger.error(f"Failed to rename file: {e}")
                        results.append({
                            "original": file_path,
                            "new_path": str(new_path),
                            "success": False,
                            "message": f"Rename failed: {str(e)}"
                        })
                        
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
                results.append({
                    "original": file_path,
                    "new_path": None,
                    "success": False,
                    "message": f"Processing error: {str(e)}"
                })
        
        # Create backup file if requested and not dry run
        if create_backup and not dry_run and backup_data:
            try:
                from path_manager import get_backups_dir
                backup_dir = get_backups_dir()
                backup_dir.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = backup_dir / f"rename_backup_{timestamp}.json"
                
                with open(backup_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "timestamp": datetime.now().isoformat(),
                        "total_files": len(file_paths),
                        "successful_renames": len([r for r in results if r["success"]]),
                        "files": backup_data
                    }, f, indent=2, ensure_ascii=False)
                
                logger.info(f"📝 Backup created: {backup_file}")
                
            except Exception as e:
                logger.error(f"Failed to create backup file: {e}")
        
        success_count = sum(1 for r in results if r["success"])
        
        logger.info(f"=== Renaming complete: {success_count}/{len(file_paths)} files renamed ===")
        
        return {
            "status": "success",
            "renamed": success_count,
            "total": len(file_paths),
            "results": results
        }
    
    def _format_filename_from_metadata(self, metadata: Dict, pattern: str) -> Optional[str]:
        """
        Format filename using metadata and pattern
        
        Args:
            metadata: Metadata dictionary from provider
            pattern: Naming pattern (e.g., "{title} - S{season}E{episode} - {episodeTitle}")
        
        Returns:
            Formatted filename or None if formatting fails
        """
        try:
            import re
            
            if not metadata:
                return None
            
            # Create a copy to avoid modifying original
            format_dict = metadata.copy()
            
            # Ensure required fields have default values
            format_dict.setdefault('title', 'Unknown')
            format_dict.setdefault('show_title', format_dict.get('title', 'Unknown'))
            format_dict.setdefault('season', 1)
            format_dict.setdefault('episode', 1)
            format_dict.setdefault('episodeTitle', format_dict.get('episode_title', ''))
            format_dict.setdefault('year', '')
            
            # Format season and episode with zero padding
            if 'season' in format_dict and format_dict['season']:
                format_dict['season'] = f"{int(format_dict['season']):02d}"
            if 'episode' in format_dict and format_dict['episode']:
                format_dict['episode'] = f"{int(format_dict['episode']):02d}"
            
            # Use show_title as title for TV shows if available
            if format_dict.get('show_title'):
                format_dict['title'] = format_dict['show_title']
            
            # Format the filename
            result = pattern.format(**format_dict)
            
            # Clean up the result
            result = result.strip()
            
            # Remove multiple spaces
            result = re.sub(r'\s+', ' ', result)
            
            # Remove invalid filename characters (cross-platform)
            result = self._sanitize_filename(result)
            
            return result if result else None
            
        except Exception as e:
            logger.error(f"Error formatting filename: {e}")
            return None
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for cross-platform compatibility"""
        # Remove or replace invalid characters based on platform
        system = platform.system().lower()
        
        if system == "windows":
            # Windows invalid characters
            invalid_chars = r'[<>:"/\\|?*]'
        else:
            # Unix/Linux/macOS - only forward slash and null character
            invalid_chars = r'[/\x00]'
        
        result = re.sub(invalid_chars, '', filename)
        
        # Additional platform-specific handling
        if system == "windows":
            # Remove trailing dots and spaces (Windows doesn't like them)
            result = result.rstrip('. ')
            # Windows reserved names
            reserved_names = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
            if result.upper() in reserved_names:
                result = result + "_"
        
        return result

