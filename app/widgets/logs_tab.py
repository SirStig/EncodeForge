"""
EncodeForge Logs Tab
Real-time log viewer with filtering and search capabilities
"""

import logging
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QComboBox, QLabel, QLineEdit, QFileDialog,
    QGroupBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QTextCursor, QFont, QColor, QTextCharFormat
from PySide6.QtWidgets import QTextEdit

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
        self.last_position = 0
        self.auto_scroll = True
        self.current_filter = "ALL"
        
        self._setup_ui()
        self._setup_timer()
        self._load_initial_logs()
        
        logger.info("Logs tab initialized")
    
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
        self.log_file_label.setStyleSheet("color: #8e8e93; font-size: 11px;")
        info_layout.addWidget(self.log_file_label)
        
        layout.addLayout(info_layout)
        
        # Apply styling
        self._apply_styling()
    
    def _apply_styling(self):
        """Apply dark theme styling to logs tab"""
        self.setStyleSheet("""
            /* Logs Tab Styling */
            QWidget {
                background-color: #2d2d2d;
                color: #ffffff;
            }
            
            QLabel {
                color: #ffffff;
                font-size: 13px;
            }
            
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 12px;
                font-size: 13px;
                font-weight: 600;
                color: #ffffff;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 12px;
                padding: 0 5px;
            }
            
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px;
                selection-background-color: #0a84ff;
            }
            
            QComboBox {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                padding: 6px 12px;
                min-width: 100px;
            }
            
            QComboBox:hover {
                border: 1px solid #0a84ff;
            }
            
            QComboBox::drop-down {
                border: none;
                padding-right: 8px;
            }
            
            QComboBox QAbstractItemView {
                background-color: #3a3a3a;
                color: #ffffff;
                selection-background-color: #0a84ff;
                border: 1px solid #4a4a4a;
            }
            
            QLineEdit {
                background-color: #3a3a3a;
                color: #ffffff;
                border: 1px solid #4a4a4a;
                border-radius: 6px;
                padding: 6px 12px;
            }
            
            QLineEdit:focus {
                border: 1px solid #0a84ff;
            }
            
            QPushButton {
                background-color: #0a84ff;
                color: #ffffff;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            
            QPushButton:hover {
                background-color: #0071e3;
            }
            
            QPushButton:pressed {
                background-color: #005bb5;
            }
            
            QCheckBox {
                color: #ffffff;
                spacing: 8px;
            }
            
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #4a4a4a;
                border-radius: 4px;
                background-color: #3a3a3a;
            }
            
            QCheckBox::indicator:checked {
                background-color: #0a84ff;
                border-color: #0a84ff;
            }
        """)
    
    def _setup_timer(self):
        """Set up timer for auto-refresh"""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._check_for_updates)
        self.refresh_timer.start(1000)  # Check every second
    
    def _load_initial_logs(self):
        """Load initial logs from file"""
        try:
            if self.log_file.exists():
                # Read full file and apply filter
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Apply filter if active
                if self.current_filter != "ALL":
                    lines = content.split('\n')
                    filtered = [line for line in lines if self.current_filter in line]
                    content_to_display = '\n'.join(filtered)
                else:
                    content_to_display = content

                self.log_display.setPlainText(content_to_display)
                try:
                    self.last_position = self.log_file.stat().st_size
                except Exception:
                    self.last_position = len(content)
                self._update_line_count()

                # Scroll to bottom
                if self.auto_scroll:
                    self.log_display.moveCursor(QTextCursor.MoveOperation.End)
        except Exception as e:
            logger.error(f"Failed to load initial logs: {e}")
    
    def _check_for_updates(self):
        """Check for new log entries"""
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
                        filtered_lines = [line for line in lines if self.current_filter in line]
                        new_content = '\n'.join(filtered_lines)

                    # Append new content
                    if new_content:
                        self.log_display.appendPlainText(new_content)
                        self._update_line_count()

                        # Auto-scroll to bottom
                        if self.auto_scroll:
                            self.log_display.moveCursor(QTextCursor.MoveOperation.End)
        except Exception as e:
            logger.error(f"Failed to check for log updates: {e}")
    
    def _on_filter_changed(self, level: str):
        """Handle log level filter change"""
        self.current_filter = level
        self._refresh_logs()
    
    def _on_search_changed(self, text: str):
        """Handle search text change"""
        if not text:
            self.log_display.setExtraSelections([])
            return
        
        # Highlight search matches using ExtraSelection
        doc = self.log_display.document()
        cursor = QTextCursor(doc)
        cursor.movePosition(QTextCursor.MoveOperation.Start)

        fmt = QTextCharFormat()
        fmt.setBackground(QColor("#ffeb3b"))
        fmt.setForeground(QColor("#000000"))

        selections = []
        while True:
            found = doc.find(text, cursor)
            if found.isNull():
                break
            sel = QTextEdit.ExtraSelection()
            sel.cursor = found
            sel.format = fmt
            selections.append(sel)
            # move cursor forward to avoid finding same match
            cursor = found
            cursor.setPosition(found.position())

        self.log_display.setExtraSelections(selections)
    
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
    
    def _update_line_count(self):
        """Update the line count label"""
        line_count = self.log_display.blockCount()
        self.line_count_label.setText(f"Lines: {line_count}")
