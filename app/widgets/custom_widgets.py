"""
EncodeForge Custom Widget Library
Complete glassmorphic UI components with proper sizing, constraints, and alignment
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTextEdit,
    QToolBar,
    QWidget,
)

# ============================================================================
# TABLE WIDGETS
# ============================================================================

class AutoResizeTable(QTableWidget):
    """
    Intelligent table with proper column sizing and constraints
    - Auto-fills width without horizontal scrollbars
    - Manual column resizing (Interactive mode for first N-1 columns)
    - Last column stretches to fill remaining space
    - Proper vertical sizing with QSizePolicy
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_defaults()
    
    def _setup_defaults(self):
        """Apply sensible defaults with proper constraints"""
        # Size policy: Expand both directions, prefer expanding
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        
        # Scrollbar policies
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Selection and appearance
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        
        # Hide vertical header (row numbers)
        self.verticalHeader().setVisible(False)
        
        # Compact row height
        self.verticalHeader().setDefaultSectionSize(24)
        self.verticalHeader().setMinimumSectionSize(20)
        
        # Minimum table size to ensure usability
        self.setMinimumHeight(150)
    
    def setColumns(self, headers, initial_widths=None, stretch_last=False):
        """
        Configure columns with smart resizing - all columns use ResizeToContents
        
        Args:
            headers (list): Column header names
            initial_widths (list): Initial widths for columns (optional, will auto-size)
            stretch_last (bool): Deprecated, kept for compatibility
        """
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)
        
        header = self.horizontalHeader()
        header.setMinimumSectionSize(40)  # Minimum width for any column
        header.setDefaultSectionSize(80)
        
        # All columns resize to content, no stretching
        for i in range(len(headers)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        
        # Set maximum widths to prevent over-stretching
        if initial_widths:
            for i, width in enumerate(initial_widths):
                if i < len(headers):
                    header.resizeSection(i, width)
                    header.setMaximumSectionSize(width + 50)  # Allow some growth
    
    def enableDragDrop(self, drag_enter_callback=None, drop_callback=None):
        """Enable drag and drop with custom handlers"""
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setAcceptDrops(True)
        
        if drag_enter_callback:
            self.dragEnterEvent = drag_enter_callback
        if drop_callback:
            self.dropEvent = drop_callback


# ============================================================================
# CONTAINER WIDGETS
# ============================================================================

class GlassmorphicCard(QGroupBox):
    """
    Container with glassmorphic styling, blur effect, and depth
    - Proper padding and margins
    - Background matches parent
    - Subtle shadow and border
    """
    
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self._setup_style()
        self._setup_constraints()
    
    def _setup_constraints(self):
        """Set proper size policies"""
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
    
    def _create_shadow(self):
        """Create drop shadow effect for depth"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(0, 4)
        return shadow
    
    def _setup_style(self):
        """Apply glassmorphic card styling with depth, blur effect simulation, and shadows"""
        self.setStyleSheet("""
            QGroupBox {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(50, 50, 55, 0.25),
                    stop:0.5 rgba(40, 40, 45, 0.20),
                    stop:1 rgba(35, 35, 40, 0.15)
                );
                border: none;
                border-radius: 16px;
                padding: 26px 16px 16px 16px;
                margin-top: 12px;
                font-size: 11px;
                font-weight: 600;
                color: rgba(255, 255, 255, 0.95);
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 6px 14px;
                left: 14px;
                background: rgba(255, 255, 255, 0.08);
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                color: rgba(255, 255, 255, 0.95);
            }
        """)
        # Enable transparency for blur effect
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setGraphicsEffect(self._create_shadow())


class GlassmorphicPanel(QWidget):
    """
    Generic panel with glassmorphic background
    Used for sidebars, sections without titles
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
    
    def _create_shadow(self):
        """Create drop shadow effect for depth"""
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(0, 2)
        return shadow
    
    def _setup_style(self):
        """Apply glassmorphic panel background with transparency"""
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(45, 45, 50, 0.20),
                    stop:1 rgba(35, 35, 40, 0.15)
                );
                border: none;
                border-radius: 12px;
            }
        """)
        self.setGraphicsEffect(self._create_shadow())


# ============================================================================
# BUTTON WIDGETS
# ============================================================================

class GlassmorphicButton(QPushButton):
    """
    Button with glassmorphic styling, hover animations, and proper sizing
    - Smooth hover transitions
    - Icon support
    - Proper minimum sizes
    """
    
    def __init__(self, text="", icon=None, parent=None):
        super().__init__(text, parent)
        if icon:
            self.setIcon(icon)
            self.setIconSize(QSize(14, 14))
        self._setup_style()
        self._setup_constraints()
    
    def _setup_constraints(self):
        """Set proper size constraints"""
        self.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed
        )
        self.setMinimumHeight(32)
        if not self.text():
            self.setMinimumWidth(32)
    
    def _setup_style(self):
        """Apply glassmorphic button styling with glow, shadows, and animations"""
        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.12),
                    stop:0.5 rgba(255, 255, 255, 0.08),
                    stop:1 rgba(255, 255, 255, 0.05)
                );
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                color: rgba(255, 255, 255, 0.95);
                font-size: 11px;
                font-weight: 500;
            }
            
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.20),
                    stop:0.5 rgba(255, 255, 255, 0.15),
                    stop:1 rgba(255, 255, 255, 0.10)
                );
            }
            
            QPushButton:pressed {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.06),
                    stop:0.5 rgba(255, 255, 255, 0.04),
                    stop:1 rgba(255, 255, 255, 0.02)
                );
                padding: 9px 15px 7px 17px;
            }
            
            QPushButton:disabled {
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.3);
            }
        """)


