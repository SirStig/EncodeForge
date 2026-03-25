"""
EncodeForge Logs Tab
Real-time log viewer with filtering and search capabilities.
Session-specific display with 5000-line circular buffer.
"""

import logging
from pathlib import Path

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core import path_manager

logger = logging.getLogger(__name__)


class LogsTab(QWidget):
    """Logs viewer tab with real-time updates and filtering"""
    
    # Signals
    log_cleared = Signal()
    log_saved = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_file = path_manager.get_logs_dir() / "encodeforge.log"
        self.session_start_position = 0  # Track where this session started
        self.last_position = 0
        self.auto_scroll = True
        self.current_filter = "ALL"
        self.max_lines = 5000  # Maximum lines to keep in display
        
        # Mark the session start position (current end of file)
        if self.log_file.exists():
            self.session_start_position = self.log_file.stat().st_size
            self.last_position = self.session_start_position
        
        self._setup_ui()
        self._setup_timer()
        self._load_initial_logs()
        
        logger.info("Logs tab initialized - showing logs from this session only (base theme)")
    
    def _setup_ui(self):
        """Set up the logs viewer UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Top controls
        controls_layout = QHBoxLayout()
        
        # Log level filter
        filter_label = QLabel("Filter:")
        controls_layout.addWidget(filter_label)
        
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["ALL", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.filter_combo.currentTextChanged.connect(self._on_filter_changed)
        self.filter_combo.setMaximumWidth(150)
        controls_layout.addWidget(self.filter_combo)
        
        controls_layout.addSpacing(20)
        
        # Search box
        search_label = QLabel("Search:")
        controls_layout.addWidget(search_label)
        
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search logs...")
        self.search_box.textChanged.connect(self._on_search_changed)
        self.search_box.setMaximumWidth(300)
        controls_layout.addWidget(self.search_box)
        
        controls_layout.addStretch()
        
        # Auto-scroll checkbox
        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.toggled.connect(self._on_auto_scroll_toggled)
        controls_layout.addWidget(self.auto_scroll_check)
        
        controls_layout.addSpacing(20)
        
        # Clear button
        self.clear_btn = QPushButton("Clear Display")
        self.clear_btn.clicked.connect(self._clear_display)
        self.clear_btn.setMaximumWidth(120)
        controls_layout.addWidget(self.clear_btn)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_logs)
        self.refresh_btn.setMaximumWidth(100)
        controls_layout.addWidget(self.refresh_btn)
        
        # Save button
        self.save_btn = QPushButton("Save Logs...")
        self.save_btn.clicked.connect(self._save_logs)
        self.save_btn.setMaximumWidth(120)
        controls_layout.addWidget(self.save_btn)
        
        layout.addLayout(controls_layout)
        
        # Log display area
        log_group = QGroupBox("Application Logs")
        log_layout = QVBoxLayout(log_group)
        
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        
        # Set monospace font
        font = QFont("Consolas", 9)
        if not font.exactMatch():
            font = QFont("Courier New", 9)
        self.log_display.setFont(font)
        
        log_layout.addWidget(self.log_display)
        layout.addWidget(log_group)
        
        # Bottom info bar
        info_layout = QHBoxLayout()
        
        self.line_count_label = QLabel("Lines: 0")
        info_layout.addWidget(self.line_count_label)
        
        info_layout.addStretch()
        
        self.log_file_label = QLabel(f"Log file: {self.log_file.name}")
        self.log_file_label.setObjectName("log_file_label")
        info_layout.addWidget(self.log_file_label)
        
        layout.addLayout(info_layout)
        
        # Styling handled by base glassmorphism theme
    
    def _setup_timer(self):
        """Set up timer for auto-refresh"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._check_for_updates)
        self.refresh_timer.start(1000)  # Check every second
    
    def _load_initial_logs(self):
        """Load initial logs from session start position only"""
        try:
            if self.log_file.exists():
                # Read from session start position only
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    f.seek(self.session_start_position)
                    content = f.read()
                    self.last_position = f.tell()

                # Apply filter if active
                if self.current_filter != "ALL":
                    lines = content.split('\n')
                    filtered = []
                    for line in lines:
                        # Check if line contains the log level using proper log format detection
                        if self._line_matches_filter(line, self.current_filter):
                            filtered.append(line)
                    content_to_display = '\n'.join(filtered)
                else:
                    content_to_display = content

                # Apply line limit
                lines = content_to_display.split('\n')
                if len(lines) > self.max_lines:
                    lines = lines[-self.max_lines:]
                    content_to_display = '\n'.join(lines)

                self.log_display.setPlainText(content_to_display)
                self._update_line_count()

                # Scroll to bottom
                if self.auto_scroll:
                    self.log_display.moveCursor(QTextCursor.MoveOperation.End)
        except Exception as e:
            logger.error(f"Failed to load initial logs: {e}")
    
    def _check_for_updates(self):
        """Check for new log entries with proper filtering"""
        try:
            if not self.log_file.exists():
                return
            
            file_size = self.log_file.stat().st_size
            if file_size > self.last_position:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    f.seek(self.last_position)
                    new_content = f.read()
                    # Advance last_position to file_size (bytes) to avoid re-reading
                    self.last_position = file_size

                    # Apply filter if active
                    if self.current_filter != "ALL":
                        lines = new_content.split('\n')
                        filtered_lines = []
                        for line in lines:
                            # Use proper log level detection
                            if self._line_matches_filter(line, self.current_filter):
                                filtered_lines.append(line)
                        new_content = '\n'.join(filtered_lines)

                    # Append new content
                    if new_content:
                        current_text = self.log_display.toPlainText()
                        if current_text:
                            updated_text = current_text + '\n' + new_content
                        else:
                            updated_text = new_content
                        
                        # Enforce line limit (circular buffer)
                        lines = updated_text.split('\n')
                        if len(lines) > self.max_lines:
                            lines = lines[-self.max_lines:]
                            updated_text = '\n'.join(lines)
                        
                        self.log_display.setPlainText(updated_text)
                        self._update_line_count()

                        # Auto-scroll to bottom
                        if self.auto_scroll:
                            self.log_display.moveCursor(QTextCursor.MoveOperation.End)

        except Exception as e:
            logger.error(f"Error checking for log updates: {e}")
    
    def _on_filter_changed(self, level: str):
        """Handle log level filter change"""
        self.current_filter = level
        self._refresh_logs()
    
    def _on_search_changed(self, text: str):
        """Handle search text change"""
        if not text:
            # Clear any existing highlights
            self.log_display.setExtraSelections([])
            return
        
        # Simple search implementation - scroll to first match
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        
        # Find first occurrence
        found = self.log_display.document().find(text, cursor)
        if not found.isNull():
            # Select and scroll to the found text
            self.log_display.setTextCursor(found)
            self.log_display.centerCursor()
    
    def _on_auto_scroll_toggled(self, checked: bool):
        """Handle auto-scroll toggle"""
        self.auto_scroll = checked
    
    def _clear_display(self):
        """Clear the log display"""
        self.log_display.clear()
        self._update_line_count()
        self.log_cleared.emit()
        logger.info("Log display cleared")
    
    def _refresh_logs(self):
        """Refresh logs from file"""
        self.log_display.clear()
        self.last_position = 0
        self._load_initial_logs()
        logger.info("Logs refreshed")
    
    def _save_logs(self):
        """Save logs to a file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Logs",
            str(Path.home() / "encodeforge_logs.txt"),
            "Text Files (*.txt);;Log Files (*.log);;All Files (*.*)"
        )
        
        if file_path:
            try:
                content = self.log_display.toPlainText()
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.log_saved.emit(file_path)
                logger.info(f"Logs saved to: {file_path}")
            except Exception as e:
                logger.error(f"Failed to save logs: {e}")
    
    def _line_matches_filter(self, line: str, filter_level: str) -> bool:
        """Check if a log line matches the current filter level"""
        if filter_level == "ALL":
            return True
        
        # Look for log level indicators in the line
        # The log format is: "2024-01-01 12:00:00 | INFO     | module.name          | message"
        # So we look for " | LEVEL " pattern
        level_patterns = {
            "DEBUG": [" | DEBUG", "DEBUG"],
            "INFO": [" | INFO", "INFO"],
            "WARNING": [" | WARNING", "WARNING", "WARN"],
            "ERROR": [" | ERROR", "ERROR", "ERR"],
            "CRITICAL": [" | CRITICAL", "CRITICAL", "FATAL"]
        }
        
        if filter_level in level_patterns:
            patterns = level_patterns[filter_level]
            for pattern in patterns:
                if pattern.upper() in line.upper():
                    return True
        
        return False

    def _update_line_count(self):
        """Update the line count label"""
        line_count = self.log_display.blockCount()
        self.line_count_label.setText(f"Lines: {line_count}")
