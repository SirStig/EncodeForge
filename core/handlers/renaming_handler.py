#!/usr/bin/env python3
"""
Renaming Handler - Media file renaming operations
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from core.metadata_grabber import KEYED_PROVIDERS, MOVIE_AUTO_PROVIDERS, TV_AUTO_PROVIDERS
from core.rename_executor import RenamePair, execute_renames, find_sidecar_files
from core.rename_pattern import sanitize_filename

from .models import ConversionSettings

logger = logging.getLogger(__name__)

# GUI/settings use "auto" / "all"; CLI historically used "automatic".
# All three mean "try providers in priority order."
_EXPAND_ALL_PROVIDER_TOKENS = frozenset({"auto", "all", "automatic"})

_PROVIDER_DISPLAY_NAMES = {
    "tmdb": "TMDB",
    "tvdb": "TVDB",
    "tvmaze": "TVmaze",
    "trakt": "Trakt",
    "omdb": "OMDB",
    "anidb": "AniDB",
    "kitsu": "Kitsu",
    "jikan": "Jikan",
}


def normalize_selected_provider(provider: Optional[str]) -> str:
    """Map GUI/CLI provider tokens to a canonical handler value.

    ``auto``, ``all``, and ``automatic`` (any case / surrounding whitespace)
    all expand to the multi-provider fallback list. Specific provider ids
    are lowercased and otherwise left unchanged.
    """
    token = (provider or "automatic").strip().lower()
    if token in _EXPAND_ALL_PROVIDER_TOKENS:
        return "automatic"
    return token


class RenamingHandler:
    """Handles media file renaming with metadata lookups"""
    
    def __init__(self, settings: ConversionSettings, renamer):
        self.settings = settings
        self.renamer = renamer

    def _provider_key_configured(self, prov: str) -> bool:
        """True when a keyed provider has a non-empty API key in settings."""
        key_attr = {
            "tmdb": "tmdb_api_key",
            "tvdb": "tvdb_api_key",
            "omdb": "omdb_api_key",
            "trakt": "trakt_api_key",
        }.get(prov)
        if not key_attr:
            return True  # free providers need no key
        value = getattr(self.settings, key_attr, None)
        return bool(value and str(value).strip())

    @property
    def _ffprobe(self) -> str:
        """
        Resolve the FFprobe executable.

        A bare "ffprobe" is not reachable when FFmpeg was installed by the app's
        own downloader, which puts it outside PATH — metadata extraction then
        fails silently and every rename preview degrades to a filename guess.
        """
        configured = (getattr(self.settings, 'ffprobe_path', '') or '').strip()
        if configured:
            return configured
        try:
            from utils.ffmpeg_manager import get_ffmpeg_manager
            path = get_ffmpeg_manager().get_ffprobe_path()
            if path:
                return str(path)
        except Exception as e:
            logger.debug(f"Could not resolve FFprobe path from manager: {e}")
        return "ffprobe"


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
                self._ffprobe,
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
                r'[Ss](\d{1,2})[Ee](\d{1,3})',  # S01E02
                # 1x02 — bounded to 1-2 digit seasons and preceded by a
                # separator so a resolution like "1920x1080" is not parsed as
                # season 1920 episode 1080.
                r'(?:^|[.\s_\-\[])(\d{1,2})[xX](\d{1,3})(?:$|[.\s_\-\]])',
                r'[Ss]eason\s*(\d{1,2}).*?[Ee]pisode\s*(\d{1,3})',  # Season 1 Episode 2
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

            # Last resort: identify by OSDB file hash — filename-independent,
            # for scene/hash releases the parsers above have nothing to read
            # from at all (garbage or numeric-only names).
            if not show_name:
                hash_info = self._identify_by_hash(file_path)
                if hash_info:
                    show_name = hash_info.get('title')
                    season = hash_info.get('season') or season
                    episode = hash_info.get('episode') or episode
                    episode_title = hash_info.get('episode_title') or episode_title

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
                    
                    # Title-only: do not invent S01E01 from a weak folder-name
                    # match. Season/episode need stronger signals (sibling
                    # SxxExx, embedded tags, or OSDB hash).
                    return {
                        'title': folder_name,
                        'season': None,
                        'episode': None,
                        'episode_title': episode_title if episode_title else None
                    }
            
            logger.info("  Could not infer metadata from folder context")
            return None
            
        except Exception as e:
            logger.error(f"Error inferring from folder context: {e}")
            return None

    def _identify_by_hash(self, file_path: str) -> Optional[Dict]:
        """
        Last-resort media identification via the OpenSubtitles OSDB file
        hash, for filenames the parsers above can't read anything from at
        all. Best-effort and silent on failure — this must never turn a
        "couldn't identify" case into a crash, and never touches the
        download quota (it's a search-only lookup).
        """
        try:
            from core.providers.subtitle.opensubtitles_manager import OpenSubtitlesManager
            mgr = OpenSubtitlesManager()
            return mgr.identify_by_hash(file_path)
        except Exception as e:
            logger.debug(f"Hash-based identification unavailable: {e}")
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
        
        # Common Japanese romaji words that indicate it's not an English title.
        #
        # These are matched as whole words. A substring test made the two-letter
        # particles ('no', 'wa', 'ni', 'to', …) fire on ordinary English titles —
        # "The Night Of", "Doctor Who" and "Snowfall" all classified as Japanese,
        # so every candidate was rejected and the function degenerated into
        # "return the first result".
        japanese_indicators = {
            'watashi', 'no', 'wa', 'ga', 'wo', 'ni', 'de', 'to', 'kara', 'made',
            'shiawase', 'kekkon', 'shoujo', 'shounen', 'sensei', 'sama', 'chan', 'kun',
            'otaku', 'kawaii', 'sugoi', 'desu', 'masu',
        }

        def _looks_japanese(title: str) -> bool:
            # Any CJK character is decisive on its own.
            if any('぀' <= ch <= 'ヿ' or '一' <= ch <= '鿿' for ch in title):
                return True
            words = set(re.findall(r"[a-z']+", title.lower()))
            return bool(words & japanese_indicators)

        # First pass: prefer English-friendly sources (free first, then keyed)
        preferred_sources = ['tvmaze', 'tvdb', 'tmdb', 'trakt', 'omdb', 'anidb', 'kitsu', 'jikan']
        for result in results_list:
            source = result.get('source', '').lower()
            title = result.get('show_title', '') or result.get('title', '')
            
            if source in preferred_sources and title:
                # Check if title contains Japanese romaji words
                has_japanese = _looks_japanese(title)

                if not has_japanese:
                    logger.info(f"  Preferring English title from {source}: {title}")
                    return result
        
        # Second pass: Find any title without Japanese indicators
        for result in results_list:
            title = result.get('show_title', '') or result.get('title', '')
            if title:
                has_japanese = _looks_japanese(title)

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
            
            # Update settings if provided. Keys must rebuild provider instances
            # (configure_keys) — assigning renamer.tmdb_key alone left self.tmdb
            # as None when the grabber started without a key (C2 / P1-A).
            if settings_dict:
                key_kwargs = {}
                if "tmdb_api_key" in settings_dict:
                    self.settings.tmdb_api_key = settings_dict["tmdb_api_key"]
                    key_kwargs["tmdb_key"] = settings_dict["tmdb_api_key"]
                if "tvdb_api_key" in settings_dict:
                    self.settings.tvdb_api_key = settings_dict["tvdb_api_key"]
                    key_kwargs["tvdb_key"] = settings_dict["tvdb_api_key"]
                if "omdb_api_key" in settings_dict:
                    self.settings.omdb_api_key = settings_dict.get("omdb_api_key", "")
                    key_kwargs["omdb_key"] = settings_dict.get("omdb_api_key", "")
                if "trakt_api_key" in settings_dict:
                    self.settings.trakt_api_key = settings_dict.get("trakt_api_key", "")
                    key_kwargs["trakt_key"] = settings_dict.get("trakt_api_key", "")
                if key_kwargs:
                    self.renamer.configure_keys(**key_kwargs)
                if "selected_provider" in settings_dict:
                    selected_provider = settings_dict["selected_provider"]

            selected_provider = normalize_selected_provider(selected_provider)
            
            logger.info(f"Selected Provider: {selected_provider}")
            
            # Log provider status
            has_tmdb = bool(self.settings.tmdb_api_key and self.settings.tmdb_api_key.strip())
            has_tvdb = bool(self.settings.tvdb_api_key and self.settings.tvdb_api_key.strip())
            has_omdb = bool(getattr(self.settings, 'omdb_api_key', None) and self.settings.omdb_api_key.strip())
            has_trakt = bool(getattr(self.settings, 'trakt_api_key', None) and self.settings.trakt_api_key.strip())
            logger.info(f"Providers: TMDB={'✓' if has_tmdb else '✗'}, TVDB={'✓' if has_tvdb else '✗'}, OMDB={'✓' if has_omdb else '✗'}, Trakt={'✓' if has_trakt else '✗'}, AniDB=✓, Kitsu=✓, Jikan=✓, TVmaze=✓")
            
            # Use parallel processing for metadata lookups
            from concurrent.futures import ThreadPoolExecutor
            from core.resource_manager import get_resource_manager
            
            # Get optimal worker count for metadata operations
            rm = get_resource_manager()
            max_workers = rm.get_optimal_worker_count("metadata")
            logger.info(f"Using {max_workers} parallel workers for metadata lookups")
            
            suggested_metadata = []  # Store raw metadata for each file
            providers = []
            errors = []
            provider_metadata = {}  # Aggregated on main thread after futures complete

            def process_single_file(file_path):
                """Process a single file; return metadata, provider, error, per-file provider map."""
                file_provider_results = {}
                try:
                    path = Path(file_path)
                    logger.info(f"Processing: {path.name}")

                    media_type = self.renamer.detect_media_type(path.name)
                    logger.info(f"  Media type: {media_type}")

                    info = None
                    provider = None
                    error = None

                    if media_type == "unknown":
                        logger.info("  Unknown media type, trying FFprobe metadata extraction...")
                        parsed = self._extract_metadata_from_file(file_path)
                        if parsed:
                            media_type = "tv"
                        else:
                            error = "❌ ERROR: Could not detect media type from filename or file metadata."

                    if media_type == "tv" or media_type == "anime":
                        parsed = self.renamer.parse_tv_filename(path.name)
                        if not parsed:
                            logger.info("  Filename parsing failed, trying FFprobe metadata extraction...")
                            parsed = self._extract_metadata_from_file(file_path)

                        if not parsed:
                            error = "❌ ERROR: Could not parse TV show information from filename or file metadata."
                        else:
                            search_query = f"Title: '{parsed.get('title')}'"
                            if parsed.get('season') is not None and parsed.get('episode') is not None:
                                search_query += f", S{parsed['season']:02d}E{parsed['episode']:02d}"
                            if parsed.get('episode_title'):
                                search_query += f", Episode: '{parsed['episode_title']}'"
                            logger.info(f"  Search query: {search_query}")

                            title = parsed.get("title")
                            season = parsed.get("season")
                            episode = parsed.get("episode")

                            # Require real season/episode — never invent S01E01.
                            if season is None or episode is None:
                                logger.info(
                                    "  Skipping provider search: season/episode unknown "
                                    "(will not invent S01E01)"
                                )
                            else:
                                if selected_provider == "automatic":
                                    providers_to_try = list(TV_AUTO_PROVIDERS)
                                else:
                                    providers_to_try = [selected_provider]

                                all_provider_info = []

                                for prov in providers_to_try:
                                    prov_info = None
                                    prov_name = None

                                    try:
                                        if prov in KEYED_PROVIDERS and not self._provider_key_configured(prov):
                                            logger.debug(
                                                "Soft-skipping %s TV search (no API key)",
                                                prov,
                                            )
                                            continue

                                        if prov in (
                                            "tvmaze",
                                            "anidb",
                                            "kitsu",
                                            "jikan",
                                            "tmdb",
                                            "tvdb",
                                            "trakt",
                                            "omdb",
                                        ):
                                            prov_info = self.renamer.search_tv_show(
                                                title,
                                                season,
                                                episode,
                                                provider=prov,
                                            )
                                            if prov_info:
                                                prov_name = _PROVIDER_DISPLAY_NAMES[prov]

                                        if prov_info and prov_name:
                                            all_provider_info.append({
                                                'info': prov_info,
                                                'provider': prov_name,
                                            })
                                            file_provider_results[prov_name] = prov_info
                                            logger.info(
                                                f"  Found match via {prov_name}: "
                                                f"{prov_info.get('show_title', 'Unknown')} "
                                                f"S{prov_info.get('season', 0):02d}"
                                                f"E{prov_info.get('episode', 0):02d} - "
                                                f"{prov_info.get('episode_title', 'N/A')}"
                                            )
                                        elif prov_name:
                                            file_provider_results[prov_name] = {}
                                    except Exception as e:
                                        logger.error(f"{prov} lookup failed: {e}")
                                        if prov in _PROVIDER_DISPLAY_NAMES:
                                            file_provider_results[_PROVIDER_DISPLAY_NAMES[prov]] = {}

                                if all_provider_info:
                                    info_dicts = [item['info'] for item in all_provider_info]
                                    preferred_info = self._prefer_english_title(info_dicts)
                                    for item in all_provider_info:
                                        if item['info'] == preferred_info:
                                            info = item['info']
                                            provider = item['provider']
                                            logger.info(
                                                f"  ✓ Selected result from {provider}: "
                                                f"{info.get('show_title', 'Unknown')} "
                                                f"S{info.get('season', 0):02d}"
                                                f"E{info.get('episode', 0):02d}"
                                            )
                                            break

                                if not info:
                                    season_str = (
                                        f"S{parsed['season']:02d}"
                                        if parsed.get('season') is not None else "S??"
                                    )
                                    episode_str = (
                                        f"E{parsed['episode']:02d}"
                                        if parsed.get('episode') is not None else "E??"
                                    )
                                    logger.info(
                                        f"  No metadata found for "
                                        f"'{parsed.get('title', 'Unknown')}' "
                                        f"{season_str}{episode_str}"
                                    )
                                elif parsed.get('episode2'):
                                    info = dict(info)
                                    info['episode2'] = parsed['episode2']
                                    prov_key = {
                                        display: key
                                        for key, display in _PROVIDER_DISPLAY_NAMES.items()
                                    }.get(provider)
                                    if prov_key:
                                        try:
                                            info2 = self.renamer.search_tv_show(
                                                title, season, parsed['episode2'],
                                                provider=prov_key,
                                            )
                                            if info2 and info2.get('episode_title'):
                                                info['episode_title'] = (
                                                    f"{info.get('episode_title', '')} & "
                                                    f"{info2['episode_title']}"
                                                ).strip(' &')
                                        except Exception as e:
                                            logger.debug(
                                                f"Second-episode title lookup failed: {e}"
                                            )

                    elif media_type == "movie":
                        parsed = self.renamer.parse_movie_filename(path.name)
                        if not parsed:
                            error = "❌ ERROR: Could not parse movie information."
                        else:
                            if selected_provider == "automatic":
                                providers_to_try = list(MOVIE_AUTO_PROVIDERS)
                            else:
                                providers_to_try = [selected_provider]

                            all_provider_info = []

                            for prov in providers_to_try:
                                prov_info = None
                                prov_name = None

                                try:
                                    if prov in KEYED_PROVIDERS and not self._provider_key_configured(prov):
                                        logger.debug(
                                            "Soft-skipping %s movie search (no API key)",
                                            prov,
                                        )
                                        continue

                                    if prov in (
                                        "anidb",
                                        "kitsu",
                                        "jikan",
                                        "tmdb",
                                        "omdb",
                                        "trakt",
                                    ):
                                        prov_info = self.renamer.search_movie(
                                            parsed["title"],
                                            parsed.get("year"),
                                            provider=prov,
                                        )
                                        if prov_info:
                                            prov_name = _PROVIDER_DISPLAY_NAMES[prov]

                                    if prov_info and prov_name:
                                        all_provider_info.append({
                                            'info': prov_info,
                                            'provider': prov_name,
                                        })
                                        file_provider_results[prov_name] = prov_info
                                        logger.info(
                                            f"  Found match via {prov_name}: "
                                            f"{prov_info.get('title', 'Unknown')} "
                                            f"({prov_info.get('year', 'N/A')})"
                                        )
                                    elif prov_name:
                                        file_provider_results[prov_name] = {}
                                except Exception as e:
                                    logger.error(f"{prov} movie lookup failed: {e}")
                                    if prov in _PROVIDER_DISPLAY_NAMES:
                                        file_provider_results[_PROVIDER_DISPLAY_NAMES[prov]] = {}

                            if all_provider_info:
                                info_dicts = [item['info'] for item in all_provider_info]
                                preferred_info = self._prefer_english_title(info_dicts)
                                for item in all_provider_info:
                                    if item['info'] == preferred_info:
                                        info = item['info']
                                        provider = item['provider']
                                        logger.info(
                                            f"  ✓ Selected result from {provider}: "
                                            f"{info.get('title', 'Unknown')} "
                                            f"({info.get('year', 'N/A')})"
                                        )
                                        break

                            if not info:
                                year_str = (
                                    f" ({parsed.get('year')})"
                                    if parsed.get('year') else ""
                                )
                                logger.info(
                                    f"  No metadata found for movie "
                                    f"'{parsed['title']}'{year_str}"
                                )

                    if info:
                        logger.info(f"  ✓ Metadata found [via {provider}]")
                    elif error:
                        logger.warning(f"  {error}")
                    else:
                        logger.info("  No metadata found - leaving blank")
                    return (
                        info if info else {},
                        provider if provider else "None",
                        error if error else "",
                        file_provider_results,
                    )
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}", exc_info=True)
                    return {}, "Error", str(e), {}

            # Process files in parallel, preserving submission order.
            # Aggregate provider_metadata on the main thread to avoid races.
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(process_single_file, fp) for fp in file_paths]

            for fp, future in zip(file_paths, futures):
                try:
                    meta, prov, err, file_prov = future.result()
                except Exception as e:
                    logger.error(f"Error processing {fp}: {e}", exc_info=True)
                    meta, prov, err, file_prov = {}, "Error", str(e), {}
                suggested_metadata.append(meta)
                providers.append(prov)
                errors.append(err)
                for prov_name, prov_info in file_prov.items():
                    if prov_name not in provider_metadata:
                        provider_metadata[prov_name] = []
                    provider_metadata[prov_name].append(prov_info if prov_info else {})

            logger.info(f"=== Preview Complete: {len(suggested_metadata)} file(s) processed ===")
            logger.info(f"Provider results: {list(provider_metadata.keys())}")

            return {
                "status": "success",
                "metadata": suggested_metadata,
                "providers": providers,
                "errors": errors,
                "provider_metadata": provider_metadata,
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
    
    def rename_files(
        self,
        file_paths: List[str],
        dry_run: bool = False,
        create_backup: bool = False,
        preview_settings: Optional[Dict] = None,
    ) -> Dict:
        """
        Rename (or move/copy/link, per settings) media files using metadata.

        Filesystem work — collision detection, the overwrite guard, dry-run,
        and the backup log — all happen in core.rename_executor, shared with
        the GUI's Apply Rename so a fix here can't drift out of sync with it.

        Args:
            file_paths: List of file paths to rename
            dry_run: If True, don't actually touch the filesystem
            create_backup: If True, write a backup log usable by rename_executor.restore_from_backup
            preview_settings: Optional dict passed to preview_rename (API keys, selected_provider)

        Returns:
            Dict with status, renamed count, total count, results, and backup_file.
            `results` covers file_paths only, in order; sidecar files that were
            carried along (subtitles, .nfo) are reported separately under
            `sidecar_results` since they weren't part of the caller's request.
        """
        logger.info(f"=== Starting file renaming for {len(file_paths)} files ===")
        logger.info(f"Dry run: {dry_run}, Create backup: {create_backup}")

        preview_result = self.preview_rename(file_paths, settings_dict=preview_settings)
        if preview_result["status"] != "success":
            return {
                "status": "error",
                "message": "Failed to get metadata for files",
                "renamed": 0,
                "total": len(file_paths),
                "results": []
            }

        metadata_list = preview_result["metadata"]
        dest_root = (getattr(self.settings, 'renaming_destination_root', '') or '').strip()
        action = getattr(self.settings, 'renaming_action', 'rename') or 'rename'
        include_sidecars = getattr(self.settings, 'renaming_include_sidecars', True)

        pairs: List[RenamePair] = []
        skip_reasons: List[Optional[str]] = []  # None = has a pair; else a fixed failure to report

        for i, file_path in enumerate(file_paths):
            path = Path(file_path)
            if not path.exists():
                pairs.append(None)  # placeholder, replaced below by a synthetic failure
                skip_reasons.append(f"File not found: {file_path}")
                continue

            metadata = metadata_list[i] if i < len(metadata_list) else {}
            if not metadata:
                pairs.append(None)
                skip_reasons.append("No metadata found for file")
                continue

            media_type = self.renamer.detect_media_type(path.name)
            pattern = self.settings.renaming_pattern_tv
            if media_type == "movie":
                pattern = self.settings.renaming_pattern_movie

            new_name = self._format_filename_from_metadata(metadata, pattern, allow_subfolders=bool(dest_root))
            if not new_name:
                pairs.append(None)
                skip_reasons.append("Failed to format new filename")
                continue

            dest = self._resolve_destination(path, new_name, dest_root)
            pairs.append(RenamePair(source=path, dest=dest))
            skip_reasons.append(None)

        # Pull out the ones we couldn't even build a pair for; execute_renames
        # only ever sees real pairs.
        real_pairs = [p for p in pairs if p is not None]
        sidecar_pairs: List[RenamePair] = []
        if include_sidecars:
            for p in real_pairs:
                for sidecar in find_sidecar_files(p.source):
                    sidecar_dest = p.dest.parent / f"{p.dest.stem}{sidecar.suffix}"
                    sidecar_pairs.append(RenamePair(source=sidecar, dest=sidecar_dest, label=f"sidecar: {sidecar.name}"))

        exec_result = execute_renames(
            real_pairs + sidecar_pairs,
            action=action,
            dry_run=dry_run,
            create_backup=create_backup,
        )
        exec_results = exec_result["results"]
        video_results = exec_results[:len(real_pairs)]
        sidecar_results = exec_results[len(real_pairs):]

        # Re-interleave with the files that never made it to a pair at all.
        results: List[Dict] = []
        vi = 0
        for file_path, reason in zip(file_paths, skip_reasons):
            if reason is not None:
                results.append({
                    "original": file_path, "new_path": None,
                    "success": False, "message": reason,
                })
            else:
                results.append(video_results[vi])
                vi += 1

        success_count = sum(1 for r in results if r["success"])
        logger.info(f"=== Renaming complete: {success_count}/{len(file_paths)} files renamed ===")

        return {
            "status": "success",
            "renamed": success_count,
            "total": len(file_paths),
            "results": results,
            "sidecar_results": sidecar_results,
            "backup_file": exec_result.get("backup_file"),
        }

    def _resolve_destination(self, path: Path, new_name: str, dest_root: str) -> Path:
        """
        new_name may itself contain '/' when a destination root is set,
        describing subfolders (e.g. "Show/Season 01/Show - S01E01"); it
        never does when renaming in place, so this stays a flat sibling.
        """
        if dest_root:
            return Path(dest_root) / f"{new_name}{path.suffix}"
        return path.parent / f"{new_name}{path.suffix}"

    def _format_filename_from_metadata(
        self, metadata: Dict, pattern: str, *, allow_subfolders: bool = False
    ) -> Optional[str]:
        """
        Format filename (or relative path, if allow_subfolders) using
        metadata and pattern.

        Args:
            metadata: Metadata dictionary from provider
            pattern: Naming pattern (e.g., "{title} - S{season:02d}E{episode:02d} - {episode_title}")
            allow_subfolders: keep '/' in the pattern as a folder separator

        Returns:
            Formatted filename/relative path or None if formatting fails
        """
        from core.rename_pattern import format_filename_stem

        if not metadata:
            return None
        stem = format_filename_stem(metadata, pattern, file_stem="")
        if not stem:
            return None
        result = sanitize_filename(stem, allow_subfolders=allow_subfolders)
        return result if result else None

