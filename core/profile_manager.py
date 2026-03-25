#!/usr/bin/env python3
"""
Profile Manager - Save and load encoding presets
"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .handlers import ConversionSettings

logger = logging.getLogger(__name__)


class ProfileManager:
    """Manages encoding profiles (presets)"""
    
    def __init__(self, profiles_dir: Optional[Path] = None):
        if profiles_dir is None:
            # Default to user's home directory
            from .path_manager import get_profiles_dir
            profiles_dir = get_profiles_dir()
        
        self.profiles_dir = Path(profiles_dir)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        # Built-in profiles
        self.builtin_profiles = {
            "High Quality HEVC": self._profile_high_quality_hevc(),
            "Fast H.264": self._profile_fast_h264(),
            "Balanced": self._profile_balanced(),
            "Small File Size": self._profile_small_size(),
            "Archive Quality": self._profile_archive(),
        }
    
    def _profile_high_quality_hevc(self):
        """High quality H.265/HEVC profile"""
        from .handlers import ConversionSettings
        settings = ConversionSettings()
        settings.use_nvenc = True
        settings.nvenc_preset = "p7"  # Slowest, best quality
        settings.nvenc_cq = 18  # High quality
        settings.amf_qp = 18  # High quality for AMD
        settings.qsv_quality = 18  # High quality for Intel
        settings.videotoolbox_bitrate = "8M"  # High bitrate for Apple
        settings.output_format = "mp4"
        settings.audio_codec = "copy"
        settings.convert_subtitles = True
        settings.delete_original = False
        return settings
    
    def _profile_fast_h264(self):
        """Fast H.264 encoding"""
        from .handlers import ConversionSettings
        settings = ConversionSettings()
        settings.use_nvenc = True
        settings.nvenc_preset = "p1"  # Fastest
        settings.nvenc_cq = 28  # Lower quality
        settings.amf_qp = 28  # Lower quality for AMD
        settings.qsv_quality = 28  # Lower quality for Intel
        settings.videotoolbox_bitrate = "3M"  # Lower bitrate for Apple
        settings.output_format = "mp4"
        settings.audio_codec = "copy"
        settings.convert_subtitles = True
        settings.delete_original = False
        return settings
    
    def _profile_balanced(self):
        """Balanced quality and speed"""
        from .handlers import ConversionSettings
        settings = ConversionSettings()
        settings.use_nvenc = True
        settings.nvenc_preset = "p4"  # Balanced
        settings.nvenc_cq = 23  # Balanced quality
        settings.amf_qp = 23  # Balanced quality for AMD
        settings.qsv_quality = 23  # Balanced quality for Intel
        settings.videotoolbox_bitrate = "5M"  # Balanced bitrate for Apple
        settings.output_format = "mp4"
        settings.audio_codec = "copy"
        settings.convert_subtitles = True
        settings.delete_original = False
        return settings
    
    def _profile_small_size(self):
        """Optimize for small file size"""
        from .handlers import ConversionSettings
        settings = ConversionSettings()
        settings.use_nvenc = True
        settings.nvenc_preset = "p7"  # Slow for better compression
        settings.nvenc_cq = 30  # Lower quality = smaller files
        settings.amf_qp = 30  # Lower quality for AMD
        settings.qsv_quality = 30  # Lower quality for Intel
        settings.videotoolbox_bitrate = "2M"  # Lower bitrate for Apple
        settings.output_format = "mp4"
        settings.audio_codec = "aac"  # Re-encode audio
        settings.audio_bitrate = "128k"  # Lower bitrate
        settings.convert_subtitles = True
        settings.delete_original = False
        return settings
    
    def _profile_archive(self):
        """Archive quality - maximum quality"""
        from .handlers import ConversionSettings
        settings = ConversionSettings()
        settings.use_nvenc = True
        settings.nvenc_preset = "p7"
        settings.nvenc_cq = 15  # Very high quality
        settings.amf_qp = 15  # Very high quality for AMD
        settings.qsv_quality = 15  # Very high quality for Intel
        settings.videotoolbox_bitrate = "10M"  # High bitrate for Apple
        settings.output_format = "mkv"  # MKV for better container support
        settings.audio_codec = "copy"
        settings.convert_subtitles = True
        settings.delete_original = False
        return settings
    
    def list_profiles(self) -> List[str]:
        """List all available profiles (built-in + custom)"""
        profiles = list(self.builtin_profiles.keys())
        
        # Add custom profiles
        for profile_file in self.profiles_dir.glob("*.json"):
            profile_name = profile_file.stem
            if profile_name not in profiles:
                profiles.append(profile_name)
        
        return sorted(profiles)
    
    def load_profile(self, profile_name: str):
        """Load a profile by name"""
        # Check built-in profiles first
        if profile_name in self.builtin_profiles:
            return self.builtin_profiles[profile_name]
        
        # Check custom profiles
        profile_path = self.profiles_dir / f"{profile_name}.json"
        
        if not profile_path.exists():
            logger.error(f"Profile not found: {profile_name}")
            return None
        
        try:
            with open(profile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Create ConversionSettings from dict
            from .handlers import ConversionSettings
            settings = ConversionSettings()
            
            # Update settings from dict
            for key, value in data.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            
            logger.info(f"Loaded profile: {profile_name}")
            return settings
        
        except Exception as e:
            logger.error(f"Error loading profile {profile_name}: {e}")
            return None
    
    def save_profile(self, profile_name: str, settings) -> bool:
        """Save a custom profile"""
        if profile_name in self.builtin_profiles:
            logger.error(f"Cannot overwrite built-in profile: {profile_name}")
            return False
        
        profile_path = self.profiles_dir / f"{profile_name}.json"
        
        try:
            # Convert settings to dict
            from dataclasses import asdict
            settings_dict = asdict(settings)
            
            # Save to file
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(settings_dict, f, indent=2)
            
            logger.info(f"Saved profile: {profile_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error saving profile {profile_name}: {e}")
            return False
    
    def delete_profile(self, profile_name: str) -> bool:
        """Delete a custom profile"""
        if profile_name in self.builtin_profiles:
            logger.error(f"Cannot delete built-in profile: {profile_name}")
            return False
        
        profile_path = self.profiles_dir / f"{profile_name}.json"
        
        if not profile_path.exists():
            logger.error(f"Profile not found: {profile_name}")
            return False
        
        try:
            profile_path.unlink()
            logger.info(f"Deleted profile: {profile_name}")
            return True
        
        except Exception as e:
            logger.error(f"Error deleting profile {profile_name}: {e}")
            return False
    
    def get_profile_info(self, profile_name: str) -> Optional[Dict]:
        """Get information about a profile"""
        settings = self.load_profile(profile_name)
        
        if settings is None:
            return None
        
        is_builtin = profile_name in self.builtin_profiles
        
        return {
            "name": profile_name,
            "builtin": is_builtin,
            "settings": {
                "format": settings.output_format,
                "hardware_accel": "NVENC" if settings.use_nvenc else "AMF" if settings.use_amf else "QSV" if settings.use_qsv else "Software",
                "quality": settings.nvenc_cq,
                "preset": settings.nvenc_preset,
                "audio": settings.audio_codec,
                "subtitles": settings.convert_subtitles,
            }
        }


def main():
    """Test the profile manager"""
    manager = ProfileManager()
    
    print("Available Profiles:")
    print("=" * 50)
    
    for profile_name in manager.list_profiles():
        info = manager.get_profile_info(profile_name)
        
        if info:
            print(f"\n📁 {profile_name} {'[Built-in]' if info['builtin'] else '[Custom]'}")
            print(f"   Format: {info['settings']['format']}")
            print(f"   Hardware: {info['settings']['hardware_accel']}")
            print(f"   Quality: CQ {info['settings']['quality']}, Preset {info['settings']['preset']}")
            print(f"   Audio: {info['settings']['audio']}")
            print(f"   Subtitles: {'Yes' if info['settings']['subtitles'] else 'No'}")
    
    # Test creating a custom profile
    print("\n\n" + "=" * 50)
    print("Creating custom profile...")
    
    custom_settings = ConversionSettings()
    custom_settings.use_nvenc = True
    custom_settings.nvenc_preset = "p5"
    custom_settings.nvenc_cq = 20
    custom_settings.output_format = "mp4"
    
    if manager.save_profile("My Custom Profile", custom_settings):
        print("✅ Custom profile created successfully")
        
        # Load it back
        loaded = manager.load_profile("My Custom Profile")
        if loaded:
            print(f"✅ Profile loaded: NVENC={loaded.use_nvenc}, Preset={loaded.nvenc_preset}")
    
    print("\n✅ Profile manager test complete!")


if __name__ == "__main__":
    try:
        from utils.logging_config import setup_logging
        setup_logging()
    except ImportError:
        logging.basicConfig(level=logging.INFO)
    main()

