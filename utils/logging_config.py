"""
EncodeForge Logging Configuration
Comprehensive logging setup with file rotation and console output
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional

from core import path_manager


class ColoredFormatter(logging.Formatter):
    """Colored log formatter for console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record):
        """Format log record with colors."""
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logging(
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_to_console: bool = True,
    max_file_size: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up comprehensive logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: Enable file logging
        log_to_console: Enable console logging
        max_file_size: Maximum log file size in bytes before rotation
        backup_count: Number of backup log files to keep
        
    Returns:
        Root logger instance
    """
    # Get root logger
    root_logger = logging.getLogger()
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # Set log level
    level = getattr(logging, log_level.upper(), logging.INFO)
    root_logger.setLevel(level)
    
    # Create formatters
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = ColoredFormatter(
        '%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # File handler with rotation
    if log_to_file:
        try:
            log_file = path_manager.get_logs_dir() / "encodeforge.log"
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)
            
            # Also create a debug log file with more detailed output
            debug_log_file = path_manager.get_logs_dir() / "encodeforge_debug.log"
            debug_file_handler = RotatingFileHandler(
                debug_log_file,
                maxBytes=max_file_size,
                backupCount=backup_count,
                encoding='utf-8'
            )
            debug_file_handler.setLevel(logging.DEBUG)
            debug_file_handler.setFormatter(file_formatter)
            root_logger.addHandler(debug_file_handler)
            
        except Exception as e:
            print(f"Failed to set up file logging: {e}", file=sys.stderr)
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Log startup message
    root_logger.info("=" * 80)
    root_logger.info(f"EncodeForge v0.5.0 - Logging initialized at {log_level} level")
    root_logger.info(f"Log file: {path_manager.get_logs_dir() / 'encodeforge.log'}")
    root_logger.info("=" * 80)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Name of the logger (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_log_level(level: str):
    """
    Change the log level for all handlers.
    
    Args:
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    for handler in root_logger.handlers:
        handler.setLevel(log_level)
    
    logging.info(f"Log level changed to {level}")


def cleanup_old_logs(days_to_keep: int = 7):
    """
    Clean up log files older than specified days.
    
    Args:
        days_to_keep: Number of days to keep log files
    """
    import time
    from datetime import datetime, timedelta
    
    try:
        logs_dir = path_manager.get_logs_dir()
        cutoff_time = time.time() - (days_to_keep * 24 * 60 * 60)
        deleted_count = 0
        
        for log_file in logs_dir.glob("*.log*"):
            if log_file.stat().st_mtime < cutoff_time:
                log_file.unlink()
                deleted_count += 1
        
        if deleted_count > 0:
            logging.info(f"Cleaned up {deleted_count} old log files")
    
    except Exception as e:
        logging.error(f"Failed to clean up old logs: {e}")


def get_recent_logs(lines: int = 100) -> str:
    """
    Get recent log lines from the main log file.
    
    Args:
        lines: Number of recent lines to retrieve
        
    Returns:
        Recent log content as string
    """
    try:
        log_file = path_manager.get_logs_dir() / "encodeforge.log"
        if not log_file.exists():
            return "No log file found."
        
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return ''.join(recent_lines)
    
    except Exception as e:
        return f"Error reading log file: {e}"
