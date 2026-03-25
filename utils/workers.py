"""
EncodeForge Worker System
QRunnable-based workers for parallel processing with progress signals
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    """
    Defines signals available from a running worker thread.
    
    Signals:
        started: Emitted when work begins
        progress: Emitted with (current, total, message) during work
        result: Emitted with result data when work completes successfully
        error: Emitted with (error_type, error_value, traceback) on failure
        finished: Emitted when work is done (success or failure)
    """
    started = Signal()
    progress = Signal(int, int, str)  # current, total, message
    result = Signal(object)  # result data
    error = Signal(tuple)  # (exc_type, value, traceback)
    finished = Signal()


class Worker(QRunnable):
    """
    Generic worker thread for executing tasks in background.
    
    Automatically emits signals for progress tracking and result handling.
    Properly handles exceptions and cleanup.
    
    Usage:
        worker = Worker(my_function, arg1, arg2, kwarg1=value1)
        worker.signals.started.connect(on_started)
        worker.signals.progress.connect(on_progress)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(on_error)
        worker.signals.finished.connect(on_finished)
        QThreadPool.globalInstance().start(worker)
    
    Signals:
        started: Emitted when work begins (no arguments)
        progress: Emitted with (current: int, total: int, message: str)
        result: Emitted with result data when work completes (result: Any)
        error: Emitted with (exc_type, value, traceback_str) on failure
        finished: Emitted when work is done - success or failure (no arguments)
    """
    
    def __init__(
        self,
        fn: Callable,
        *args,
        **kwargs
    ):
        """
        Initialize worker.
        
        Args:
            fn: The function to execute in background
            *args: Positional arguments for fn
            **kwargs: Keyword arguments for fn
        """
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._is_running = False
        self._should_stop = False
        
        # Add progress callback to kwargs if function supports it
        def progress_callback_wrapper(progress_data):
            """Convert progress callback dict to signal emission"""
            if self._should_stop:
                return  # Don't emit if stopped
                
            if isinstance(progress_data, dict):
                current = progress_data.get('progress', 0)
                total = progress_data.get('total', 100)
                message = progress_data.get('message', '')
                self.signals.progress.emit(current, total, message)
            else:
                # Handle old-style progress callbacks
                self.signals.progress.emit(progress_data, 100, "")
        
        self.kwargs['progress_callback'] = progress_callback_wrapper
    
    @Slot()
    def run(self):
        """
        Execute the worker function with comprehensive error handling.
        
        This method:
        1. Emits started signal
        2. Executes the function with provided args/kwargs
        3. Checks for cancellation requests periodically
        4. Emits result on success
        5. Catches and emits errors with full traceback
        6. Always emits finished signal in finally block
        """
        import sys
        import traceback
        
        result = None
        
        try:
            self._is_running = True
            self.signals.started.emit()
            logger.info(f"Worker started: {self.fn.__name__}")
            
            # Execute the function
            result = self.fn(*self.args, **self.kwargs)
            
            # Only emit result if not cancelled
            if not self._should_stop:
                self.signals.result.emit(result)
                logger.info(f"Worker completed successfully: {self.fn.__name__}")
            else:
                logger.info(f"Worker cancelled: {self.fn.__name__}")
        
        except Exception as e:
            # Capture full exception information
            exctype, value, tb = sys.exc_info()
            tb_str = traceback.format_exc()
            
            # Log the error
            logger.error(f"Worker error in {self.fn.__name__}: {e}")
            logger.error(f"Traceback:\n{tb_str}")
            
            # Emit error signal with full information
            self.signals.error.emit((exctype, value, tb_str))
        
        finally:
            # Cleanup
            self._is_running = False
            self.signals.finished.emit()
            logger.debug(f"Worker finished: {self.fn.__name__}")
    
    def stop(self):
        """
        Request worker to stop (cooperative cancellation).
        
        Sets the should_stop flag. The worker function must check this
        flag periodically and return early if it's set.
        """
        self._should_stop = True
        logger.info(f"Stop requested for worker: {self.fn.__name__}")
    
    @property
    def is_running(self) -> bool:
        """Check if worker is currently running."""
        return self._is_running
    
    @property
    def should_stop(self) -> bool:
        """Check if worker should stop."""
        return self._should_stop


class EncoderWorker(Worker):
    """
    Specialized worker for video encoding tasks.
    
    Handles video conversion with FFmpeg, supporting various codecs,
    quality settings, and hardware acceleration.
    
    Usage:
        worker = EncoderWorker(
            file_path=Path("input.mp4"),
            output_path=Path("output.mkv"),
            encoder_settings={'codec': 'H.265/HEVC', 'quality': 'High (CQ 18)'}
        )
        worker.signals.progress.connect(update_progress_bar)
        worker.signals.result.connect(on_complete)
        QThreadPool.globalInstance().start(worker)
    
    Signals (inherited from Worker):
        started: Encoding started
        progress: (current_frame, total_frames, status_message)
        result: Encoding completed successfully with output path
        error: Encoding failed with (exc_type, value, traceback)
        finished: Encoding finished (success or failure)
    """
    
    def __init__(
        self,
        file_path: Path,
        output_path: Path,
        encoder_settings: Dict[str, Any],
        **kwargs
    ):
        """
        Initialize encoder worker.
        
        Args:
            file_path: Input video file path
            output_path: Output file path
            encoder_settings: Dictionary of encoding settings:
                - codec: str (e.g., 'H.264', 'H.265/HEVC', 'AV1')
                - preset: str (e.g., 'ultrafast', 'medium', 'slow')
                - quality: str (e.g., 'High (CQ 18)', 'Medium (CQ 23)')
                - hw_accel: bool (use hardware acceleration)
                - normalize_audio: bool
                - format: str (e.g., 'MP4', 'MKV', 'WebM')
            **kwargs: Additional arguments passed to parent Worker
        """
        from core.encodeforge_core import EncodeForgeCore
        
        # Create core instance
        core = EncodeForgeCore()
        
        # Prepare conversion settings from encoder settings
        from core.handlers import ConversionSettings
        settings = ConversionSettings()
        
        # Map encoder settings to conversion settings
        if 'codec' in encoder_settings:
            codec_map = {
                'H.264': 'libx264',
                'H.265/HEVC': 'libx265', 
                'AV1': 'libaom-av1',
                'VP9': 'libvpx-vp9',
                'Copy': 'copy',
                'Auto': 'libx264'
            }
            settings.video_codec_fallback = codec_map.get(encoder_settings['codec'], 'libx264')
        if 'preset' in encoder_settings:
            settings.video_preset = encoder_settings['preset']
        if 'quality' in encoder_settings:
            # Parse quality string like "Medium (CQ 23)" to get CQ value
            quality_str = encoder_settings['quality']
            if 'CQ' in quality_str:
                cq_value = int(quality_str.split('CQ')[1].strip().rstrip(')'))
                settings.video_crf = cq_value
        if 'hw_accel' in encoder_settings:
            settings.use_nvenc = encoder_settings['hw_accel']
        if 'normalize_audio' in encoder_settings:
            settings.normalize_audio = encoder_settings['normalize_audio']
        if 'format' in encoder_settings:
            format_map = {
                'MP4': 'mp4',
                'MKV': 'mkv', 
                'WebM': 'webm',
                'AVI': 'avi',
                'MOV': 'mov'
            }
            settings.output_format = format_map.get(encoder_settings['format'], 'mp4')
        
        # Update core with settings
        core.settings = settings
        
        # Store reference to conversion handler for cancellation
        self.conversion_handler = core.conversion_handler
        
        super().__init__(
            core.convert_file,
            input_path=str(file_path),
            output_path=str(output_path),
            **kwargs
        )
        self.file_path = file_path
        self.output_path = output_path
        self.encoder_settings = encoder_settings
    
    def stop(self):
        """
        Stop the encoding process.
        
        Requests cancellation of the FFmpeg process and sets the
        should_stop flag for cooperative cancellation.
        """
        # Call parent stop first
        super().stop()
        
        # Cancel the conversion handler FFmpeg process
        if hasattr(self, 'conversion_handler') and self.conversion_handler:
            try:
                self.conversion_handler.cancel_current()
                logger.info(f"Requested FFmpeg cancellation for {self.file_path}")
            except Exception as e:
                logger.error(f"Error cancelling encoding: {e}")


class SubtitleWorker(Worker):
    """
    Specialized worker for subtitle generation/download tasks.
    
    Supports downloading subtitles from various providers and
    generating them using Whisper AI.
    
    Usage:
        worker = SubtitleWorker(
            file_path=Path("movie.mp4"),
            subtitle_settings={'languages': ['eng', 'spa'], 'providers': ['opensubtitles']}
        )
        worker.signals.result.connect(on_subtitles_ready)
        QThreadPool.globalInstance().start(worker)
    
    Signals (inherited from Worker):
        started: Subtitle download/generation started
        progress: (current, total, status_message)
        result: Subtitle files downloaded/generated
        error: Operation failed with (exc_type, value, traceback)
        finished: Operation finished
    """
    
    def __init__(
        self,
        file_path: Path,
        subtitle_settings: Dict[str, Any],
        **kwargs
    ):
        """
        Initialize subtitle worker.
        
        Args:
            file_path: Input video file path
            subtitle_settings: Dictionary of subtitle settings:
                - languages: List[str] (e.g., ['eng', 'spa', 'fra'])
                - providers: List[str] (e.g., ['opensubtitles', 'whisper'])
                - whisper_model: str (e.g., 'base', 'small', 'medium')
            **kwargs: Additional arguments passed to parent Worker
        """
        from core.encodeforge_core import EncodeForgeCore
        
        # Create core instance
        core = EncodeForgeCore()
        
        super().__init__(
            core.download_subtitles,
            file_path=str(file_path),
            languages=subtitle_settings.get('languages', ['eng']),
            **kwargs
        )
        self.file_path = file_path
        self.subtitle_settings = subtitle_settings


class RenamerWorker(Worker):
    """
    Specialized worker for file renaming tasks.
    
    Renames files based on metadata from TMDB, TVDB, and other providers.
    Supports pattern-based renaming with preview and undo capabilities.
    
    Usage:
        worker = RenamerWorker(
            file_path=Path("video.mkv"),
            renaming_settings={'pattern': '{title} ({year})', 'dry_run': False}
        )
        worker.signals.result.connect(on_rename_complete)
        QThreadPool.globalInstance().start(worker)
    
    Signals (inherited from Worker):
        started: Renaming started
        progress: (current, total, status_message)
        result: Renaming completed with new paths
        error: Renaming failed with (exc_type, value, traceback)
        finished: Operation finished
    """
    
    def __init__(
        self,
        file_path: Path,
        renaming_settings: Dict[str, Any],
        **kwargs
    ):
        """
        Initialize renamer worker.
        
        Args:
            file_path: Input file path
            renaming_settings: Dictionary of renaming settings:
                - pattern: str (e.g., '{title} ({year})')
                - dry_run: bool (preview only, don't actually rename)
                - create_backup: bool (create backup before renaming)
                - provider: str (e.g., 'tmdb', 'tvdb', 'omdb')
            **kwargs: Additional arguments passed to parent Worker
        """
        from core.encodeforge_core import EncodeForgeCore
        
        # Create core instance
        core = EncodeForgeCore()
        
        super().__init__(
            core.rename_files,
            file_paths=[str(file_path)],
            dry_run=renaming_settings.get('dry_run', False),
            create_backup=renaming_settings.get('create_backup', False),
            **kwargs
        )
        self.file_path = file_path
        self.renaming_settings = renaming_settings
