#!/usr/bin/env python3
"""
Whisper Manager - Handles faster-whisper model management and subtitle generation.

Uses faster-whisper (CTranslate2 backend) instead of openai-whisper:
- No manual PyTorch/CUDA wheel selection needed
- Significantly faster transcription (4x+ vs openai-whisper)
- Lower VRAM/RAM usage via int8 quantization
- GPU support works automatically when CUDA drivers are present
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class WhisperManager:
    """Manages faster-whisper AI for subtitle generation."""

    MODELS = [
        "tiny", "base", "small", "medium",
        "large-v2", "large-v3", "large-v3-turbo",
    ]

    MODEL_SIZES = {
        "tiny": "75 MB",
        "base": "145 MB",
        "small": "466 MB",
        "medium": "1.5 GB",
        "large-v2": "2.9 GB",
        "large-v3": "2.9 GB",
        "large-v3-turbo": "1.6 GB",
    }

    MODEL_DESCRIPTIONS = {
        "tiny": "Fastest, lowest accuracy",
        "base": "Fast, decent accuracy",
        "small": "Good balance of speed and accuracy",
        "medium": "High accuracy, slower",
        "large-v2": "Very high accuracy",
        "large-v3": "Best accuracy",
        "large-v3-turbo": "Recommended — nearly large-v3 accuracy at 8x speed",
    }

    # Map 3-letter ISO 639-2 codes to 2-letter ISO 639-1 codes
    LANGUAGE_CODE_MAP = {
        "eng": "en", "spa": "es", "fre": "fr", "fra": "fr",
        "ger": "de", "deu": "de", "ita": "it", "por": "pt",
        "rus": "ru", "jpn": "ja", "kor": "ko", "chi": "zh",
        "zho": "zh", "ara": "ar", "hin": "hi", "tur": "tr",
        "pol": "pl", "ukr": "uk", "vie": "vi", "tha": "th",
        "nld": "nl", "dut": "nl", "swe": "sv", "dan": "da",
        "nor": "no", "fin": "fi", "cze": "cs", "ces": "cs",
        "hun": "hu", "rum": "ro", "ron": "ro", "gre": "el",
        "ell": "el", "heb": "he", "ind": "id", "msa": "ms",
        "may": "ms",
    }

    def __init__(self):
        self.whisper_available = False
        self.installed_models: List[str] = []
        self.device = "cpu"
        self._check_installation()

    # ------------------------------------------------------------------
    # Installation check
    # ------------------------------------------------------------------

    def _check_installation(self) -> bool:
        """Check if faster-whisper is installed and discover cached models."""
        try:
            from faster_whisper import WhisperModel  # noqa: F401
            self.whisper_available = True
            self.device = self._detect_device()
            self.installed_models = self._find_installed_models()
            return True
        except ImportError:
            self.whisper_available = False
            return False

    def _detect_device(self) -> str:
        """Detect best compute device available (cuda > mps > cpu)."""
        try:
            import ctranslate2
            providers = ctranslate2.get_supported_compute_types("cuda")
            if providers:
                return "cuda"
        except Exception:
            pass

        try:
            import platform
            if platform.system() == "Darwin" and platform.machine() == "arm64":
                # faster-whisper uses Metal via CTranslate2 on Apple Silicon
                return "auto"
        except Exception:
            pass

        return "cpu"

    def _get_model_cache_dir(self) -> Path:
        """Return the directory where faster-whisper models are cached."""
        try:
            from core.path_manager import get_models_dir
            return get_models_dir() / "faster-whisper"
        except Exception:
            return Path.home() / ".cache" / "faster-whisper"

    def _find_installed_models(self) -> List[str]:
        """Scan cache directory for downloaded model directories."""
        installed = []
        cache_dir = self._get_model_cache_dir()
        if not cache_dir.exists():
            return installed

        # faster-whisper stores models as: models--Systran--faster-whisper-{name}
        for model_name in self.MODELS:
            folder_name = f"models--Systran--faster-whisper-{model_name}"
            model_dir = cache_dir / folder_name
            # A HuggingFace cache directory gains blobs/refs/snapshots as soon
            # as a download *starts*, so "directory is non-empty" reported a
            # cancelled 15%-complete download as installed — the Download button
            # disappeared and loading later failed with an opaque cache error.
            # Require the actual weights to be present.
            if not model_dir.is_dir():
                continue

            snapshots = model_dir / "snapshots"
            has_weights = any(
                snapshots.glob("*/model.bin")
            ) or any(
                snapshots.glob("*/model.safetensors")
            ) if snapshots.is_dir() else False

            if has_weights:
                installed.append(model_name)
            elif any(model_dir.iterdir()):
                logger.debug(
                    "Ignoring incomplete Whisper model cache for '%s' (no weights present)",
                    model_name,
                )

        return installed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        return self.whisper_available

    def get_status(self) -> Dict:
        return {
            "installed": self.whisper_available,
            "models": self.installed_models,
            "available_models": self.MODELS,
            "model_sizes": self.MODEL_SIZES,
            "model_descriptions": self.MODEL_DESCRIPTIONS,
            "device": self.device,
        }

    def get_model_info(self, model_name: str) -> Dict:
        return {
            "name": model_name,
            "size": self.MODEL_SIZES.get(model_name, "Unknown"),
            "description": self.MODEL_DESCRIPTIONS.get(model_name, ""),
            "installed": model_name in self.installed_models,
            "available": model_name in self.MODELS,
        }

    # ------------------------------------------------------------------
    # Install
    # ------------------------------------------------------------------

    def install_whisper(self, progress_callback=None) -> Tuple[bool, str]:
        """
        Install faster-whisper via pip.

        No GPU wheel selection needed — CTranslate2 auto-detects CUDA.
        """
        def _cb(pct: int, msg: str):
            if progress_callback:
                progress_callback({"status": "installing", "progress": pct, "message": msg})

        try:
            _cb(10, "Installing faster-whisper…")
            logger.info("Running: pip install faster-whisper")

            # A frozen (Nuitka one-file) build has no importable pip and
            # sys.executable is the app itself, so "-m pip" would just relaunch
            # the GUI. Detect that and tell the user what to do instead.
            if getattr(sys, "frozen", False) or "__compiled__" in globals():
                return False, (
                    "Automatic installation is not available in the packaged build. "
                    "Install faster-whisper into a Python environment and launch "
                    "EncodeForge from source, or use a pre-built model bundle."
                )

            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-U", "faster-whisper"],
                capture_output=True,
                text=True,
                # Without a timeout a stalled package index blocks the worker
                # thread forever with the UI stuck at "Installing… 10%".
                timeout=900,
            )

            if result.returncode != 0:
                err = result.stderr or "pip returned non-zero exit code"
                logger.error("faster-whisper install failed: %s", err)
                return False, f"Installation failed:\n{err}"

            _cb(80, "Verifying installation…")

            # Re-check
            self._check_installation()

            if not self.whisper_available:
                return False, "faster-whisper installed but import still fails. Restart may be needed."

            device_hint = {
                "cuda": "NVIDIA GPU (CUDA)",
                "auto": "Apple Silicon (Metal)",
            }.get(self.device, "CPU")

            _cb(100, f"faster-whisper installed — using {device_hint}")
            logger.info("faster-whisper installed successfully, device=%s", self.device)
            return True, f"faster-whisper installed successfully!\nCompute device: {device_hint}"

        except subprocess.TimeoutExpired:
            logger.error("faster-whisper install timed out after 15 minutes")
            return False, (
                "Installation timed out after 15 minutes. Check your network "
                "connection and try again."
            )
        except Exception as exc:
            logger.exception("Error installing faster-whisper")
            return False, f"Installation error: {exc}"

    # ------------------------------------------------------------------
    # Model download
    # ------------------------------------------------------------------

    def download_model(self, model_name: str, progress_callback=None) -> Tuple[bool, str]:
        """
        Download a faster-whisper model (stored in HuggingFace hub format).

        The download happens by instantiating WhisperModel which triggers
        automatic download if the model isn't cached.
        """
        if not self.whisper_available:
            return False, "faster-whisper is not installed. Install it first."

        if model_name not in self.MODELS:
            return False, f"Unknown model: {model_name}. Available: {', '.join(self.MODELS)}"

        def _cb(pct: int, msg: str):
            if progress_callback:
                progress_callback({"status": "downloading", "progress": pct, "message": msg})

        try:
            from faster_whisper import WhisperModel

            size = self.MODEL_SIZES.get(model_name, "unknown size")
            _cb(5, f"Downloading faster-whisper {model_name} ({size})…")
            logger.info("Downloading model: %s", model_name)

            cache_dir = self._get_model_cache_dir()
            cache_dir.mkdir(parents=True, exist_ok=True)

            # Instantiating the model triggers download + verification
            _cb(10, f"Fetching {model_name} from HuggingFace hub…")
            WhisperModel(
                model_name,
                device="cpu",            # load on CPU just for download check
                compute_type="int8",
                download_root=str(cache_dir),
            )

            if model_name not in self.installed_models:
                self.installed_models.append(model_name)

            _cb(100, f"Model {model_name} ready")
            logger.info("Model %s downloaded successfully", model_name)
            return True, f"Model '{model_name}' downloaded and verified."

        except Exception as exc:
            logger.error("Error downloading model %s: %s", model_name, exc)
            return False, f"Download failed: {exc}"

    # ------------------------------------------------------------------
    # Subtitle generation
    # ------------------------------------------------------------------

    def generate_subtitles(
        self,
        video_path: str,
        model_name: str = "base",
        language: Optional[str] = None,
        progress_callback=None,
    ) -> Tuple[bool, str, Optional[Dict]]:
        """
        Generate subtitles for a video file using faster-whisper.

        Returns:
            (success, message, subtitle_info_dict)
        """
        if not self.whisper_available:
            return False, "faster-whisper is not installed", None

        if not Path(video_path).exists():
            return False, f"Video file not found: {video_path}", None

        def _cb(pct: int, msg: str):
            if progress_callback:
                progress_callback({"status": "transcribing", "progress": pct, "message": msg})

        try:
            from core.path_manager import get_temp_dir
            from faster_whisper import WhisperModel

            temp_dir = get_temp_dir() / "subtitles"
            temp_dir.mkdir(parents=True, exist_ok=True)

            video_file = Path(video_path)
            lang_suffix = language if language else "auto"
            output_filename = f"{video_file.stem}.{lang_suffix}.srt"
            output_path = temp_dir / output_filename

            _cb(0, f"Loading model {model_name}…")
            logger.info("Loading faster-whisper model: %s on %s", model_name, self.device)

            cache_dir = self._get_model_cache_dir()

            # _detect_device() reports what the CTranslate2 *wheel* was built
            # with, not whether a usable GPU and runtime are actually present.
            # A CUDA-enabled wheel on a machine with no driver (or a missing
            # cuDNN) throws here, so fall back to CPU rather than making the
            # whole feature unusable.
            attempts = [(self.device, "float16" if self.device == "cuda" else "int8")]
            if self.device != "cpu":
                attempts.append(("cpu", "int8"))

            model = None
            last_error = None
            for device, compute_type in attempts:
                try:
                    model = WhisperModel(
                        model_name,
                        device=device,
                        compute_type=compute_type,
                        download_root=str(cache_dir),
                    )
                    if device != self.device:
                        logger.warning(
                            "Could not initialise Whisper on '%s' (%s); using CPU instead",
                            self.device, last_error,
                        )
                        _cb(2, "GPU unavailable — falling back to CPU (slower)…")
                        self.device = device
                    break
                except Exception as e:
                    last_error = e
                    logger.warning("Whisper model load failed on '%s': %s", device, e)

            if model is None:
                return False, f"Could not load Whisper model '{model_name}': {last_error}"

            lang_arg = self._convert_language_code(language) if language else None
            _cb(5, f"Transcribing with {model_name}…")
            logger.info("Transcribing: %s (lang=%s)", video_path, lang_arg)

            segments_gen, info = model.transcribe(
                video_path,
                language=lang_arg,
                beam_size=5,
                vad_filter=True,          # skip silent sections — faster
            )

            # Consume the generator segment by segment so progress reflects real
            # position in the media. Materialising it with list() did all the
            # work inside one call, leaving the bar frozen at 10% for what can
            # be hours on CPU.
            total_duration = getattr(info, "duration", 0) or 0
            segments = []
            last_reported = 10

            for segment in segments_gen:
                segments.append(segment)
                if total_duration > 0:
                    # Map media position onto the 10–95% band; the remaining 5%
                    # covers writing the file out.
                    pct = 10 + int((getattr(segment, "end", 0) / total_duration) * 85)
                    pct = max(10, min(95, pct))
                    if pct > last_reported:
                        last_reported = pct
                        _cb(pct, f"Transcribing… {pct}%")

            _cb(96, "Writing subtitles…")
            srt_content = self._segments_to_srt(segments)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(srt_content)

            detected_lang = info.language if hasattr(info, "language") else (lang_arg or "unknown")
            logger.info("Subtitles written to: %s (detected=%s)", output_path, detected_lang)

            subtitle_info = {
                "file_path": str(output_path),
                "language": language if language else detected_lang,
                "provider": "Whisper AI",
                "format": "srt",
                "score": 95,
                "download_count": 0,
                "filename": output_filename,
                "model": model_name,
                "detected_language": detected_lang,
            }

            _cb(100, "Subtitles generated successfully")
            return True, f"Subtitles generated (detected language: {detected_lang})", subtitle_info

        except Exception as exc:
            logger.error("Error generating subtitles: %s", exc)
            return False, f"Transcription failed: {exc}", None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _convert_language_code(self, lang_code: Optional[str]) -> Optional[str]:
        if not lang_code:
            return None
        if len(lang_code) == 2:
            return lang_code.lower()
        converted = self.LANGUAGE_CODE_MAP.get(lang_code.lower(), lang_code[:2])
        return converted

    def _segments_to_srt(self, segments) -> str:
        lines = []
        for i, seg in enumerate(segments, start=1):
            start = self._format_ts(seg.start)
            end = self._format_ts(seg.end)
            text = seg.text.strip()
            lines += [str(i), f"{start} --> {end}", text, ""]
        return "\n".join(lines)

    def _format_ts(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
