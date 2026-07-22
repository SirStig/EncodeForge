#!/usr/bin/env python3
"""
Multi-provider subtitle search and download orchestrator
Uses modular provider implementations
"""

import logging
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.providers.subtitle import (
    Addic7edProvider,
    JimakuProvider,
    OpenSubtitlesManager,
    PodnapisiProvider,
    SubDivXProvider,
    SubDLProvider,
    Subf2mProvider,
    YifyProvider
)

logger = logging.getLogger(__name__)


class SubtitleProviders:
    """Orchestrates multiple subtitle providers"""
    
    def __init__(self, opensubtitles_key: str = "", username: str = "", password: str = ""):
        """
        Initialize subtitle providers.
        
        Args:
            opensubtitles_key: DEPRECATED - Consumer API key is now hardcoded
            username: OpenSubtitles username (for user login to get higher quotas)
            password: OpenSubtitles password (for user login to get higher quotas)
        """
        self.opensubtitles = OpenSubtitlesManager(api_key=opensubtitles_key, username=username, password=password)

        # Initialize modular providers
        self.yify = YifyProvider()
        self.addic7ed = Addic7edProvider()
        self.subdl = SubDLProvider()
        self.subf2m = Subf2mProvider()
        self.jimaku = JimakuProvider()
        self.podnapisi = PodnapisiProvider()
        self.subdivx = SubDivXProvider()

        self.providers = [
            "OpenSubtitles.com", "Addic7ed", "SubDL", "Subf2m",
            "YIFY", "Podnapisi", "SubDivX", "Jimaku"
        ]
        # None means "no restriction". Set enabled_providers to honour a user's
        # provider selection; anything not listed is skipped entirely.
        self.enabled_providers: Optional[List[str]] = None
        self.session_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def is_provider_enabled(self, provider_name: str) -> bool:
        """
        Report whether a provider should be queried.

        Matching is loose so UI labels ("OpenSubtitles") still select the
        internal name ("OpenSubtitles.com").
        """
        if not self.enabled_providers:
            return True

        target = provider_name.lower().replace(".com", "").strip()
        for enabled in self.enabled_providers:
            candidate = str(enabled).lower().replace(".com", "").strip()
            if candidate in ("all", target) or target in candidate:
                return True
        return False

    def _search_opensubtitles(self, video_path: str, lang_codes: List[str]) -> List[Dict]:
        """Adapter giving OpenSubtitles the same signature as the scrapers."""
        if not self.opensubtitles:
            logger.info("  OpenSubtitles.com: Not configured (no API key)")
            return []
        success, results = self.opensubtitles.search_subtitles(video_path, lang_codes)
        return results if (success and results) else []

    def extract_media_metadata(self, file_path: str) -> Dict:
        """
        Use the base provider's metadata extraction
        (Kept here for backward compatibility with existing code)
        """
        return self.yify.extract_media_metadata(file_path)
        
    def calculate_hash(self, file_path: str) -> Optional[str]:
        """Calculate OpenSubtitles hash for a video file"""
        try:
            longlongformat = '<q'
            bytesize = struct.calcsize(longlongformat)
            
            with open(file_path, "rb") as f:
                filesize = Path(file_path).stat().st_size
                hash_value = filesize
                
                if filesize < 65536 * 2:
                    return None
                
                # Read first 64kb
                for _ in range(65536 // bytesize):
                    buffer = f.read(bytesize)
                    (l_value,) = struct.unpack(longlongformat, buffer)
                    hash_value += l_value
                    hash_value &= 0xFFFFFFFFFFFFFFFF
                
                # Read last 64kb
                f.seek(max(0, filesize - 65536), 0)
                for _ in range(65536 // bytesize):
                    buffer = f.read(bytesize)
                    (l_value,) = struct.unpack(longlongformat, buffer)
                    hash_value += l_value
                    hash_value &= 0xFFFFFFFFFFFFFFFF
                
                return "%016x" % hash_value
        except Exception as e:
            logger.error(f"Error calculating hash: {e}")
            return None
    
    def search_opensubs_com(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search OpenSubtitles.org free API (deprecated)"""
        logger.info("OpenSubtitles.org free API is deprecated - skipping")
        return []
    
    def search_yifysubtitles(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search YIFY Subtitles"""
        return self.yify.search(video_path, languages)
    
    def search_addic7ed(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search Addic7ed"""
        return self.addic7ed.search(video_path, languages)
    
    def search_subdl(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search SubDL"""
        return self.subdl.search(video_path, languages)
    
    def search_subf2m(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search Subf2m"""
        return self.subf2m.search(video_path, languages)
    
    def search_jimaku(self, video_path: str, languages: List[str], anilist_url: str = "") -> List[Dict]:
        """Search Jimaku"""
        return self.jimaku.search(video_path, languages, anilist_url)
    
    def search_podnapisi(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search Podnapisi"""
        return self.podnapisi.search(video_path, languages)
    
    def search_subdivx(self, video_path: str, languages: List[str]) -> List[Dict]:
        """Search SubDivX"""
        return self.subdivx.search(video_path, languages)
    
    def advanced_search(self, video_path: str, languages: List[str], anilist_url: str = "") -> List[Dict]:
        """Advanced subtitle search with multiple query variations"""
        logger.info(f"=== ADVANCED SEARCH for: {Path(video_path).name} ===")
        
        all_results = []
        seen_file_ids = set()
        
        metadata = self.extract_media_metadata(video_path)
        
        for i, query in enumerate(metadata['search_queries'], 1):
            logger.info(f"→ Advanced search attempt {i}/{len(metadata['search_queries'])}: '{query}'")
            temp_path = str(Path(video_path).parent / f"{query}{Path(video_path).suffix}")
            results = self.search_all_providers(temp_path, languages)
            
            for result in results:
                file_id = result.get('file_id', '')
                if file_id and file_id not in seen_file_ids:
                    seen_file_ids.add(file_id)
                    all_results.append(result)
        
        if anilist_url:
            logger.info("→ Advanced search: Trying Jimaku with AniList URL")
            jimaku_results = self.search_jimaku(video_path, languages, anilist_url)
            for result in jimaku_results:
                file_id = result.get('file_id', '')
                if file_id and file_id not in seen_file_ids:
                    seen_file_ids.add(file_id)
                    all_results.append(result)
        
        all_results = self._rank_subtitles(all_results)
        logger.info(f"=== ADVANCED SEARCH COMPLETE: Total {len(all_results)} unique subtitle(s) found ===")
        
        return all_results
    
    def search_all_providers(self, video_path: str, languages: List[str], progress_callback=None) -> List[Dict]:
        """
        Search all providers and aggregate results
        
        Args:
            video_path: Path to video file
            languages: List of language codes
            progress_callback: Optional callback function(provider_name, results, is_complete)
                             Called after each provider finishes with incremental results
        
        Returns:
            List of all subtitle results
        """
        logger.info(f"=== Searching ALL Providers for: {Path(video_path).name} ===")
        logger.info(f"Languages: {languages}")
        all_results = []

        # Normalize to 3-letter ISO 639-2 codes used internally
        _lang2_to_3 = {
            'en': 'eng', 'es': 'spa', 'fr': 'fre', 'de': 'ger', 'it': 'ita',
            'pt': 'por', 'ru': 'rus', 'ar': 'ara', 'zh': 'chi', 'ja': 'jpn',
            'ko': 'kor', 'hi': 'hin', 'th': 'tha', 'vi': 'vie', 'tr': 'tur',
            'pl': 'pol', 'nl': 'dut', 'sv': 'swe', 'no': 'nor', 'da': 'dan',
            'fi': 'fin', 'cs': 'cze', 'el': 'gre', 'he': 'heb', 'hu': 'hun',
            'ro': 'rum', 'id': 'ind', 'ms': 'may', 'fa': 'per', 'uk': 'ukr',
            'bg': 'bul', 'hr': 'hrv', 'sr': 'srp', 'sl': 'slv', 'lt': 'lit',
            'lv': 'lav',
        }
        lang_codes = []
        for lang in languages:
            if len(lang) == 2:
                lang_codes.append(_lang2_to_3.get(lang.lower(), lang))
            else:
                lang_codes.append(lang)
        lang_codes = list(dict.fromkeys(lang_codes))  # deduplicate, preserve order

        logger.info(f"Normalized language codes: {lang_codes}")
        
        # Each provider is (display name, search callable, only-if predicate).
        # This replaced eight near-identical copy-pasted blocks; adding or
        # disabling a provider is now a one-line change.
        provider_specs = [
            ("OpenSubtitles.com", self._search_opensubtitles, None),
            ("Addic7ed", self.search_addic7ed, None),
            ("SubDL", self.search_subdl, None),
            ("Subf2m", self.search_subf2m, None),
            ("YIFY", self.search_yifysubtitles, None),
            ("Podnapisi", self.search_podnapisi, None),
            # SubDivX is a Spanish-language site; querying it otherwise is waste.
            ("SubDivX", self.search_subdivx,
             lambda codes: any(c in codes for c in ("spa", "es", "es-MX"))),
            ("Jimaku", self.search_jimaku, None),
        ]

        for name, search_fn, predicate in provider_specs:
            if not self.is_provider_enabled(name):
                logger.info(f"→ Skipping {name} (disabled in settings)")
                continue
            if predicate and not predicate(lang_codes):
                logger.debug(f"→ Skipping {name} (not applicable to {lang_codes})")
                continue

            logger.info(f"→ Searching {name}...")
            if progress_callback:
                progress_callback(name, all_results.copy(), False)  # Notify start

            try:
                provider_results = search_fn(video_path, lang_codes) or []
                logger.info(f"  {name} returned {len(provider_results)} results")
                for result in provider_results:
                    result.setdefault("provider", name)
                all_results.extend(provider_results)

                if provider_results:
                    logger.info(f"  \u2705 {name}: Found {len(provider_results)} subtitles")
                    if progress_callback:
                        progress_callback(name, self._rank_subtitles(all_results.copy()), False)
                else:
                    logger.info(f"  \u26a0\ufe0f {name}: No results")
            except Exception as e:
                logger.error(f"  \u274c {name} search failed: {e}")

        logger.info(f"=== SEARCH COMPLETE: Total {len(all_results)} subtitle(s) from {len(set(r.get('provider', 'unknown') for r in all_results))} provider(s) ===")
        
        if all_results:
            # Calculate scores and rank results
            all_results = self._rank_subtitles(all_results)
            
            # Log provider breakdown
            provider_counts = {}
            for r in all_results:
                provider = r.get('provider', 'unknown')
                provider_counts[provider] = provider_counts.get(provider, 0) + 1
            logger.info("Provider breakdown:")
            for provider, count in provider_counts.items():
                logger.info(f"  - {provider}: {count}")
            
            logger.info(f"✅ Top ranked subtitle: {all_results[0].get('provider')} - {all_results[0].get('file_name')} (score: {all_results[0].get('score', 0)})")
        else:
            logger.warning("No subtitles found from any provider!")
        
        # Send final update
        if progress_callback:
            progress_callback("Complete", all_results, True)
        
        return all_results
    
    def _rank_subtitles(self, results: List[Dict]) -> List[Dict]:
        """Rank and score subtitle results based on multiple factors"""
        for result in results:
            score = 0.0
            
            provider = result.get('provider', 'unknown')
            provider_scores = {
                "OpenSubtitles.com": 100,
                "Addic7ed": 90,
                "Jimaku": 85,
                "SubDL": 85,
                "Podnapisi": 80,
                "Subf2m": 70,
                "YIFY": 65,
                "SubDivX": 60,
            }
            score += provider_scores.get(provider, 50)
            
            downloads = result.get('downloads', 0)
            if downloads > 0:
                score += min(20, downloads / 100)
            
            rating = result.get('rating', 0.0)
            score += rating
            
            format_type = result.get('format', 'srt').lower()
            if format_type == 'ass':
                score += 5
            elif format_type == 'srt':
                score += 3
            
            result['score'] = round(score, 2)
        
        results.sort(key=lambda x: x.get('score', 0), reverse=True)
        return results
    
    def download_subtitle(self, file_id: str, provider: str, output_path: str, download_url: str = "") -> Tuple[bool, str]:
        """Download a specific subtitle by file_id and provider"""
        try:
            logger.info(f"Downloading subtitle from {provider}: {file_id}")
            logger.info(f"Output path: {output_path}")
            
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            
            if provider == "OpenSubtitles.com":
                if isinstance(file_id, str) and file_id.isdigit():
                    file_id_int = int(file_id)
                else:
                    file_id_int = int(file_id) if isinstance(file_id, int) else 0
                success, message = self.opensubtitles.download_subtitle(file_id_int, output_path)
                if success:
                    logger.info(f"✅ Successfully downloaded from OpenSubtitles: {output_path}")
                    return True, output_path
                else:
                    logger.error(f"❌ OpenSubtitles download failed: {message}")
                    return False, message
            
            elif provider == "Addic7ed":
                return self.addic7ed.download(file_id, download_url, output_path)
            
            elif provider == "Jimaku":
                return self.jimaku.download(file_id, download_url, output_path)
            
            elif provider == "SubDL":
                return self.subdl.download(file_id, download_url, output_path)
            
            elif provider == "YIFY":
                return self.yify.download(file_id, download_url, output_path)
            
            elif provider == "Podnapisi":
                return self.podnapisi.download(file_id, download_url, output_path)
            
            elif provider == "SubDivX":
                return self.subdivx.download(file_id, download_url, output_path)
            
            elif provider == "Subf2m":
                return self.subf2m.download(file_id, download_url, output_path)
            
            else:
                return False, f"Download not implemented for provider: {provider}"
                
        except Exception as e:
            logger.error(f"Error downloading subtitle: {e}", exc_info=True)
            return False, f"Download error: {str(e)}"
    
    def download_best_subtitle(self, video_path: str, language: str = "en") -> Tuple[bool, Optional[str]]:
        """Download best subtitle from any provider"""
        results = self.search_all_providers(video_path, [language])
        
        if not results:
            logger.warning(f"No subtitles found for {video_path}")
            return False, None
        
        for subtitle in results:
            try:
                provider = subtitle.get("provider", "unknown")
                logger.info(f"Attempting to download from {provider}: {subtitle.get('file_name', 'unknown')}")
                
                video_file = Path(video_path)
                lang_code = subtitle.get("language", language)
                output_path = str(video_file.parent / f"{video_file.stem}.{lang_code}.srt")
                
                success, result = self.download_subtitle(
                    subtitle["file_id"],
                    provider,
                    output_path,
                    subtitle.get("download_url", "")
                )
                
                if success:
                    logger.info(f"✅ Successfully downloaded: {result}")
                    return True, result
                else:
                    logger.warning(f"⚠️ {provider} download failed: {result}")
                    continue
                
            except Exception as e:
                logger.error(f"Error downloading from {subtitle.get('provider')}: {e}")
                continue
        
        logger.error("All subtitle download attempts failed")
        return False, None
    
    def batch_download(self, video_paths: List[str], languages: List[str]) -> Dict:
        """Download subtitles for multiple files"""
        results = {
            "success": [],
            "failed": [],
            "skipped": []
        }
        
        for video_path in video_paths:
            for language in languages:
                success, subtitle_path = self.download_best_subtitle(video_path, language)
                
                if success:
                    results["success"].append({
                        "video": video_path,
                        "subtitle": subtitle_path,
                        "language": language
                    })
                else:
                    results["failed"].append({
                        "video": video_path,
                        "language": language
                    })
        
        return results


def main():
    """Test subtitle providers"""
    import sys
    
    if len(sys.argv) < 2:
        logger.error("Usage: python subtitle_providers.py <video_file>")
        return
    
    video_file = sys.argv[1]
    providers = SubtitleProviders()
    
    logger.info(f"Searching subtitles for: {Path(video_file).name}")
    results = providers.search_all_providers(video_file, ["en", "es"])
    
    logger.info(f"Found {len(results)} subtitle(s)")
    for i, result in enumerate(results, 1):
        logger.info(f"{i}. {result.get('file_name', 'Unknown')} - Provider: {result.get('provider', 'Unknown')} - Language: {result.get('language', 'Unknown')} - Downloads: {result.get('downloads', 0)} - Rating: {result.get('rating', 0)}")


if __name__ == "__main__":
    try:
        from utils.logging_config import setup_logging
        setup_logging()
    except ImportError:
        logging.basicConfig(level=logging.INFO)
    main()
