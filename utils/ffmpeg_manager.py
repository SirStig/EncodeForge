"""
FFmpeg Manager
Single source of truth for FFmpeg detection, download, validation, and HW probing.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

# Platform download URLs (Apple Silicon aware). Kept in one place so the setup
# dialog and EncodeForgeCore.download_ffmpeg share the same story.
_STATIC_BASE = "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1"


def derive_ffprobe_path(ffmpeg_path: str) -> str:
    """
    Derive the ffprobe path from an ffmpeg path by renaming only the file.

    A plain str.replace("ffmpeg", "ffprobe") also rewrites directory
    components, so an install under
    ...\\ffmpeg\\ffmpeg-7.1-essentials_build\\bin\\ffmpeg.exe becomes a path
    that does not exist — which silently breaks every probe the app makes.

    Both separators are handled explicitly rather than relying on Path, so
    the result is correct regardless of which OS the string came from.
    """
    separator_index = max(ffmpeg_path.rfind("/"), ffmpeg_path.rfind("\\"))
    directory = ffmpeg_path[: separator_index + 1]
    name = ffmpeg_path[separator_index + 1 :]
    return directory + name.replace("ffmpeg", "ffprobe", 1)


def get_download_urls() -> Dict[str, Any]:
    """
    Resolve FFmpeg download URLs for the current platform.

    Returns:
        Dict with keys: url, ffprobe_url (optional), direct_binary (bool),
        system (str), supported (bool).
    """
    system = platform.system()
    machine = platform.machine().lower()
    is_arm = "arm" in machine or machine in ("arm64", "aarch64")

    if system == "Windows":
        return {
            "supported": True,
            "system": system,
            "url": "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip",
            "ffprobe_url": None,
            "direct_binary": False,
        }
    if system == "Linux":
        arch = "arm64" if is_arm else "amd64"
        return {
            "supported": True,
            "system": system,
            "url": f"https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-{arch}-static.tar.xz",
            "ffprobe_url": None,
            "direct_binary": False,
        }
    if system == "Darwin":
        arch = "arm64" if is_arm else "x64"
        return {
            "supported": True,
            "system": system,
            "url": f"{_STATIC_BASE}/ffmpeg-darwin-{arch}",
            "ffprobe_url": f"{_STATIC_BASE}/ffprobe-darwin-{arch}",
            "direct_binary": True,
        }
    return {
        "supported": False,
        "system": system,
        "url": None,
        "ffprobe_url": None,
        "direct_binary": False,
    }


class FFmpegManager:
    """
    Singleton manager for FFmpeg detection, download, and execution.

    GUI, CLI, and handlers all use this instance via get_ffmpeg_manager().
    """

    _instance: Optional["FFmpegManager"] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "FFmpegManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, custom_path: Optional[str] = None):
        """Initialize once; later calls may update preferred custom_path."""
        if custom_path:
            # Ignore bare default token used by ConversionSettings
            if custom_path.strip() and custom_path.strip() not in ("ffmpeg", "ffmpeg.exe"):
                self._custom_path = custom_path.strip()
            elif not getattr(self, "_initialized", False):
                self._custom_path = None
        elif not getattr(self, "_initialized", False):
            self._custom_path = None

        if getattr(self, "_initialized", False):
            return

        self._initialized = True
        self._ffmpeg_path: Optional[Path] = None
        self._ffprobe_path: Optional[Path] = None
        self._version_info: Dict[str, Any] = {}
        self._detection_cache: Optional[Tuple[bool, Dict[str, Any]]] = None
        self._cache_timestamp = 0.0
        self._encoder_test_cache: Dict[str, Tuple[bool, float]] = {}
        self._encoder_cache_duration = 300
        # Legacy attribute aliases used by some handlers/tests
        self.ffmpeg_path: Optional[str] = None
        self.ffprobe_path: Optional[str] = None
        self.version_info: Dict[str, Any] = {}
        logger.info("FFmpeg manager initialized")

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (tests only)."""
        cls._instance = None

    # ------------------------------------------------------------------ #
    # Path helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _derive_ffprobe_path(ffmpeg_path: str) -> str:
        return derive_ffprobe_path(ffmpeg_path)

    def _sync_legacy_attrs(self) -> None:
        self.ffmpeg_path = str(self._ffmpeg_path) if self._ffmpeg_path else None
        self.ffprobe_path = str(self._ffprobe_path) if self._ffprobe_path else None
        self.version_info = dict(self._version_info)

    def _exe_names(self) -> Tuple[str, str]:
        if platform.system() == "Windows":
            return "ffmpeg.exe", "ffprobe.exe"
        return "ffmpeg", "ffprobe"

    # ------------------------------------------------------------------ #
    # Detection
    # ------------------------------------------------------------------ #

    def detect_ffmpeg(
        self,
        force_refresh: bool = False,
        use_cache: bool = True,
    ) -> Union[bool, Tuple[bool, Dict[str, Any]]]:
        """
        Detect FFmpeg and populate version/encoder info.

        When called with no keyword intent for a rich result, returns bool
        (True if found). Pass return_info=True via the detailed helper, or
        call detect_ffmpeg_info() for the (success, info) tuple used by Core.

        force_refresh / use_cache control caching (force_refresh wins).
        """
        success, _info = self.detect_ffmpeg_info(
            use_cache=use_cache and not force_refresh
        )
        return success

    def detect_ffmpeg_info(
        self, use_cache: bool = True
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Detect FFmpeg and return (success, info_dict).

        info_dict on success includes ffmpeg_path, ffprobe_path, version,
        encoders, encoder_ids, decoders.
        """
        if use_cache and self._detection_cache is not None:
            cache_age = time.time() - self._cache_timestamp
            if cache_age < 300:
                logger.debug("Using cached FFmpeg detection (age: %.1fs)", cache_age)
                return self._detection_cache

        ffmpeg_exe, ffprobe_exe = self._exe_names()
        candidates: List[Path] = []

        # 1) Explicit custom path (ConversionSettings / constructor)
        if self._custom_path:
            candidates.append(Path(self._custom_path))

        # 2) SettingsManager application paths
        try:
            from utils.settings_manager import SettingsManager

            settings = SettingsManager()
            if settings.application.ffmpeg_path:
                candidates.append(Path(settings.application.ffmpeg_path))
        except Exception as e:
            logger.debug("Could not load FFmpeg path from settings: %s", e)

        # 3) Environment
        env_path = os.getenv("FFMPEG_PATH")
        if env_path:
            candidates.append(Path(env_path))

        # 4) PATH
        which = shutil.which(ffmpeg_exe) or shutil.which("ffmpeg")
        if which:
            candidates.append(Path(which))

        # 5) Common install locations (first match wins; no recursive AppData crawl)
        for search_dir in self._get_common_paths():
            if not search_dir.exists():
                continue
            direct = search_dir / ffmpeg_exe
            if direct.is_file():
                candidates.append(direct)
            # Shallow bin/ layout
            bin_direct = search_dir / "bin" / ffmpeg_exe
            if bin_direct.is_file():
                candidates.append(bin_direct)

        seen: set[str] = set()
        for cand in candidates:
            key = str(cand)
            if key in seen:
                continue
            seen.add(key)
            if not cand.is_file() and not shutil.which(str(cand)):
                # Allow bare "ffmpeg" from which already handled; skip missing files
                if not cand.exists():
                    continue
            resolved = cand if cand.is_file() else Path(shutil.which(str(cand)) or "")
            if not resolved or not resolved.exists():
                continue
            if not self._validate_ffmpeg(resolved):
                continue

            self._ffmpeg_path = resolved
            sibling = resolved.parent / ffprobe_exe
            if sibling.exists():
                self._ffprobe_path = sibling
            else:
                derived = Path(derive_ffprobe_path(str(resolved)))
                self._ffprobe_path = derived if derived.exists() else None

            self._version_info = self._collect_version_info(str(resolved))
            self._sync_legacy_attrs()

            info: Dict[str, Any] = {
                "ffmpeg_path": str(self._ffmpeg_path),
                "ffprobe_path": str(self._ffprobe_path) if self._ffprobe_path else "",
                "version": self._version_info.get("version", "Unknown"),
                "configuration": self._version_info.get("configuration", ""),
                "encoders": self._version_info.get("encoders", []),
                "encoder_ids": self._version_info.get("encoder_ids", []),
                "decoders": self._version_info.get("decoders", []),
            }
            result = (True, info)
            self._detection_cache = result
            self._cache_timestamp = time.time()
            logger.info("FFmpeg found: %s", self._ffmpeg_path)
            return result

        logger.warning("FFmpeg not found")
        result = (
            False,
            {
                "error": "FFmpeg not found in system PATH or common locations",
                "searched_paths": [str(p) for p in candidates],
            },
        )
        self._detection_cache = result
        self._cache_timestamp = time.time()
        return result

    def _get_common_paths(self) -> List[Path]:
        """Common installation directories (OS-specific). No Java embed path."""
        system = platform.system()
        paths: List[Path] = []

        if system == "Windows":
            localappdata = os.getenv("LOCALAPPDATA", "")
            userprofile = os.getenv("USERPROFILE", "")
            programfiles = os.getenv("PROGRAMFILES", "")
            if localappdata:
                paths.extend(
                    [
                        Path(localappdata) / "EncodeForge" / "ffmpeg" / "bin",
                        Path(localappdata) / "EncodeForge" / "ffmpeg",
                        Path(localappdata) / "ffmpeg" / "bin",
                        Path(localappdata) / "ffmpeg",
                    ]
                )
            paths.extend(
                [
                    Path("C:/ffmpeg/bin"),
                    Path("C:/ffmpeg"),
                    Path("C:/Program Files/ffmpeg/bin"),
                    Path("C:/Program Files (x86)/ffmpeg/bin"),
                ]
            )
            if programfiles:
                paths.append(Path(programfiles) / "ffmpeg" / "bin")
            if userprofile:
                paths.extend(
                    [
                        Path(userprofile) / "ffmpeg" / "bin",
                        Path(userprofile) / "ffmpeg",
                        Path(userprofile) / "Documents" / "ffmpeg" / "bin",
                        Path(userprofile) / "Downloads" / "ffmpeg" / "bin",
                    ]
                )
        elif system == "Darwin":
            paths.extend(
                [
                    Path("/opt/homebrew/bin"),
                    Path("/usr/local/bin"),
                    Path("/opt/local/bin"),
                    Path("/opt/ffmpeg/bin"),
                    Path.home() / "bin",
                    Path.home() / ".local" / "bin",
                ]
            )
        else:  # Linux
            paths.extend(
                [
                    Path("/usr/bin"),
                    Path("/usr/local/bin"),
                    Path("/opt/ffmpeg/bin"),
                    Path("/opt/ffmpeg"),
                    Path("/snap/bin"),
                    Path.home() / ".local" / "bin",
                    Path.home() / "bin",
                ]
            )

        try:
            from core.path_manager import get_bin_dir

            bin_dir = get_bin_dir()
            paths.insert(0, bin_dir / "ffmpeg")
            paths.insert(0, bin_dir / "ffmpeg" / "bin")
            paths.insert(0, bin_dir)
        except Exception:
            pass

        return paths

    def _validate_ffmpeg(self, ffmpeg_path: Path) -> bool:
        try:
            result = subprocess.run(
                [str(ffmpeg_path), "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 and "ffmpeg version" in result.stdout.lower()
        except Exception as e:
            logger.debug("FFmpeg validation failed for %s: %s", ffmpeg_path, e)
            return False

    def _collect_version_info(self, ffmpeg_path: str) -> Dict[str, Any]:
        info: Dict[str, Any] = {}
        try:
            result = subprocess.run(
                [ffmpeg_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.split("\n")
                if lines and "version" in lines[0]:
                    info["version"] = lines[0].split("version")[1].split()[0]
                for line in lines:
                    if "configuration:" in line:
                        info["configuration"] = line.split("configuration:")[1].strip()
                        break

            encoders, encoder_ids = self._check_encoders(ffmpeg_path)
            info["encoders"] = encoders
            info["encoder_ids"] = encoder_ids
            info["decoders"] = self._check_decoders(ffmpeg_path)
        except Exception as e:
            logger.error("Error getting FFmpeg version info: %s", e)
        return info

    def _check_encoders(self, ffmpeg_path: str) -> Tuple[List[str], List[str]]:
        encoders: List[str] = []
        encoder_ids: List[str] = []
        try:
            result = subprocess.run(
                [ffmpeg_path, "-encoders"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return encoders, encoder_ids

            output = result.stdout.lower()
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
                    if self._test_encoder(encoder_id, ffmpeg_path=ffmpeg_path):
                        encoders.append(encoder_name)
                        encoder_ids.append(encoder_id)
                    else:
                        logger.warning(
                            "Encoder %s is available but not functional", encoder_id
                        )
        except Exception as e:
            logger.error("Error checking encoders: %s", e)
        return encoders, encoder_ids

    def _test_encoder(
        self,
        encoder_name: str,
        use_cache: bool = True,
        ffmpeg_path: Optional[str] = None,
    ) -> bool:
        path = ffmpeg_path or self.ffmpeg_path
        if use_cache and encoder_name in self._encoder_test_cache:
            cached_result, cached_time = self._encoder_test_cache[encoder_name]
            if time.time() - cached_time < self._encoder_cache_duration:
                return cached_result

        if not path:
            self._encoder_test_cache[encoder_name] = (False, time.time())
            return False

        try:
            cmd = [
                path,
                "-f",
                "lavfi",
                "-i",
                "color=black:size=320x240:duration=0.1",
                "-c:v",
                encoder_name,
                "-f",
                "null",
                "-",
            ]
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5
            )
            success = result.returncode == 0
            self._encoder_test_cache[encoder_name] = (success, time.time())
            return success
        except Exception as e:
            logger.debug("Error testing encoder %s: %s", encoder_name, e)
            self._encoder_test_cache[encoder_name] = (False, time.time())
            return False

    def _check_decoders(self, ffmpeg_path: str) -> List[str]:
        decoders: List[str] = []
        try:
            result = subprocess.run(
                [ffmpeg_path, "-decoders"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return decoders
            output = result.stdout.lower()
            for decoder_id, decoder_name in (
                ("h264_cuvid", "NVIDIA H.264 (CUVID)"),
                ("hevc_cuvid", "NVIDIA H.265 (CUVID)"),
                ("h264_qsv", "Intel Quick Sync H.264"),
                ("hevc_qsv", "Intel Quick Sync H.265"),
            ):
                if decoder_id in output:
                    decoders.append(decoder_name)
        except Exception as e:
            logger.error("Error checking decoders: %s", e)
        return decoders

    # ------------------------------------------------------------------ #
    # Public path / version API
    # ------------------------------------------------------------------ #

    def get_ffmpeg_path(self) -> Optional[Path]:
        if not self._ffmpeg_path:
            self.detect_ffmpeg()
        return self._ffmpeg_path

    def get_ffprobe_path(self) -> Optional[Path]:
        if not self._ffprobe_path:
            if not self._ffmpeg_path:
                self.detect_ffmpeg()
            if self._ffmpeg_path:
                ffprobe_exe = self._exe_names()[1]
                potential = self._ffmpeg_path.parent / ffprobe_exe
                if potential.exists():
                    self._ffprobe_path = potential
                    self._sync_legacy_attrs()
        return self._ffprobe_path

    def set_ffmpeg_path(
        self, ffmpeg_path: Path, ffprobe_path: Optional[Path] = None
    ) -> None:
        ffmpeg_path = Path(ffmpeg_path)
        if not self._validate_ffmpeg(ffmpeg_path):
            raise ValueError(f"Invalid FFmpeg path: {ffmpeg_path}")

        ffprobe_exe = self._exe_names()[1]
        resolved_ffprobe: Optional[Path] = None
        if ffprobe_path is not None:
            fp = Path(ffprobe_path)
            if fp.is_file() and fp.resolve() != ffmpeg_path.resolve():
                resolved_ffprobe = fp
        if resolved_ffprobe is None:
            candidate = ffmpeg_path.parent / ffprobe_exe
            if candidate.exists():
                resolved_ffprobe = candidate
            else:
                derived = Path(derive_ffprobe_path(str(ffmpeg_path)))
                if derived.exists():
                    resolved_ffprobe = derived

        self._ffmpeg_path = ffmpeg_path
        self._ffprobe_path = resolved_ffprobe
        self._version_info = self._collect_version_info(str(ffmpeg_path))
        self._detection_cache = None
        self._sync_legacy_attrs()
        logger.info("FFmpeg path set to: %s", ffmpeg_path)

        try:
            from utils.settings_manager import SettingsManager

            settings = SettingsManager()
            settings.application.ffmpeg_path = str(ffmpeg_path)
            settings.application.ffprobe_path = (
                str(resolved_ffprobe) if resolved_ffprobe else ""
            )
            settings.save()
        except Exception as e:
            logger.error("Failed to save FFmpeg path to settings: %s", e)

    def get_version_info(self) -> Optional[Dict[str, Any]]:
        if not self._version_info and self._ffmpeg_path:
            self._version_info = self._collect_version_info(str(self._ffmpeg_path))
            self._sync_legacy_attrs()
        return self._version_info or None

    def is_available(self) -> bool:
        return self.get_ffmpeg_path() is not None

    # ------------------------------------------------------------------ #
    # Hardware acceleration
    # ------------------------------------------------------------------ #

    def get_hwaccel_options(self) -> Dict[str, List[str]]:
        options: Dict[str, List[str]] = {"decode": [], "encode": []}

        if not self._version_info.get("encoder_ids"):
            logger.info(
                "Encoder list not populated, running FFmpeg detection for HW accel..."
            )
            success, _info = self.detect_ffmpeg_info(use_cache=True)
            if not success:
                logger.warning(
                    "FFmpeg auto-detection failed, no hardware acceleration available"
                )
                return options

        if not self._ffmpeg_path:
            return options

        encoder_ids = list(self._version_info.get("encoder_ids", []))
        options["encoder_ids"] = encoder_ids

        vendors = (
            ("nvenc", ["cuda", "cuvid"], "nvenc"),
            ("amf", ["amf"], "amf"),
            ("qsv", ["qsv"], "qsv"),
            ("videotoolbox", ["videotoolbox"], "videotoolbox"),
        )
        for suffix, decode_tokens, encode_token in vendors:
            if any(eid.endswith(suffix) for eid in encoder_ids):
                options["decode"].extend(decode_tokens)
                options["encode"].append(encode_token)

        return options

    def supports_encoder(self, encoder_id: str) -> bool:
        return encoder_id in self.get_hwaccel_options().get("encoder_ids", [])

    def detect_hardware(self) -> Dict[str, Any]:
        """Detect GPUs via utils.gpu_detector (no Java / WMI leftovers)."""
        hardware_info: Dict[str, Any] = {
            "gpu": {
                "nvidia": False,
                "amd": False,
                "intel": False,
                "apple": False,
                "details": [],
            },
            "cpu": {
                "vendor": "unknown",
                "model": platform.processor() or "unknown",
                "supports_qsv": False,
            },
        }
        try:
            from utils.gpu_detector import get_gpu_info

            for gpu in get_gpu_info():
                vendor = gpu.vendor.upper()
                if vendor == "NVIDIA":
                    hardware_info["gpu"]["nvidia"] = True
                    hardware_info["gpu"]["details"].append(f"NVIDIA GPU: {gpu.model}")
                elif vendor == "AMD":
                    hardware_info["gpu"]["amd"] = True
                    hardware_info["gpu"]["details"].append(f"AMD GPU: {gpu.model}")
                elif vendor == "INTEL":
                    hardware_info["gpu"]["intel"] = True
                    hardware_info["gpu"]["details"].append(f"Intel GPU: {gpu.model}")
                    hardware_info["cpu"]["supports_qsv"] = True
                    hardware_info["cpu"]["vendor"] = "intel"
                elif vendor == "APPLE":
                    hardware_info["gpu"]["apple"] = True
                    hardware_info["gpu"]["details"].append(f"Apple GPU: {gpu.model}")
        except Exception as e:
            logger.debug("Error detecting hardware: %s", e)
        return hardware_info

    def get_recommended_encoder(
        self, hardware_info: Optional[Dict[str, Any]] = None
    ) -> str:
        if hardware_info is None:
            hardware_info = self.detect_hardware()
        available = self._version_info.get("encoders", [])
        if hardware_info["gpu"]["nvidia"] and "NVIDIA H.264" in available:
            return "h264_nvenc"
        if hardware_info["gpu"]["amd"] and "AMD H.264" in available:
            return "h264_amf"
        if hardware_info["cpu"]["supports_qsv"] and "Intel Quick Sync H.264" in available:
            return "h264_qsv"
        if hardware_info["gpu"]["apple"] and "Apple VideoToolbox H.264" in available:
            return "h264_videotoolbox"
        return "libx264"

    # ------------------------------------------------------------------ #
    # Download / install
    # ------------------------------------------------------------------ #

    def download_ffmpeg(
        self,
        install_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Tuple[bool, str]:
        """
        Download and install FFmpeg for the current platform.

        Uses the same URL matrix as the GUI setup dialog.
        """
        import stat as stat_mod

        from utils.download_manager import DownloadError, DownloadManager

        urls = get_download_urls()
        if not urls["supported"]:
            return False, f"Automatic download not supported for {urls['system']}"

        try:
            from core.path_manager import get_bin_dir

            default_root = get_bin_dir()
        except Exception:
            default_root = Path.home() / ".local" / "share" / "encodeforge" / "bin"

        if install_dir is None:
            install_dir = default_root / "ffmpeg"
        install_dir = Path(install_dir)
        install_dir.mkdir(parents=True, exist_ok=True)

        dm = DownloadManager()
        url = urls["url"]
        ffprobe_url = urls["ffprobe_url"]
        direct_binary = urls["direct_binary"]
        system = urls["system"]

        def _emit(progress: float, message: str, status: str = "downloading") -> None:
            if progress_callback:
                progress_callback(
                    {"status": status, "progress": progress, "message": message}
                )

        def _dl_progress(downloaded: int, total: int, percentage: float) -> None:
            pct = min(99.0, percentage * 0.9)
            mb_dl = downloaded / (1024 * 1024)
            mb_tot = total / (1024 * 1024) if total else 0
            _emit(pct, f"Downloading: {mb_dl:.1f} / {mb_tot:.1f} MB ({percentage:.0f}%)")

        try:
            _emit(0, "Downloading FFmpeg...")
            if direct_binary:
                ffmpeg_dest = install_dir / "ffmpeg"
                dm.download(
                    url=url,
                    destination=str(ffmpeg_dest),
                    progress_callback=_dl_progress,
                    resume=False,
                )
                ffmpeg_dest.chmod(ffmpeg_dest.stat().st_mode | stat_mod.S_IEXEC)

                ffprobe_dest = install_dir / "ffprobe"
                if ffprobe_url:
                    _emit(90, "Downloading ffprobe…", status="extracting")
                    dm.download(
                        url=ffprobe_url,
                        destination=str(ffprobe_dest),
                        resume=False,
                    )
                    ffprobe_dest.chmod(ffprobe_dest.stat().st_mode | stat_mod.S_IEXEC)

                found_ffmpeg = ffmpeg_dest
                found_ffprobe = ffprobe_dest if ffprobe_dest.exists() else None
            else:
                archive_name = url.split("/")[-1].split("?")[0] or "ffmpeg_download"
                archive_path = dm.download(
                    url=url,
                    destination=str(install_dir.parent / archive_name),
                    progress_callback=_dl_progress,
                    resume=True,
                )
                _emit(95, "Extracting FFmpeg…", status="extracting")
                try:
                    dm.extract_archive(archive_path, install_dir)
                finally:
                    archive_path.unlink(missing_ok=True)

                ffmpeg_exe, ffprobe_exe = self._exe_names()
                found_ffmpeg = next(
                    (p for p in install_dir.rglob(ffmpeg_exe) if p.is_file()), None
                )
                found_ffprobe = next(
                    (p for p in install_dir.rglob(ffprobe_exe) if p.is_file()), None
                )
                if not found_ffmpeg:
                    return False, "FFmpeg executable not found in downloaded package"
                if system != "Windows":
                    found_ffmpeg.chmod(found_ffmpeg.stat().st_mode | stat_mod.S_IEXEC)
                    if found_ffprobe:
                        found_ffprobe.chmod(
                            found_ffprobe.stat().st_mode | stat_mod.S_IEXEC
                        )

            self.set_ffmpeg_path(found_ffmpeg, found_ffprobe)
            msg = f"FFmpeg installed at {found_ffmpeg}"
            _emit(100, msg, status="complete")
            return True, msg
        except DownloadError as e:
            logger.error("Error downloading FFmpeg: %s", e)
            return False, f"Download failed: {e}"
        except Exception as e:
            logger.error("Error downloading FFmpeg: %s", e)
            return False, f"Download failed: {e}"

    # ------------------------------------------------------------------ #
    # Execution helpers
    # ------------------------------------------------------------------ #

    def run_ffmpeg(self, args: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
        if not self.is_available():
            raise RuntimeError("FFmpeg is not available")
        return subprocess.run([str(self._ffmpeg_path)] + args, **kwargs)

    def run_ffprobe(self, args: List[str], **kwargs: Any) -> subprocess.CompletedProcess:
        ffprobe_path = self.get_ffprobe_path()
        if not ffprobe_path:
            raise RuntimeError("FFprobe is not available")
        return subprocess.run([str(ffprobe_path)] + args, **kwargs)


def get_ffmpeg_manager(custom_path: Optional[str] = None) -> FFmpegManager:
    """Get the FFmpeg manager singleton instance."""
    return FFmpegManager(custom_path=custom_path)


# Common-path helpers exported for unit tests without touching the filesystem
def common_search_paths_for_system(system: str) -> List[str]:
    """
    Return expected search path *patterns* for a given OS name.

    Used by unit tests to assert OS-specific detection roots without requiring
    FFmpeg to be installed.
    """
    if system == "Windows":
        return [
            "EncodeForge/ffmpeg",
            "ffmpeg/bin",
            "C:/ffmpeg",
            "Program Files/ffmpeg",
        ]
    if system == "Darwin":
        return [
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/opt/local/bin",
        ]
    if system == "Linux":
        return [
            "/usr/bin",
            "/usr/local/bin",
            "/opt/ffmpeg",
            "/snap/bin",
            ".local/bin",
        ]
    return []
