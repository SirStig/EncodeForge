"""
Theme Manager for EncodeForge
Handles application-wide theme loading and management
"""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication

from utils.app_stylesheet import build_app_stylesheet
from utils.design_tokens import default_tokens

logger = logging.getLogger(__name__)


class ThemeManager:
    """Manages application themes and styles."""
    
    _instance = None
    _styles_loaded = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.initialized = True
            self.current_theme = "glassmorphism"
            self.styles_dir = Path(__file__).parent.parent / "resources" / "styles"
            self.loaded_styles = {}
    
    def load_base_theme(self) -> bool:
        """
        Load the base glassmorphism theme for the entire application.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            theme_file = self.styles_dir / "theme_base.css"
            if not theme_file.exists():
                logger.warning(f"Base theme file not found: {theme_file}")
                return False

            tokens = default_tokens()
            css = build_app_stylesheet(tokens)
            app = QApplication.instance()
            if app:
                app.setStyleSheet(css)
                self.loaded_styles["base"] = css
                ThemeManager._styles_loaded = True
                logger.info("Base glassmorphism theme loaded successfully")
                return True

            logger.error("Failed to build base theme stylesheet")
            return False
            
        except Exception as e:
            logger.error(f"Error loading base theme: {e}")
            return False
    
    def load_component_style(self, component_name: str, widget=None) -> Optional[str]:
        """
        Load additional component-specific styles.
        
        Args:
            component_name: Name of the component CSS file (without .css extension)
            widget: Optional widget to apply the style to
            
        Returns:
            CSS string if successful, None otherwise
        """
        try:
            # Check cache first
            if component_name in self.loaded_styles:
                logger.debug(f"Using cached styles for {component_name}")
                return self.loaded_styles[component_name]
            
            css_file = self.styles_dir / f"{component_name}.css"
            if not css_file.exists():
                logger.debug(f"Component style file not found: {css_file}")
                return None
            
            css = self._read_css_file(css_file)
            if css:
                self.loaded_styles[component_name] = css
                if widget:
                    widget.setStyleSheet(css)
                logger.debug(f"Loaded component styles: {component_name}")
                return css
            
            return None
            
        except Exception as e:
            logger.error(f"Error loading component style {component_name}: {e}")
            return None
    
    def apply_dialog_theme(self, dialog) -> None:
        """No-op: QDialog / QMessageBox chrome lives in the global stylesheet (build_app_stylesheet)."""
        _ = dialog
    
    def _read_css_file(self, file_path: Path) -> Optional[str]:
        """
        Read CSS file contents.

        Args:
            file_path: Path to CSS file

        Returns:
            CSS content as string, or None if failed
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading CSS file {file_path}: {e}")
            return None
    
    def reload_theme(self) -> bool:
        """
        Reload the current theme.
        
        Returns:
            True if successful, False otherwise
        """
        self.loaded_styles.clear()
        return self.load_base_theme()
    
    @staticmethod
    def is_theme_loaded() -> bool:
        """Check if base theme has been loaded."""
        return ThemeManager._styles_loaded
    
    @staticmethod
    def get_accent_color() -> str:
        return default_tokens().accent

    @staticmethod
    def get_success_color() -> str:
        return "#4ade80"

    @staticmethod
    def get_warning_color() -> str:
        return "#fbbf24"

    @staticmethod
    def get_error_color() -> str:
        return "#f87171"
    
    @staticmethod
    def configure_table_columns(table_widget) -> None:
        """
        Configure table widget columns to be resizable within full width without scrollbars.
        
        Args:
            table_widget: QTableWidget to configure
        """
        try:
            from PySide6.QtWidgets import QHeaderView
            
            # Get header
            header = table_widget.horizontalHeader()
            if header:
                header.setMinimumSectionSize(40)
                # Allow manual resizing
                header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
                # Last column stretches to fill remaining space
                header.setStretchLastSection(True)
            
            # Ensure no horizontal scrollbar
            from PySide6.QtCore import Qt
            table_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            table_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            
            logger.debug("Configured table columns for full-width resizable layout")
            
        except Exception as e:
            logger.error(f"Error configuring table columns: {e}")


# Singleton instance
_theme_manager = ThemeManager()


def get_theme_manager() -> ThemeManager:
    """Get the global theme manager instance."""
    return _theme_manager


def load_theme() -> bool:
    """
    Convenience function to load the base theme.
    
    Returns:
        True if successful, False otherwise
    """
    return _theme_manager.load_base_theme()
