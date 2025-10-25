#!/usr/bin/env python3
"""
Subtitle Handler - All subtitle-related operations
"""

import logging
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .models import ConversionSettings

logger = logging.getLogger(__name__)


class SubtitleHandler:
    """Handles all subtitle generation, search, and download operations"""
    
    def __init__(self, settings: ConversionSettings, core_or_whisper_mgr, subtitle_providers):
        logger.info("SubtitleHandler.__init__ ENTRY")
        self.settings = settings
        logger.info("SubtitleHandler.__init__ - settings assigned")
        # Support three modes: None (truly lazy), parent core, or direct whisper_mgr
        if core_or_whisper_mgr is None:
            logger.info("SubtitleHandler.__init__ - no core/whisper_mgr provided, will load lazily when needed")
            self._core = None
            self._whisper_mgr = None
            self._lazy_load = True
        elif hasattr(core_or_whisper_mgr, 'whisper_mgr'):
            logger.info("SubtitleHandler.__init__ - detected parent core, setting up lazy access")
            # It's the parent core - access whisper_mgr lazily
            self._core = core_or_whisper_mgr
            self._whisper_mgr = None
            self._lazy_load = False
        else:
            logger.info("SubtitleHandler.__init__ - using direct whisper_mgr")
            # It's whisper_mgr directly (backwards compatibility)
            self._core = None
            self._whisper_mgr = core_or_whisper_mgr
            self._lazy_load = False
        logger.info("SubtitleHandler.__init__ - assigning subtitle_providers")
        self.subtitle_providers = subtitle_providers
        logger.info("SubtitleHandler.__init__ EXIT - initialization complete")
    
    @property
    def whisper_mgr(self):
        """Lazy access to whisper_mgr"""
        if self._lazy_load and self._whisper_mgr is None:
            # Truly lazy - import and create WhisperManager only when first accessed
            logger.info("Lazy loading WhisperManager for the first time...")
            try:
                from subtitle_providers.whisper_manager import WhisperManager
                self._whisper_mgr = WhisperManager()
                logger.info("WhisperManager loaded successfully")
            except ImportError:
                logger.info("WhisperManager not available (optional feature)")
                self._whisper_mgr = None
        elif self._core is not None:
            return self._core.whisper_mgr
        return self._whisper_mgr
    
    def generate_subtitles(self, video_path: str, language: Optional[str] = None, 
                          progress_callback: Optional[Callable] = None) -> Dict:
        """Generate subtitles for a video file using Whisper AI"""
        logger.info("=== Starting Whisper AI Subtitle Generation ===")
        logger.info(f"Video: {video_path}")
        logger.info(f"Language: {language or 'auto-detect'}")
        logger.info(f"Model: {self.settings.whisper_model}")
        
        # Check if Whisper manager is available
        if self.whisper_mgr is None:
            logger.error("Whisper AI not available (optional dependencies not installed)")
            return {
                "status": "error",
                "message": "AI subtitle generation not available. Install Whisper via Tools > Setup AI Subtitles",
                "subtitle_path": None
            }
        
        # Check if Whisper is available
        whisper_status = self.whisper_mgr.get_status()
        if not whisper_status.get("installed"):
            logger.error("Whisper AI is not installed")
            return {
                "status": "error",
                "message": "Whisper AI is not installed. Please install it from Settings > Subtitles.",
                "subtitle_path": None
            }
        
        # Check if requested model is available
        installed_models = whisper_status.get("models", [])
        requested_model = self.settings.whisper_model
        
        logger.info(f"Installed Whisper models: {installed_models}")
        logger.info(f"Requested model: {requested_model}")
        
        # Fallback logic: use best available model if requested one isn't installed
        actual_model = requested_model
        if requested_model not in installed_models:
            if not installed_models:
                # No models installed at all
                available = whisper_status.get("available_models", [])
                logger.error("No Whisper models installed.")
                return {
                    "status": "error",
                    "message": f"No Whisper models are downloaded yet.\n\nPlease download a model from Settings > Subtitles.\n\nAvailable models: {', '.join(available)}",
                    "subtitle_path": None
                }
            
            # Use fallback model - prefer similar size or smaller for speed
            # Model order by size: tiny < base < small < medium < large < large-v2 < large-v3
            model_priority = {
                'tiny': ['tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3'],
                'base': ['base', 'small', 'tiny', 'medium', 'large', 'large-v2', 'large-v3'],
                'small': ['small', 'base', 'medium', 'tiny', 'large', 'large-v2', 'large-v3'],
                'medium': ['medium', 'small', 'base', 'large', 'tiny', 'large-v2', 'large-v3'],
                'large': ['large', 'large-v2', 'large-v3', 'medium', 'small', 'base', 'tiny'],
                'large-v2': ['large-v2', 'large-v3', 'large', 'medium', 'small', 'base', 'tiny'],
                'large-v3': ['large-v3', 'large-v2', 'large', 'medium', 'small', 'base', 'tiny']
            }
            
            # Get priority list for requested model, or default priority
            priority = model_priority.get(requested_model, ['base', 'small', 'medium', 'tiny', 'large', 'large-v2', 'large-v3'])
            
            # Find first available model from priority list
            for fallback in priority:
                if fallback in installed_models:
                    actual_model = fallback
                    logger.warning(f"Requested model '{requested_model}' not installed, using fallback: '{actual_model}'")
                    break
            else:
                # No suitable fallback found, use first installed model
                actual_model = installed_models[0]
                logger.warning(f"Requested model '{requested_model}' not installed, using first available: '{actual_model}'")
        else:
            logger.info(f"Using requested model: {actual_model}")
        
        try:
            # Generate output path with language code
            video_file = Path(video_path)
            lang_suffix = language if language else "auto"
            output_path = video_file.parent / f"{video_file.stem}.{lang_suffix}.srt"
            
            logger.info(f"Output subtitle path: {output_path}")
            logger.info(f"Using Whisper model: {actual_model}")
            logger.info("Starting Whisper transcription (this may take several minutes)...")
            
            success, message, subtitle_info = self.whisper_mgr.generate_subtitles(
                video_path,
                model_name=actual_model,  # Use actual_model (may be fallback)
                language=language,
                progress_callback=progress_callback
            )
            
            if success and subtitle_info:
                logger.info(f"✅ Successfully generated subtitles")
                logger.info(f"Message: {message}")
                
                # Add note if fallback model was used
                if actual_model != requested_model:
                    message = f"{message}\n\nNote: Used '{actual_model}' model (fallback) instead of '{requested_model}' which is not installed."
                
                # Return subtitle info for UI to populate Available Subtitles list
                return {
                    "status": "success",
                    "message": message,
                    "subtitle": subtitle_info  # Include full subtitle metadata
                }
            else:
                logger.error(f"❌ Failed to generate subtitles: {message}")
                return {
                    "status": "error",
                    "message": message,
                    "subtitle": None
                }
        except Exception as e:
            logger.error(f"❌ Error generating subtitles: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Failed to generate subtitles: {str(e)}",
                "subtitle_path": None
            }
    
    def search_subtitles(self, video_path: str, languages: Optional[List[str]] = None, 
                        progress_callback: Optional[Callable] = None) -> Dict:
        """Search for available subtitles without downloading"""
        try:
            logger.info("=== Starting Subtitle Search ===")
            logger.info(f"Video: {video_path}")
            
            if languages is None:
                languages = self.settings.subtitle_languages
            
            logger.info(f"Languages: {languages}")
            logger.info("Searching across multiple providers...")
            
            # Define callback wrapper for progress updates
            def handle_progress(provider_name: str, results: List[Dict], is_complete: bool):
                if progress_callback:
                    # Format results for UI
                    formatted = []
                    for result in results:
                        formatted.append({
                            "language": result.get("language", "unknown"),
                            "provider": result.get("provider", "unknown"),
                            "format": result.get("format", "srt"),
                            "download_url": result.get("download_url", ""),
                            "file_id": result.get("file_id", ""),
                            "score": result.get("score", 0),
                            "filename": result.get("file_name", ""),
                            "manual_download_only": result.get("manual_download_only", False)
                        })
                    
                    # Send progress update - ALWAYS include subtitles array (even when complete!)
                    progress_callback({
                        "progress": True,
                        "provider": provider_name,
                        "provider_complete": is_complete,  # This provider is done (stream continues)
                        "subtitles": formatted,  # Always send the results!
                        "status": "searching"  # ALWAYS "searching" during batch - only final result uses "file_complete"
                    })
            
            # Search all providers with progress callback
            results = self.subtitle_providers.search_all_providers(
                video_path, 
                languages, 
                progress_callback=handle_progress if progress_callback else None
            )
            
            logger.info(f"Found {len(results)} subtitle(s) from {len(set(r.get('provider', 'unknown') for r in results))} providers")
            
            # Log provider breakdown
            provider_counts = {}
            for r in results:
                provider = r.get('provider', 'unknown')
                provider_counts[provider] = provider_counts.get(provider, 0) + 1
            
            for provider, count in provider_counts.items():
                logger.info(f"  - {provider}: {count} subtitle(s)")
            
            # Format results for UI
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "language": result.get("language", "unknown"),
                    "provider": result.get("provider", "unknown"),
                    "format": result.get("format", "srt"),
                    "download_url": result.get("download_url", ""),
                    "file_id": result.get("file_id", ""),
                    "score": result.get("score", 0),
                    "filename": result.get("file_name", "")
                })
            
            return {
                "status": "success",
                "message": f"Found {len(results)} subtitle(s)",
                "count": len(results),
                "subtitles": formatted_results,
                "complete": True
            }
        except Exception as e:
            logger.error(f"Error searching subtitles: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Search failed: {str(e)}",
                "count": 0,
                "subtitles": []
            }
    
    def advanced_search_subtitles(self, video_path: str, languages: Optional[List[str]] = None, anilist_url: str = "") -> Dict:
        """Advanced subtitle search using multiple query variations for better results"""
        try:
            logger.info("=== Starting ADVANCED Subtitle Search ===")
            logger.info(f"Video: {video_path}")
            
            if languages is None:
                languages = self.settings.subtitle_languages
            
            logger.info(f"Languages: {languages}")
            if anilist_url:
                logger.info(f"AniList URL provided: {anilist_url}")
            logger.info("Using advanced search with multiple query variations...")
            
            # Use advanced search from subtitle providers
            results = self.subtitle_providers.advanced_search(video_path, languages, anilist_url)
            
            logger.info(f"Advanced search found {len(results)} unique subtitle(s)")
            
            # Log provider breakdown
            provider_counts = {}
            for r in results:
                provider = r.get('provider', 'unknown')
                provider_counts[provider] = provider_counts.get(provider, 0) + 1
            
            for provider, count in provider_counts.items():
                logger.info(f"  - {provider}: {count} subtitle(s)")
            
            # Format results for UI
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "language": result.get("language", "unknown"),
                    "provider": result.get("provider", "unknown"),
                    "format": result.get("format", "srt"),
                    "download_url": result.get("download_url", ""),
                    "file_id": result.get("file_id", ""),
                    "score": result.get("score", 0),
                    "filename": result.get("filename", "")
                })
            
            return {
                "status": "success",
                "message": f"Advanced search found {len(results)} unique subtitle(s)",
                "count": len(results),
                "subtitles": formatted_results
            }
        except Exception as e:
            logger.error(f"Error in advanced subtitle search: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Advanced search failed: {str(e)}",
                "count": 0,
                "subtitles": []
            }
    
    def download_subtitle(
        self,
        file_id: str,
        provider: str,
        video_path: str,
        language: str = "eng",
        download_url: str = ""
    ) -> Dict:
        """Download a specific subtitle by file_id and provider"""
        logger.info("=== Starting Subtitle Download ===")
        logger.info(f"Provider: {provider}")
        logger.info(f"File ID: {file_id}")
        logger.info(f"Language: {language}")
        
        try:
            video_file = Path(video_path)
            if not video_file.exists():
                return {
                    "status": "error",
                    "message": f"Video file not found: {video_path}"
                }
            
            # Generate output path
            output_path = str(video_file.parent / f"{video_file.stem}.{language}.srt")
            
            # Download subtitle using SubtitleProviders
            success, result = self.subtitle_providers.download_subtitle(
                file_id,
                provider,
                output_path,
                download_url
            )
            
            if success:
                logger.info(f"✅ Successfully downloaded subtitle to: {result}")
                return {
                    "status": "success",
                    "message": f"Downloaded subtitle from {provider}",
                    "subtitle_path": result,
                    "provider": provider,
                    "language": language
                }
            else:
                logger.error(f"❌ Failed to download subtitle: {result}")
                return {
                    "status": "error",
                    "message": result,
                    "provider": provider,
                    "requires_manual_download": "manual download" in result.lower()
                }
        
        except Exception as e:
            logger.error(f"Error downloading subtitle: {e}", exc_info=True)
            return {
                "status": "error",
                "message": f"Download failed: {str(e)}"
            }
    
    def download_subtitles(self, video_path: str, languages: Optional[List[str]] = None) -> Dict:
        """Search and download best matching subtitles automatically"""
        try:
            logger.info("=== Starting Auto-Download Best Subtitle ===")
            
            if languages is None:
                languages = self.settings.subtitle_languages
            
            # Search for subtitles
            search_results = self.search_subtitles(video_path, languages)
            
            if search_results["status"] != "success" or search_results["count"] == 0:
                return {
                    "status": "error",
                    "message": "No subtitles found",
                    "subtitles_downloaded": []
                }
            
            # Try to download the best subtitle for each language
            downloaded = []
            for subtitle in search_results["subtitles"]:
                result = self.download_subtitle(
                    subtitle["file_id"],
                    subtitle["provider"],
                    video_path,
                    subtitle["language"],
                    subtitle.get("download_url", "")
                )
                
                if result["status"] == "success":
                    downloaded.append(result)
                    break  # Successfully downloaded, stop
            
            if downloaded:
                return {
                    "status": "success",
                    "message": f"Downloaded {len(downloaded)} subtitle(s)",
                    "subtitles_downloaded": downloaded
                }
            else:
                return {
                    "status": "error",
                    "message": "Failed to download any subtitles",
                    "subtitles_downloaded": []
                }
                
        except Exception as e:
            logger.error(f"Error in download_subtitles: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e),
                "subtitles_downloaded": []
            }
    
    def apply_subtitles(
        self,
        video_path: str,
        subtitle_paths: List[str],
        output_path: Optional[str] = None,
        mode: str = "external",  # "external", "embed", or "burn-in"
        language: str = "eng",
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        Apply subtitles to video file
        
        Args:
            video_path: Path to video file
            subtitle_paths: List of subtitle file paths (local files or URLs to download)
            output_path: Output path (None for auto-generate)
            mode: "external" (copy to same dir), "embed" (soft subs), or "burn-in" (hard subs)
            language: Language code for subtitle track
            progress_callback: Progress callback function
            
        Returns:
            Dict with status, message, and output_path
        """
        try:
            logger.info("=== Applying Subtitles to Video ===")
            logger.info(f"Video: {video_path}")
            logger.info(f"Mode: {mode}")
            logger.info(f"Language: {language}")
            
            video_file = Path(video_path)
            if not video_file.exists():
                return {"status": "error", "message": "Video file not found"}
            
            if not subtitle_paths:
                return {"status": "error", "message": "No subtitle files provided"}
            
            # Handle subtitle paths - check if local files or need download
            local_subtitle_paths = []
            for sub_path in subtitle_paths:
                if Path(sub_path).exists():
                    # Already a local file (AI-generated or previously downloaded)
                    logger.info(f"Using local subtitle file: {sub_path}")
                    local_subtitle_paths.append(sub_path)
                else:
                    # Assume it's a download URL or file_id - would need download logic here
                    logger.warning(f"Subtitle path not found locally: {sub_path}")
                    return {"status": "error", "message": f"Subtitle file not found: {sub_path}"}
            
            if not local_subtitle_paths:
                return {"status": "error", "message": "No valid subtitle files found"}
            
            subtitle_file = local_subtitle_paths[0]  # Use first subtitle
            
            # Handle different modes
            if mode == "external":
                # Simply copy subtitle to video directory
                output_sub_path = video_file.parent / f"{video_file.stem}.{language}.srt"
                import shutil
                shutil.copy2(subtitle_file, output_sub_path)
                
                logger.info(f"✅ External subtitle copied to: {output_sub_path}")
                return {
                    "status": "success",
                    "message": "Subtitle file created successfully",
                    "output_path": str(output_sub_path),
                    "mode": "external"
                }
            
            elif mode == "embed":
                # Embed subtitle as soft subtitle stream (no re-encoding)
                if output_path is None:
                    output_path = str(video_file.parent / f"{video_file.stem}.with_subs{video_file.suffix}")
                
                return self._embed_subtitles_ffmpeg(video_path, subtitle_file, output_path, language, progress_callback)
            
            elif mode == "burn-in":
                # Burn subtitles into video (requires re-encoding)
                if output_path is None:
                    output_path = str(video_file.parent / f"{video_file.stem}.burned{video_file.suffix}")
                
                return self._burn_in_subtitles_ffmpeg(video_path, subtitle_file, output_path, progress_callback)
            
            else:
                return {"status": "error", "message": f"Unknown mode: {mode}"}
                
        except Exception as e:
            logger.error(f"Error applying subtitles: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _embed_subtitles_ffmpeg(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
        language: str = "eng",
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        Embed subtitles as soft subtitle stream (no re-encoding)
        
        Args:
            video_path: Path to input video
            subtitle_path: Path to subtitle file
            output_path: Path to output video
            language: Language code for subtitle track
            progress_callback: Progress callback function
            
        Returns:
            Dict with status, message, and output_path
        """
        try:
            if progress_callback:
                progress_callback({
                    "status": "processing",
                    "progress": 0,
                    "message": "Embedding subtitles..."
                })
            
            # Build FFmpeg command for embedding (fast, no re-encoding)
            cmd = [
                "ffmpeg",
                "-i", video_path,      # Input video
                "-i", subtitle_path,    # Input subtitle
                "-c", "copy",           # Copy all streams without re-encoding
                "-c:s", "mov_text",     # Subtitle codec (mov_text for MP4, srt for MKV)
                "-metadata:s:s:0", f"language={language}",  # Set subtitle language
                "-y",                   # Overwrite output file
                output_path
            ]
            
            logger.info(f"Running: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                if progress_callback:
                    progress_callback({
                        "status": "complete",
                        "progress": 100,
                        "message": "Subtitles embedded successfully"
                    })
                
                logger.info(f"✅ Successfully embedded subtitles to: {output_path}")
                return {
                    "status": "success",
                    "message": "Subtitles embedded successfully",
                    "output_path": output_path,
                    "mode": "embed"
                }
            else:
                logger.error(f"❌ Failed to embed subtitles: {stderr}")
                return {
                    "status": "error",
                    "message": f"FFmpeg error: {stderr}"
                }
                
        except Exception as e:
            logger.error(f"Error embedding subtitles: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }
    
    def _burn_in_subtitles_ffmpeg(
        self,
        video_path: str,
        subtitle_path: str,
        output_path: str,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """
        Burn subtitles into video (hardcode, requires re-encoding)
        
        Args:
            video_path: Path to input video
            subtitle_path: Path to subtitle file
            output_path: Path to output video
            progress_callback: Progress callback function
            
        Returns:
            Dict with status, message, and output_path
        """
        try:
            if progress_callback:
                progress_callback({
                    "status": "processing",
                    "progress": 0,
                    "message": "Burning subtitles into video (this may take a while)..."
                })
            
            # Escape subtitle path for FFmpeg filter (Windows paths with backslashes)
            # Replace backslashes with forward slashes and escape special chars
            sub_filter_path = subtitle_path.replace('\\', '/').replace(':', '\\:')
            
            # Build FFmpeg command for burn-in (slow, re-encodes video)
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vf", f"subtitles='{sub_filter_path}'",  # Video filter to burn subtitles
                "-c:a", "copy",         # Copy audio without re-encoding
                "-y",                   # Overwrite output file
                output_path
            ]
            
            logger.info(f"Running: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # For burn-in, we could parse FFmpeg progress from stderr
            # but for now just wait for completion
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                if progress_callback:
                    progress_callback({
                        "status": "complete",
                        "progress": 100,
                        "message": "Subtitles burned into video successfully"
                    })
                
                logger.info(f"✅ Successfully burned subtitles to: {output_path}")
                return {
                    "status": "success",
                    "message": "Subtitles burned into video successfully",
                    "output_path": output_path,
                    "mode": "burn-in"
                }
            else:
                logger.error(f"❌ Failed to burn-in subtitles: {stderr}")
                return {
                    "status": "error",
                    "message": f"FFmpeg error: {stderr}"
                }
                
        except Exception as e:
            logger.error(f"Error burning subtitles: {e}", exc_info=True)
            return {
                "status": "error",
                "message": str(e)
            }

