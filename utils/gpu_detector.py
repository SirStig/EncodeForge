"""
GPU Detection Utility for EncodeForge

Detects GPUs for FFmpeg hardware-encoder selection (NVENC / AMF / QSV /
VideoToolbox / VAAPI). Whisper uses faster-whisper / CTranslate2 — not PyTorch —
so this module does not recommend torch wheels.
"""

import logging
import platform
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# OS → FFmpeg hardware encode backends EncodeForge will attempt.
# NVENC is cross-platform where an NVIDIA driver exists; AMF is Windows-only;
# VAAPI covers Linux AMD/Intel; QSV is Win/Linux; VideoToolbox is macOS.
OS_ENCODER_BACKENDS: Dict[str, List[str]] = {
    "windows": ["nvenc", "amf", "qsv"],
    "linux": ["nvenc", "vaapi", "qsv"],
    "darwin": ["nvenc", "videotoolbox"],
}


@dataclass
class GPUInfo:
    """GPU information container"""
    vendor: str  # nvidia, amd, apple, intel, unknown
    model: str
    driver_version: Optional[str] = None
    compute_capability: Optional[str] = None
    vram_mb: Optional[int] = None


# Detection spawns several subprocesses, each with a 5 s timeout — and on a
# machine with a wedged NVIDIA driver nvidia-smi hangs rather than failing, so
# an uncached call can block for 10 s. Results are stable for the life of the
# process, so they are computed once behind a lock.
_gpu_cache: Optional[List[GPUInfo]] = None
_gpu_cache_lock = threading.Lock()


def get_gpu_info(force_refresh: bool = False) -> List[GPUInfo]:
    """
    Detect all GPUs in the system.

    Results are cached for the process lifetime; pass force_refresh=True after
    a driver change.

    Returns:
        List of GPUInfo objects for each detected GPU
    """
    global _gpu_cache

    if _gpu_cache is not None and not force_refresh:
        return list(_gpu_cache)

    with _gpu_cache_lock:
        # Another thread may have populated the cache while we waited.
        if _gpu_cache is not None and not force_refresh:
            return list(_gpu_cache)

        gpus = []

        # Try NVIDIA detection
        gpus.extend(_detect_nvidia())

        # Try AMD detection
        gpus.extend(_detect_amd())

        # Try Apple Silicon detection
        apple_gpu = _detect_apple_silicon()
        if apple_gpu:
            gpus.append(apple_gpu)

        # Try Intel detection (optional)
        gpus.extend(_detect_intel())

        if not gpus:
            logger.info("No discrete GPUs detected, will use CPU")
        else:
            logger.info(f"Detected {len(gpus)} GPU(s): {[gpu.model for gpu in gpus]}")

        _gpu_cache = gpus
        return list(_gpu_cache)


def clear_gpu_cache() -> None:
    """Drop the process-wide GPU cache (tests / after driver changes)."""
    global _gpu_cache
    with _gpu_cache_lock:
        _gpu_cache = None


def has_cuda() -> bool:
    """Check if NVIDIA CUDA is available"""
    return any(g.vendor.lower() == "nvidia" for g in get_gpu_info())


def has_rocm() -> bool:
    """Check if AMD ROCm is available (Linux only)"""
    if platform.system().lower() != "linux":
        return False
    return any(g.vendor.lower() == "amd" for g in get_gpu_info())


def has_mps() -> bool:
    """Check if Apple Metal Performance Shaders is available"""
    return any(g.vendor.lower() == "apple" for g in get_gpu_info())


def has_vaapi() -> bool:
    """True when a Linux DRM render node suitable for VAAPI is present."""
    return find_vaapi_device() is not None


def find_vaapi_device() -> Optional[str]:
    """
    Return the preferred VAAPI device path (e.g. /dev/dri/renderD128), or None.

    VAAPI is Linux-only. Prefers render nodes over legacy card nodes.
    """
    if platform.system().lower() != "linux":
        return None

    dri = Path("/dev/dri")
    if not dri.is_dir():
        return None

    render_nodes = sorted(p for p in dri.glob("renderD*") if p.exists())
    if render_nodes:
        return str(render_nodes[0])

    card_nodes = sorted(
        p for p in dri.glob("card*")
        if p.exists() and p.name.count("-") == 0  # card0, not card0-DP-1
    )
    if card_nodes:
        return str(card_nodes[0])

    return None


def supported_encoder_backends(system: Optional[str] = None) -> List[str]:
    """
    Return the FFmpeg hardware backends EncodeForge supports on this OS.

    Args:
        system: Override platform.system() value (windows/linux/darwin), for tests.
    """
    if system is None:
        system = platform.system()
    key = system.lower()
    if key == "windows" or key.startswith("win"):
        return list(OS_ENCODER_BACKENDS["windows"])
    if key == "linux":
        return list(OS_ENCODER_BACKENDS["linux"])
    if key in ("darwin", "macos", "mac"):
        return list(OS_ENCODER_BACKENDS["darwin"])
    return ["nvenc"]  # unknown OS: NVIDIA path only if present


