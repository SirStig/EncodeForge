"""
Active job monitor for encode / subtitle / metadata workers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.widgets.custom_widgets import StyledLabel

logger = logging.getLogger(__name__)

# Layout density aligned with design tokens (space_sm / space_md).
PAGE_MARGIN = 12
PAGE_SPACING = 8


class ProcessesTab(QWidget):
    """Table of in-flight background jobs with progress and cancel."""

    COL_KIND = 0
    COL_FILE = 1
    COL_PROGRESS = 2
    COL_STATUS = 3
    COL_ACTION = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress: Dict[str, Tuple[int, int, str]] = {}
        self._cancel_handlers: Dict[str, Callable[[], None]] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(PAGE_SPACING)

        header = QHBoxLayout()
        header.setSpacing(PAGE_SPACING)
        title = StyledLabel("Active Jobs")
        title.setProperty("heading", True)
        header.addWidget(title)
        header.addStretch()
        self.info_label = StyledLabel("No active jobs")
        self.info_label.setObjectName("section_label")
        header.addWidget(self.info_label)
        layout.addLayout(header)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Type", "File", "Progress", "Status", ""]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(self.COL_KIND, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(self.COL_FILE, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self.COL_PROGRESS, QHeaderView.ResizeMode.Fixed)
        hdr.resizeSection(self.COL_PROGRESS, 140)
        hdr.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(self.COL_ACTION, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        hint = QLabel(
            "Shows encoding, subtitle, and metadata jobs. Cancel asks the worker to stop."
        )
        hint.setWordWrap(True)
        hint.setObjectName("section_label")
        layout.addWidget(hint)

    def note_progress(
        self, job_id: str, current: int, total: int, message: str = ""
    ) -> None:
        """Record latest progress for a job id (path or synthetic key)."""
        self._progress[job_id] = (max(0, current), max(0, total), message or "")

    def clear_progress(self, job_id: str) -> None:
        self._progress.pop(job_id, None)

    def refresh(self, jobs: List[Dict[str, Any]]) -> None:
        """
        Rebuild the table from job dicts.

        Each job: id, kind, name, worker (optional), cancelable (bool).
        """
        self._cancel_handlers.clear()
        seen_ids = {str(j.get("id")) for j in jobs if j.get("id") is not None}
        for stale in list(self._progress.keys()):
            if stale not in seen_ids:
                self._progress.pop(stale, None)

        self.table.setRowCount(0)
        for job in jobs:
            job_id = str(job.get("id", ""))
            kind = str(job.get("kind", "Job"))
            name = str(job.get("name") or Path(job_id).name or job_id)
            cancelable = bool(job.get("cancelable", False))
            worker = job.get("worker")

            row = self.table.rowCount()
            self.table.insertRow(row)

            kind_item = QTableWidgetItem(kind)
            kind_item.setData(Qt.ItemDataRole.UserRole, job_id)
            self.table.setItem(row, self.COL_KIND, kind_item)
            self.table.setItem(row, self.COL_FILE, QTableWidgetItem(name))

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(True)
            bar.setMinimumHeight(18)
            cur, tot, msg = self._progress.get(job_id, (0, 0, ""))
            if tot > 0:
                pct = int((cur / tot) * 100)
                bar.setValue(min(100, max(0, pct)))
                bar.setFormat(f"{pct}%")
            else:
                bar.setRange(0, 0)  # busy indicator
                bar.setFormat("…")
            self.table.setCellWidget(row, self.COL_PROGRESS, bar)

            status = msg or ("Running" if tot == 0 else f"{cur}/{tot}")
            self.table.setItem(row, self.COL_STATUS, QTableWidgetItem(status))

            if cancelable and worker is not None and hasattr(worker, "stop"):
                btn = QPushButton("Cancel")
                btn.setMinimumWidth(72)

                def _make_cancel(w=worker, jid=job_id) -> Callable[[], None]:
                    def _cancel() -> None:
                        try:
                            w.stop()
                            self.note_progress(jid, 0, 1, "Cancelling…")
                            logger.info("Cancel requested for job %s", jid)
                        except Exception as e:
                            logger.debug("Cancel failed for %s: %s", jid, e)

                    return _cancel

                handler = _make_cancel()
                self._cancel_handlers[job_id] = handler
                btn.clicked.connect(handler)
                self.table.setCellWidget(row, self.COL_ACTION, btn)
            else:
                placeholder = QLabel("—")
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setCellWidget(row, self.COL_ACTION, placeholder)

        count = len(jobs)
        if count:
            self.info_label.setText(f"{count} active job{'s' if count != 1 else ''}")
        else:
            self.info_label.setText("No active jobs")

    @staticmethod
    def collect_jobs(
        encoder_tab: Optional[Any],
        subtitle_tab: Optional[Any],
        metadata_tab: Optional[Any],
    ) -> List[Dict[str, Any]]:
        """Gather active workers from the three feature tabs."""
        jobs: List[Dict[str, Any]] = []

        if encoder_tab is not None:
            workers = getattr(encoder_tab, "active_workers", None) or {}
            for path, worker in list(workers.items()):
                jobs.append(
                    {
                        "id": str(path),
                        "kind": "Encode",
                        "name": Path(str(path)).name,
                        "worker": worker,
                        "cancelable": True,
                    }
                )

        if subtitle_tab is not None:
            workers = getattr(subtitle_tab, "active_workers", None) or {}
            for key, worker in list(workers.items()):
                label = str(key)
                if ":" in label:
                    kind_prefix, rest = label.split(":", 1)
                    kind = {
                        "search": "Subtitle search",
                        "generate": "Whisper",
                        "apply": "Subtitle apply",
                        "batch": "Subtitle batch",
                    }.get(kind_prefix, "Subtitle")
                    name = Path(rest).name if rest else label
                else:
                    kind = "Subtitle"
                    name = Path(label).name
                jobs.append(
                    {
                        "id": str(key),
                        "kind": kind,
                        "name": name,
                        "worker": worker,
                        "cancelable": hasattr(worker, "stop"),
                    }
                )

        if metadata_tab is not None:
            workers = getattr(metadata_tab, "active_workers", None) or {}
            for path, worker in list(workers.items()):
                jobs.append(
                    {
                        "id": str(path),
                        "kind": "Metadata",
                        "name": Path(str(path)).name,
                        "worker": worker,
                        "cancelable": True,
                    }
                )

        return jobs