# ============================================================================
# INPUT WIDGETS
# ============================================================================

class StyledComboBox(QComboBox):
    """
    Dropdown with proper sizing, alignment, and glassmorphic styling
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()
        self._setup_constraints()
    
    def _setup_constraints(self):
        """Set proper size constraints"""
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.setMinimumHeight(30)
        self.setMinimumWidth(120)
    
    def _setup_style(self):
        """Apply minimalist glassmorphic dropdown - text only, no visible button/icon"""
        self.setStyleSheet("""
            QComboBox {
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                color: rgba(255, 255, 255, 0.95);
                font-size: 11px;
            }
            
            QComboBox:hover {
                background: rgba(255, 255, 255, 0.12);
            }
            
            QComboBox::drop-down {
                border: none;
                width: 0px;
            }
            
            QComboBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
            
            QComboBox QAbstractItemView {
                background: rgba(35, 35, 40, 0.95);
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                selection-background-color: rgba(255, 255, 255, 0.15);
                color: rgba(255, 255, 255, 0.95);
                padding: 4px;
                outline: none;
            }
            
            QComboBox QAbstractItemView::item {
                padding: 8px 12px;
                border-radius: 6px;
                min-height: 24px;
            }
            
            QComboBox QAbstractItemView::item:hover {
                background: rgba(255, 255, 255, 0.12);
            }
            
            QComboBox QAbstractItemView::item:selected {
                background: rgba(255, 255, 255, 0.18);
            }
        """)


class StyledLineEdit(QLineEdit):
    """
    Text input with glassmorphic styling and proper sizing
    """
    
    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        if placeholder:
            self.setPlaceholderText(placeholder)
        self._setup_style()
        self._setup_constraints()
    
    def _setup_constraints(self):
        """Set proper size constraints"""
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.setMinimumHeight(30)
    
    def _setup_style(self):
        """Apply glassmorphic input styling"""
        self.setStyleSheet("""
            QLineEdit {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.08),
                    stop:1 rgba(255, 255, 255, 0.05)
                );
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 5px 10px;
                color: rgba(255, 255, 255, 0.95);
                font-size: 11px;
                selection-background-color: rgba(100, 150, 255, 0.4);
            }
            
            QLineEdit:focus {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.12),
                    stop:1 rgba(255, 255, 255, 0.08)
                );
                border: 1px solid rgba(100, 150, 255, 0.5);
            }
            
            QLineEdit:disabled {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.05);
                color: rgba(255, 255, 255, 0.3);
            }
        """)


class StyledSpinBox(QSpinBox):
    """
    Number input with glassmorphic styling
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()
        self._setup_constraints()
    
    def _setup_constraints(self):
        """Set proper size constraints"""
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.setMinimumHeight(30)
        self.setMinimumWidth(80)
    
    def _setup_style(self):
        """Apply glassmorphic spinbox styling"""
        self.setStyleSheet("""
            QSpinBox {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.08),
                    stop:1 rgba(255, 255, 255, 0.05)
                );
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 5px 10px;
                color: rgba(255, 255, 255, 0.95);
                font-size: 11px;
            }
            
            QSpinBox:focus {
                border: 1px solid rgba(100, 150, 255, 0.5);
            }
            
            QSpinBox::up-button, QSpinBox::down-button {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 3px;
                width: 16px;
            }
            
            QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                background: rgba(255, 255, 255, 0.15);
            }
            
            QSpinBox::up-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-bottom: 4px solid rgba(255, 255, 255, 0.8);
            }
            
            QSpinBox::down-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 4px solid rgba(255, 255, 255, 0.8);
            }
        """)