def encoder_backend_matrix() -> Dict[str, List[str]]:
    """Copy of the documented OS → backend matrix."""
    return {os_name: list(backends) for os_name, backends in OS_ENCODER_BACKENDS.items()}


def _detect_nvidia() -> List[GPUInfo]:
    """Detect NVIDIA GPUs using nvidia-smi"""
    gpus = []
    
    try:
        # Try nvidia-smi
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 1:
                        model = parts[0]
                        driver = parts[1] if len(parts) > 1 else None
                        vram_str = parts[2] if len(parts) > 2 else None
                        
                        # Parse VRAM (e.g., "8192 MiB" -> 8192)
                        vram_mb = None
                        if vram_str:
                            try:
                                vram_mb = int(vram_str.split()[0])
                            except (ValueError, IndexError):
                                pass
                        
                        gpus.append(GPUInfo(
                            vendor="nvidia",
                            model=model,
                            driver_version=driver,
                            vram_mb=vram_mb
                        ))
            
            logger.info(f"Detected {len(gpus)} NVIDIA GPU(s) via nvidia-smi")
    
    except FileNotFoundError:
        logger.debug("nvidia-smi not found")
    except subprocess.TimeoutExpired:
        logger.warning("nvidia-smi timed out")
    except Exception as e:
        logger.debug(f"nvidia-smi error: {e}")
    
    # Fallback: Try pynvml if available
    if not gpus:
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            
            for i in range(device_count):
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                name = pynvml.nvmlDeviceGetName(handle)
                
                try:
                    memory_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    vram_mb = memory_info.total // (1024 * 1024)
                except Exception:
                    vram_mb = None
                
                gpus.append(GPUInfo(
                    vendor="nvidia",
                    model=name if isinstance(name, str) else name.decode(),
                    vram_mb=vram_mb
                ))
            
            pynvml.nvmlShutdown()
            logger.info(f"Detected {len(gpus)} NVIDIA GPU(s) via pynvml")
        
        except ImportError:
            logger.debug("pynvml not available")
        except Exception as e:
            logger.debug(f"pynvml error: {e}")
    
    return gpus


