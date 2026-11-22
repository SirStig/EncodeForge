"""
Subtitle Providers Package
Modular subtitle provider implementations and subtitle-related utilities
"""

from .addic7ed_provider import Addic7edProvider
from .base_provider import BaseSubtitleProvider
from .jimaku_provider import JimakuProvider
from .opensubtitles_manager import OpenSubtitlesManager
from .podnapisi_provider import PodnapisiProvider
from .provider_status import (
    PROVIDER_CATALOG,
    QUARANTINED_PROVIDERS,
    is_provider_quarantined,
    ui_provider_entries,
)
from .subdivx_provider import SubDivXProvider
from .subdl_provider import SubDLProvider
from .subf2m_provider import Subf2mProvider
from .whisper_manager import WhisperManager
from .yify_provider import YifyProvider

__all__ = [
    'BaseSubtitleProvider',
    'YifyProvider',
    'Addic7edProvider',
    'SubDLProvider',
    'Subf2mProvider',
    'JimakuProvider',
    'PodnapisiProvider',
    'SubDivXProvider',
    'OpenSubtitlesManager',
    'WhisperManager',
    'PROVIDER_CATALOG',
    'QUARANTINED_PROVIDERS',
    'is_provider_quarantined',
    'ui_provider_entries',
]

