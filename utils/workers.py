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
        self.kwargs['progress_callback'] = self.signals.progress
    
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
        from core.ffmpeg_core import encode_video  # Import here to avoid circular deps
        
        super().__init__(
            encode_video,
            file_path=file_path,
            output_path=output_path,
            settings=encoder_settings,
            **kwargs
        )
        self.file_path = file_path
        self.output_path = output_path
        self.encoder_settings = encoder_settings


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
        from core.subtitle_manager import process_subtitles
        
        super().__init__(
            process_subtitles,
            file_path=file_path,
            settings=subtitle_settings,
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
        from core.metadata_grabber import rename_file
        
        super().__init__(
            rename_file,
            file_path=file_path,
            settings=renaming_settings,
            **kwargs
        )
        self.file_path = file_path
        self.renaming_settings = renaming_settings
