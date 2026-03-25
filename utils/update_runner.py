"""
Background GitHub release check (QThreadPool + QRunnable).
"""

import logging

from PySide6.QtCore import QObject, QRunnable, Signal

from utils.update_checker import UpdateCheckOutcome, fetch_latest_release, is_newer

logger = logging.getLogger(__name__)


class UpdateCheckSignals(QObject):
    finished = Signal(object)


class UpdateCheckRunnable(QRunnable):
    def __init__(self, current_version: str):
        super().__init__()
        self._current = current_version
        self.signals = UpdateCheckSignals()

    def run(self) -> None:
        try:
            rel = fetch_latest_release()
            if rel is None:
                self.signals.finished.emit(UpdateCheckOutcome())
                return
            newer = is_newer(rel.version, self._current)
            self.signals.finished.emit(
                UpdateCheckOutcome(release=rel, is_newer=newer)
            )
        except Exception as e:
            logger.debug("Update check error", exc_info=True)
            self.signals.finished.emit(UpdateCheckOutcome(error=str(e)))
