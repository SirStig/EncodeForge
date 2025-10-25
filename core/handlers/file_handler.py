#!/usr/bin/env python3
"""
File Handler - Media file information and scanning operations
"""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .models import ConversionSettings, FileInfo

logger = logging.getLogger(__name__)


class FileHandler:
    """Handles file information retrieval and directory scanning"""
    
    def __init__(self, settings: ConversionSettings, ffmpeg_mgr):
        self.settings = settings
        self.ffmpeg_mgr = ffmpeg_mgr
    
    def get_file_info(self, file_path: str) -> Dict:
        """Get basic file information (duration, format) - faster version"""
        try:
            if not os.path.exists(file_path):
                return {"status": "error", "message": "File not found", "duration": 0}
            
            # Get ffprobe path from manager (it's detected and stored there)
            ffprobe_path = self.ffmpeg_mgr.ffprobe_path if self.ffmpeg_mgr.ffprobe_path else "ffprobe"
            
            # Use ffprobe to get basic info
            cmd = [
                ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                file_path
            ]
            
            logger.debug(f"Running ffprobe: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            
            if result.returncode != 0:
                return {"status": "error", "message": "Failed to probe file", "duration": 0}
            
            probe_data = json.loads(result.stdout)
            format_info = probe_data.get("format", {})
            
            duration = float(format_info.get("duration", 0))
            
            return {
                "status": "success",
                "duration": duration,
                "size": format_info.get("size", "Unknown"),
                "format": format_info.get("format_name", "Unknown")
            }
            
        except Exception as e:
            logger.error(f"Error getting file info: {e}")
            return {"status": "error", "message": str(e), "duration": 0}
    
    def get_media_info(self, file_path: str) -> Dict:
        """Get detailed media information for a file"""
        try:
            if not os.path.exists(file_path):
                return {"status": "error", "message": "File not found"}
            
            # Validate file is readable
            try:
                with open(file_path, 'rb') as f:
                    # Try to read first few bytes to ensure file is accessible
                    f.read(1024)
            except Exception as e:
                return {"status": "error", "message": f"File not readable: {e}"}
            
            # Get ffprobe path from manager (it's detected and stored there)
            ffprobe_path = self.ffmpeg_mgr.ffprobe_path if self.ffmpeg_mgr.ffprobe_path else "ffprobe"
            
            # Use ffprobe to get media info - properly quote file path
            cmd = [
                ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                file_path  # subprocess.run handles path quoting automatically
            ]
            
            logger.debug(f"Running ffprobe for media info: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown ffprobe error"
                logger.error(f"ffprobe failed with code {result.returncode}: {error_msg}")
                return {"status": "error", "message": f"Failed to probe file: {error_msg}"}
            
            probe_data = json.loads(result.stdout)
            
            # Extract track information
            video_tracks = []
            audio_tracks = []
            subtitle_tracks = []
            
            for stream in probe_data.get("streams", []):
                codec_type = stream.get("codec_type", "")
                
                if codec_type == "video":
                    video_tracks.append({
                        "codec": stream.get("codec_name", "Unknown"),
                        "resolution": f"{stream.get('width', '?')}x{stream.get('height', '?')}",
                        "fps": str(eval(stream.get("r_frame_rate", "0/1"))) if "/" in stream.get("r_frame_rate", "") else stream.get("r_frame_rate", "Unknown"),
                        "bitrate": stream.get("bit_rate", "Unknown")
                    })
                
                elif codec_type == "audio":
                    audio_tracks.append({
                        "codec": stream.get("codec_name", "Unknown"),
                        "language": stream.get("tags", {}).get("language", "und"),
                        "channels": str(stream.get("channels", "?")),
                        "sample_rate": stream.get("sample_rate", "Unknown"),
                        "bitrate": stream.get("bit_rate", "Unknown")
                    })
                
                elif codec_type == "subtitle":
                    subtitle_tracks.append({
                        "codec": stream.get("codec_name", "Unknown"),
                        "language": stream.get("tags", {}).get("language", "und"),
                        "forced": stream.get("disposition", {}).get("forced", 0) == 1,
                        "title": stream.get("tags", {}).get("title", "")
                    })
            
            format_info = probe_data.get("format", {})
            
            return {
                "status": "success",
                "video_tracks": video_tracks,
                "audio_tracks": audio_tracks,
                "subtitle_tracks": subtitle_tracks,
                "duration": format_info.get("duration", "Unknown"),
                "size": format_info.get("size", "Unknown"),
                "bitrate": format_info.get("bit_rate", "Unknown"),
                "format": format_info.get("format_name", "Unknown")
            }
            
        except Exception as e:
            logger.error(f"Error getting media info: {e}")
            return {"status": "error", "message": str(e)}
    
    def scan_directory(self, directory: str, recursive: bool = True,
                      progress_callback: Optional[Callable] = None) -> Dict:
        """Scan directory for media files"""
        try:
            valid_extensions = {'.mkv', '.mp4', '.avi', '.mov', '.m4v', '.wmv', '.flv', '.webm', '.ts', '.m2ts'}
            
            files = []
            path = Path(directory)
            
            if not path.exists():
                return {"status": "error", "message": "Directory not found", "files": []}
            
            if not path.is_dir():
                return {"status": "error", "message": "Not a directory", "files": []}
            
            # Scan directory
            file_pattern = "**/*" if recursive else "*"
            all_files = list(path.glob(file_pattern))
            
            total_files = len(all_files)
            logger.info(f"Scanning {total_files} files in {directory}")
            
            for idx, file_path in enumerate(all_files):
                if progress_callback:
                    progress_callback(idx + 1, total_files, f"Scanning: {file_path.name}")
                
                if file_path.is_file() and file_path.suffix.lower() in valid_extensions:
                    try:
                        size_mb = file_path.stat().st_size / (1024 * 1024)
                        
                        file_info = FileInfo(
                            path=file_path,
                            size_mb=round(size_mb, 2)
                        )
                        
                        files.append({
                            "path": str(file_path),
                            "name": file_path.name,
                            "size_mb": file_info.size_mb
                        })
                    except Exception as e:
                        logger.warning(f"Error processing {file_path}: {e}")
            
            logger.info(f"Found {len(files)} media files")
            
            return {
                "status": "success",
                "files": files,
                "count": len(files)
            }
            
        except Exception as e:
            logger.error(f"Error scanning directory: {e}")
            return {"status": "error", "message": str(e), "files": []}

