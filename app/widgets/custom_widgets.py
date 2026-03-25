"""
EncodeForge Custom Widget Library
Glassmorphic UI components — styling delegated to theme_base.css
"""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
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
    QVBoxLayout,
    QWidget,
)

# ============================================================================
# TABLE WIDGETS
# ============================================================================

class AutoResizeTable(QTableWidget):
    """
    Intelligent table with proper column sizing and constraints.
    - Non-last columns size to contents; last column stretches
    - Horizontal scrollbar appears when content exceeds viewport
    - Proper vertical sizing with QSizePolicy
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_defaults()

    def _setup_defaults(self):
        """Apply sensible defaults with proper constraints."""
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)

        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(22)
        self.verticalHeader().setMinimumSectionSize(20)

        self.setMinimumHeight(100)

    def setColumns(self, headers, initial_widths=None, stretch_last=False):
        """
        Configure columns with smart resizing.

        Args:
            headers (list): Column header names
            initial_widths (list): Initial widths for columns (optional)
            stretch_last (bool): Deprecated, kept for compatibility
        """
        self.setColumnCount(len(headers))
        self.setHorizontalHeaderLabels(headers)

        header = self.horizontalHeader()
        header.setMinimumSectionSize(40)
        header.setDefaultSectionSize(80)

        n = len(headers)
        for i in range(n):
            if i == n - 1:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        if initial_widths:
            for i, width in enumerate(initial_widths):
                if i < len(headers):
                    header.resizeSection(i, width)

    def enableDragDrop(self, drag_enter_callback=None, drop_callback=None):
        """Enable drag and drop with custom handlers."""
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setAcceptDrops(True)

        if drag_enter_callback:
            self.dragEnterEvent = drag_enter_callback
        if drop_callback:
            self.dropEvent = drop_callback


# ============================================================================
# CONTAINER WIDGETS
# ============================================================================

class GlassmorphicCard(QFrame):
    """
    Section title above a single rounded surface (styled in theme_base.css).
    Add children via content_layout() or QFormLayout(body()).
    """

    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("glass_card")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        if title:
            tl = QLabel(title)
            tl.setObjectName("glass_card_title")
            tl.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Fixed,
            )
            root.addWidget(tl)
            root.setSpacing(8)
        self._body = QFrame()
        self._body.setObjectName("glass_card_body")
        self._body.setFrameShape(QFrame.Shape.NoFrame)
        self._body.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._body_layout = QVBoxLayout(self._body)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._body, 1)
        self.setGraphicsEffect(self._create_shadow())

    def body(self) -> QFrame:
        return self._body

    def content_layout(self) -> QVBoxLayout:
        return self._body_layout

    def _create_shadow(self):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(18)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(0, 3)
        return shadow


class GlassmorphicPanel(QWidget):
    """
    Generic panel — styling delegated to CSS.
    Only sets shadow effect.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.setGraphicsEffect(self._create_shadow())

    def _create_shadow(self):
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(Qt.GlobalColor.black)
        shadow.setOffset(0, 2)
        return shadow


# ============================================================================
# BUTTON WIDGETS
# ============================================================================

class GlassmorphicButton(QPushButton):
    """
    Button — styling via CSS QPushButton rules.
    Only enforces size constraints.
    """

    def __init__(self, text="", icon=None, parent=None):
        super().__init__(text, parent)
        if icon:
            self.setIcon(icon)
            self.setIconSize(QSize(12, 12))
        self._setup_constraints()

    def _setup_constraints(self):
        self.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed
        )
        self.setMinimumHeight(24)
        text = self.text()
        fm = QFontMetrics(self.font())
        has_icon = self.icon() is not None and not self.icon().isNull()
        if text:
            text_w = fm.horizontalAdvance(text)
            pad = 24
            if has_icon:
                pad = 28 + self.iconSize().width() + 6
            self.setMinimumWidth(max(70, text_w + pad))
        elif has_icon:
            self.setMinimumWidth(max(28, self.iconSize().width() + 28))
        else:
            self.setMinimumWidth(28)


class PrimaryButton(GlassmorphicButton):
    """Accent-coloured primary action button (primary=true CSS property)."""

    def __init__(self, text="", icon=None, parent=None):
        super().__init__(text, icon, parent)
        self.setProperty("primary", True)


