#!/usr/bin/env python3
"""
Conversion Handler - Video conversion and encoding operations
"""

import json
import logging
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .models import ConversionSettings

logger = logging.getLogger(__name__)


class ConversionHandler:
    """Handles video file conversion and encoding with hardware acceleration"""
    
    def __init__(self, settings: ConversionSettings, ffmpeg_mgr):
        self.settings = settings
        self.ffmpeg_mgr = ffmpeg_mgr
        self.current_process: Optional[subprocess.Popen] = None
        self.cancel_requested: bool = False
        self.current_output_path: Optional[str] = None  # Track current output file for cleanup
        
        # Queue state tracking for recovery
        self._file_queue: List[Dict] = []  # Full queue with status
        self._current_index: int = 0
        self._completed_files: List[str] = []
        self._failed_files: List[Dict] = []
    
    def _select_best_encoder(self, is_10bit: bool = False) -> Dict[str, Any]:
        """
        Determine the best available encoder (hardware or software fallback)
        
        Args:
            is_10bit: Whether the source video is 10-bit
        
        Returns:
            Dict with 'type', 'codec', 'platform', and 'needs_conversion' keys
        """
        hwaccel_options = self.ffmpeg_mgr.get_hwaccel_options()
        logger.info(f"Hardware acceleration options: {hwaccel_options}")
        logger.info(f"Settings - use_nvenc: {self.settings.use_nvenc}, use_amf: {self.settings.use_amf}, use_qsv: {self.settings.use_qsv}")
        logger.info(f"Source is 10-bit: {is_10bit}")
        
        # For 10-bit sources, prefer HEVC hardware encoders or software with conversion
        if is_10bit:
            logger.info("10-bit source detected - selecting appropriate encoder")
            
            # Try HEVC hardware encoders first (they support 10-bit)
            if self.settings.use_nvenc and "nvenc" in hwaccel_options.get("encode", []):
                logger.info("Selected NVENC HEVC hardware encoder for 10-bit source")
                return {"type": "hardware", "codec": "hevc_nvenc", "platform": "nvidia", "needs_conversion": False}
            
            if self.settings.use_amf and "amf" in hwaccel_options.get("encode", []):
                logger.info("Selected AMF HEVC hardware encoder for 10-bit source")
                return {"type": "hardware", "codec": "hevc_amf", "platform": "amd", "needs_conversion": False}
            
            if self.settings.use_qsv and "qsv" in hwaccel_options.get("encode", []):
                logger.info("Selected QSV HEVC hardware encoder for 10-bit source")
                return {"type": "hardware", "codec": "hevc_qsv", "platform": "intel", "needs_conversion": False}
            
            if self.settings.use_videotoolbox and "videotoolbox" in hwaccel_options.get("encode", []):
                logger.info("Selected VideoToolbox HEVC hardware encoder for 10-bit source")
                return {"type": "hardware", "codec": "hevc_videotoolbox", "platform": "apple", "needs_conversion": False}
            
            # If HEVC not available, use H.264 hardware with 8-bit conversion
            if self.settings.use_nvenc and "nvenc" in hwaccel_options.get("encode", []):
                logger.info("Using NVENC H.264 with 10-bit to 8-bit conversion")
                return {"type": "hardware", "codec": "h264_nvenc", "platform": "nvidia", "needs_conversion": True}
            
            if self.settings.use_amf and "amf" in hwaccel_options.get("encode", []):
                logger.info("Using AMF H.264 with 10-bit to 8-bit conversion")
                return {"type": "hardware", "codec": "h264_amf", "platform": "amd", "needs_conversion": True}
            
            if self.settings.use_qsv and "qsv" in hwaccel_options.get("encode", []):
                logger.info("Using QSV H.264 with 10-bit to 8-bit conversion")
                return {"type": "hardware", "codec": "h264_qsv", "platform": "intel", "needs_conversion": True}
            
            if self.settings.use_videotoolbox and "videotoolbox" in hwaccel_options.get("encode", []):
                logger.info("Using VideoToolbox H.264 with 10-bit to 8-bit conversion")
                return {"type": "hardware", "codec": "h264_videotoolbox", "platform": "apple", "needs_conversion": True}
            
            # Fallback to software (supports 10-bit natively)
            logger.info("Using software encoder (supports 10-bit natively)")
            return {"type": "software", "codec": self.settings.video_codec_fallback, "platform": "cpu", "needs_conversion": False}
        
        # For 8-bit sources, use H.264 hardware encoders
        if self.settings.use_nvenc and "nvenc" in hwaccel_options.get("encode", []):
            logger.info("Selected NVENC H.264 hardware encoder")
            return {"type": "hardware", "codec": "h264_nvenc", "platform": "nvidia", "needs_conversion": False}
        
        if self.settings.use_amf and "amf" in hwaccel_options.get("encode", []):
            logger.info("Selected AMF H.264 hardware encoder")
            return {"type": "hardware", "codec": "h264_amf", "platform": "amd", "needs_conversion": False}
        
        if self.settings.use_qsv and "qsv" in hwaccel_options.get("encode", []):
            logger.info("Selected QSV H.264 hardware encoder")
            return {"type": "hardware", "codec": "h264_qsv", "platform": "intel", "needs_conversion": False}
        
        if self.settings.use_videotoolbox and "videotoolbox" in hwaccel_options.get("encode", []):
            logger.info("Selected VideoToolbox H.264 hardware encoder")
            return {"type": "hardware", "codec": "h264_videotoolbox", "platform": "apple", "needs_conversion": False}
        
        # Fallback to software encoding
        logger.info("No hardware encoders available or enabled, falling back to software")
        return {"type": "software", "codec": self.settings.video_codec_fallback, "platform": "cpu", "needs_conversion": False}
    
    def _is_hardware_encoder_error(self, error_output: str) -> bool:
        """Check if error is related to hardware encoder failure"""
        hw_error_indicators = [
            "cannot load",
            "not available",
            "not found",
            "nvenc",
            "amf",
            "qsv",
            "videotoolbox",
            "cuda",
            "driver",
            "gpu"
        ]
        error_lower = error_output.lower()
        return any(indicator in error_lower for indicator in hw_error_indicators)
    
    def _parse_ffmpeg_progress(self, line: str) -> Optional[Dict]:
        """Parse FFmpeg progress information from output line"""
        import re
        
        # FFmpeg progress lines typically look like:
        # frame=  123 fps= 45 q=28.0 size=    1024kB time=00:00:05.12 bitrate=1638.4kbits/s speed=1.8x
        # Also handle progress pipe format: out_time_us=5120000
        
        # Handle progress pipe format first (more reliable)
        if 'out_time_us=' in line:
            try:
                time_match = re.search(r'out_time_us=(\d+)', line)
                if time_match:
                    microseconds = int(time_match.group(1))
                    seconds = microseconds / 1_000_000
                    
                    progress_data = {
                        'time': seconds,
                        'status': 'processing',
                        'file': getattr(self, '_current_file', 'Unknown')
                    }
                    
                    # Calculate progress percentage if we have duration
                    if hasattr(self, '_total_duration') and self._total_duration > 0:
                        progress_data['progress'] = min(100, int((seconds / self._total_duration) * 100))
                        
                        # Calculate ETA
                        remaining_time = self._total_duration - seconds
                        if remaining_time > 0:
                            if remaining_time < 60:
                                progress_data['eta'] = f"{int(remaining_time)}s"
                            elif remaining_time < 3600:
                                minutes = int(remaining_time // 60)
                                secs = int(remaining_time % 60)
                                progress_data['eta'] = f"{minutes}m {secs}s"
                            else:
                                hours = int(remaining_time // 3600)
                                minutes = int((remaining_time % 3600) // 60)
                                progress_data['eta'] = f"{hours}h {minutes}m"
                        else:
                            progress_data['eta'] = "Almost done"
                    else:
                        progress_data['eta'] = "Calculating..."
                    
                    logger.debug(f"Parsed progress: {progress_data}")
                    return progress_data
            except Exception as e:
                logger.debug(f"Error parsing progress pipe format: {e}")
        
        # Fallback to traditional format (more reliable - what -stats outputs)
        if 'frame=' in line and 'time=' in line:
            try:
                progress_data = {}
                
                # Extract frame number
                frame_match = re.search(r'frame=\s*(\d+)', line)
                if frame_match:
                    progress_data['frame'] = int(frame_match.group(1))
                
                # Extract FPS
                fps_match = re.search(r'fps=\s*([\d.]+)', line)
                if fps_match:
                    progress_data['fps'] = float(fps_match.group(1))
                
                # Extract time (format: HH:MM:SS.ss)
                time_match = re.search(r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})', line)
                if time_match:
                    hours = int(time_match.group(1))
                    minutes = int(time_match.group(2))
                    seconds = int(time_match.group(3))
                    centiseconds = int(time_match.group(4))
                    total_seconds = hours * 3600 + minutes * 60 + seconds + centiseconds / 100
                    progress_data['time'] = total_seconds
                
                # Extract bitrate
                bitrate_match = re.search(r'bitrate=\s*([\d.]+)kbits/s', line)
                if bitrate_match:
                    progress_data['bitrate'] = f"{bitrate_match.group(1)}kbits/s"
                
                # Extract speed
                speed_match = re.search(r'speed=\s*([\d.]+)x', line)
                if speed_match:
                    progress_data['speed'] = f"{speed_match.group(1)}x"
                
                # Extract size
                size_match = re.search(r'size=\s*(\d+)kB', line)
                if size_match:
                    progress_data['size'] = f"{size_match.group(1)}kB"
                
                if progress_data:
                    # Add status and file info
                    progress_data['status'] = 'processing'
                    progress_data['file'] = getattr(self, '_current_file', 'Unknown')
                    
                    # Calculate progress percentage
                    # Prefer frame-based progress (more accurate) over time-based
                    if 'frame' in progress_data and hasattr(self, '_total_frames') and self._total_frames > 0:
                        progress_data['progress'] = min(100, int((progress_data['frame'] / self._total_frames) * 100))
                    elif 'time' in progress_data and hasattr(self, '_total_duration') and self._total_duration > 0:
                        progress_data['progress'] = min(100, int((progress_data['time'] / self._total_duration) * 100))
                    
                    # Calculate ETA if we have enough data
                    if 'fps' in progress_data and progress_data['fps'] > 0:
                        if 'frame' in progress_data and hasattr(self, '_total_frames') and self._total_frames > 0:
                            # Frame-based ETA calculation (most accurate)
                            remaining_frames = self._total_frames - progress_data['frame']
                            estimated_seconds = remaining_frames / progress_data['fps']
                        elif 'time' in progress_data and hasattr(self, '_total_duration') and self._total_duration > 0:
                            # Time-based ETA calculation
                            estimated_seconds = self._total_duration - progress_data['time']
                        else:
                            estimated_seconds = 0
                        
                        if estimated_seconds > 0:
                            if estimated_seconds < 60:
                                progress_data['eta'] = f"{int(estimated_seconds)}s"
                            elif estimated_seconds < 3600:
                                minutes = int(estimated_seconds // 60)
                                seconds = int(estimated_seconds % 60)
                                progress_data['eta'] = f"{minutes}m {seconds}s"
                            else:
                                hours = int(estimated_seconds // 3600)
                                minutes = int((estimated_seconds % 3600) // 60)
                                progress_data['eta'] = f"{hours}h {minutes}m"
                        else:
                            progress_data['eta'] = "Almost done"
                    else:
                        progress_data['eta'] = "Calculating..."
                    
                    return progress_data
                    
            except Exception as e:
                logger.debug(f"Error parsing FFmpeg progress: {e}")
        
        return None
    
    def _get_video_duration(self, input_path: str) -> float:
        """Get video duration in seconds using ffprobe"""
        try:
            cmd = [
                self.settings.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                input_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                import json
                data = json.loads(result.stdout)
                duration = float(data.get("format", {}).get("duration", 0))
                logger.debug(f"Video duration: {duration:.2f} seconds")
                return duration
                
        except Exception as e:
            logger.debug(f"Error getting video duration: {e}")
        
        return 0.0  # Return 0 if duration cannot be determined
    
    def _format_time(self, seconds: int) -> str:
        """Format seconds into human-readable time string (e.g., '5m 30s' or '1h 23m')"""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"
    
    def _get_video_info(self, input_path: str) -> Dict:
        """Get video duration and frame count using ffprobe for accurate progress calculation"""
        try:
            cmd = [
                self.settings.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                "-select_streams", "v:0",
                input_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data.get("format", {}).get("duration", 0))
                
                streams = data.get("streams", [])
                total_frames = 0
                fps = 0
                if streams:
                    # Try nb_frames first (most accurate if available)
                    total_frames = int(streams[0].get("nb_frames", 0))
                    
                    # Get FPS for fallback calculation
                    r_frame_rate = streams[0].get("r_frame_rate", "0/1")
                    try:
                        if "/" in r_frame_rate:
                            num, den = r_frame_rate.split("/")
                            fps = float(num) / float(den) if float(den) > 0 else 0
                        else:
                            fps = float(r_frame_rate)
                    except (ValueError, ZeroDivisionError):
                        fps = 0
                    
                    # If nb_frames not available, calculate from duration and fps
                    if not total_frames and duration > 0 and fps > 0:
                        total_frames = int(duration * fps)
                
                logger.debug(f"Video info: duration={duration:.2f}s, frames={total_frames}, fps={fps:.2f}")
                
                return {
                    "duration": duration,
                    "total_frames": total_frames,
                    "fps": fps
                }
                
        except Exception as e:
            logger.debug(f"Error getting video info: {e}")
        
        return {"duration": 0.0, "total_frames": 0, "fps": 0}
    
    def _get_pixel_format(self, input_path: str) -> Optional[str]:
        """Get pixel format of video stream using ffprobe"""
        try:
            cmd = [
                self.settings.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "v:0",
                input_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                streams = data.get("streams", [])
                if streams:
                    pix_fmt = streams[0].get("pix_fmt", "")
                    logger.info(f"Source pixel format: {pix_fmt}")
                    return pix_fmt
                
        except Exception as e:
            logger.debug(f"Error getting pixel format: {e}")
        
        return None
    
    def _is_10bit_format(self, pix_fmt: Optional[str]) -> bool:
        """Check if pixel format is 10-bit"""
        if not pix_fmt:
            return False
        
        # 10-bit formats typically end with '10le', '10be', or 'p10'
        ten_bit_indicators = ['10le', '10be', 'p10', '10']
        return any(indicator in pix_fmt.lower() for indicator in ten_bit_indicators)
    
    def _supports_10bit(self, encoder: str) -> bool:
        """Check if encoder supports 10-bit encoding"""
        # HEVC encoders generally support 10-bit
        if 'hevc' in encoder.lower() or 'h265' in encoder.lower():
            return True
        
        # H.264 hardware encoders typically do NOT support 10-bit
        if 'h264' in encoder.lower():
            if any(hw in encoder.lower() for hw in ['nvenc', 'amf', 'qsv', 'videotoolbox']):
                return False
        
        # Software encoders (libx264/libx265) support 10-bit
        if encoder in ['libx264', 'libx265']:
            return True
        
        return False
    
    def _analyze_subtitle_tracks(self, input_path: str) -> List[Dict]:
        """Analyze subtitle tracks and return their formats"""
        try:
            cmd = [
                self.settings.ffprobe_path,
                "-v", "quiet",
                "-print_format", "json",
                "-show_streams",
                "-select_streams", "s",
                input_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                subtitle_tracks = []
                for stream in data.get("streams", []):
                    subtitle_tracks.append({
                        "index": stream.get("index"),
                        "codec": stream.get("codec_name"),
                        "language": stream.get("tags", {}).get("language", "und"),
                        "title": stream.get("tags", {}).get("title", "")
                    })
                return subtitle_tracks
        except Exception as e:
            logger.debug(f"Error analyzing subtitle tracks: {e}")
        
        return []
    
    def _extract_and_convert_subtitles(self, input_path: str, subtitle_tracks: List[Dict], output_dir: Path, progress_callback: Optional[Callable] = None) -> List[tuple]:
        """Extract ASS/SSA subtitles and convert to SRT, return list of (index, path) tuples"""
        converted_subs = []
        
        for i, track in enumerate(subtitle_tracks):
            codec = track.get("codec", "")
            index = track.get("index")
            
            # ASS/SSA subtitles need conversion
            if codec in ["ass", "ssa"]:
                try:
                    # Send progress update
                    if progress_callback:
                        progress_callback({
                            'file': Path(input_path).name,
                            'status': 'converting_subtitles',
                            'progress': int((i / len(subtitle_tracks)) * 100),
                            'message': f'Converting subtitle track {index} from {codec.upper()} to SRT...'
                        })
                    
                    temp_srt = output_dir / f"temp_subtitle_{index}.srt"
                    
                    cmd = [
                        self.settings.ffmpeg_path,
                        "-hide_banner",
                        "-loglevel", "error",
                        "-i", input_path,
                        "-map", f"0:{index}",
                        "-c:s", "srt",
                        "-y", str(temp_srt)
                    ]
                    
                    logger.info(f"Converting subtitle track {index} from {codec} to SRT...")
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)  # Increased timeout
                    
                    if result.returncode == 0 and temp_srt.exists():
                        logger.info(f"✅ Converted subtitle track {index} from {codec} to SRT")
                        converted_subs.append((index, temp_srt))
                    else:
                        logger.warning(f"❌ Failed to convert subtitle track {index}: {result.stderr}")
                except subprocess.TimeoutExpired:
                    logger.error(f"⏰ Timeout converting subtitle track {index} from {codec}")
                except Exception as e:
                    logger.warning(f"Error converting subtitle {index}: {e}")
        
        return converted_subs
    
    def _retry_with_software_encoder(self, input_file: Path, output_path_obj: Path, 
                                     progress_callback: Optional[Callable] = None) -> Dict:
        """Retry conversion using software encoder as fallback"""
        logger.warning("⚠️ Retrying with software encoder...")
        
        # Build software encoding command
        cmd = [
            self.settings.ffmpeg_path,
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(input_file),
            "-c:v", self.settings.video_codec_fallback,
            "-preset", self.settings.video_preset,
            "-crf", str(self.settings.video_crf)
        ]
        
        # Add audio codec
        if self.settings.audio_codec == "copy":
            cmd.extend(["-c:a", "copy"])
        else:
            cmd.extend(["-c:a", self.settings.audio_codec])
            if self.settings.audio_bitrate:
                cmd.extend(["-b:a", self.settings.audio_bitrate])
        
        # Add audio normalization filter
        if self.settings.normalize_audio:
            logger.info("Applying audio normalization (loudnorm)")
            cmd.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])
        
        # Add faststart for MP4
        if self.settings.use_faststart and self.settings.output_format in ["mp4", "m4v"]:
            cmd.extend(["-movflags", "+faststart"])
        
        cmd.extend(["-y", str(output_path_obj)])
        
        logger.info(f"Software encoding command: {' '.join(cmd)}")
        
        try:
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            stdout, stderr = self.current_process.communicate()
            
            if self.current_process.returncode == 0:
                logger.info("✅ Software encoding completed successfully")
                return {
                    "status": "success",
                    "message": "Conversion completed (software encoder)",
                    "output_path": str(output_path_obj),
                    "encoder": "software"
                }
            else:
                logger.error(f"Software encoding also failed: {stderr}")
                return {
                    "status": "error",
                    "message": f"Software encoding failed: {stderr}",
                    "encoder": "software"
                }
        except Exception as e:
            logger.error(f"Error during software encoding: {e}")
            return {
                "status": "error",
                "message": f"Software encoding error: {str(e)}",
                "encoder": "software"
            }
    
    def convert_file(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """Convert a single video file with the current settings"""
        # Initialize temp_subtitle_files list for cleanup
        temp_subtitle_files = []
        
        try:
            input_file = Path(input_path)
            
            # Validate input
            if not input_file.exists():
                return {"status": "error", "message": f"Input file not found: {input_path}"}
            
            if not input_file.is_file():
                return {"status": "error", "message": f"Input path is not a file: {input_path}"}
            
            # Check file size
            file_size = input_file.stat().st_size
            if file_size == 0:
                return {"status": "error", "message": f"Input file is empty: {input_path}"}
            
            logger.info(f"Input file size: {file_size / (1024**2):.2f} MB")
            
            # Set current file for progress tracking
            self._current_file = input_file.name
            
            # Send analysis progress update
            if progress_callback:
                progress_callback({
                    'file': input_file.name,
                    'status': 'analyzing',
                    'progress': 0,
                    'message': 'Analyzing video file...'
                })
            
            # Get video info for progress calculation (duration, frames, fps)
            video_info = self._get_video_info(str(input_file))
            self._total_duration = video_info.get("duration", 0)
            self._total_frames = video_info.get("total_frames", 0)
            logger.info(f"Video info: {self._total_duration:.1f}s, {self._total_frames} frames")
            
            # Detect pixel format for encoder selection
            pixel_format = self._get_pixel_format(str(input_file))
            is_10bit = self._is_10bit_format(pixel_format)
            
            if is_10bit:
                logger.info(f"10-bit source detected: {pixel_format}")
            
            # Generate output path
            if output_path is None:
                output_dir = input_file.parent
                base_name = input_file.stem
                
                if input_file.suffix.lower().lstrip('.') == self.settings.output_format.lower():
                    if self.settings.output_suffix:
                        output_path_obj = output_dir / f"{base_name}{self.settings.output_suffix}.{self.settings.output_format}"
                    else:
                        output_path_obj = output_dir / f"{base_name}_converted.{self.settings.output_format}"
                else:
                    if self.settings.output_suffix:
                        output_path_obj = output_dir / f"{base_name}{self.settings.output_suffix}.{self.settings.output_format}"
                    else:
                        output_path_obj = output_dir / f"{base_name}.{self.settings.output_format}"
                
                # Generate unique name if needed
                if output_path_obj.exists() and not self.settings.overwrite_existing:
                    counter = 1
                    while output_path_obj.exists():
                        if self.settings.output_suffix:
                            output_path_obj = output_dir / f"{base_name}{self.settings.output_suffix}_{counter}.{self.settings.output_format}"
                        else:
                            output_path_obj = output_dir / f"{base_name}_{counter}.{self.settings.output_format}"
                        counter += 1
            else:
                output_path_obj = Path(output_path)
                if output_path_obj.exists() and not self.settings.overwrite_existing:
                    return {"status": "error", "message": f"Output file already exists: {output_path_obj}"}
            
            # Store output path for cleanup on cancel
            self.current_output_path = str(output_path_obj)
            
            # Build FFmpeg command with progress output enabled
            # -nostdin prevents FFmpeg from waiting for stdin (critical for pipes)
            # -progress - sends progress to stdout in key=value format
            # -flush_packets 1 reduces buffering delays
            cmd = [
                self.settings.ffmpeg_path,
                "-hide_banner",
                "-nostdin",  # CRITICAL: Prevent FFmpeg from reading stdin (prevents hanging)
                "-loglevel", "error",  # Only errors to keep stderr clean
                "-progress", "-",  # Send progress to stdout (not stderr)
                "-flush_packets", "1",  # Flush output immediately to reduce buffering
                "-i", str(input_file)
            ]
            
            # Map streams explicitly to control what gets included
            cmd.extend(["-map", "0:v:0"])  # First video stream
            
            # Select encoder based on pixel format
            if progress_callback:
                progress_callback({
                    'file': input_file.name,
                    'status': 'preparing',
                    'progress': 10,
                    'message': 'Selecting encoder and preparing conversion...'
                })
            
            encoder_info = self._select_best_encoder(is_10bit=is_10bit)
            logger.info(f"Using encoder: {encoder_info['codec']} ({encoder_info['type']})")
            
            # Add pixel format conversion if needed
            if encoder_info.get("needs_conversion", False):
                logger.info("Adding pixel format conversion: 10-bit -> 8-bit (yuv420p)")
                cmd.extend(["-pix_fmt", "yuv420p"])
            
            if encoder_info["type"] == "hardware":
                cmd.extend(["-c:v", encoder_info["codec"]])
                
                # Hardware-specific optimizations (works for both H.264 and HEVC variants)
                if encoder_info["codec"].endswith("nvenc"):
                    cmd.extend([
                        "-preset", self.settings.nvenc_preset,
                        "-cq", str(self.settings.nvenc_cq),
                        "-rc", "vbr"
                    ])
                    logger.info(f"NVENC quality: preset={self.settings.nvenc_preset}, cq={self.settings.nvenc_cq}")
                elif encoder_info["codec"].endswith("amf"):
                    # Use constant QP mode for better quality control
                    # CQP (Constant QP) mode prevents file size explosion
                    cmd.extend([
                        "-rc", "cqp",  # Constant QP mode
                        "-qp", str(self.settings.amf_qp)    # Quality parameter from user settings
                    ])
                    logger.info(f"AMF quality: CQP mode, QP={self.settings.amf_qp}")
                elif encoder_info["codec"].endswith("qsv"):
                    cmd.extend([
                        "-preset", self.settings.qsv_preset,
                        "-global_quality", str(self.settings.qsv_quality)
                    ])
                    logger.info(f"QSV quality: {self.settings.qsv_preset} preset, global_quality={self.settings.qsv_quality}")
                elif encoder_info["codec"].endswith("videotoolbox"):
                    cmd.extend(["-b:v", self.settings.videotoolbox_bitrate])
                    logger.info(f"VideoToolbox bitrate: {self.settings.videotoolbox_bitrate}")
            else:
                cmd.extend([
                    "-c:v", encoder_info["codec"],
                    "-preset", self.settings.video_preset,
                    "-crf", str(self.settings.video_crf)
                ])
            
            # Audio stream mapping and codec
            # Map all audio streams by default (Java sends 'all' or 'first')
            audio_selection = getattr(self.settings, 'audio_track_selection', 'all')
            if audio_selection == "all":
                cmd.extend(["-map", "0:a"])  # Include all audio streams
                logger.info("Mapping: All audio tracks")
            else:
                cmd.extend(["-map", "0:a:0"])  # Only first audio stream
                logger.info("Mapping: First audio track only")
            
            if self.settings.audio_codec == "copy":
                cmd.extend(["-c:a", "copy"])
            else:
                cmd.extend(["-c:a", self.settings.audio_codec])
                if self.settings.audio_bitrate and self.settings.audio_bitrate != "Auto":
                    cmd.extend(["-b:a", self.settings.audio_bitrate])
            
            # Add audio normalization filter
            if self.settings.normalize_audio:
                logger.info("Applying audio normalization (loudnorm)")
                cmd.extend(["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"])
            
            # Subtitle handling with comprehensive format support
            temp_subtitle_files = []
            subtitle_tracks = []  # Initialize to avoid unbound variable
            if self.settings.convert_subtitles:
                # Send subtitle analysis progress update
                if progress_callback:
                    progress_callback({
                        'file': input_file.name,
                        'status': 'analyzing_subtitles',
                        'progress': 5,
                        'message': 'Analyzing subtitle tracks...'
                    })
                
                # Analyze subtitle tracks
                subtitle_tracks = self._analyze_subtitle_tracks(str(input_file))
                
                if subtitle_tracks:
                    logger.info(f"Found {len(subtitle_tracks)} subtitle track(s)")
                    
                    # For MP4, handle different subtitle formats appropriately
                    if self.settings.output_format.lower() in ["mp4", "m4v"]:
                        # Check subtitle formats
                        has_ass_ssa = any(t.get("codec") in ["ass", "ssa"] for t in subtitle_tracks)
                        has_mov_text = any(t.get("codec") in ["mov_text", "text"] for t in subtitle_tracks)
                        has_srt = any(t.get("codec") in ["srt", "subrip"] for t in subtitle_tracks)
                        
                        logger.info(f"Subtitle formats detected - ASS/SSA: {has_ass_ssa}, mov_text: {has_mov_text}, SRT: {has_srt}")
                        
                        if has_ass_ssa:
                            logger.info("ASS/SSA subtitles detected, converting directly to mov_text...")
                            
                            # Send progress update
                            if progress_callback:
                                progress_callback({
                                    'file': input_file.name,
                                    'status': 'converting_subtitles',
                                    'progress': 15,
                                    'message': 'Converting ASS/SSA subtitles to mov_text...'
                                })
                            
                            # Map all subtitle tracks directly and convert ASS/SSA to mov_text
                            cmd.extend(["-map", "0:s?"])
                            cmd.extend(["-c:s", "mov_text"])
                            logger.info(f"Mapped {len(subtitle_tracks)} subtitle tracks, converting ASS/SSA to mov_text")
                        else:
                            # No ASS/SSA, map all subtitle tracks directly
                            cmd.extend(["-map", "0:s?"])
                            
                            # For MP4, convert all subtitles to mov_text for compatibility
                            if has_mov_text or has_srt:
                                cmd.extend(["-c:s", "mov_text"])
                                logger.info("Converting subtitles to mov_text for MP4 compatibility")
                            else:
                                cmd.extend(["-c:s", "mov_text"])
                                logger.info("Converting all subtitles to mov_text for MP4")
                    else:
                        # MKV/WebM can handle most subtitle formats natively
                        cmd.extend(["-map", "0:s?"])
                        
                        if self.settings.subtitle_format == "auto":
                            cmd.extend(["-c:s", "copy"])
                        else:
                            cmd.extend(["-c:s", self.settings.subtitle_format])
                        
                        logger.info("Mapping all subtitle tracks (copy)")
                else:
                    # No subtitle tracks found, but user wants subtitles enabled
                    logger.info("No subtitle tracks found in input file")
            else:
                cmd.extend(["-sn"])
                logger.info("Subtitles disabled")
            
            # MP4 faststart
            if self.settings.use_faststart and self.settings.output_format in ["mp4", "m4v"]:
                cmd.extend(["-movflags", "+faststart"])
            
            # Target resolution
            if self.settings.target_resolution:
                cmd.extend(["-vf", f"scale={self.settings.target_resolution}"])
            
            # Output
            cmd.extend(["-y", str(output_path_obj)])
            
            # Send final preparation progress update
            if progress_callback:
                progress_callback({
                    'file': input_file.name,
                    'status': 'ready',
                    'progress': 20,
                    'message': 'Starting video conversion...'
                })
            
            logger.info(f"Starting conversion: {input_file.name} -> {output_path_obj.name}")
            logger.info(f"Full FFmpeg command: {' '.join(cmd)}")
            
            # Log subtitle handling details
            if self.settings.convert_subtitles and subtitle_tracks:
                logger.info("Subtitle conversion details:")
                for i, track in enumerate(subtitle_tracks):
                    logger.info(f"  Track {i}: {track.get('codec', 'unknown')} ({track.get('language', 'und')})")
                if self.settings.output_format.lower() in ["mp4", "m4v"]:
                    logger.info("  Target format: mov_text (MP4 compatibility)")
                else:
                    logger.info("  Target format: copy (MKV/WebM)")
            
            # Execute conversion
            # On Unix, start FFmpeg in its own process group so we can kill the entire tree
            if os.name != 'nt':
                # Unix: use preexec_fn to create new process group
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,  # Keep stderr separate to capture progress
                    universal_newlines=True,
                    bufsize=1,  # Line buffered
                    preexec_fn=os.setsid  # Create new process group
                )
            else:
                # Windows: CREATE_NEW_PROCESS_GROUP flag is set automatically
                self.current_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,  # Keep stderr separate to capture progress
                    universal_newlines=True,
                    bufsize=1,  # Line buffered
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
                )
            
            # Monitor progress in real-time
            import threading
            
            stdout_lines = []
            stderr_lines = []
            
            # Track conversion start time for duration calculation
            conversion_start_time = time.time()
            
            if progress_callback and self.current_process:
                # Save PID immediately for state tracking
                current_pid = self.current_process.pid
                logger.info(f"FFmpeg PID: {current_pid}")
                
                # Save process state immediately after PID is available
                # We need to reconstruct the file paths from the current context
                # since we're inside convert_file, not convert_files
                logger.debug("Saving process state with PID after process start")
                # Note: This will be handled by the calling convert_files method
                
                # -progress - sends to stdout, stderr has errors/info
                logger.info("Starting progress monitoring threads...")
                
                def read_stdout():
                    """Read stdout for progress data (-progress -)"""
                    logger.info("Stdout thread started (progress data)")
                    progress_count = 0
                    last_progress_time = 0
                    last_progress_data = None
                    line_count = 0
                    
                    # Progress accumulation buffer
                    progress_buffer = {}
                    
                    while True:
                        if self.cancel_requested:
                            logger.info("Cancel requested, stopping stdout thread")
                            break
                        
                        if self.current_process and self.current_process.stdout:
                            line = self.current_process.stdout.readline()
                            if not line:
                                logger.info("Stdout EOF reached")
                                if last_progress_data:
                                    try:
                                        progress_callback(last_progress_data)
                                        logger.info("Sent final progress update")
                                    except Exception as cb_error:
                                        logger.error(f"Error in final progress callback: {cb_error}")
                                break
                        else:
                            break
                        
                        line_count += 1
                        stdout_lines.append(line)
                        
                        line_stripped = line.strip()
                        if not line_stripped:
                            continue
                        
                        # Parse key=value format from -progress -
                        if '=' in line_stripped:
                            try:
                                key, value = line_stripped.split('=', 1)
                                progress_buffer[key] = value
                                
                                # When we see "progress=continue", we have a complete update
                                if key == 'progress' and value == 'continue':
                                    # Calculate metrics from accumulated buffer
                                    try:
                                        # Get raw values from FFmpeg (handle N/A values gracefully)
                                        frame_str = progress_buffer.get('frame', '0')
                                        current_frame = int(frame_str) if frame_str and frame_str != 'N/A' else 0
                                        
                                        # Handle fps (can be N/A during startup)
                                        fps_str = progress_buffer.get('fps', '0')
                                        encoding_fps = float(fps_str) if fps_str and fps_str != 'N/A' else 0.0
                                        
                                        # Handle speed (can be N/A during startup)
                                        speed_str = progress_buffer.get('speed', '0x').replace('x', '').strip()
                                        encoding_speed = float(speed_str) if speed_str and speed_str != 'N/A' else 0.0
                                        
                                        # Calculate progress percentage from frames (most reliable)
                                        # This works even when other metrics are N/A
                                        if current_frame > 0 and video_info["total_frames"] > 0:
                                            progress_pct = (current_frame / video_info["total_frames"]) * 100
                                        else:
                                            progress_pct = 0
                                        
                                        progress_pct = min(99.9, progress_pct)  # Cap at 99.9% until complete
                                        
                                        # Calculate current time from frames and source fps
                                        # This gives us accurate time even when out_time_us freezes
                                        current_time_seconds = current_frame / video_info["fps"] if video_info["fps"] > 0 else 0
                                        
                                        # Calculate ETA from frames and encoding fps
                                        if encoding_fps > 0 and video_info["total_frames"] > 0 and current_frame > 0:
                                            remaining_frames = video_info["total_frames"] - current_frame
                                            eta_seconds = remaining_frames / encoding_fps
                                            eta_formatted = self._format_time(int(eta_seconds))
                                        else:
                                            eta_formatted = "Calculating..."
                                        
                                        # Calculate actual encoding speed from source fps vs encoding fps
                                        if video_info["fps"] > 0 and encoding_fps > 0:
                                            actual_speed = encoding_fps / video_info["fps"]
                                            speed_formatted = f"{actual_speed:.2f}x"
                                        elif encoding_speed > 0:
                                            speed_formatted = f"{encoding_speed:.2f}x"  # Fallback to FFmpeg's reported speed
                                        else:
                                            speed_formatted = "N/A"  # Initial state - show N/A rather than 0.00x
                                        
                                        # Build complete progress dict
                                        progress_info = {
                                            'file': input_file.name,
                                            'status': 'processing',
                                            'progress': float(progress_pct),
                                            'fps': encoding_fps,
                                            'speed': speed_formatted,
                                            'eta': eta_formatted,
                                            'frame': current_frame,
                                            'total_frames': video_info["total_frames"],
                                            'time': current_time_seconds
                                        }
                                        
                                        last_progress_data = progress_info
                                        
                                        # Send progress even during initial state (when fps/speed are N/A)
                                        # as long as we have frame count for progress percentage
                                        current_time = time.time()
                                        should_send = False
                                        
                                        # Always send if we have meaningful progress (>0%)
                                        if progress_pct > 0:
                                            # Throttle to once every 0.5 seconds during initial state
                                            if current_time - last_progress_time >= 0.5:
                                                should_send = True
                                                last_progress_time = current_time
                                        
                                        if should_send:
                                            progress_count += 1
                                            # Format log message based on available data
                                            if encoding_fps > 0:
                                                logger.info(f"✓ Progress: {progress_pct:.1f}% | Frame: {current_frame}/{video_info['total_frames']} | FPS: {encoding_fps:.1f} | Speed: {speed_formatted} | ETA: {eta_formatted}")
                                            else:
                                                logger.info(f"✓ Progress: {progress_pct:.1f}% | Frame: {current_frame}/{video_info['total_frames']} (initializing...)")
                                            
                                            try:
                                                progress_callback(progress_info)
                                            except Exception as cb_error:
                                                logger.error(f"Error in progress callback: {cb_error}")
                                        
                                    except (ValueError, ZeroDivisionError, TypeError) as e:
                                        # Only log if it's not the common N/A case
                                        if 'N/A' not in str(e):
                                            logger.debug(f"Error calculating progress metrics: {e}")
                                    
                                    # Clear buffer for next update
                                    progress_buffer = {}
                                    
                            except ValueError:
                                logger.debug(f"Could not parse key=value: {line_stripped}")
                    
                    logger.info(f"Stdout thread finished: {line_count} lines, {progress_count} progress updates")
                
                def read_stderr():
                    """Read stderr for errors only (loglevel=error)"""
                    logger.info("Stderr thread started (errors only)")
                    line_count = 0
                    
                    while True:
                        if self.cancel_requested:
                            break
                        
                        if self.current_process and self.current_process.stderr:
                            line = self.current_process.stderr.readline()
                            if not line:
                                logger.info("Stderr EOF reached")
                                break
                        else:
                            break
                        
                        line_count += 1
                        stderr_lines.append(line)
                        
                        # Only log errors (since loglevel=error)
                        if line.strip():
                            error_line = line.strip()
                            logger.error(f"FFmpeg ERROR: {error_line}")
                            
                            # Check for subtitle-specific errors
                            if any(keyword in error_line.lower() for keyword in ['subtitle', 'mov_text', 'srt', 'ass', 'ssa']):
                                logger.warning(f"Subtitle conversion error detected: {error_line}")
                                if 'mov_text' in error_line.lower():
                                    logger.warning("mov_text conversion failed - subtitles may not be included in output")
                    
                    logger.info(f"Stderr thread finished: {line_count} lines")
                
                # Start both threads
                stdout_thread = threading.Thread(target=read_stdout, daemon=True)
                stderr_thread = threading.Thread(target=read_stderr, daemon=True)
                stdout_thread.start()
                stderr_thread.start()
                logger.info("Progress monitoring threads launched")
                
                # Wait for process to complete
                logger.info("Waiting for FFmpeg process to complete...")
                self.current_process.wait()
                logger.info(f"FFmpeg process completed with return code: {self.current_process.returncode}")
                
                # Wait for threads
                stdout_thread.join(timeout=2)
                stderr_thread.join(timeout=2)
                if stdout_thread.is_alive() or stderr_thread.is_alive():
                    logger.warning("Monitoring threads still running after 2s timeout")
                
                stdout = ''.join(stdout_lines)
                stderr = ''.join(stderr_lines)
            else:
                # No progress monitoring, use communicate
                stdout, stderr = self.current_process.communicate()
            
            # Check if cancelled
            if self.cancel_requested:
                self.cancel_requested = False
                # Clean up temporary subtitle files
                for temp_file in temp_subtitle_files:
                    try:
                        if temp_file.exists():
                            temp_file.unlink()
                            logger.debug(f"Cleaned up temp subtitle: {temp_file.name}")
                    except Exception as e:
                        logger.debug(f"Could not delete temp subtitle {temp_file}: {e}")
                return {"status": "cancelled", "message": "Conversion cancelled by user"}
            
            # Check result
            if self.current_process.returncode == 0:
                # Verify output file
                if output_path_obj.exists() and output_path_obj.stat().st_size > 0:
                    # Calculate file size and conversion duration
                    output_size = output_path_obj.stat().st_size
                    output_size_mb = output_size / (1024 * 1024)
                    input_size_mb = input_file.stat().st_size / (1024 * 1024)
                    conversion_duration = time.time() - conversion_start_time if 'conversion_start_time' in locals() else 0
                    
                    logger.info(f"✅ Conversion completed: {output_path_obj.name}")
                    logger.info(f"   Input: {input_size_mb:.2f} MB → Output: {output_size_mb:.2f} MB ({(output_size_mb/input_size_mb)*100:.1f}%)")
                    logger.info(f"   Duration: {self._format_time(int(conversion_duration))}")
                    
                    # Verify subtitle inclusion if subtitles were enabled
                    if self.settings.convert_subtitles and subtitle_tracks:
                        output_subtitle_tracks = self._analyze_subtitle_tracks(str(output_path_obj))
                        if output_subtitle_tracks:
                            logger.info(f"✅ Subtitles included: {len(output_subtitle_tracks)} track(s)")
                            for i, track in enumerate(output_subtitle_tracks):
                                logger.info(f"   Output track {i}: {track.get('codec', 'unknown')} ({track.get('language', 'und')})")
                        else:
                            logger.warning("⚠️ No subtitles found in output file - conversion may have failed")
                    
                    # Send completion progress callback
                    if progress_callback:
                        try:
                            progress_callback({
                                'file': input_file.name,
                                'status': 'completed',
                                'progress': 100,
                                'output_size': output_size,
                                'output_size_mb': f"{output_size_mb:.2f}",
                                'duration_seconds': int(conversion_duration),
                                'duration_formatted': self._format_time(int(conversion_duration))
                            })
                        except Exception as cb_error:
                            logger.error(f"Error sending completion callback: {cb_error}")
                    
                    # Delete original if requested
                    if self.settings.delete_original and input_file != output_path_obj:
                        try:
                            input_file.unlink()
                            logger.info(f"🗑️ Deleted original file: {input_file.name}")
                        except Exception as e:
                            logger.warning(f"Could not delete original file: {e}")
                    
                    # Clean up temporary subtitle files
                    for temp_file in temp_subtitle_files:
                        try:
                            if temp_file.exists():
                                temp_file.unlink()
                                logger.debug(f"Cleaned up temp subtitle: {temp_file.name}")
                        except Exception as e:
                            logger.debug(f"Could not delete temp subtitle {temp_file}: {e}")
                    
                    # Clear output path tracking on successful completion
                    self.current_output_path = None
                    
                    return {
                        "status": "success",
                        "message": "Conversion completed successfully",
                        "output_path": str(output_path_obj),
                        "encoder": encoder_info["codec"],
                        "output_size": output_size,
                        "output_size_mb": output_size_mb,
                        "duration_seconds": conversion_duration
                    }
                else:
                    # Clean up temporary subtitle files on failure
                    for temp_file in temp_subtitle_files:
                        try:
                            if temp_file.exists():
                                temp_file.unlink()
                                logger.debug(f"Cleaned up temp subtitle: {temp_file.name}")
                        except Exception as e:
                            logger.debug(f"Could not delete temp subtitle {temp_file}: {e}")
                    
                    # Clear output path tracking on error
                    self.current_output_path = None
                    
                    return {"status": "error", "message": "Output file is empty or missing"}
            else:
                # Clean up temporary subtitle files on error
                for temp_file in temp_subtitle_files:
                    try:
                        if temp_file.exists():
                            temp_file.unlink()
                            logger.debug(f"Cleaned up temp subtitle: {temp_file.name}")
                    except Exception as e:
                        logger.debug(f"Could not delete temp subtitle {temp_file}: {e}")
                
                # Check if it's a hardware encoder error
                if encoder_info["type"] == "hardware" and self._is_hardware_encoder_error(stderr):
                    logger.warning("Hardware encoder failed, trying software fallback...")
                    return self._retry_with_software_encoder(input_file, output_path_obj, progress_callback)
                else:
                    logger.error(f"Conversion failed: {stderr}")
                    # Clear output path tracking on error
                    self.current_output_path = None
                    
                    return {
                        "status": "error",
                        "message": f"FFmpeg error: {stderr}"
                    }
        
        except Exception as e:
            logger.error(f"Error during conversion: {e}", exc_info=True)
            # Clean up temporary subtitle files on exception
            for temp_file in temp_subtitle_files:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                        logger.debug(f"Cleaned up temp subtitle: {temp_file.name}")
                except Exception as cleanup_error:
                    logger.debug(f"Could not delete temp subtitle {temp_file}: {cleanup_error}")
            # Clear output path tracking on exception
            self.current_output_path = None
            
            return {
                "status": "error",
                "message": f"Conversion error: {str(e)}"
            }
        finally:
            self.current_process = None
    
    def convert_files(
        self,
        file_paths: List[str],
        progress_callback: Optional[Callable] = None
    ) -> Dict:
        """Convert multiple files with full queue tracking"""
        logger.info(f"ConversionHandler.convert_files ENTRY: {len(file_paths)} files, progress_callback={progress_callback is not None}")
        logger.info(f"File paths: {file_paths}")
        
        results = []
        total_files = len(file_paths)
        logger.info(f"Initialized: total_files={total_files}")
        
        # Initialize queue tracking
        self._file_queue = []
        self._current_index = 0
        self._completed_files = []
        self._failed_files = []
        logger.info("Queue tracking initialized")
        
        logger.info(f"Starting loop over {total_files} files")
        for idx, file_path in enumerate(file_paths, 1):
            logger.info(f"=== Processing {idx}/{total_files}: {Path(file_path).name} ===")
            
            # Update current index
            self._current_index = idx
            
            # Save process state before starting each file
            self._save_process_state(file_paths, idx, total_files)
            
            if progress_callback:
                progress_callback({
                    "file": Path(file_path).name,
                    "progress": int((idx - 1) / total_files * 100),
                    "status": f"Converting {Path(file_path).name}",
                    "current": idx,
                    "total": total_files
                })
            
            result = self.convert_file(file_path, progress_callback=progress_callback)
            
            # Save process state with PID after conversion starts (if process is running)
            if self.current_process:
                try:
                    current_pid = self.current_process.pid
                    logger.info(f"Saving process state with PID: {current_pid}")
                    self._save_process_state(file_paths, idx, total_files)
                except Exception as e:
                    logger.warning(f"Could not save process state with PID: {e}")
            results.append({
                "input": file_path,
                "result": result
            })
            
            # Track completion/failure
            if result["status"] == "success":
                self._completed_files.append(file_path)
                logger.info(f"✓ Completed {idx}/{total_files}: {Path(file_path).name}")
            elif result["status"] == "error":
                self._failed_files.append({
                    'path': file_path,
                    'error': result.get('message', 'Unknown error')
                })
                logger.error(f"✗ Failed {idx}/{total_files}: {Path(file_path).name} - {result['message']}")
            elif result["status"] == "cancelled":
                logger.info("Batch conversion cancelled by user")
                break
            
            # Update state after each file completes
            self._save_process_state(file_paths, idx, total_files)
        
        success_count = sum(1 for r in results if r["result"]["status"] == "success")
        
        # Clear process state only when batch fully completes or is cancelled
        self._clear_process_state()
        
        return {
            "status": "success",
            "converted": success_count,
            "failed": len(self._failed_files),
            "total": total_files,
            "results": results
        }
    
    def cancel_current(self) -> Dict:
        """Cancel the current conversion (cross-platform process tree termination)"""
        logger.info(f"cancel_current called, current_process: {self.current_process is not None}")
        if self.current_process:
            try:
                logger.info("Attempting to cancel conversion...")
                self.cancel_requested = True
                pid = self.current_process.pid
                
                # Platform-specific process tree termination
                # We need to kill the entire process tree, not just the parent
                if os.name == 'nt':  # Windows
                    logger.info(f"Windows: Using taskkill to terminate PID {pid} and all children")
                    try:
                        # /F = Force termination, /T = Tree kill (kills children too)
                        result = subprocess.run(
                            ['taskkill', '/F', '/T', '/PID', str(pid)],
                            capture_output=True, text=True, timeout=5
                        )
                        logger.info(f"taskkill output: {result.stdout}")
                        if result.stderr:
                            logger.warning(f"taskkill stderr: {result.stderr}")
                        
                    except subprocess.TimeoutExpired:
                        logger.error("taskkill command timed out")
                    except Exception as e:
                        logger.error(f"taskkill failed: {e}")
                        
                else:  # Linux/macOS
                    logger.info(f"Unix: Using process group kill for PID {pid}")
                    try:
                        # Kill process group (includes all children spawned by FFmpeg)
                        # This is the proper way to kill FFmpeg and its subprocesses
                        pgid = os.getpgid(pid)
                        logger.info(f"Process group ID: {pgid}")
                        os.killpg(pgid, signal.SIGTERM)
                        logger.info("Sent SIGTERM to process group")
                        
                    except ProcessLookupError:
                        logger.warning("Process group not found, trying direct kill")
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except ProcessLookupError:
                            logger.warning("Process no longer exists")
                    except Exception as e:
                        logger.error(f"Process group kill failed: {e}")
                        # Try direct kill as fallback
                        try:
                            os.kill(pid, signal.SIGTERM)
                        except Exception as direct_kill_error:
                            logger.error(f"Direct kill also failed: {direct_kill_error}")
                
                # Wait for termination
                time.sleep(1.0)
                
                # Verify process is actually dead
                if not self._is_process_running(pid):
                    logger.info("✓ Conversion cancelled successfully - process terminated")
                    
                    # Clean up incomplete output file
                    self._cleanup_incomplete_file()
                    
                    self._clear_process_state()
                    return {"status": "success", "message": "Conversion cancelled"}
                else:
                    logger.error(f"Process {pid} still running after termination attempt!")
                    
                    # Force kill as last resort
                    logger.warning("Attempting force kill...")
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                                     capture_output=True, timeout=3)
                    else:
                        try:
                            os.killpg(os.getpgid(pid), signal.SIGKILL)
                        except Exception:
                            os.kill(pid, signal.SIGKILL)
                    
                    # Final verification
                    time.sleep(0.5)
                    if not self._is_process_running(pid):
                        logger.warning("Process force killed")
                        
                        # Clean up incomplete output file
                        self._cleanup_incomplete_file()
                        
                        self._clear_process_state()
                        return {"status": "success", "message": "Conversion force killed"}
                    else:
                        logger.error(f"Failed to kill process {pid} - it may be stuck")
                        return {"status": "error", "message": "Failed to terminate process"}
                        
            except Exception as e:
                logger.error(f"Error cancelling conversion: {e}", exc_info=True)
                return {"status": "error", "message": f"Failed to cancel: {str(e)}"}
            finally:
                # Always reset the process reference and cancel flag
                self.current_process = None
                self.cancel_requested = False
                self.current_output_path = None
        else:
            logger.info("No active conversion to cancel")
            return {"status": "success", "message": "No active conversion"}
    
    def _cleanup_incomplete_file(self):
        """Clean up incomplete output file when conversion is cancelled"""
        if self.current_output_path:
            try:
                output_file = Path(self.current_output_path)
                if output_file.exists():
                    file_size = output_file.stat().st_size
                    logger.info(f"Cleaning up incomplete output file: {output_file} ({file_size} bytes)")
                    output_file.unlink()
                    logger.info(f"✓ Deleted incomplete file: {output_file}")
                else:
                    logger.debug(f"Output file doesn't exist, nothing to clean up: {output_file}")
            except Exception as e:
                logger.error(f"Failed to clean up incomplete file {self.current_output_path}: {e}")
            finally:
                self.current_output_path = None
    
    def _verify_file_integrity(self, input_path: str, output_path: str) -> Dict[str, Any]:
        """Verify the integrity of converted file"""
        try:
            # input_file = Path(input_path)  # Not used currently
            output_file = Path(output_path)
            
            if not output_file.exists():
                return {"valid": False, "error": "Output file does not exist"}
            
            output_size = output_file.stat().st_size
            if output_size == 0:
                return {"valid": False, "error": "Output file is empty"}
            
            # Try to get duration of output file
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(output_file)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                duration = float(data.get("format", {}).get("duration", 0))
                
                if duration > 0:
                    return {
                        "valid": True,
                        "duration": duration,
                        "size": output_size
                    }
                else:
                    return {"valid": False, "error": "Output file has no duration"}
            else:
                return {"valid": False, "error": "Could not probe output file"}
        
        except Exception as e:
            logger.error(f"Error verifying file: {e}")
            return {"valid": False, "error": str(e)}
    
    def _get_process_state_file(self) -> Path:
        """Get the path to the process state file"""
        # Use unified application data directory
        from path_manager import get_conversion_state_file
        return get_conversion_state_file()
    
    def _save_process_state(self, file_paths: List[str], current_index: int, total_files: int):
        """Save entire conversion queue state to disk for recovery"""
        try:
            # Build queue status for all files
            queue = []
            for i, path in enumerate(file_paths):
                file_entry = {
                    "path": path,
                    "index": i,
                    "filename": Path(path).name
                }
                
                if i < current_index - 1:
                    # Already processed
                    file_entry["status"] = "completed"
                    # Find in completed files
                    for completed in self._completed_files:
                        if completed == path:
                            file_entry["output"] = str(Path(path).with_suffix(f".{self.settings.output_format}"))
                            break
                elif i == current_index - 1:
                    # Currently processing
                    file_entry["status"] = "processing"
                    # Get PID with error handling
                    if self.current_process:
                        try:
                            file_entry["pid"] = self.current_process.pid
                        except Exception as e:
                            logger.warning(f"Could not get PID for processing file: {e}")
                            file_entry["pid"] = None
                    else:
                        file_entry["pid"] = None
                else:
                    # Waiting to process
                    file_entry["status"] = "queued"
                
                # Check if failed
                for failed in self._failed_files:
                    if failed.get('path') == path:
                        file_entry["status"] = "failed"
                        file_entry["error"] = failed.get('error', 'Unknown error')
                        break
                
                queue.append(file_entry)
            
            # Get PID with better error handling
            current_pid = None
            if self.current_process:
                try:
                    current_pid = self.current_process.pid
                    logger.debug(f"Saving process state with PID: {current_pid}")
                except Exception as e:
                    logger.warning(f"Could not get PID from current_process: {e}")
                    current_pid = None
            
            state = {
                'timestamp': time.time(),
                'pid': current_pid,
                'queue': queue,
                'current_index': current_index,
                'total_files': total_files,
                'current_file': getattr(self, '_current_file', ''),
                'completed_count': len(self._completed_files),
                'failed_count': len(self._failed_files),
                'settings': {
                    'ffmpeg_path': self.settings.ffmpeg_path,
                    'ffprobe_path': self.settings.ffprobe_path,
                    'output_format': self.settings.output_format,
                    'video_codec_fallback': self.settings.video_codec_fallback,
                    'audio_codec': self.settings.audio_codec,
                }
            }
            
            state_file = self._get_process_state_file()
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            logger.debug(f"Saved conversion queue state to {state_file} ({len(queue)} files)")
            
        except Exception as e:
            logger.error(f"Error saving process state: {e}")
    
    def _clear_process_state(self):
        """Clear the saved process state"""
        try:
            state_file = self._get_process_state_file()
            if state_file.exists():
                state_file.unlink()
                logger.debug("Cleared conversion state")
        except Exception as e:
            logger.error(f"Error clearing process state: {e}")
    
    def get_saved_process_state(self) -> Optional[Dict]:
        """Get saved process state if it exists and is recent"""
        try:
            state_file = self._get_process_state_file()
            if not state_file.exists():
                return None
            
            with open(state_file, 'r') as f:
                state = json.load(f)
            
            # Check if state is recent (within last hour)
            if time.time() - state.get('timestamp', 0) > 3600:
                logger.debug("Saved state is too old, ignoring")
                self._clear_process_state()
                return None
            
            # Check if the process is still running
            pid = state.get('pid')
            if pid and self._is_process_running(pid):
                logger.info(f"Found ongoing conversion process (PID: {pid})")
                return state
            else:
                logger.debug("Saved process is no longer running")
                self._clear_process_state()
                return None
                
        except Exception as e:
            logger.error(f"Error reading process state: {e}")
            return None
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is still running (cross-platform)"""
        try:
            if os.name == 'nt':  # Windows
                # Use tasklist command to check if process exists
                result = subprocess.run(['tasklist', '/FI', f'PID eq {pid}'], 
                                      capture_output=True, text=True, timeout=5)
                return str(pid) in result.stdout and result.returncode == 0
            else:  # Unix-like (Linux, macOS)
                try:
                    # Signal 0 just checks if process exists without killing it
                    os.kill(pid, 0)
                    return True
                except (OSError, ProcessLookupError):
                    return False
        except subprocess.TimeoutExpired:
            logger.debug(f"Timeout checking process {pid}")
            return False
        except Exception as e:
            logger.debug(f"Error checking if process {pid} is running: {e}")
            return False

