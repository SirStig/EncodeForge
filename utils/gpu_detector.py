"""
GPU Detection Utility for EncodeForge
Cross-platform GPU detection for selecting appropriate PyTorch builds
"""

import logging
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class GPUInfo:
    """GPU information container"""
    vendor: str  # nvidia, amd, apple, intel, unknown
    model: str
    driver_version: Optional[str] = None
    compute_capability: Optional[str] = None
    vram_mb: Optional[int] = None


def get_gpu_info() -> List[GPUInfo]:
    """
    Detect all GPUs in the system.
    
    Returns:
        List of GPUInfo objects for each detected GPU
    """
    gpus = []
    
    # Try NVIDIA detection
    nvidia_gpus = _detect_nvidia()
    gpus.extend(nvidia_gpus)
    
    # Try AMD detection
    amd_gpus = _detect_amd()
    gpus.extend(amd_gpus)
    
    # Try Apple Silicon detection
    apple_gpu = _detect_apple_silicon()
    if apple_gpu:
        gpus.append(apple_gpu)
    
    # Try Intel detection (optional)
    intel_gpus = _detect_intel()
    gpus.extend(intel_gpus)
    
    if not gpus:
        logger.info("No discrete GPUs detected, will use CPU")
    else:
        logger.info(f"Detected {len(gpus)} GPU(s): {[gpu.model for gpu in gpus]}")
    
    return gpus


def has_cuda() -> bool:
    """Check if NVIDIA CUDA is available"""
    nvidia_gpus = _detect_nvidia()
    return len(nvidia_gpus) > 0


def has_rocm() -> bool:
    """Check if AMD ROCm is available (Linux only)"""
    if platform.system().lower() != "linux":
        return False
    amd_gpus = _detect_amd()
    return len(amd_gpus) > 0


def has_mps() -> bool:
    """Check if Apple Metal Performance Shaders is available"""
    return _detect_apple_silicon() is not None


def recommend_torch_variant() -> str:
    """
    Recommend the best PyTorch variant for this system.
    
    Returns:
        One of: 'cuda', 'rocm', 'mps', 'cpu'
    """
    system = platform.system().lower()
    
    # Check for Apple Silicon first (macOS specific)
    if system == "darwin":
        if has_mps():
            return "mps"
        return "cpu"
    
    # Check for NVIDIA CUDA
    if has_cuda():
        return "cuda"
    
    # Check for AMD ROCm (Linux only for now)
    if system == "linux" and has_rocm():
        return "rocm"
    
    # Fallback to CPU
    return "cpu"


def get_torch_install_command() -> str:
    """
    Get the pip install command for the recommended PyTorch variant.
    
    Returns:
        pip install command string
    """
    variant = recommend_torch_variant()
    
    if variant == "cuda":
        # CUDA 12.1 (compatible with most modern NVIDIA GPUs)
        return "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"
    elif variant == "rocm":
        # ROCm 5.7 (latest stable as of Oct 2024)
        return "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7"
    elif variant == "mps":
        # MPS support is in default PyTorch for macOS
        return "pip install torch torchvision torchaudio"
    else:  # cpu
        return "pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu"


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
                # Parse rocm-smi output
                for line in result.stdout.split('\n'):
                    if 'GPU' in line and 'Card series' in line:
                        # Extract GPU model name
                        parts = line.split(':')
                        if len(parts) > 1:
                            model = parts[1].strip()
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
            try:
                drm_path = Path("/sys/class/drm")
                if drm_path.exists():
                    for card_dir in drm_path.iterdir():
                        if card_dir.name.startswith("card"):
                            device_path = card_dir / "device"
                            vendor_path = device_path / "vendor"
                            
                            if vendor_path.exists():
                                vendor_id = vendor_path.read_text().strip()
                                # AMD vendor ID is 0x1002
                                if vendor_id == "0x1002":
                                    # Try to get device name
                                    device_name_path = device_path / "device"
                                    if device_name_path.exists():
                                        device_id = device_name_path.read_text().strip()
                                        gpus.append(GPUInfo(
                                            vendor="amd",
                                            model=f"AMD GPU (Device {device_id})"
                                        ))
                
                if gpus:
                    logger.info(f"Detected {len(gpus)} AMD GPU(s) via /sys/class/drm")
            
            except Exception as e:
                logger.debug(f"DRM detection error: {e}")
    
    elif system == "windows":
        # Try wmic on Windows
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n')[1:]:  # Skip header
                    line = line.strip()
                    if line and ('AMD' in line.upper() or 'Radeon' in line):
                        gpus.append(GPUInfo(
                            vendor="amd",
                            model=line
                        ))
                
                if gpus:
                    logger.info(f"Detected {len(gpus)} AMD GPU(s) via wmic")
        
        except Exception as e:
            logger.debug(f"wmic error: {e}")
    
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
    """Detect Intel integrated GPUs (optional)"""
    gpus = []
    system = platform.system().lower()
    
    if system == "windows":
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n')[1:]:  # Skip header
                    line = line.strip()
                    if line and 'Intel' in line:
                        gpus.append(GPUInfo(
                            vendor="intel",
                            model=line
                        ))
        
        except Exception as e:
            logger.debug(f"Intel detection error: {e}")
    
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
    print()
    
    recommended = recommend_torch_variant()
    print(f"Recommended PyTorch variant: {recommended}")
    print()
    
    install_cmd = get_torch_install_command()
    print("Install command:")
    print(f"  {install_cmd}")
