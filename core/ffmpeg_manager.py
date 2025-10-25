#!/usr/bin/env python3
"""
FFmpeg Manager - Handles FFmpeg detection, download, and version management
"""

import logging
import os
import platform
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class FFmpegManager:
    """Manages FFmpeg installation and detection"""
    
    FFMPEG_DOWNLOAD_URLS = {
        "Windows": "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
        "Darwin": "https://evermeet.cx/ffmpeg/getrelease/ffmpeg/zip",
        "Linux": "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    }
    
    def __init__(self, custom_path: Optional[str] = None):
        self.custom_path = custom_path
        self.ffmpeg_path = None
        self.ffprobe_path = None
        self.version_info = {}
        self._detection_cache = None  # Cache detection results for instant subsequent calls
        self._cache_timestamp = 0
        self._encoder_test_cache = {}  # Cache encoder test results {encoder_name: (is_functional, timestamp)}
        self._encoder_cache_duration = 300  # 5 minutes
        self._embedded_ffmpeg_checked = False
        self._embedded_ffmpeg_path = None
        self._embedded_ffprobe_path = None
    
    def _check_embedded_ffmpeg(self) -> bool:
        """Check if embedded FFmpeg is available from Java runtime"""
        if self._embedded_ffmpeg_checked:
            return self._embedded_ffmpeg_path is not None
        
        self._embedded_ffmpeg_checked = True
        
        try:
            # Check for FFmpeg runtime directory from Java system property
            import os
            ffmpeg_runtime_dir = os.getenv('FFMPEG_RUNTIME_DIR')
            if not ffmpeg_runtime_dir:
                # Try to get from Java system property (set by JavaBridge)
                # This is a fallback method - ideally Java should set the environment variable
                return False
            
            # Check for FFmpeg binaries in the runtime directory
            if platform.system() == "Windows":
                ffmpeg_exe = os.path.join(ffmpeg_runtime_dir, "ffmpeg.exe")
                ffprobe_exe = os.path.join(ffmpeg_runtime_dir, "ffprobe.exe")
            else:
                ffmpeg_exe = os.path.join(ffmpeg_runtime_dir, "ffmpeg")
                ffprobe_exe = os.path.join(ffmpeg_runtime_dir, "ffprobe")
            
            if os.path.exists(ffmpeg_exe) and os.path.exists(ffprobe_exe):
                self._embedded_ffmpeg_path = ffmpeg_exe
                self._embedded_ffprobe_path = ffprobe_exe
                logger.info(f"Found embedded FFmpeg: {ffmpeg_exe}")
                return True
            
        except Exception as e:
            logger.debug(f"Error checking for embedded FFmpeg: {e}")
        
        return False
    
    def detect_ffmpeg(self, use_cache: bool = True) -> Tuple[bool, Dict[str, Union[str, List[str]]]]:
        """
        Detect FFmpeg installation and get version information
        
        Args:
            use_cache: If True, return cached results if available (default)
        
        Returns:
            (success, info_dict)
        """
        import time
        
        # Return cached results instantly if available and not too old (< 5 minutes)
        if use_cache and self._detection_cache is not None:
            cache_age = time.time() - self._cache_timestamp
            if cache_age < 300:  # 5 minutes
                logger.debug(f"Using cached FFmpeg detection (age: {cache_age:.1f}s)")
                return self._detection_cache
        paths_to_check = []
        
        # Check embedded FFmpeg first (highest priority)
        if self._check_embedded_ffmpeg():
            paths_to_check.append(self._embedded_ffmpeg_path)
        
        # Check custom path second
        if self.custom_path:
            paths_to_check.append(self.custom_path)
        
        # Check environment variable
        if os.getenv("FFMPEG_PATH"):
            paths_to_check.append(os.getenv("FFMPEG_PATH"))
        
        # Check common installation paths
        if platform.system() == "Windows":
            # Check PATH using shutil.which first (most reliable)
            try:
                import shutil
                which_result = shutil.which("ffmpeg")
                if which_result:
                    paths_to_check.insert(0, which_result)
            except Exception:
                pass
            
            # Add executable variants
            paths_to_check.extend([
                "ffmpeg.exe",
                "ffmpeg",
            ])
            
            # User directories (including Documents)
            userprofile = os.getenv("USERPROFILE", "")
            if userprofile:
                paths_to_check.extend([
                    os.path.join(userprofile, "ffmpeg\\bin\\ffmpeg.exe"),
                    os.path.join(userprofile, "ffmpeg\\ffmpeg.exe"),
                    os.path.join(userprofile, "Documents\\ffmpeg\\bin\\ffmpeg.exe"),
                    os.path.join(userprofile, "Documents\\ffmpeg\\ffmpeg.exe"),
                    os.path.join(userprofile, "Downloads\\ffmpeg\\bin\\ffmpeg.exe"),
                    os.path.join(userprofile, "Downloads\\ffmpeg\\ffmpeg.exe"),
                ])
            
            # Common installation paths
            paths_to_check.extend([
                "C:\\ffmpeg\\bin\\ffmpeg.exe",
                "C:\\ffmpeg\\ffmpeg.exe",
                "C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe",
                "C:\\Program Files (x86)\\ffmpeg\\bin\\ffmpeg.exe",
            ])
            
            # Check LOCALAPPDATA and PROGRAMFILES
            localappdata = os.getenv("LOCALAPPDATA", "")
            if localappdata:
                paths_to_check.extend([
                    # EncodeForge embedded FFmpeg location (highest priority for LOCALAPPDATA)
                    os.path.join(localappdata, "EncodeForge\\ffmpeg\\bin\\ffmpeg.exe"),
                    os.path.join(localappdata, "EncodeForge\\ffmpeg\\ffmpeg.exe"),
                    os.path.join(localappdata, "EncodeForge\\ffmpeg.exe"),
                    # Generic FFmpeg installation
                    os.path.join(localappdata, "ffmpeg\\bin\\ffmpeg.exe"),
                    os.path.join(localappdata, "ffmpeg\\ffmpeg.exe"),
                ])
            
            programfiles = os.getenv("PROGRAMFILES", "")
            if programfiles:
                paths_to_check.append(os.path.join(programfiles, "ffmpeg\\bin\\ffmpeg.exe"))
            
            # Try recursive search in Documents folder
            if userprofile:
                docs_path = os.path.join(userprofile, "Documents")
                if os.path.exists(docs_path):
                    logger.info(f"Searching recursively in: {docs_path}")
                    found_path = self._recursive_search(docs_path, "ffmpeg.exe", max_depth=3)
                    if found_path:
                        logger.info(f"Recursive search found: {found_path}")
                        paths_to_check.insert(0, found_path)
                    else:
                        logger.debug("Recursive search in Documents did not find ffmpeg.exe")
        elif platform.system() == "Darwin":  # macOS
            # Check PATH using shutil.which first (most reliable)
            try:
                import shutil
                which_result = shutil.which("ffmpeg")
                if which_result:
                    paths_to_check.insert(0, which_result)
            except Exception:
                pass
            
            # Common macOS installation paths
            paths_to_check.extend([
                "ffmpeg",
                "/usr/local/bin/ffmpeg",
                "/opt/homebrew/bin/ffmpeg",  # Apple Silicon Homebrew
                "/usr/bin/ffmpeg",
                "/opt/ffmpeg/bin/ffmpeg",
                os.path.expanduser("~/bin/ffmpeg"),
                os.path.expanduser("~/ffmpeg/ffmpeg"),
            ])
            
            # Check Homebrew installations
            homebrew_prefixes = ["/opt/homebrew", "/usr/local"]
            for prefix in homebrew_prefixes:
                if os.path.exists(prefix):
                    paths_to_check.extend([
                        os.path.join(prefix, "bin", "ffmpeg"),
                        os.path.join(prefix, "Cellar", "ffmpeg", "bin", "ffmpeg")
                    ])
            
            # Check MacPorts
            if os.path.exists("/opt/local"):
                paths_to_check.extend([
                    "/opt/local/bin/ffmpeg",
                    "/opt/local/lib/ffmpeg/bin/ffmpeg"
                ])

        else:  # Linux/Unix
            # Check PATH using shutil.which first (most reliable)
            try:
                import shutil
                which_result = shutil.which("ffmpeg")
                if which_result:
                    paths_to_check.insert(0, which_result)
            except Exception:
                pass
            
            # Common Linux installation paths
            paths_to_check.extend([
                "ffmpeg",
                "/usr/bin/ffmpeg",
                "/usr/local/bin/ffmpeg",
                "/opt/ffmpeg/bin/ffmpeg",
                "/snap/bin/ffmpeg",  # Snap package
                os.path.expanduser("~/bin/ffmpeg"),
                os.path.expanduser("~/ffmpeg/ffmpeg"),
            ])
            
            # Check snap installations
            snap_path = "/snap/bin/ffmpeg"
            if os.path.exists(snap_path):
                paths_to_check.append(snap_path)
            
            # Check Flatpak installations
            flatpak_paths = [
                os.path.expanduser("~/.local/share/flatpak/exports/bin/ffmpeg"),
                "/var/lib/flatpak/exports/bin/ffmpeg"
            ]
            for flatpak_path in flatpak_paths:
                if os.path.exists(flatpak_path):
                    paths_to_check.append(flatpak_path)
        
        # Try each path
        logger.info(f"Searching for FFmpeg in {len([p for p in paths_to_check if p])} locations...")
        for path in paths_to_check:
            if path:
                logger.debug(f"Checking: {path}")
                if self._test_ffmpeg(path):
                    self.ffmpeg_path = path
                    self.ffprobe_path = path.replace("ffmpeg", "ffprobe")
                    
                    logger.info(f"✓ Found FFmpeg at: {path}")
                    
                    # Get version info
                    self.version_info = self._get_version_info()
                    
                    # Cache the successful result for instant subsequent calls
                    result = (True, {
                        "ffmpeg_path": self.ffmpeg_path,
                        "ffprobe_path": self.ffprobe_path,
                        "version": self.version_info.get("version", "Unknown"),
                        "configuration": self.version_info.get("configuration", ""),
                        "encoders": self.version_info.get("encoders", []),
                        "decoders": self.version_info.get("decoders", []),
                    })
                    self._detection_cache = result
                    self._cache_timestamp = time.time()
                    logger.debug("Cached FFmpeg detection results")
                    return result
        
        logger.warning("FFmpeg not found in any checked location")
        logger.debug(f"Searched paths: {[p for p in paths_to_check if p]}")
        
        # Cache failure result too (but with shorter timeout handled above)
        result = (False, {
            "error": "FFmpeg not found in system PATH or common locations",
            "searched_paths": [p for p in paths_to_check if p]
        })
        self._detection_cache = result
        self._cache_timestamp = time.time()
        return result
    
    def _recursive_search(self, directory: str, filename: str, max_depth: int = 3, current_depth: int = 0) -> Optional[str]:
        """Recursively search for a file in directory tree"""
        if current_depth > max_depth:
            return None
        
        try:
            for entry in os.listdir(directory):
                full_path = os.path.join(directory, entry)
                
                # Check if this is the file we're looking for
                if entry.lower() == filename.lower() and os.path.isfile(full_path):
                    return full_path
                
                # Recurse into subdirectories
                if os.path.isdir(full_path) and not entry.startswith('.'):
                    result = self._recursive_search(full_path, filename, max_depth, current_depth + 1)
                    if result:
                        return result
        except (PermissionError, OSError):
            pass
        
        return None
    
    def _test_ffmpeg(self, path: str) -> bool:
        """Test if FFmpeg is available at the given path"""
        if not path:
            return False
        
        try:
            result = subprocess.run(
                [path, "-version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            return False
    
    def _get_version_info(self) -> Dict:
        """Get detailed version information from FFmpeg"""
        info = {}
        
        try:
            # Get version
            if self.ffmpeg_path:
                result = subprocess.run(
                    [self.ffmpeg_path, "-version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
            else:
                return info
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                if lines:
                    # Parse version line
                    version_line = lines[0]
                    if "version" in version_line:
                        info["version"] = version_line.split("version")[1].split()[0]
                    
                    # Parse configuration
                    for line in lines:
                        if "configuration:" in line:
                            info["configuration"] = line.split("configuration:")[1].strip()
                            break
            
            # Check for hardware encoders
            encoders = self._check_encoders()
            info["encoders"] = encoders
            
            # Check for hardware decoders
            decoders = self._check_decoders()
            info["decoders"] = decoders
            
        except Exception as e:
            logger.error(f"Error getting FFmpeg version info: {e}")
        
        return info
    
    def _check_encoders(self) -> list:
        """Check available hardware encoders"""
        encoders = []
        
        try:
            if not self.ffmpeg_path:
                return encoders
            
            result = subprocess.run(
                [self.ffmpeg_path, "-encoders"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                
                # Check for various hardware encoders
                hw_encoders = [
                    ("h264_nvenc", "NVIDIA H.264"),
                    ("hevc_nvenc", "NVIDIA H.265"),
                    ("h264_amf", "AMD H.264"),
                    ("hevc_amf", "AMD H.265"),
                    ("h264_qsv", "Intel Quick Sync H.264"),
                    ("hevc_qsv", "Intel Quick Sync H.265"),
                    ("h264_videotoolbox", "Apple VideoToolbox H.264"),
                    ("hevc_videotoolbox", "Apple VideoToolbox H.265"),
                ]
                
                for encoder_id, encoder_name in hw_encoders:
                    if encoder_id in output:
                        # Test if the encoder actually works
                        if self._test_encoder(encoder_id):
                            encoders.append(encoder_name)
                        else:
                            logger.warning(f"Encoder {encoder_id} is available but not functional")
        
        except Exception as e:
            logger.error(f"Error checking encoders: {e}")
        
        return encoders
    
    def _test_encoder(self, encoder_name: str, use_cache: bool = True) -> bool:
        """
        Test if a hardware encoder is actually functional
        
        Args:
            encoder_name: Name of the encoder to test
            use_cache: If True, return cached results if available (default)
        
        Returns:
            True if encoder is functional, False otherwise
        """
        import time
        
        # Check cache first (return instantly if available)
        if use_cache and encoder_name in self._encoder_test_cache:
            cached_result, cached_time = self._encoder_test_cache[encoder_name]
            cache_age = time.time() - cached_time
            if cache_age < self._encoder_cache_duration:
                logger.debug(f"Using cached encoder test for {encoder_name}: {cached_result} (age: {cache_age:.1f}s)")
                return cached_result
        
        try:
            if not self.ffmpeg_path:
                self._encoder_test_cache[encoder_name] = (False, time.time())
                return False
            
            # Create a minimal test command to check if encoder works
            # This creates a 0.1s black video to test the encoder quickly
            cmd = [
                self.ffmpeg_path,
                "-f", "lavfi",
                "-i", "color=black:size=320x240:duration=0.1",
                "-c:v", encoder_name,
                "-f", "null",
                "-"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5  # Reduced from 10s for faster detection
            )
            
            # If return code is 0, encoder works
            success = result.returncode == 0
            if not success:
                logger.debug(f"Encoder {encoder_name} test failed: {result.stderr[:200]}")  # Limit log size
            
            # Cache the result for instant subsequent calls
            self._encoder_test_cache[encoder_name] = (success, time.time())
            
            return success
            
        except Exception as e:
            logger.debug(f"Error testing encoder {encoder_name}: {e}")
            # Cache the failure result
            self._encoder_test_cache[encoder_name] = (False, time.time())
            return False
    
    def _check_decoders(self) -> list:
        """Check available hardware decoders"""
        decoders = []
        
        try:
            if not self.ffmpeg_path:
                return decoders
            
            result = subprocess.run(
                [self.ffmpeg_path, "-decoders"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                
                # Check for various hardware decoders
                hw_decoders = [
                    ("h264_cuvid", "NVIDIA H.264 (CUVID)"),
                    ("hevc_cuvid", "NVIDIA H.265 (CUVID)"),
                    ("h264_qsv", "Intel Quick Sync H.264"),
                    ("hevc_qsv", "Intel Quick Sync H.265"),
                ]
                
                for decoder_id, decoder_name in hw_decoders:
                    if decoder_id in output:
                        decoders.append(decoder_name)
        
        except Exception as e:
            logger.error(f"Error checking decoders: {e}")
        
        return decoders
    
    def download_ffmpeg(self, install_dir: Optional[Path] = None, progress_callback=None) -> Tuple[bool, str]:
        """
        Download and install FFmpeg
        
        Args:
            install_dir: Directory to install FFmpeg (default: user's home directory)
            progress_callback: Function to call with progress updates
            
        Returns:
            (success, message)
        """
        system = platform.system()
        
        if system not in self.FFMPEG_DOWNLOAD_URLS:
            return False, f"Automatic download not supported for {system}"
        
        download_url = self.FFMPEG_DOWNLOAD_URLS[system]
        
        # Set install directory
        if install_dir is None:
            if system == "Windows":
                local_appdata = os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
                install_dir = Path(local_appdata) / "ffmpeg"
            else:
                install_dir = Path.home() / ".local" / "bin"
        
        install_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Download file
            if progress_callback:
                progress_callback({"status": "downloading", "progress": 0, "message": "Downloading FFmpeg..."})
            
            filename = download_url.split("/")[-1]
            download_path = install_dir / filename
            
            logger.info(f"Downloading FFmpeg from {download_url}")
            
            def download_progress(block_num, block_size, total_size):
                if progress_callback and total_size > 0:
                    progress = min(100, (block_num * block_size * 100) / total_size)
                    progress_callback({
                        "status": "downloading",
                        "progress": progress,
                        "message": f"Downloading: {progress:.1f}%"
                    })
            
            urllib.request.urlretrieve(download_url, download_path, reporthook=download_progress)
            
            # Extract
            if progress_callback:
                progress_callback({"status": "extracting", "progress": 50, "message": "Extracting..."})
            
            logger.info(f"Extracting {download_path}")
            
            if filename.endswith(".zip"):
                with zipfile.ZipFile(download_path, 'r') as zip_ref:
                    zip_ref.extractall(install_dir)
            elif filename.endswith((".tar.xz", ".tar.gz")):
                with tarfile.open(download_path, 'r:*') as tar_ref:
                    tar_ref.extractall(install_dir)
            
            # Find ffmpeg executable
            for root, dirs, files in os.walk(install_dir):
                for file in files:
                    if file.startswith("ffmpeg") and (file.endswith(".exe") or "." not in file):
                        ffmpeg_exe = Path(root) / file
                        self.ffmpeg_path = str(ffmpeg_exe)
                        self.ffprobe_path = str(ffmpeg_exe).replace("ffmpeg", "ffprobe")
                        
                        # Make executable on Unix systems
                        if system != "Windows":
                            os.chmod(ffmpeg_exe, 0o755)
                            if Path(self.ffprobe_path).exists():
                                os.chmod(self.ffprobe_path, 0o755)
                        
                        # Clean up download file
                        download_path.unlink()
                        
                        if progress_callback:
                            progress_callback({
                                "status": "complete",
                                "progress": 100,
                                "message": f"FFmpeg installed successfully at {self.ffmpeg_path}"
                            })
                        
                        return True, f"FFmpeg installed at {self.ffmpeg_path}"
            
            return False, "FFmpeg executable not found in downloaded package"
            
        except Exception as e:
            logger.error(f"Error downloading FFmpeg: {e}")
            return False, f"Download failed: {str(e)}"
    
    def detect_hardware(self) -> Dict[str, Any]:
        """Detect system hardware (GPU, CPU) for codec compatibility"""
        hardware_info = {
            "gpu": {
                "nvidia": False,
                "amd": False,
                "intel": False,
                "apple": False,
                "details": []
            },
            "cpu": {
                "vendor": "unknown",
                "model": "unknown",
                "supports_qsv": False
            }
        }
        
        try:
            # Detect GPU using multiple methods
            self._detect_gpu_wmi(hardware_info)
            self._detect_gpu_nvidia_smi(hardware_info)
            self._detect_gpu_dxdiag(hardware_info)
            
            # Detect CPU
            self._detect_cpu(hardware_info)
            
        except Exception as e:
            logger.debug(f"Error detecting hardware: {e}")
        
        return hardware_info
    
    def _detect_gpu_wmi(self, hardware_info: Dict):
        """Detect GPU using WMI (Windows only)"""
        if platform.system() != "Windows":
            return
        
        try:
            import subprocess
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                output = result.stdout.lower()
                if "nvidia" in output or "geforce" in output or "quadro" in output or "rtx" in output or "gtx" in output:
                    hardware_info["gpu"]["nvidia"] = True
                    hardware_info["gpu"]["details"].append("NVIDIA GPU detected via WMI")
                
                if "amd" in output or "radeon" in output or "rx " in output:
                    hardware_info["gpu"]["amd"] = True
                    hardware_info["gpu"]["details"].append("AMD GPU detected via WMI")
                
                if "intel" in output or "uhd" in output or "iris" in output:
                    hardware_info["gpu"]["intel"] = True
                    hardware_info["gpu"]["details"].append("Intel GPU detected via WMI")
                    
        except Exception as e:
            logger.debug(f"WMI GPU detection failed: {e}")
    
    def _detect_gpu_nvidia_smi(self, hardware_info: Dict):
        """Detect NVIDIA GPU using nvidia-smi"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and result.stdout.strip():
                hardware_info["gpu"]["nvidia"] = True
                gpu_name = result.stdout.strip()
                hardware_info["gpu"]["details"].append(f"NVIDIA GPU: {gpu_name}")
                
        except Exception as e:
            logger.debug(f"nvidia-smi detection failed: {e}")
    
    def _detect_gpu_dxdiag(self, hardware_info: Dict):
        """Detect GPU using dxdiag (Windows only)"""
        if platform.system() != "Windows":
            return
        
        try:
            result = subprocess.run(
                ["dxdiag", "/t", "dxdiag_output.txt"],
                capture_output=True,
                timeout=15
            )
            
            if result.returncode == 0:
                try:
                    with open("dxdiag_output.txt", "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read().lower()
                        
                        if "nvidia" in content or "geforce" in content:
                            hardware_info["gpu"]["nvidia"] = True
                            hardware_info["gpu"]["details"].append("NVIDIA GPU detected via dxdiag")
                        
                        if "amd" in content or "radeon" in content:
                            hardware_info["gpu"]["amd"] = True
                            hardware_info["gpu"]["details"].append("AMD GPU detected via dxdiag")
                        
                        if "intel" in content and ("uhd" in content or "iris" in content):
                            hardware_info["gpu"]["intel"] = True
                            hardware_info["gpu"]["details"].append("Intel GPU detected via dxdiag")
                    
                    # Clean up
                    os.remove("dxdiag_output.txt")
                except Exception as e:
                    logger.debug(f"Error reading dxdiag output: {e}")
                    
        except Exception as e:
            logger.debug(f"dxdiag detection failed: {e}")
    
    def _detect_cpu(self, hardware_info: Dict):
        """Detect CPU information"""
        try:
            import platform
            hardware_info["cpu"]["model"] = platform.processor()
            
            # Try to get more detailed CPU info
            if platform.system() == "Windows":
                try:
                    result = subprocess.run(
                        ["wmic", "cpu", "get", "name"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    
                    if result.returncode == 0:
                        cpu_name = result.stdout.strip().split('\n')[-1].strip()
                        if cpu_name and cpu_name != "Name":
                            hardware_info["cpu"]["model"] = cpu_name
                            
                            # Check for Intel (supports Quick Sync)
                            if "intel" in cpu_name.lower():
                                hardware_info["cpu"]["vendor"] = "intel"
                                hardware_info["cpu"]["supports_qsv"] = True
                            elif "amd" in cpu_name.lower():
                                hardware_info["cpu"]["vendor"] = "amd"
                                
                except Exception as e:
                    logger.debug(f"CPU detection via wmic failed: {e}")
            
            else:
                # Linux/macOS
                try:
                    with open("/proc/cpuinfo", "r") as f:
                        content = f.read().lower()
                        if "intel" in content:
                            hardware_info["cpu"]["vendor"] = "intel"
                            hardware_info["cpu"]["supports_qsv"] = True
                        elif "amd" in content:
                            hardware_info["cpu"]["vendor"] = "amd"
                except Exception:
                    pass
                    
        except Exception as e:
            logger.debug(f"CPU detection failed: {e}")

    def get_hwaccel_options(self) -> Dict[str, List[str]]:
        """Get available hardware acceleration options"""
        options = {
            "decode": [],
            "encode": []
        }
        
        # Auto-detect FFmpeg if not already done (lazy detection)
        if not self.ffmpeg_path:
            logger.info("FFmpeg path not set, attempting auto-detection for hardware acceleration...")
            success, info = self.detect_ffmpeg()
            if not success:
                logger.warning("FFmpeg auto-detection failed, no hardware acceleration available")
                return options
            logger.info(f"FFmpeg auto-detected: {info.get('ffmpeg_path')}")
        
        if not self.ffmpeg_path:
            logger.debug("No FFmpeg path available for hardware detection")
            return options
        
        logger.debug(f"Available encoders: {self.version_info.get('encoders', [])}")
        
        # Check for NVIDIA
        if "NVIDIA" not in " ".join(self.version_info.get("encoders", [])):
            pass
        else:
            options["decode"].append("cuda")
            options["decode"].append("cuvid")
            options["encode"].append("nvenc")
        
        # Check for AMD (AMF encoders)
        encoders_str = " ".join(self.version_info.get("encoders", []))
        if "AMD" in encoders_str or "h264_amf" in encoders_str or "hevc_amf" in encoders_str:
            options["decode"].append("amf")
            options["encode"].append("amf")
        
        # Check for Intel
        if "Intel" in " ".join(self.version_info.get("encoders", [])):
            options["decode"].append("qsv")
            options["encode"].append("qsv")
        
        # Check for Apple
        if "Apple" in " ".join(self.version_info.get("encoders", [])):
            options["decode"].append("videotoolbox")
            options["encode"].append("videotoolbox")
        
        logger.debug(f"Hardware acceleration options detected: {options}")
        return options
    
    def get_recommended_encoder(self, hardware_info: Optional[Dict[str, Any]] = None) -> str:
        """Get the best available encoder based on hardware"""
        if hardware_info is None:
            hardware_info = self.detect_hardware()
        
        available_encoders = self.version_info.get("encoders", [])
        
        # Priority order: NVIDIA > AMD > Intel > Software
        if hardware_info["gpu"]["nvidia"] and "NVIDIA H.264" in available_encoders:
            return "h264_nvenc"
        elif hardware_info["gpu"]["amd"] and "AMD H.264" in available_encoders:
            return "h264_amf"
        elif hardware_info["cpu"]["supports_qsv"] and "Intel Quick Sync H.264" in available_encoders:
            return "h264_qsv"
        elif hardware_info["gpu"]["apple"] and "Apple VideoToolbox H.264" in available_encoders:
            return "h264_videotoolbox"
        else:
            return "libx264"  # Software fallback


def main():
    """Test the FFmpeg manager"""
    manager = FFmpegManager()
    
    success, info = manager.detect_ffmpeg()
    
    if success:
        print("SUCCESS: FFmpeg detected!")
        print(f"Path: {info['ffmpeg_path']}")
        print(f"Version: {info['version']}")
        print(f"Hardware Encoders: {', '.join(info['encoders']) if info['encoders'] else 'None'}")
        print(f"Hardware Decoders: {', '.join(info['decoders']) if info['decoders'] else 'None'}")
        
        hwaccel = manager.get_hwaccel_options()
        print("\nHardware Acceleration Options:")
        print(f"  Decode: {', '.join(hwaccel['decode']) if hwaccel['decode'] else 'None'}")
        print(f"  Encode: {', '.join(hwaccel['encode']) if hwaccel['encode'] else 'None'}")
    else:
        print("ERROR: FFmpeg not found")
        print(info.get("error", "Unknown error"))
        print("\nAttempting automatic download...")
        
        def progress_handler(update):
            print(f"  {update['message']}")
        
        success, message = manager.download_ffmpeg(progress_callback=progress_handler)
        
        if success:
            print(f"SUCCESS: {message}")
        else:
            print(f"ERROR: {message}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

