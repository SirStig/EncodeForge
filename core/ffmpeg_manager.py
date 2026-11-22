"""
Compatibility façade for the unified FFmpeg manager.

Prefer importing from ``utils.ffmpeg_manager`` (single source of truth).
This module re-exports the same API so existing ``core.ffmpeg_manager``
imports keep working during the transition.
"""

from utils.ffmpeg_manager import (  # noqa: F401
    FFmpegManager,
    common_search_paths_for_system,
    derive_ffprobe_path,
    get_download_urls,
    get_ffmpeg_manager,
)

__all__ = [
    "FFmpegManager",
    "common_search_paths_for_system",
    "derive_ffprobe_path",
    "get_download_urls",
    "get_ffmpeg_manager",
]