class StyledTextEdit(QTextEdit):
    """
    Multi-line text input with glassmorphic styling
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()
        self._setup_constraints()
    
    def _setup_constraints(self):
        """Set proper size constraints"""
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.setMinimumHeight(80)
    
    def _setup_style(self):
        """Apply glassmorphic text area styling"""
        self.setStyleSheet("""
            QTextEdit {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.06),
                    stop:1 rgba(255, 255, 255, 0.03)
                );
                border: 1px solid rgba(255, 255, 255, 0.15);
                border-radius: 6px;
                padding: 8px;
                color: rgba(255, 255, 255, 0.95);
                font-size: 11px;
                selection-background-color: rgba(100, 150, 255, 0.4);
            }
            
            QTextEdit:focus {
                border: 1px solid rgba(100, 150, 255, 0.5);
            }
        """)


class StyledCheckBox(QCheckBox):
    """
    Checkbox with glassmorphic styling and proper alignment
    """
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._setup_style()
        self._setup_constraints()
    
    def _setup_constraints(self):
        """Set proper size constraints"""
        self.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed
        )
        self.setMinimumHeight(24)
    
    def _setup_style(self):
        """Apply styled checkbox with SVG checkmark"""
        self.setStyleSheet("""
            QCheckBox {
                spacing: 8px;
                color: rgba(255, 255, 255, 0.95);
                font-size: 11px;
            }
            
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 4px;
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.10),
                    stop:1 rgba(255, 255, 255, 0.06)
                );
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            
            QCheckBox::indicator:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.15),
                    stop:1 rgba(255, 255, 255, 0.10)
                );
                border: 1px solid rgba(255, 255, 255, 0.3);
            }
            
            QCheckBox::indicator:checked {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(100, 150, 255, 0.6),
                    stop:1 rgba(80, 120, 230, 0.5)
                );
                border: 1px solid rgba(100, 150, 255, 0.7);
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTAiIHZpZXdCb3g9IjAgMCAxMiAxMCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEuNSA1TDQuNSA4TDEwLjUgMiIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
            }
            
            QCheckBox::indicator:disabled {
                background: rgba(255, 255, 255, 0.02);
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
        """)


# ============================================================================
# LABEL WIDGETS
# ============================================================================

class StyledLabel(QLabel):
    """
    Label with proper alignment, sizing, and optional styling
    """
    
    def __init__(self, text="", bold=False, color=None, parent=None):
        super().__init__(text, parent)
        self._setup_constraints()
        self._setup_style(bold, color)
    
    def _setup_constraints(self):
        """Set proper size constraints with better alignment"""
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum
        )
        self.setMinimumHeight(18)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    
    def _setup_style(self, bold=False, color=None):
        """Apply label styling with proper spacing"""
        weight = 600 if bold else 400
        text_color = color if color else "rgba(255, 255, 255, 0.95)"
        
        self.setStyleSheet(f"""
            QLabel {{
                color: {text_color};
                font-size: 11px;
                font-weight: {weight};
                padding: 0px;
                margin: 0px;
            }}
        """)


# ============================================================================
# LAYOUT WIDGETS
# ============================================================================

class GlassmorphicToolBar(QToolBar):
    """
    Toolbar with glassmorphic styling and proper spacing
    """
    
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self._setup_style()
        self._setup_constraints()
    
    def _setup_constraints(self):
        """Set proper size constraints"""
        self.setMinimumHeight(44)
        self.setIconSize(QSize(16, 16))
    
    def _setup_style(self):
        """Apply glassmorphic toolbar styling"""
        self.setStyleSheet("""
            QToolBar {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(45, 45, 50, 0.8),
                    stop:1 rgba(35, 35, 40, 0.7)
                );
                border: none;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
                spacing: 8px;
                padding: 8px 12px;
            }
            
            QToolBar::separator {
                background: rgba(255, 255, 255, 0.15);
                width: 1px;
                margin: 6px 10px;
            }
            
            QToolButton {
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 6px 12px;
                color: rgba(255, 255, 255, 0.95);
                font-size: 11px;
            }
            
            QToolButton:hover {
                background: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }
            
            QToolButton:pressed {
                background: rgba(255, 255, 255, 0.06);
            }
        """)


class GlassmorphicStatusBar(QStatusBar):
    """
    Status bar with glassmorphic bottom bar styling
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()
        self._setup_constraints()
    
    def _setup_constraints(self):
        """Set proper size constraints"""
        self.setMinimumHeight(28)
        self.setSizeGripEnabled(True)
    
    def _setup_style(self):
        """Apply glassmorphic status bar styling"""
        self.setStyleSheet("""
            QStatusBar {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(35, 35, 40, 0.7),
                    stop:1 rgba(30, 30, 35, 0.6)
                );
                border: none;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                color: rgba(255, 255, 255, 0.85);
                font-size: 10px;
                padding: 4px 12px;
            }
            
            QStatusBar::item {
                border: none;
            }
            
            QSizeGrip {
                background: transparent;
            }
        """)


