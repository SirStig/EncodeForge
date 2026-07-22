"""
Manual match picker — lets the user correct a wrong (or missing) auto-match.

Auto-match always picks one result per its provider fallback chain with no
way to see or choose an alternative. This dialog runs a fresh, user-editable
search across every configured provider and lets the user pick the right
candidate from the full list, instead of the only recourse being to rename
the source file and hope the parser does better next time.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.widgets.custom_widgets import StyledComboBox, StyledLineEdit, StyledSpinBox
from utils.workers import Worker

logger = logging.getLogger(__name__)


class MatchPickerDialog(QDialog):
    """Search for and pick a metadata match by hand."""

    def __init__(
        self,
        parent,
        thread_pool: QThreadPool,
        *,
        file_stem: str = "",
        media_type: str = "tv",
        initial: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Search / Fix Match")
        self.setMinimumSize(760, 480)
        self.thread_pool = thread_pool
        self._candidates: List[Dict[str, Any]] = []
        self._selected: Optional[Dict[str, Any]] = None
        self._build_ui()

        initial = initial or {}
        self.title_edit.setText(str(initial.get("show_title") or initial.get("title") or file_stem or ""))
        self.type_combo.setCurrentIndex(1 if media_type == "movie" else 0)
        try:
            self.season_spin.setValue(int(initial.get("season") or 1))
        except (TypeError, ValueError):
            pass
        try:
            self.episode_spin.setValue(int(initial.get("episode") or 1))
        except (TypeError, ValueError):
            pass
        year = initial.get("year") or initial.get("show_year") or ""
        self.year_edit.setText(str(year))
        self._on_type_changed()

        if self.title_edit.text().strip():
            self._search()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        form = QGridLayout()
        form.addWidget(QLabel("Type:"), 0, 0)
        self.type_combo = StyledComboBox()
        self.type_combo.addItem("TV Show", "tv")
        self.type_combo.addItem("Movie", "movie")
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addWidget(self.type_combo, 0, 1)

        form.addWidget(QLabel("Title:"), 0, 2)
        self.title_edit = StyledLineEdit()
        self.title_edit.returnPressed.connect(self._search)
        form.addWidget(self.title_edit, 0, 3, 1, 3)

        form.addWidget(QLabel("Season:"), 1, 0)
        self.season_spin = StyledSpinBox()
        self.season_spin.setRange(0, 999)
        self.season_spin.setValue(1)
        form.addWidget(self.season_spin, 1, 1)

        form.addWidget(QLabel("Episode:"), 1, 2)
        self.episode_spin = StyledSpinBox()
        self.episode_spin.setRange(0, 9999)
        self.episode_spin.setValue(1)
        form.addWidget(self.episode_spin, 1, 3)

        form.addWidget(QLabel("Year:"), 1, 4)
        self.year_edit = StyledLineEdit()
        self.year_edit.setPlaceholderText("optional")
        self.year_edit.setMaximumWidth(90)
        form.addWidget(self.year_edit, 1, 5)

        root.addLayout(form)

        search_row = QHBoxLayout()
        self.search_btn = QPushButton("Search")
        self.search_btn.clicked.connect(self._search)
        search_row.addWidget(self.search_btn)
        self.status_label = QLabel("")
        search_row.addWidget(self.status_label, 1)
        root.addLayout(search_row)

        self.results_table = QTableWidget(0, 4)
        self.results_table.setHorizontalHeaderLabels(["Source", "Title", "Year / S-E", "Episode / Overview"])
        self.results_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.itemDoubleClicked.connect(lambda _i: self._accept_if_selected())
        root.addWidget(self.results_table, 1)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self._accept_if_selected)
        box.rejected.connect(self.reject)
        root.addWidget(box)

    def _on_type_changed(self) -> None:
        is_tv = self.type_combo.currentData() == "tv"
        self.season_spin.setEnabled(is_tv)
        self.episode_spin.setEnabled(is_tv)

    def _search(self) -> None:
        title = self.title_edit.text().strip()
        if not title:
            self.status_label.setText("Enter a title to search.")
            return

        media_type = self.type_combo.currentData()
        season = self.season_spin.value()
        episode = self.episode_spin.value()
        year_text = self.year_edit.text().strip()
        year = int(year_text) if year_text.isdigit() else None

        self.search_btn.setEnabled(False)
        self.status_label.setText("Searching…")
        self.results_table.setRowCount(0)
        self._candidates = []

        def _job(progress_callback=None, **_kw):
            from core.encodeforge_core import EncodeForgeCore
            from utils.settings_manager import get_settings_manager

            cs = get_settings_manager().get_merged_conversion_settings()
            core = EncodeForgeCore(settings=cs)
            return core.search_rename_candidates(
                title, media_type=media_type, season=season, episode=episode, year=year
            )

        worker = Worker(_job)
        worker.signals.result.connect(self._on_results)
        worker.signals.error.connect(self._on_search_error)
        self.thread_pool.start(worker)

    def _on_search_error(self, error: tuple) -> None:
        self.search_btn.setEnabled(True)
        msg = str(error[1]) if len(error) > 1 else "Unknown error"
        self.status_label.setText(f"Search failed: {msg}")
        logger.error(f"Match picker search failed: {msg}")

    def _on_results(self, candidates: List[Dict[str, Any]]) -> None:
        self.search_btn.setEnabled(True)
        self._candidates = candidates or []
        self.results_table.setRowCount(len(self._candidates))

        for row, c in enumerate(self._candidates):
            source = str(c.get("source", "")).upper()
            title = c.get("show_title") or c.get("title") or "Unknown"
            year = c.get("year") or c.get("show_year") or ""
            season = c.get("season")
            episode = c.get("episode")
            se = f"S{int(season):02d}E{int(episode):02d}" if season and episode else str(year)
            detail = c.get("episode_title") or c.get("overview") or ""

            self.results_table.setItem(row, 0, QTableWidgetItem(source))
            self.results_table.setItem(row, 1, QTableWidgetItem(str(title)))
            self.results_table.setItem(row, 2, QTableWidgetItem(se))
            self.results_table.setItem(row, 3, QTableWidgetItem(str(detail)[:120]))

        if self._candidates:
            self.results_table.selectRow(0)
            self.status_label.setText(f"{len(self._candidates)} candidate(s)")
        else:
            self.status_label.setText("No candidates found.")

    def _accept_if_selected(self) -> None:
        rows = self.results_table.selectionModel().selectedRows() if self.results_table.selectionModel() else []
        if not rows or not self._candidates:
            self.status_label.setText("Select a candidate first.")
            return
        idx = rows[0].row()
        if 0 <= idx < len(self._candidates):
            self._selected = self._candidates[idx]
            self.accept()

    def selected_metadata(self) -> Optional[Dict[str, Any]]:
        return self._selected