# ============================================================================
# INPUT WIDGETS
# ============================================================================

class StyledComboBox(QComboBox):
    """
    Dropdown — styling via CSS QComboBox rules.
    Only enforces size constraints.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_constraints()

    def _setup_constraints(self):
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.setMinimumHeight(22)
        self.setMinimumWidth(72)
        self.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )


class StyledLineEdit(QLineEdit):
    """
    Text input — styling via CSS QLineEdit rules.
    Only enforces size constraints.
    """

    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        if placeholder:
            self.setPlaceholderText(placeholder)
        self._setup_constraints()

    def _setup_constraints(self):
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.setMinimumHeight(22)


class StyledSpinBox(QSpinBox):
    """
    Number input — styling via CSS QSpinBox rules.
    Only enforces size constraints.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_constraints()

    def _setup_constraints(self):
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )
        self.setMinimumHeight(22)
        self.setMinimumWidth(72)


class StyledTextEdit(QTextEdit):
    """
    Multi-line text input — styling via CSS QTextEdit rules.
    Only enforces size constraints.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_constraints()

    def _setup_constraints(self):
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.setMinimumHeight(80)


class StyledCheckBox(QCheckBox):
    """
    Checkbox — styling via CSS QCheckBox rules.
    Only enforces size constraints.
    """

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._setup_constraints()

    def _setup_constraints(self):
        self.setSizePolicy(
            QSizePolicy.Policy.Minimum,
            QSizePolicy.Policy.Fixed
        )
        self.setMinimumHeight(22)


# ============================================================================
# LABEL WIDGETS
# ============================================================================

class StyledLabel(QLabel):
    """
    Label with proper alignment and sizing.
    """

    def __init__(self, text="", bold=False, color=None, parent=None):
        super().__init__(text, parent)
        self._bold = bold
        self._color = color
        self._setup_constraints()

    def _setup_constraints(self):
        self.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum
        )
        self.setMinimumHeight(18)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def setHeading(self):
        self.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.92);"
        )


# ============================================================================
# LAYOUT WIDGETS
# ============================================================================

class GlassmorphicToolBar(QToolBar):
    """
    Toolbar — styling via CSS QToolBar rules.
    Only enforces size constraints.
    """

    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self._setup_constraints()

    def _setup_constraints(self):
        self.setMinimumHeight(34)
        self.setIconSize(QSize(16, 16))


class GlassmorphicStatusBar(QStatusBar):
    """
    Status bar — styling via CSS QStatusBar rules.
    Only enforces size constraints.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_constraints()

    def _setup_constraints(self):
        self.setMinimumHeight(24)
        self.setSizeGripEnabled(True)


# ============================================================================
# WINDOW WIDGETS
# ============================================================================

class GlassmorphicMainWindow(QMainWindow):
    """
    Main window — background styling via CSS QMainWindow rule.
    No inline stylesheet needed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        )


# ============================================================================
# UTILITY WIDGETS
# ============================================================================

class ButtonRow(QWidget):
    """
    Container for horizontal button rows with consistent spacing.
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
        btn = GlassmorphicButton(text, icon)
        if callback:
            btn.clicked.connect(callback)
        self.layout.addWidget(btn)
        return btn

    def addStretch(self):
        self.layout.addStretch()


class FormRow(QWidget):
    """
    Container for form label + widget pairs with proper alignment.
    """

    def __init__(self, label_text, widget, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = StyledLabel(label_text)
        label.setMinimumWidth(100)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(label)
        layout.addWidget(widget, 1)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )


class SectionDivider(QFrame):
    """Thin horizontal rule for separating sidebar sections."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet("background: rgba(255,255,255,0.07); border: none;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


__all__ = [
    "AutoResizeTable",
    "GlassmorphicCard",
    "GlassmorphicPanel",
    "GlassmorphicButton",
    "PrimaryButton",
    "StyledComboBox",
    "StyledLineEdit",
    "StyledSpinBox",
    "StyledTextEdit",
    "StyledCheckBox",
    "StyledLabel",
    "GlassmorphicToolBar",
    "GlassmorphicStatusBar",
    "GlassmorphicMainWindow",
    "ButtonRow",
    "FormRow",
    "SectionDivider",
]