# ============================================================================
# WINDOW WIDGETS
# ============================================================================

class GlassmorphicMainWindow(QMainWindow):
    """
    Main window with glassmorphic background and blur effect
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_style()
    
    def _setup_style(self):
        """Apply glassmorphic window background"""
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(25, 25, 30, 1.0),
                    stop:0.5 rgba(30, 30, 35, 1.0),
                    stop:1 rgba(35, 35, 40, 1.0)
                );
            }
            
            QMainWindow::separator {
                background: rgba(255, 255, 255, 0.1);
                width: 1px;
                height: 1px;
            }
        """)


# ============================================================================
# UTILITY WIDGETS
# ============================================================================

class ButtonRow(QWidget):
    """
    Container for horizontal button rows with consistent spacing
    """
    
    def __init__(self, spacing=8, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(spacing)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
    
    def addButton(self, text, icon=None, callback=None):
        """Add a glassmorphic button"""
        btn = GlassmorphicButton(text, icon)
        if callback:
            btn.clicked.connect(callback)
        self.layout.addWidget(btn)
        return btn
    
    def addStretch(self):
        """Add stretch to separate button groups"""
        self.layout.addStretch()


class FormRow(QWidget):
    """
    Container for form label + widget pairs with proper alignment
    """
    
    def __init__(self, label_text, widget, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Label with fixed width for alignment
        label = StyledLabel(label_text)
        label.setMinimumWidth(100)
        label.setMaximumWidth(150)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        layout.addWidget(label)
        layout.addWidget(widget, 1)
        
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
