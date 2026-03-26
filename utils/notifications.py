"""
EncodeForge Notification System
Desktop notifications using desktop-notifier
"""

import asyncio
import logging
from typing import Optional
from desktop_notifier import DesktopNotifier, Icon, Urgency, Button, ReplyField
from pathlib import Path

logger = logging.getLogger(__name__)


def _encodeforge_notification_icon() -> Icon | None:
    """Real filesystem path only — Nuitka breaks desktop_notifier's DEFAULT_ICON (importlib.resources → as_uri)."""
    path = Path(__file__).resolve().parent.parent / "resources" / "icons" / "app-icon.png"
    return Icon(path=path) if path.is_file() else None


class NotificationManager:
    """Manages desktop notifications for EncodeForge"""
    
    def __init__(self, app_name: str = "EncodeForge"):
        self.notifier = DesktopNotifier(
            app_name=app_name,
            notification_limit=10,
            app_icon=_encodeforge_notification_icon(),
        )
    
    async def notify_success(self, title: str, message: str):
        """Show success notification"""
        try:
            await self.notifier.send(
                title=title,
                message=message,
                urgency=Urgency.Normal
            )
            logger.info(f"Notification sent: {title}")
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
    
    async def notify_error(self, title: str, message: str):
        """Show error notification"""
        try:
            await self.notifier.send(
                title=title,
                message=message,
                urgency=Urgency.Critical
            )
            logger.error(f"Error notification sent: {title}")
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
    
    async def notify_warning(self, title: str, message: str):
        """Show warning notification"""
        try:
            await self.notifier.send(
                title=title,
                message=message,
                urgency=Urgency.Normal
            )
            logger.warning(f"Warning notification sent: {title}")
        except Exception as e:
            logger.error(f"Failed to send warning notification: {e}")
    
    async def notify_progress(self, title: str, message: str, progress: int):
        """Show progress notification"""
        try:
            # Note: Not all platforms support progress in notifications
            await self.notifier.send(
                title=title,
                message=f"{message} ({progress}%)",
                urgency=Urgency.Low
            )
        except Exception as e:
            logger.error(f"Failed to send progress notification: {e}")
    
    async def notify_encode_complete(self, filename: str, duration: float):
        """Notify when encoding completes"""
        await self.notify_success(
            title="Encoding Complete",
            message=f"{filename} finished in {duration:.1f}s"
        )
    
    async def notify_subtitle_downloaded(self, filename: str, language: str):
        """Notify when subtitles are downloaded"""
        await self.notify_success(
            title="Subtitles Downloaded",
            message=f"{language} subtitles for {filename}"
        )
    
    async def notify_whisper_complete(self, filename: str, duration: float):
        """Notify when Whisper generation completes"""
        await self.notify_success(
            title="AI Subtitles Generated",
            message=f"{filename} completed in {duration:.1f}s"
        )
    
    async def notify_batch_complete(self, count: int, total_time: float):
        """Notify when batch processing completes"""
        await self.notify_success(
            title="Batch Processing Complete",
            message=f"Processed {count} files in {total_time:.1f}s"
        )
    
    async def notify_error_occurred(self, filename: str, error: str):
        """Notify when an error occurs"""
        await self.notify_error(
            title="Processing Error",
            message=f"{filename}: {error}"
        )


# Singleton instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get the global notification manager instance"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
