"""
EncodeForge Worker System
QRunnable-based workers for parallel processing with progress signals
"""

import logging
from typing import Callable, Optional, Any, Dict
from pathlib import Path
from PySide6.QtCore import QRunnable, QObject, Signal, Slot

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
            if isinstance(progress_data, dict):
                current = progress_data.get('progress', 0)
                total = 100  # Default total
                message = progress_data.get('message', '')
                # Don't log progress messages to reduce log spam
                self.signals.progress.emit(current, total, message)
            else:
                # Handle old-style progress callbacks
                self.signals.progress.emit(progress_data, 100, "")
        
        self.kwargs['progress_callback'] = progress_callback_wrapper
    
    @Slot()
    def run(self):
        """Execute the worker function with exception handling."""
        try:
            self._is_running = True
            self.signals.started.emit()
            logger.debug(f"Worker started: {self.fn.__name__}")
            
            result = self.fn(*self.args, **self.kwargs)
            
            if not self._should_stop:
                self.signals.result.emit(result)
                logger.debug(f"Worker completed: {self.fn.__name__}")
        
        except Exception as e:
            import sys
            import traceback
            exctype, value, tb = sys.exc_info()
            logger.error(f"Worker error in {self.fn.__name__}: {e}")
            logger.error(traceback.format_exc())
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        
        finally:
            self._is_running = False
            self.signals.finished.emit()
    
    def stop(self):
        """Request worker to stop (cooperative cancellation)."""
        self._should_stop = True
        logger.debug(f"Stop requested for worker: {self.fn.__name__}")
    
    @property
    def is_running(self) -> bool:
        """Check if worker is currently running."""
        return self._is_running
    
    @property
    def should_stop(self) -> bool:
        """Check if worker should stop."""
        return self._should_stop


class EncoderWorker(Worker):
    """Specialized worker for video encoding tasks."""
    
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
            encoder_settings: Dictionary of encoding settings
            **kwargs: Additional arguments passed to parent
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
        """Stop the encoding process."""
        # Call parent stop first
        super().stop()
        
        # Cancel the conversion handler
        if hasattr(self, 'conversion_handler') and self.conversion_handler:
            try:
                self.conversion_handler.cancel_current()
                logger.info(f"Cancelled encoding for {self.file_path}")
            except Exception as e:
                logger.error(f"Error cancelling encoding: {e}")


class SubtitleWorker(Worker):
    """Specialized worker for subtitle generation/download tasks."""
    
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
            subtitle_settings: Dictionary of subtitle settings
            **kwargs: Additional arguments passed to parent
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
    """Specialized worker for file renaming tasks."""
    
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
            renaming_settings: Dictionary of renaming settings
            **kwargs: Additional arguments passed to parent
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
