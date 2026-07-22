#!/usr/bin/env python3
"""
EncodeForge Core - Main orchestrator for all encoding operations
Lightweight orchestrator that delegates to specialized handlers
"""

import logging
import threading
from copy import deepcopy
from dataclasses import asdict
from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from core.handlers import (
    ConversionHandler,
    ConversionSettings,
    FileHandler,
    RenamingHandler,
    SubtitleHandler,
)
from core.ffmpeg_manager import FFmpegManager
from core.metadata_grabber import MetadataGrabber
from core.profile_manager import ProfileManager
from core.subtitle_manager import SubtitleProviders

# Setup logging
try:
    from utils.logging_config import setup_logging
    setup_logging()
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)


class EncodeForgeCore:
    """
    Main EncodeForge orchestrator
    Delegates operations to specialized handlers:
    - FileHandler: File info and scanning
    - SubtitleHandler: Subtitle operations
    - RenamingHandler: File renaming
    - ConversionHandler: Video conversion
    """
    
    def __init__(self, settings: Optional[ConversionSettings] = None):
        self.settings = settings or ConversionSettings()
        
        # Thread lock for handler initialization (prevents race conditions in parallel batch operations)
        self._init_lock = threading.Lock()
        self._handlers_initialized = False
        
        # Initialize managers
        self.ffmpeg_mgr = FFmpegManager(self.settings.ffmpeg_path)
        
        # Whisper manager initialized lazily (allows detection after installation)
        self._whisper_mgr = None
        self._whisper_checked = False
        
        self.renamer = MetadataGrabber(
            tmdb_key=self.settings.tmdb_api_key,
            tvdb_key=self.settings.tvdb_api_key
        )
        self.subtitle_providers = SubtitleProviders(
            opensubtitles_key=self.settings.opensubtitles_api_key,
            username=self.settings.opensubtitles_username,
            password=self.settings.opensubtitles_password
        )
        self.profile_mgr = ProfileManager()
        
        # Skip expensive FFmpeg detection during initialization for faster startup
        # FFmpeg will be detected on first use (lazy detection)
    
    @property
    def whisper_mgr(self):
        """Lazy initialization of Whisper manager - checks at runtime"""
        if not self._whisper_checked:
            try:
                from core.providers.subtitle.whisper_manager import WhisperManager
                self._whisper_mgr = WhisperManager()
                logger.info("Whisper AI available for subtitle generation")
            except ImportError:
                self._whisper_mgr = None
                logger.info("Whisper not available (optional AI subtitle feature)")
            self._whisper_checked = True
        return self._whisper_mgr
    
    def reset_whisper_check(self):
        """Force re-check of Whisper availability (useful after installation)"""
        self._whisper_checked = False
        self._whisper_mgr = None
        logger.info("Whisper check reset - will re-detect on next access")
    
    def _ensure_handlers_initialized(self):
        """Lazy initialize handlers (called before first use) - Thread-safe for parallel operations"""
        # Quick check without lock (performance optimization)
        if self._handlers_initialized:
            return
        
        # Acquire lock for initialization
        with self._init_lock:
            # Double-check after acquiring lock (another thread may have initialized)
            if self._handlers_initialized:
                return
            
            logger.info("Initializing EncodeForge handlers")
            try:
                logger.info("Creating FileHandler...")
                self.file_handler = FileHandler(self.settings, self.ffmpeg_mgr)
                logger.info("FileHandler created successfully")
                
                logger.info("Creating SubtitleHandler...")
                logger.info("About to call SubtitleHandler constructor...")
                # Pass None instead of self to avoid triggering lazy whisper_mgr loading during handler init
                # SubtitleHandler will get whisper_mgr from the parent later when actually needed
                self.subtitle_handler = SubtitleHandler(self.settings, None, self.subtitle_providers)
                logger.info("SubtitleHandler constructor returned")
                logger.info("SubtitleHandler created successfully")
                
                logger.info("Creating RenamingHandler...")
                self.renaming_handler = RenamingHandler(self.settings, self.renamer)
                logger.info("RenamingHandler created successfully")
                
                logger.info("Creating ConversionHandler...")
                self.conversion_handler = ConversionHandler(self.settings, self.ffmpeg_mgr)
                logger.info("ConversionHandler created successfully")
                
                # Mark as initialized (must be last step)
                self._handlers_initialized = True
                logger.info("All handlers initialized successfully")
            except Exception as e:
                logger.error(f"Error initializing handlers: {e}", exc_info=True)
                raise
    
    # ======================
    # FFmpeg & Whisper Setup
    # ======================
    
    def check_ffmpeg(self) -> Dict:
        """Check FFmpeg availability"""
        success, info = self.ffmpeg_mgr.detect_ffmpeg()
        
        if success:
            self.settings.ffmpeg_path = str(info["ffmpeg_path"])
            self.settings.ffprobe_path = str(info["ffprobe_path"])
            
            hwaccel = self.ffmpeg_mgr.get_hwaccel_options()
            
            return {
                "status": "success",
                "ffmpeg_available": True,
                "ffmpeg_version": info["version"],
                "ffmpeg_path": info["ffmpeg_path"],
                "ffprobe_path": info["ffprobe_path"],
                "hardware_encoders": info["encoders"],
                "hardware_decoders": info["decoders"],
                "hwaccel_options": hwaccel
            }
        else:
            return {
                "status": "error",
                "ffmpeg_available": False,
                "message": info.get("error", "FFmpeg not found")
            }
    
    def check_whisper(self) -> Dict:
        """Check Whisper availability"""
        if self.whisper_mgr is None:
            return {
                "status": "success",
                "whisper_available": False,
                "installed_models": [],
                "available_models": [],
                "model_sizes": {}
            }
        
        status = self.whisper_mgr.get_status()
        return {
            "status": "success",
            "whisper_available": status["installed"],
            "installed_models": status["models"],
            "available_models": status["available_models"],
            "model_sizes": status["model_sizes"]
        }
    
    def download_ffmpeg(self, progress_callback: Optional[Callable] = None) -> Dict:
        """Download and install FFmpeg"""
        success, message = self.ffmpeg_mgr.download_ffmpeg(progress_callback=progress_callback)
        return {
            "status": "success" if success else "error",
            "message": message
        }
    
    def install_whisper(self, progress_callback: Optional[Callable] = None) -> Dict:
        """Install Whisper"""
        if self.whisper_mgr is None:
            return {
                "status": "error",
                "message": "Whisper not available. Please install required dependencies."
            }
        
        success, message = self.whisper_mgr.install_whisper(progress_callback=progress_callback)
        return {
            "status": "success" if success else "error",
            "message": message
        }
    
    def download_whisper_model(self, model: str, progress_callback: Optional[Callable] = None) -> Dict:
        """Download a Whisper model"""
        if self.whisper_mgr is None:
            return {
                "status": "error",
                "message": "Whisper not available. Please install required dependencies."
            }
        
        success, message = self.whisper_mgr.download_model(model, progress_callback=progress_callback)
        return {
            "status": "success" if success else "error",
            "message": message
        }
    
    # ==================
    # File Operations
    # ==================
    
    def get_file_info(self, file_path: str) -> Dict:
        """Get basic file information"""
        self._ensure_handlers_initialized()
        return self.file_handler.get_file_info(file_path)
    
    def get_media_info(self, file_path: str) -> Dict:
        """Get detailed media information"""
        self._ensure_handlers_initialized()
        return self.file_handler.get_media_info(file_path)
    
    def scan_directory(self, directory: str, recursive: bool = True,
                      progress_callback: Optional[Callable] = None) -> Dict:
        """Scan directory for media files"""
        self._ensure_handlers_initialized()
        return self.file_handler.scan_directory(directory, recursive, progress_callback)
    
    # ====================
    # Subtitle Operations
    # ====================
    
    def generate_subtitles(self, video_path: str, language: Optional[str] = None,
                          progress_callback: Optional[Callable] = None) -> Dict:
        """Generate subtitles using Whisper AI"""
        self._ensure_handlers_initialized()
        return self.subtitle_handler.generate_subtitles(video_path, language, progress_callback)
    
    def search_subtitles(self, video_path: str, languages: Optional[List[str]] = None,
                        progress_callback: Optional[Callable] = None) -> Dict:
        """Search for available subtitles"""
        self._ensure_handlers_initialized()
        return self.subtitle_handler.search_subtitles(video_path, languages, progress_callback)
    
    def advanced_search_subtitles(self, video_path: str, languages: Optional[List[str]] = None, 
                                  anilist_url: str = "") -> Dict:
        """Advanced subtitle search with multiple query variations"""
        self._ensure_handlers_initialized()
        return self.subtitle_handler.advanced_search_subtitles(video_path, languages, anilist_url)
    
    def download_subtitle(self, file_id: str, provider: str, video_path: str,
                         language: str = "eng", download_url: str = "") -> Dict:
        """Download a specific subtitle"""
        self._ensure_handlers_initialized()
        return self.subtitle_handler.download_subtitle(file_id, provider, video_path, language, download_url)
    
    def download_subtitles(self, video_path: str, languages: Optional[List[str]] = None) -> Dict:
        """Download best matching subtitles automatically"""
        self._ensure_handlers_initialized()
        return self.subtitle_handler.download_subtitles(video_path, languages)
    
    def apply_subtitles(self, video_path: str, subtitle_paths: List[str],
                       output_path: Optional[str] = None, mode: str = "external",
                       language: str = "eng", progress_callback: Optional[Callable] = None) -> Dict:
        """
        Apply subtitles to video
        
        Args:
            video_path: Path to video file
            subtitle_paths: List of subtitle file paths
            output_path: Output path (None for auto-generate)
            mode: "external" (copy to same dir), "embed" (soft subs), or "burn-in" (hard subs)
            language: Language code for subtitle track
            progress_callback: Progress callback function
        """
        self._ensure_handlers_initialized()
        return self.subtitle_handler.apply_subtitles(video_path, subtitle_paths, output_path, 
                                                     mode, language, progress_callback)
    
    # ===================
    # Renaming Operations
    # ===================
    
    def preview_rename(self, file_paths: List[str], settings_dict: Optional[Dict] = None) -> Dict:
        """Preview how files would be renamed"""
        self._ensure_handlers_initialized()
        return self.renaming_handler.preview_rename(file_paths, settings_dict)
    
    def rename_files(
        self,
        file_paths: List[str],
        dry_run: bool = False,
        create_backup: bool = False,
        preview_settings: Optional[Dict] = None,
    ) -> Dict:
        """Rename media files using metadata"""
        self._ensure_handlers_initialized()
        return self.renaming_handler.rename_files(
            file_paths, dry_run, create_backup, preview_settings=preview_settings
        )
    
    # =======================
    # Conversion Operations
    # =======================
    
    def convert_file(self, input_path: str, output_path: Optional[str] = None,
                    progress_callback: Optional[Callable] = None) -> Dict:
        """Convert a single video file"""
        self._ensure_handlers_initialized()
        return self.conversion_handler.convert_file(input_path, output_path, progress_callback)
    
    def convert_files(self, file_paths: List[str], progress_callback: Optional[Callable] = None) -> Dict:
        """Convert multiple files"""
        logger.info(f"EncodeForgeCore.convert_files called with {len(file_paths)} files")
        self._ensure_handlers_initialized()
        logger.info("Handlers initialized, calling conversion_handler.convert_files")
        result = self.conversion_handler.convert_files(file_paths, progress_callback)
        logger.info(f"conversion_handler.convert_files returned: {result}")
        return result
    
    def cancel_current(self) -> Dict:
        """Cancel current conversion"""
        self._ensure_handlers_initialized()
        return self.conversion_handler.cancel_current()
    
    # ==================
    # Profile Management
    # ==================
    
    def save_profile(self, name: str, settings=None) -> Dict:
        """
        Save a conversion profile.

        Args:
            name: Profile name
            settings: A ConversionSettings instance, or a dict of overrides.
                Defaults to the current settings.

        ProfileManager.save_profile calls dataclasses.asdict(), which raises on
        a plain dict — so passing one used to fail every save.
        """
        if settings is None:
            settings = self.settings
        elif isinstance(settings, dict):
            merged = deepcopy(self.settings)
            for key, value in settings.items():
                if hasattr(merged, key):
                    setattr(merged, key, value)
            settings = merged

        success = self.profile_mgr.save_profile(name, settings)
        return {
            "status": "success" if success else "error",
            "message": f"Profile '{name}' saved" if success else "Failed to save profile"
        }

    def load_profile(self, name: str) -> Dict:
        """
        Load a conversion profile and apply it to the current settings.

        ProfileManager returns a ConversionSettings instance, so the previous
        `isinstance(profile, dict)` guard was never true and the loaded profile
        was reported as applied without changing anything.
        """
        profile = self.profile_mgr.load_profile(name)
        if not profile:
            return {
                "status": "error",
                "message": f"Profile '{name}' not found"
            }

        if isinstance(profile, dict):
            applied = profile
        else:
            applied = asdict(profile)

        for key, value in applied.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)

        # Return a JSON-serialisable view rather than the dataclass itself.
        return {
            "status": "success",
            "profile": applied,
        }
    
    def list_profiles(self) -> Dict:
        """List all saved profiles"""
        profiles = self.profile_mgr.list_profiles()
        return {
            "status": "success",
            "profiles": profiles
        }
    
    def delete_profile(self, name: str) -> Dict:
        """Delete a profile"""
        success = self.profile_mgr.delete_profile(name)
        return {
            "status": "success" if success else "error",
            "message": f"Profile '{name}' deleted" if success else "Failed to delete profile"
        }


# Backward compatibility alias
FFmpegCore = EncodeForgeCore


def main():
    """Test the EncodeForge core"""
    core = EncodeForgeCore()
    
    # Check FFmpeg
    ffmpeg_status = core.check_ffmpeg()
    print(f"FFmpeg Status: {ffmpeg_status}")
    
    # Check Whisper
    whisper_status = core.check_whisper()
    print(f"Whisper Status: {whisper_status}")


if __name__ == "__main__":
    main()

