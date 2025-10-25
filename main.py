#!/usr/bin/env python3
"""
EncodeForge - PySide6 Application
Main entry point for the desktop application
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Initialize logging FIRST
from utils.logging_config import setup_logging, get_logger
setup_logging()
logger = get_logger(__name__)

from app.main_window import MainWindow


def main():
    """Main application entry point"""
    logger.info("Starting EncodeForge v0.5.0")

    # Enable High DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("EncodeForge")
    app.setApplicationVersion("0.5.0")
    app.setOrganizationName("EncodeForge")
    
    # Set application icon
    icon_path = Path(__file__).parent / "resources" / "icons" / "app-icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    
    # Create and show main window
    try:
        window = MainWindow()
        window.show()
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Failed to create main window: {e}", exc_info=True)
        return 1
    
    # Run application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
