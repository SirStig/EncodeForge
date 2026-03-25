"""
FFmpeg Manager
Centralized FFmpeg detection, validation, and execution
"""

import logging
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class FFmpegManager:
    """
    Singleton manager for FFmpeg operations.
    
    Handles detection, validation, and execution of FFmpeg/FFprobe.
    Provides a single source of truth for FFmpeg paths across the application.
    """
    
    _instance: Optional['FFmpegManager'] = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize FFmpeg manager."""
        if self._initialized:
            return
        
        self._initialized = True
        self._ffmpeg_path: Optional[Path] = None
        self._ffprobe_path: Optional[Path] = None
        self._version_info: Optional[Dict[str, str]] = None
        
        logger.info("FFmpeg manager initialized")
    
    def detect_ffmpeg(self, force_refresh: bool = False) -> bool:
        """
        Detect FFmpeg in common locations.
        
        Args:
            force_refresh: Force re-detection even if already found
        
        Returns:
            True if FFmpeg was detected, False otherwise
        """
        if self._ffmpeg_path and not force_refresh:
            return True
        
        logger.info("Detecting FFmpeg...")
        
        # Try settings first
        try:
            from utils.settings_manager import SettingsManager
            settings = SettingsManager()
            
            if settings.application.ffmpeg_path:
                ffmpeg_path = Path(settings.application.ffmpeg_path)
                if ffmpeg_path.exists() and self._validate_ffmpeg(ffmpeg_path):
                    self._ffmpeg_path = ffmpeg_path
                    
                    # Also check for ffprobe
                    if settings.application.ffprobe_path:
                        ffprobe_path = Path(settings.application.ffprobe_path)
                        if ffprobe_path.exists():
                            self._ffprobe_path = ffprobe_path
                    
                    logger.info(f"FFmpeg found in settings: {self._ffmpeg_path}")
                    return True
        except Exception as e:
            logger.debug(f"Could not load from settings: {e}")
        
        # Try system PATH
        ffmpeg_exe = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
        ffprobe_exe = "ffprobe.exe" if platform.system() == "Windows" else "ffprobe"
        
        ffmpeg_in_path = shutil.which(ffmpeg_exe)
        if ffmpeg_in_path:
            ffmpeg_path = Path(ffmpeg_in_path)
            if self._validate_ffmpeg(ffmpeg_path):
                self._ffmpeg_path = ffmpeg_path
                
                # Try to find ffprobe
                ffprobe_in_path = shutil.which(ffprobe_exe)
                if ffprobe_in_path:
                    self._ffprobe_path = Path(ffprobe_in_path)
                else:
                    # Look in same directory as ffmpeg
                    potential_ffprobe = ffmpeg_path.parent / ffprobe_exe
                    if potential_ffprobe.exists():
                        self._ffprobe_path = potential_ffprobe
                
                logger.info(f"FFmpeg found in PATH: {self._ffmpeg_path}")
                return True
        
        # Try common installation directories
        search_paths = self._get_common_paths()
        
        for search_dir in search_paths:
            if not search_dir.exists():
                continue
            
            # Search for ffmpeg executable
            for ffmpeg_path in search_dir.rglob(ffmpeg_exe):
                if ffmpeg_path.is_file() and self._validate_ffmpeg(ffmpeg_path):
                    self._ffmpeg_path = ffmpeg_path
                    
                    # Look for ffprobe in same directory
                    potential_ffprobe = ffmpeg_path.parent / ffprobe_exe
                    if potential_ffprobe.exists():
                        self._ffprobe_path = potential_ffprobe
                    
                    logger.info(f"FFmpeg found in common location: {self._ffmpeg_path}")
                    return True
        
        logger.warning("FFmpeg not found")
        return False
    
    def _get_common_paths(self) -> List[Path]:
        """Get list of common installation paths based on OS."""
        system = platform.system()
        paths = []
        
        if system == "Windows":
            # Common Windows locations
            if Path.home().exists():
                paths.append(Path.home() / "Downloads")
                paths.append(Path.home() / "Documents")
            
            # AppData locations
            appdata_local = Path.home() / "AppData" / "Local"
            if appdata_local.exists():
                paths.append(appdata_local)
                paths.append(appdata_local / "Programs")
            
            # Program Files
            for pf in ["C:/Program Files", "C:/Program Files (x86)"]:
                pf_path = Path(pf)
                if pf_path.exists():
                    paths.append(pf_path)
            
            # Common portable locations
            for drive in ["C:", "D:", "E:"]:
                for folder in ["ffmpeg", "tools", "bin"]:
                    path = Path(drive) / folder
                    if path.exists():
                        paths.append(path)
        
        elif system == "Darwin":  # macOS
            # Homebrew locations
            paths.extend([
                Path("/usr/local/bin"),
                Path("/opt/homebrew/bin"),  # Apple Silicon
                Path("/usr/local/Cellar/ffmpeg"),
                Path("/opt/homebrew/Cellar/ffmpeg"),
            ])
            
            # User locations
            paths.extend([
                Path.home() / "Applications",
                Path.home() / "Downloads",
                Path.home() / ".local" / "bin",
            ])
        
        elif system == "Linux":
            # Standard Linux locations
            paths.extend([
                Path("/usr/bin"),
                Path("/usr/local/bin"),
                Path("/opt/ffmpeg"),
                Path("/snap/bin"),
            ])
            
            # User locations
            paths.extend([
                Path.home() / ".local" / "bin",
                Path.home() / "bin",
                Path.home() / "Downloads",
            ])
        
        # Add EncodeForge's own bin directory
        try:
            from core.path_manager import get_bin_dir
            paths.append(get_bin_dir())
        except Exception:
            pass
        
        return paths
    
    def _validate_ffmpeg(self, ffmpeg_path: Path) -> bool:
        """
        Validate that a path points to a working FFmpeg executable.
        
        Args:
            ffmpeg_path: Path to FFmpeg executable
        
        Returns:
            True if valid, False otherwise
        """
        try:
            result = subprocess.run(
                [str(ffmpeg_path), "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and "ffmpeg version" in result.stdout.lower():
                # Extract version info
                lines = result.stdout.split('\n')
                if lines:
                    version_line = lines[0]
                    self._version_info = {"version": version_line}
                return True
        except Exception as e:
            logger.debug(f"FFmpeg validation failed for {ffmpeg_path}: {e}")
        
        return False
    
    def get_ffmpeg_path(self) -> Optional[Path]:
        """
        Get the FFmpeg executable path.
        
        Returns:
            Path to FFmpeg or None if not found
        """
        if not self._ffmpeg_path:
            self.detect_ffmpeg()
        return self._ffmpeg_path
    
    def get_ffprobe_path(self) -> Optional[Path]:
        """
        Get the FFprobe executable path.
        
        Returns:
            Path to FFprobe or None if not found
        """
        if not self._ffprobe_path and self._ffmpeg_path:
            # Try to find ffprobe near ffmpeg
            ffprobe_exe = "ffprobe.exe" if platform.system() == "Windows" else "ffprobe"
            potential_ffprobe = self._ffmpeg_path.parent / ffprobe_exe
            if potential_ffprobe.exists():
                self._ffprobe_path = potential_ffprobe
        
        return self._ffprobe_path
    
    def set_ffmpeg_path(self, ffmpeg_path: Path, ffprobe_path: Optional[Path] = None):
        """
        Manually set FFmpeg paths.
        
        Args:
            ffmpeg_path: Path to FFmpeg executable
            ffprobe_path: Optional path to FFprobe executable
        """
        if self._validate_ffmpeg(ffmpeg_path):
            self._ffmpeg_path = ffmpeg_path
            self._ffprobe_path = ffprobe_path
            logger.info(f"FFmpeg path set to: {ffmpeg_path}")
            
            # Save to settings
            try:
                from utils.settings_manager import SettingsManager
                settings = SettingsManager()
                settings.application.ffmpeg_path = str(ffmpeg_path)
                if ffprobe_path:
                    settings.application.ffprobe_path = str(ffprobe_path)
                settings.save()
            except Exception as e:
                logger.error(f"Failed to save FFmpeg path to settings: {e}")
        else:
            raise ValueError(f"Invalid FFmpeg path: {ffmpeg_path}")
    
    def get_version_info(self) -> Optional[Dict[str, str]]:
        """
        Get FFmpeg version information.
        
        Returns:
            Dictionary with version info or None
        """
        if not self._version_info and self._ffmpeg_path:
            self._validate_ffmpeg(self._ffmpeg_path)
        return self._version_info
    
    def is_available(self) -> bool:
        """
        Check if FFmpeg is available.
        
        Returns:
            True if FFmpeg is available, False otherwise
        """
        return self.get_ffmpeg_path() is not None
    
    def run_ffmpeg(self, args: List[str], **kwargs) -> subprocess.CompletedProcess:
        """
        Run FFmpeg with given arguments.
        
        Args:
            args: FFmpeg command arguments (without 'ffmpeg' itself)
            **kwargs: Additional arguments for subprocess.run()
        
        Returns:
            CompletedProcess instance
        
        Raises:
            RuntimeError: If FFmpeg is not available
        """
        if not self.is_available():
            raise RuntimeError("FFmpeg is not available")
        
        cmd = [str(self._ffmpeg_path)] + args
        return subprocess.run(cmd, **kwargs)
    
    def run_ffprobe(self, args: List[str], **kwargs) -> subprocess.CompletedProcess:
        """
        Run FFprobe with given arguments.
        
        Args:
            args: FFprobe command arguments (without 'ffprobe' itself)
            **kwargs: Additional arguments for subprocess.run()
        
        Returns:
            CompletedProcess instance
        
        Raises:
            RuntimeError: If FFprobe is not available
        """
        ffprobe_path = self.get_ffprobe_path()
        if not ffprobe_path:
            raise RuntimeError("FFprobe is not available")
        
        cmd = [str(ffprobe_path)] + args
        return subprocess.run(cmd, **kwargs)


# Convenience function for getting the singleton instance
def get_ffmpeg_manager() -> FFmpegManager:
    """Get the FFmpeg manager singleton instance."""
    return FFmpegManager()


if __name__ == "__main__":
    # Test the manager
    logging.basicConfig(level=logging.INFO)
    
    print("=== FFmpeg Manager Test ===")
    print()
    
    manager = get_ffmpeg_manager()
    
    if manager.detect_ffmpeg():
        print(f"✓ FFmpeg found: {manager.get_ffmpeg_path()}")
        print(f"✓ FFprobe found: {manager.get_ffprobe_path()}")
        
        version_info = manager.get_version_info()
        if version_info:
            print(f"✓ Version: {version_info.get('version', 'Unknown')}")
        
        # Test execution
        try:
            result = manager.run_ffmpeg(["-version"], capture_output=True, text=True)
            print("✓ Execution test passed")
        except Exception as e:
            print(f"✗ Execution test failed: {e}")
    else:
        print("✗ FFmpeg not found")
