
#!/usr/bin/env python3
"""
Whisper Manager - Handles Whisper AI model management and subtitle generation
"""

import logging
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class WhisperManager:
    """Manages Whisper AI for subtitle generation"""
    
    MODELS = ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"]
    
    MODEL_SIZES = {
        "tiny": "75 MB",
        "base": "142 MB",
        "small": "466 MB",
        "medium": "1.5 GB",
        "large": "2.9 GB",
        "large-v2": "2.9 GB",
        "large-v3": "2.9 GB",
    }
    
    # Map 3-letter ISO 639-2 codes to 2-letter ISO 639-1 codes (Whisper format)
    LANGUAGE_CODE_MAP = {
        "eng": "en",
        "spa": "es",
        "fre": "fr",
        "fra": "fr",
        "ger": "de",
        "deu": "de",
        "ita": "it",
        "por": "pt",
        "rus": "ru",
        "jpn": "ja",
        "kor": "ko",
        "chi": "zh",
        "zho": "zh",
        "ara": "ar",
        "hin": "hi",
        "tur": "tr",
        "pol": "pl",
        "ukr": "uk",
        "vie": "vi",
        "tha": "th",
        "nld": "nl",
        "dut": "nl",
        "swe": "sv",
        "dan": "da",
        "nor": "no",
        "fin": "fi",
        "cze": "cs",
        "ces": "cs",
        "hun": "hu",
        "rum": "ro",
        "ron": "ro",
        "gre": "el",
        "ell": "el",
        "heb": "he",
        "ind": "id",
        "msa": "ms",
        "may": "ms",
    }
    
    def __init__(self):
        self.whisper_available = False
        self.installed_models = []
        self.device = self._detect_device()
        self._check_installation()
    
    def _detect_device(self) -> str:
        """
        Detect best available device for PyTorch/Whisper
        Supports: NVIDIA CUDA, AMD ROCm (Windows/Linux), Apple Silicon MPS (macOS)
        """
        try:
            import torch
            
            # NVIDIA CUDA or AMD ROCm (both use torch.cuda API)
            # ROCm on Windows: Requires PyTorch built with ROCm support
            # Install with: pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
            if torch.cuda.is_available():
                device = "cuda"
                try:
                    gpu_name = torch.cuda.get_device_name(0)
                    # Detect AMD vs NVIDIA
                    if 'AMD' in gpu_name.upper() or 'RADEON' in gpu_name.upper():
                        # Check if ROCm is actually being used
                        if hasattr(torch.version, 'hip') and torch.version.hip:
                            logger.info(f"🔴 AMD GPU with ROCm detected: {gpu_name}")
                            logger.info(f"   ROCm version: {torch.version.hip} - Whisper will use GPU acceleration")
                        else:
                            logger.info(f"🔴 AMD GPU detected: {gpu_name} - Whisper will use ROCm/CUDA acceleration")
                    else:
                        cuda_version = torch.version.cuda if hasattr(torch.version, 'cuda') else "Unknown"
                        logger.info(f"🎮 NVIDIA GPU detected: {gpu_name}")
                        logger.info(f"   CUDA version: {cuda_version} - Whisper will use GPU acceleration")
                except Exception as e:
                    logger.info(f"🎮 GPU detected - Whisper will use CUDA/ROCm acceleration")
                    logger.debug(f"GPU detection details failed: {e}")
                return device
            
            # Apple Silicon M1/M2/M3/M4 (macOS ARM64)
            if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                device = "mps"
                logger.info(f"🍎 Apple Silicon GPU detected - Whisper will use Metal Performance Shaders (MPS)")
                logger.info(f"   This provides significant speedup on M-series Macs")
                return device
            
            # DirectML support (experimental - requires special PyTorch build)
            # Not currently supported by Whisper, but may work with custom builds
            
        except ImportError:
            logger.debug("PyTorch not available for GPU detection")
            pass
        except Exception as e:
            logger.warning(f"Error detecting GPU: {e}")
        
        # Fallback to CPU
        import platform
        system = platform.system()
        logger.info("💻 No GPU detected - Whisper will use CPU")
        
        # Provide helpful hints based on platform
        if system == "Windows":
            logger.info("   💡 For AMD GPU: Install PyTorch with ROCm support")
            logger.info("   💡 For NVIDIA GPU: Install PyTorch with CUDA support")
        elif system == "Darwin":  # macOS
            logger.info("   💡 For Apple Silicon (M1/M2/M3): Install PyTorch with MPS support")
        elif system == "Linux":
            logger.info("   💡 For AMD GPU: Install PyTorch with ROCm support")
            logger.info("   💡 For NVIDIA GPU: Install PyTorch with CUDA support")
        
        return "cpu"
    
    def _convert_language_code(self, lang_code: Optional[str]) -> Optional[str]:
        """Convert 3-letter ISO 639-2 code to 2-letter ISO 639-1 code for Whisper"""
        if not lang_code:
            return None
        
        # If already 2 letters, return as-is
        if len(lang_code) == 2:
            return lang_code.lower()
        
        # Convert 3-letter to 2-letter
        lang_lower = lang_code.lower()
        converted = self.LANGUAGE_CODE_MAP.get(lang_lower, lang_lower)
        
        # If we couldn't convert and it's 3 letters, just take first 2
        if len(converted) == 3:
            converted = converted[:2]
        
        logger.debug(f"Language code conversion: {lang_code} -> {converted}")
        return converted
    
    def _check_installation(self) -> bool:
        """Check if Whisper is installed"""
        try:
            import whisper  # noqa: F401
            self.whisper_available = True
            
            # Check which models are downloaded
            from path_manager import get_models_dir
            model_dir = get_models_dir() / "whisper"
            if model_dir.exists():
                for model_file in model_dir.glob("*.pt"):
                    model_name = model_file.stem
                    if model_name in self.MODELS:
                        self.installed_models.append(model_name)
            
            return True
        except ImportError:
            self.whisper_available = False
            return False
    
    def is_available(self) -> bool:
        """Check if Whisper is available"""
        return self.whisper_available
    
    def get_status(self) -> Dict:
        """Get Whisper installation status"""
        return {
            "installed": self.whisper_available,
            "models": self.installed_models,
            "available_models": self.MODELS,
            "model_sizes": self.MODEL_SIZES,
        }
    
    def _detect_gpu_type(self) -> str:
        """
        Detect GPU type to install appropriate PyTorch version
        Returns: 'nvidia', 'amd', 'apple', or 'none'
        """
        import platform
        system = platform.system()
        
        try:
            # macOS - Apple Silicon (ARM64) or Intel
            if system == "Darwin":
                machine = platform.machine()
                if machine == "arm64":
                    return "apple"  # Apple Silicon - use MPS
                return "none"  # Intel Mac - no GPU support
            
            # Windows/Linux - Check for NVIDIA or AMD
            if system in ["Windows", "Linux"]:
                # Try to detect NVIDIA via nvidia-smi
                try:
                    result = subprocess.run(
                        ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        logger.info(f"Detected NVIDIA GPU: {result.stdout.strip()}")
                        return "nvidia"
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
                
                # Try to detect AMD via rocm-smi (Linux) or other methods (Windows)
                try:
                    result = subprocess.run(
                        ["rocm-smi", "--showproductname"],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if result.returncode == 0:
                        logger.info("Detected AMD GPU with ROCm")
                        return "amd"
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
                
                # Windows - Check via wmic for AMD GPU
                if system == "Windows":
                    try:
                        result = subprocess.run(
                            ["wmic", "path", "win32_VideoController", "get", "name"],
                            capture_output=True,
                            text=True,
                            timeout=2
                        )
                        if result.returncode == 0:
                            output = result.stdout.lower()
                            if "radeon" in output or "amd" in output:
                                logger.info("Detected AMD GPU via wmic")
                                return "amd"
                            elif "nvidia" in output or "geforce" in output or "quadro" in output:
                                logger.info("Detected NVIDIA GPU via wmic")
                                return "nvidia"
                    except (FileNotFoundError, subprocess.TimeoutExpired):
                        pass
        
        except Exception as e:
            logger.warning(f"Error detecting GPU: {e}")
        
        return "none"
    
    def install_whisper(self, progress_callback=None) -> tuple[bool, str]:
        """
        Install Whisper library with appropriate PyTorch version for detected GPU
        
        Args:
            progress_callback: Function to call with progress updates
            
        Returns:
            (success, message)
        """
        try:
            import sys
            
            # Step 1: Detect GPU type
            if progress_callback:
                progress_callback({
                    "status": "installing",
                    "progress": 10,
                    "message": "Detecting GPU hardware..."
                })
            
            gpu_type = self._detect_gpu_type()
            logger.info(f"Detected GPU type: {gpu_type}")
            
            # Step 2: Install PyTorch with appropriate backend
            if progress_callback:
                progress_callback({
                    "status": "installing",
                    "progress": 20,
                    "message": f"Installing PyTorch for {gpu_type.upper()} GPU..."
                })
            
            # Determine PyTorch installation command based on GPU
            if gpu_type == "nvidia":
                # NVIDIA CUDA 12.1
                logger.info("Installing PyTorch with CUDA 12.1 support...")
                torch_cmd = [
                    sys.executable, "-m", "pip", "install", 
                    "torch", "torchvision", "torchaudio",
                    "--index-url", "https://download.pytorch.org/whl/cu121"
                ]
                gpu_msg = "NVIDIA CUDA"
            elif gpu_type == "amd":
                # AMD ROCm 6.0
                logger.info("Installing PyTorch with ROCm 6.0 support...")
                torch_cmd = [
                    sys.executable, "-m", "pip", "install",
                    "torch", "torchvision", "torchaudio",
                    "--index-url", "https://download.pytorch.org/whl/rocm6.0"
                ]
                gpu_msg = "AMD ROCm"
            elif gpu_type == "apple":
                # Apple Silicon - default PyTorch includes MPS
                logger.info("Installing PyTorch with Apple Silicon MPS support...")
                torch_cmd = [
                    sys.executable, "-m", "pip", "install",
                    "torch", "torchvision", "torchaudio"
                ]
                gpu_msg = "Apple Silicon MPS"
            else:
                # CPU-only
                logger.info("Installing CPU-only PyTorch...")
                torch_cmd = [
                    sys.executable, "-m", "pip", "install",
                    "torch", "torchvision", "torchaudio",
                    "--index-url", "https://download.pytorch.org/whl/cpu"
                ]
                gpu_msg = "CPU"
            
            result = subprocess.run(torch_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                error = result.stderr or "PyTorch installation failed"
                logger.error(f"PyTorch installation failed: {error}")
                return False, f"PyTorch installation failed: {error}"
            
            # Step 3: Install Whisper
            if progress_callback:
                progress_callback({
                    "status": "installing",
                    "progress": 70,
                    "message": "Installing Whisper AI..."
                })
            
            logger.info("Installing openai-whisper...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", "openai-whisper"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.whisper_available = True
                
                # Verify GPU detection after installation
                self.device = self._detect_device()
                
                if progress_callback:
                    progress_callback({
                        "status": "complete",
                        "progress": 100,
                        "message": f"Whisper installed successfully with {gpu_msg} support"
                    })
                
                success_msg = f"Whisper installed successfully!\nGPU Support: {gpu_msg}"
                logger.info(success_msg)
                return True, success_msg
            else:
                error = result.stderr or "Installation failed"
                return False, f"Whisper installation failed: {error}"
                
        except Exception as e:
            logger.error(f"Error installing Whisper: {e}")
            return False, f"Installation error: {str(e)}"
    
    def _verify_and_cleanup_model(self, model_name: str) -> bool:
        """
        Check if model file exists and is accessible.
        Whisper library handles its own checksum verification internally.
        
        Returns:
            True if model exists and is accessible, False if there's an issue
        """
        try:
            from pathlib import Path
            
            # Get the model cache directory (where Whisper stores models)
            cache_dir = Path.home() / ".cache" / "whisper"
            model_file = cache_dir / f"{model_name}.pt"
            
            if not model_file.exists():
                logger.debug(f"Model {model_name} not found at {model_file}")
                return False  # Model not downloaded yet
            
            # Check if file is readable and has reasonable size (> 1MB)
            if model_file.stat().st_size < 1_000_000:
                logger.warning(f"Model file {model_name} is suspiciously small ({model_file.stat().st_size} bytes)")
                return False
            
            logger.debug(f"Model {model_name} exists and appears valid ({model_file.stat().st_size / 1_000_000:.1f} MB)")
            return True
                
        except Exception as e:
            logger.warning(f"Could not check model file: {e}")
            return False
    
    def download_model(self, model_name: str, progress_callback=None) -> tuple[bool, str]:
        """
        Download a Whisper model
        
        Args:
            model_name: Model to download (tiny, base, small, medium, large)
            progress_callback: Function to call with progress updates
            
        Returns:
            (success, message)
        """
        if not self.whisper_available:
            return False, "Whisper is not installed. Install it first."
        
        if model_name not in self.MODELS:
            return False, f"Invalid model: {model_name}. Available models: {', '.join(self.MODELS)}"
        
        try:
            if progress_callback:
                progress_callback({
                    "status": "downloading",
                    "progress": 0,
                    "message": f"Downloading Whisper {model_name} model ({self.MODEL_SIZES[model_name]})..."
                })
            
            import os
            import sys

            import whisper
            
            logger.info(f"Downloading Whisper model: {model_name}")
            
            # Set the download directory to our models folder
            from path_manager import get_models_dir
            model_dir = get_models_dir() / "whisper"
            model_dir.mkdir(parents=True, exist_ok=True)
            
            # Whisper saves models to ~/.cache/whisper by default on Linux/Mac
            # On Windows it uses different paths
            # We override both XDG_CACHE_HOME (Linux/Mac) and set download_root explicitly
            whisper_cache_dir = model_dir
            os.environ["XDG_CACHE_HOME"] = str(whisper_cache_dir.parent)
            
            # Also set for Windows (though Whisper uses download_root parameter primarily)
            if sys.platform == 'win32':
                # On Windows, Whisper checks LOCALAPPDATA but we override with download_root
                pass
            
            logger.info(f"Set XDG_CACHE_HOME to: {whisper_cache_dir.parent}")
            logger.info(f"Whisper models will be saved to: {whisper_cache_dir}")
            logger.info(f"Download root parameter: {model_dir}")
            
            # Suppress tqdm progress bars that corrupt our JSON output
            # Whisper's download uses tqdm which prints to stderr
            old_stderr = sys.stderr
            try:
                sys.stderr = open(os.devnull, 'w')
                
                # This will download the model if not already present
                # Whisper handles checksum verification internally - trust it!
                # The download can take several minutes for large models
                logger.info(f"Calling whisper.load_model('{model_name}') with device={self.device}...")
                model = whisper.load_model(model_name, download_root=str(model_dir), device=self.device)
                logger.info(f"Model {model_name} loaded and verified by Whisper library on {self.device}")
            finally:
                # Restore stderr
                sys.stderr.close()
                sys.stderr = old_stderr
            
            # Update installed models list
            if model_name not in self.installed_models:
                self.installed_models.append(model_name)
                logger.info(f"Added {model_name} to installed models list")
            
            # Check where the model was saved
            from path_manager import get_models_dir
            model_dir = get_models_dir() / "whisper"
            logger.info(f"Whisper models directory: {model_dir}")
            if model_dir.exists():
                model_files = list(model_dir.glob("*.pt"))
                logger.info(f"Found {len(model_files)} model files in directory")
            
            # Send final progress update (without "status" to avoid premature completion)
            if progress_callback:
                progress_callback({
                    "type": "progress",
                    "progress": 100,
                    "message": f"Model {model_name} downloaded and verified ✓"
                })
            
            return True, f"Model {model_name} downloaded and verified successfully"
            
        except Exception as e:
            logger.error(f"Error downloading model: {e}")
            return False, f"Download failed: {str(e)}"
    
    def generate_subtitles(
        self,
        video_path: str,
        model_name: str = "base",
        language: Optional[str] = None,
        progress_callback=None
    ) -> tuple[bool, str, Optional[Dict]]:
        """
        Generate subtitles for a video file
        
        Args:
            video_path: Path to video file
            model_name: Whisper model to use
            language: Target language (None for auto-detect)
            progress_callback: Function to call with progress updates
            
        Returns:
            (success, message, subtitle_info_dict)
            subtitle_info_dict format matches downloaded subtitles:
            {
                "file_path": "path/to/subtitle.srt",
                "language": "eng",
                "provider": "Whisper AI",
                "format": "srt",
                "score": 95,
                "download_count": 0,
                "filename": "filename.srt"
            }
        """
        if not self.whisper_available:
            return False, "Whisper is not installed", None
        
        if not Path(video_path).exists():
            return False, f"Video file not found: {video_path}", None
        
        try:
            # Generate output path in temp directory
            from path_manager import get_temp_dir
            
            temp_subtitles_dir = get_temp_dir() / "subtitles"
            temp_subtitles_dir.mkdir(parents=True, exist_ok=True)
            
            video_file = Path(video_path)
            lang_suffix = language if language else "auto"
            output_filename = f"{video_file.stem}.{lang_suffix}.srt"
            output_path = str(temp_subtitles_dir / output_filename)
            if progress_callback:
                progress_callback({
                    "status": "transcribing",
                    "progress": 0,
                    "message": f"Transcribing audio with Whisper {model_name}..."
                })
            
            import os
            import sys

            import whisper
            
            logger.info(f"Loading Whisper model: {model_name}")
            
            # Suppress tqdm progress bars during model loading and transcription
            old_stderr = sys.stderr
            try:
                sys.stderr = open(os.devnull, 'w')
                
                # Load model - Whisper handles its own checksum verification
                logger.info(f"Loading model on device: {self.device}")
                model = whisper.load_model(model_name, device=self.device)
                
                logger.info(f"Transcribing: {video_path} using {self.device.upper()}")
                
                # Send initial progress if callback provided
                if progress_callback:
                    progress_callback({
                        "status": "processing",
                        "progress": 0,
                        "message": "Transcribing audio with Whisper AI..."
                    })
                
                # Transcribe
                options = {}
                if language:
                    # Convert language code from 3-letter to 2-letter format
                    converted_lang = self._convert_language_code(language)
                    if converted_lang:
                        options["language"] = converted_lang
                        logger.info(f"Using language: {language} -> {converted_lang}")
                
                # Whisper transcription is blocking and doesn't provide progress
                # We show indeterminate progress instead of fake incremental progress
                result = model.transcribe(video_path, **options)
            finally:
                # Restore stderr
                sys.stderr.close()
                sys.stderr = old_stderr
            
            # Convert to SRT format
            segments = result.get("segments", [])
            if isinstance(segments, list):
                srt_content = self._segments_to_srt(segments)
            else:
                return False, "Invalid segments data from Whisper", None
            
            # Write to file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(srt_content)
            
            detected_lang = result.get("language", "unknown")
            logger.info(f"✅ Successfully generated subtitles: {output_path}")
            logger.info(f"Detected language: {detected_lang}")
            
            # Create subtitle info dict matching downloaded subtitle format
            subtitle_info = {
                "file_path": output_path,
                "language": language if language else detected_lang,
                "provider": "Whisper AI",
                "format": "srt",
                "score": 95,  # High score for AI-generated
                "download_count": 0,
                "filename": output_filename,
                "model": model_name,
                "detected_language": detected_lang
            }
            
            if progress_callback:
                progress_callback({
                    "status": "complete",
                    "progress": 100,
                    "message": f"Subtitles generated successfully"
                })
            
            return True, f"Subtitles generated successfully (detected language: {detected_lang})", subtitle_info
            
        except Exception as e:
            logger.error(f"Error generating subtitles: {e}")
            return False, f"Transcription failed: {str(e)}", None
    
    def _segments_to_srt(self, segments: List[Dict]) -> str:
        """Convert Whisper segments to SRT format"""
        srt_lines = []
        
        for i, segment in enumerate(segments, start=1):
            start_time = self._format_timestamp(segment["start"])
            end_time = self._format_timestamp(segment["end"])
            text = segment["text"].strip()
            
            srt_lines.append(f"{i}")
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(text)
            srt_lines.append("")  # Blank line between subtitles
        
        return "\n".join(srt_lines)
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds to SRT timestamp format (HH:MM:SS,mmm)"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    def get_model_info(self, model_name: str) -> Dict:
        """Get information about a specific model"""
        return {
            "name": model_name,
            "size": self.MODEL_SIZES.get(model_name, "Unknown"),
            "installed": model_name in self.installed_models,
            "available": model_name in self.MODELS,
        }


def main():
    """Test the Whisper manager"""
    manager = WhisperManager()
    
    status = manager.get_status()
    
    print("Whisper Status:")
    print(f"  Installed: {status['installed']}")
    
    if status['installed']:
        print("  Downloaded Models: " + (', '.join(status['models']) if status['models'] else 'None'))
        print("\nAvailable Models:")
        for model in status['available_models']:
            info = manager.get_model_info(model)
            status_icon = "✅" if info['installed'] else "❌"
            print(f"    {status_icon} {model} ({info['size']})")
    else:
        print("\n❌ Whisper is not installed")
        print("Install with: pip install openai-whisper")
        print("\nOr use the application's auto-install feature")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()