def _detect_amd() -> List[GPUInfo]:
    """Detect AMD GPUs"""
    gpus = []
    system = platform.system().lower()
    
    if system == "linux":
        # Try rocm-smi
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                # Parse rocm-smi output — lines look like:
                # "GPU[0]    : Card Series    : Radeon RX 6800 XT"
                for line in result.stdout.split('\n'):
                    line_lower = line.lower()
                    if 'gpu' in line_lower and 'card series' in line_lower:
                        parts = line.split(':')
                        if len(parts) >= 3:
                            model = parts[2].strip()
                            gpus.append(GPUInfo(
                                vendor="amd",
                                model=model
                            ))

                logger.info(f"Detected {len(gpus)} AMD GPU(s) via rocm-smi")
        
        except FileNotFoundError:
            logger.debug("rocm-smi not found")
        except subprocess.TimeoutExpired:
            logger.warning("rocm-smi timed out")
        except Exception as e:
            logger.debug(f"rocm-smi error: {e}")
        
        # Fallback: Check /sys/class/drm
        if not gpus:
            gpus.extend(_detect_drm_vendor("0x1002", "amd", "AMD"))
    
    elif system == "windows":
        # Try wmic first (deprecated on Windows 11 — fallback to PowerShell below)
        _amd_gpu_names = []
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                _amd_gpu_names = [
                    line.strip() for line in result.stdout.split('\n')[1:]
                    if line.strip() and ('AMD' in line.upper() or 'Radeon' in line)
                ]
                if _amd_gpu_names:
                    logger.info(f"Detected {len(_amd_gpu_names)} AMD GPU(s) via wmic")

        except Exception as e:
            logger.debug(f"wmic unavailable: {e}, trying PowerShell fallback")
            try:
                ps_result = subprocess.run(
                    [
                        "powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if ps_result.returncode == 0:
                    _amd_gpu_names = [
                        line.strip() for line in ps_result.stdout.split('\n')
                        if line.strip() and ('AMD' in line.upper() or 'Radeon' in line)
                    ]
                    if _amd_gpu_names:
                        logger.info(f"Detected {len(_amd_gpu_names)} AMD GPU(s) via PowerShell")
            except Exception as ps_err:
                logger.debug(f"PowerShell fallback also failed: {ps_err}")

        for name in _amd_gpu_names:
            gpus.append(GPUInfo(vendor="amd", model=name))

    return gpus


def _detect_drm_vendor(vendor_id: str, vendor: str, label: str) -> List[GPUInfo]:
    """Detect GPUs on Linux via /sys/class/drm matching a PCI vendor id."""
    gpus: List[GPUInfo] = []
    seen_device_ids = set()

    try:
        drm_path = Path("/sys/class/drm")
        if not drm_path.exists():
            return gpus

        for card_dir in sorted(drm_path.iterdir()):
            # Only top-level cards (card0), not connectors (card0-DP-1).
            if not card_dir.name.startswith("card"):
                continue
            if "-" in card_dir.name:
                continue

            device_path = card_dir / "device"
            vendor_path = device_path / "vendor"
            if not vendor_path.exists():
                continue

            found_vendor = vendor_path.read_text().strip().lower()
            if found_vendor != vendor_id.lower():
                continue

            device_id = "unknown"
            device_id_path = device_path / "device"
            if device_id_path.exists():
                device_id = device_id_path.read_text().strip()

            if device_id in seen_device_ids:
                continue
            seen_device_ids.add(device_id)

            gpus.append(GPUInfo(
                vendor=vendor,
                model=f"{label} GPU (Device {device_id})"
            ))

        if gpus:
            logger.info(f"Detected {len(gpus)} {label} GPU(s) via /sys/class/drm")

    except Exception as e:
        logger.debug(f"DRM {label} detection error: {e}")

    return gpus


def _detect_apple_silicon() -> Optional[GPUInfo]:
    """Detect Apple Silicon GPU (M1, M2, M3, etc.)"""
    system = platform.system().lower()
    
    if system != "darwin":
        return None
    
    try:
        # Check processor architecture
        processor = platform.processor()
        machine = platform.machine()
        
        # Apple Silicon uses arm architecture
        if machine == "arm64" or "arm" in processor.lower():
            # Try to get chip model from system_profiler
            try:
                result = subprocess.run(
                    ["system_profiler", "SPHardwareDataType"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.returncode == 0:
                    # Look for "Chip" line
                    for line in result.stdout.split('\n'):
                        if 'Chip:' in line:
                            chip_name = line.split(':')[1].strip()
                            logger.info(f"Detected Apple Silicon: {chip_name}")
                            return GPUInfo(
                                vendor="apple",
                                model=chip_name
                            )
            
            except Exception as e:
                logger.debug(f"system_profiler error: {e}")
            
            # Fallback: Generic Apple Silicon detection
            logger.info("Detected Apple Silicon (model unknown)")
            return GPUInfo(
                vendor="apple",
                model="Apple Silicon"
            )
    
    except Exception as e:
        logger.debug(f"Apple Silicon detection error: {e}")
    
    return None


def _detect_intel() -> List[GPUInfo]:
    """Detect Intel integrated / discrete GPUs (Windows + Linux)."""
    gpus = []
    system = platform.system().lower()
    
    if system == "windows":
        _intel_gpu_names = []
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                _intel_gpu_names = [
                    line.strip() for line in result.stdout.split('\n')[1:]
                    if line.strip() and 'Intel' in line
                ]

        except Exception as e:
            logger.debug(f"wmic unavailable for Intel detection: {e}, trying PowerShell")
            try:
                ps_result = subprocess.run(
                    [
                        "powershell", "-NoProfile", "-Command",
                        "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if ps_result.returncode == 0:
                    _intel_gpu_names = [
                        line.strip() for line in ps_result.stdout.split('\n')
                        if line.strip() and 'Intel' in line
                    ]
            except Exception as ps_err:
                logger.debug(f"PowerShell Intel detection failed: {ps_err}")

        for name in _intel_gpu_names:
            gpus.append(GPUInfo(vendor="intel", model=name))

    elif system == "linux":
        # PCI vendor 0x8086 = Intel. Mirrors AMD's DRM fallback so QSV/VAAPI
        # selection can see iGPU presence on Linux.
        gpus.extend(_detect_drm_vendor("0x8086", "intel", "Intel"))

    return gpus


if __name__ == "__main__":
    # Test the GPU detector
    logging.basicConfig(level=logging.INFO)
    
    print("=== GPU Detection Test ===")
    print()
    
    gpus = get_gpu_info()
    
    if gpus:
        for i, gpu in enumerate(gpus):
            print(f"GPU {i + 1}:")
            print(f"  Vendor: {gpu.vendor}")
            print(f"  Model: {gpu.model}")
            if gpu.driver_version:
                print(f"  Driver: {gpu.driver_version}")
            if gpu.vram_mb:
                print(f"  VRAM: {gpu.vram_mb} MB")
            print()
    else:
        print("No GPUs detected")
        print()
    
    print(f"CUDA available: {has_cuda()}")
    print(f"ROCm available: {has_rocm()}")
    print(f"MPS available: {has_mps()}")
    print(f"VAAPI device: {find_vaapi_device()}")
    print()
    print(f"Supported encoder backends: {supported_encoder_backends()}")
    print("OS encoder matrix:")
    for os_name, backends in encoder_backend_matrix().items():
        print(f"  {os_name}: {', '.join(backends)}")
