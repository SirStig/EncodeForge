"""
Dialog for editing rename patterns with built-in and user-saved templates.
"""

from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.rename_pattern import (
    BUILTIN_TEMPLATE_GROUPS,
    PLACEHOLDER_DOCS,
    SAMPLE_MOVIE_METADATA,
    SAMPLE_TV_METADATA,
    format_filename_stem,
    load_custom_templates,
    save_custom_templates,
    validate_pattern,
)

class RenamePatternDialog(QDialog):
    def __init__(self, parent=None, initial_pattern: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Format / Pattern")
        self.setMinimumSize(920, 560)
        self._result_pattern = (initial_pattern or "").strip()
        self._custom: List[Tuple[str, str]] = list(load_custom_templates())
        self._build_ui()
        self._pattern_edit.setPlainText(self._result_pattern or self._first_builtin_pattern())
        self._refresh_preview()

    def _first_builtin_pattern(self) -> str:
        for _g, items in BUILTIN_TEMPLATE_GROUPS:
            if items:
                return items[0][1]
        return "{title} - S{season:02d}E{episode:02d} - {episode_title}"

    def selected_pattern(self) -> str:
        return self._result_pattern

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Templates"])
        self._tree.setMinimumWidth(260)
        self._populate_tree()
        self._tree.itemClicked.connect(self._on_tree_item)
        split.addWidget(self._tree)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.addWidget(QLabel("Pattern (Python-style placeholders, e.g. S{season:02d}E{episode:02d}):"))
        self._pattern_edit = QPlainTextEdit()
        self._pattern_edit.setPlaceholderText("{title} - S{season:02d}E{episode:02d} - {episode_title}")
        self._pattern_edit.setMinimumHeight(88)
        self._pattern_edit.textChanged.connect(self._refresh_preview)
        rv.addWidget(self._pattern_edit)

        ins_row = QHBoxLayout()
        ins_row.addWidget(QLabel("Insert:"), 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(140)
        chip_host = QWidget()
        chip_grid = QGridLayout(chip_host)
        chip_grid.setContentsMargins(0, 0, 0, 0)
        chip_grid.setHorizontalSpacing(6)
        chip_grid.setVerticalSpacing(4)
        cols = 5
        for i, (name, _desc) in enumerate(PLACEHOLDER_DOCS):
            b = QPushButton("{" + name + "}")
            b.setToolTip(_desc)
            b.clicked.connect(lambda checked=False, n=name: self._insert_placeholder("{" + n + "}"))
            chip_grid.addWidget(b, i // cols, i % cols)
        scroll.setWidget(chip_host)
        ins_row.addWidget(scroll, 1)
        rv.addLayout(ins_row)

        rv.addWidget(QLabel("Live preview (sample TV / movie):"))
        self._preview_tv = QLabel()
        self._preview_tv.setWordWrap(True)
        self._preview_tv.setTextFormat(Qt.TextFormat.RichText)
        self._preview_tv.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._preview_movie = QLabel()
        self._preview_movie.setWordWrap(True)
        self._preview_movie.setTextFormat(Qt.TextFormat.RichText)
        self._preview_movie.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        rv.addWidget(self._preview_tv)
        rv.addWidget(self._preview_movie)

        rv.addWidget(QLabel("Reference:"))
        ref = QLabel(
            "<table>"
            + "".join(
                f"<tr><td><code>{{{n}}}</code></td><td>{d}</td></tr>" for n, d in PLACEHOLDER_DOCS
            )
            + "</table>"
        )
        ref.setWordWrap(True)
        ref.setTextFormat(Qt.TextFormat.RichText)
        rv.addWidget(ref)

        split.addWidget(right)
        split.setStretchFactor(1, 1)
        root.addWidget(split)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save as template…")
        save_btn.clicked.connect(self._save_custom)
        del_btn = QPushButton("Delete template")
        del_btn.clicked.connect(self._delete_custom)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.accepted.connect(self._on_ok)
        box.rejected.connect(self.reject)
        root.addWidget(box)

    def _populate_tree(self) -> None:
        self._tree.clear()
        for group_name, items in BUILTIN_TEMPLATE_GROUPS:
            g = QTreeWidgetItem([group_name])
            g.setFlags(Qt.ItemFlag.ItemIsEnabled)
            for title, pat in items:
                c = QTreeWidgetItem([title])
                c.setData(0, Qt.ItemDataRole.UserRole, pat)
                c.setToolTip(0, pat)
                g.addChild(c)
            self._tree.addTopLevelItem(g)
            g.setExpanded(True)
        custom_root = QTreeWidgetItem(["My templates"])
        custom_root.setFlags(Qt.ItemFlag.ItemIsEnabled)
        for name, pat in self._custom:
            c = QTreeWidgetItem([name])
            c.setData(0, Qt.ItemDataRole.UserRole, pat)
            c.setToolTip(0, pat)
            custom_root.addChild(c)
        self._tree.addTopLevelItem(custom_root)
        custom_root.setExpanded(True)

    def _on_tree_item(self, item: QTreeWidgetItem, column: int) -> None:
        pat = item.data(0, Qt.ItemDataRole.UserRole)
        if pat:
            self._pattern_edit.setPlainText(pat)

    def _insert_placeholder(self, token: str) -> None:
        cur = self._pattern_edit.textCursor()
        cur.insertText(token)
        self._pattern_edit.setTextCursor(cur)
        self._pattern_edit.setFocus()

    def _refresh_preview(self) -> None:
        pat = self._pattern_edit.toPlainText().strip()
        tv_stem = format_filename_stem(SAMPLE_TV_METADATA, pat, file_stem="Sample.Show") or "(invalid pattern)"
        mv_stem = format_filename_stem(SAMPLE_MOVIE_METADATA, pat, file_stem="Sample.Movie") or "(invalid pattern)"
        self._preview_tv.setText(f"<b>TV sample:</b> {tv_stem}.mkv")
        self._preview_movie.setText(f"<b>Movie sample:</b> {mv_stem}.mkv")

    def _save_custom(self) -> None:
        pat = self._pattern_edit.toPlainText().strip()
        ok, err = validate_pattern(pat)
        if not ok:
            QMessageBox.warning(self, "Pattern", err)
            return
        name, ok2 = QInputDialog.getText(self, "Save template", "Template name:")
        if not ok2 or not name.strip():
            return
        name = name.strip()
        self._custom = [(n, p) for n, p in self._custom if n != name]
        self._custom.append((name, pat))
        save_custom_templates(self._custom)
        self._populate_tree()
        QMessageBox.information(self, "Saved", f"Template “{name}” saved.")

    def _delete_custom(self) -> None:
        item = self._tree.currentItem()
        if not item:
            return
        parent = item.parent()
        if not parent or parent.text(0) != "My templates":
            QMessageBox.information(self, "Delete", "Select a template under “My templates”.")
            return
        name = item.text(0)
        self._custom = [(n, p) for n, p in self._custom if n != name]
        save_custom_templates(self._custom)
        self._populate_tree()

    def _on_ok(self) -> None:
        pat = self._pattern_edit.toPlainText().strip()
        ok, err = validate_pattern(pat)
        if not ok:
            QMessageBox.warning(self, "Pattern", err)
            return
        self._result_pattern = pat
        self.accept()
