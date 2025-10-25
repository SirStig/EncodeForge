#!/usr/bin/env python3
"""
Data models and settings for FFmpeg operations
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class ConversionSettings:
    """Settings for the conversion process"""
    # FFmpeg paths
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    additional_ffmpeg_args: str = ""  # Custom FFmpeg arguments to append
    
    # Hardware acceleration
    use_nvenc: bool = True
    nvenc_preset: str = "p4"
    nvenc_cq: int = 23
    nvenc_codec: str = "h264_nvenc"  # Default to H.264 NVENC
    use_amf: bool = False  # AMD
    amf_qp: int = 23  # AMD quality parameter
    amf_preset: str = "balanced"  # AMD preset
    use_qsv: bool = False  # Intel Quick Sync
    qsv_quality: int = 23  # Intel quality parameter
    qsv_preset: str = "medium"  # Intel preset
    use_videotoolbox: bool = False  # Apple
    videotoolbox_bitrate: str = "5M"  # Apple bitrate
    
    # Subtitle options
    convert_subtitles: bool = True
    subtitle_format: str = "srt"
    extract_forced_subs: bool = True
    extract_sdh_subs: bool = True
    
    # Subtitle generation/download
    enable_subtitle_generation: bool = False
    enable_subtitle_download: bool = False
    subtitle_languages: List[str] = field(default_factory=lambda: ["eng"])
    replace_existing_subtitles: bool = False
    whisper_model: str = "base"
    opensubtitles_api_key: str = ""  # DEPRECATED - Consumer API key now hardcoded
    opensubtitles_username: str = ""  # User's OpenSubtitles username (for higher quotas)
    opensubtitles_password: str = ""  # User's OpenSubtitles password (for higher quotas)
    
    # Media renaming
    enable_renaming: bool = False
    renaming_pattern_tv: str = "{title} - S{season}E{episode} - {episodeTitle}"
    renaming_pattern_movie: str = "{title} ({year})"
    tmdb_api_key: str = ""
    tvdb_api_key: str = ""
    omdb_api_key: str = ""
    trakt_api_key: str = ""
    fanart_api_key: str = ""
    anidb_api_key: str = ""
    
    # Audio options
    audio_codec: str = "copy"
    audio_bitrate: Optional[str] = None
    normalize_audio: bool = False
    
    # Video options
    video_codec_fallback: str = "libx264"
    video_preset: str = "medium"
    video_crf: int = 23
    target_resolution: Optional[str] = None
    
    # General options
    traverse_subdirs: bool = True
    delete_original: bool = True
    use_faststart: bool = True
    output_suffix: str = ""
    overwrite_existing: bool = False
    dry_run: bool = False
    output_format: str = "mp4"


@dataclass
class FileInfo:
    """Information about a media file"""
    path: Path
    size_mb: float
    duration: float = 0.0
    video_codec: str = "Unknown"
    audio_tracks: List[Dict[str, str]] = field(default_factory=list)
    subtitle_tracks: List[Dict[str, str]] = field(default_factory=list)

