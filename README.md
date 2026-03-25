<div align="center">

# EncodeForge

<img src="resources/icons/app-icon.png" alt="EncodeForge Logo" width="128" height="128">

### Professional FFmpeg GUI for Video Encoding, AI Subtitles &amp; Media Renaming

*A cross-platform desktop application built with Python &amp; PySide6*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)](https://github.com/SirStig/EncodeForge/releases)
[![GitHub release](https://img.shields.io/github/v/release/SirStig/EncodeForge)](https://github.com/SirStig/EncodeForge/releases/latest)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

[Features](#features) • [Installation](#installation) • [Quick Start](#quick-start) • [Configuration](#configuration) • [Contributing](#contributing)

</div>

---

## About

**EncodeForge** is a free, open-source FFmpeg GUI built with Python and PySide6. It brings professional video encoding, AI subtitle generation, and media file management into a single, clean desktop application — no command-line experience required.

**v0.5.0-alpha-1** is the in-development PySide6 rewrite: modern Fluent-style UI, improved performance, and a unified settings layer for the **desktop app**. It is **not** on GitHub Releases yet. **v0.4.1** remains the latest published binary (JavaFX; deprecated). Command-line and web interfaces are planned for a later release.

**AI subtitles in v0.5.0** use **[faster-whisper](https://github.com/SYSTRAN/faster-whisper)** (Whisper models via **CTranslate2**) instead of the OpenAI Whisper + PyTorch path from the JavaFX era. Expect **much faster** transcription, **lower RAM use**, and the same GPU backends (CUDA, ROCm, Apple Silicon, CPU) — a clear upgrade over **v0.4.x**.

### Why EncodeForge?

- **Batch Processing** — Convert entire video libraries while you sleep
- **Hardware Accelerated** — Leverage your GPU for lightning-fast encoding via NVENC, AMF, Quick Sync, or VideoToolbox
- **AI-Powered** — **v0.5.0:** faster-whisper (CTranslate2) for local subtitles in 90+ languages — far faster than the v0.4.x Whisper stack
- **Modern UI** — Clean PySide6 interface with Fluent Design and dark/light theme support
- **Cross-Platform** — Windows, macOS, and Linux
- **Self-Contained builds** — Nuitka targets bundled Python dependencies; FFmpeg is still required (Whisper models download in-app)
- **CLI** — Not implemented in v0.5.0-alpha-1; use `python main.py` or `python cli.py gui`

### Built With

- [PySide6](https://doc.qt.io/qtforpython/) — Qt 6 for Python
- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) — Modern Fluent Design UI components
- [FFmpeg](https://ffmpeg.org/) — Industry-standard multimedia processing
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Fast Whisper inference (CTranslate2); used for AI subtitles in **v0.5.0+**
- [OpenAI Whisper](https://github.com/openai/whisper) — Model architecture and weights (recognition quality)
- [Nuitka](https://nuitka.net/) — Python compiler for standalone distribution

---

## Features

### Video Encoding

- **Hardware Acceleration** — NVIDIA NVENC, AMD AMF, Intel Quick Sync, Apple VideoToolbox
- **Smart Codec Detection** — Automatic best-codec selection based on available hardware
- **Batch Processing** — Queue multiple files with real-time progress tracking
- **Stream Preservation** — Copy streams without re-encoding when possible
- **Audio Normalization** — Consistent volume levels across all output files

### Subtitle Generation

- **AI-Powered (v0.5.0+)** — **faster-whisper** with GPU acceleration; substantially faster and lighter than the OpenAI Whisper + PyTorch pipeline in **v0.4.x**
- **90+ Languages** — Full multilingual transcription support
- **8 Download Providers** — OpenSubtitles.com (API), Addic7ed, SubDL (API), Subf2m, YIFY, Podnapisi, SubDivX (Spanish), Jimaku (anime)
- **Anime Providers** — Jimaku for anime subtitles (English/Japanese)
- **Format Support** — SRT, ASS, SSA, VTT, and more

### Smart File Renaming

- **10+ Metadata Providers** — TMDB, TVDB, OMDB, Trakt, Fanart.tv, AniDB, Kitsu, Jikan/MAL, TVmaze
- **Auto-Detection** — Intelligent movie, TV show, and anime recognition
- **Custom Patterns** — Define naming conventions with powerful template variables
- **Preview Mode** — Review all changes before applying
- **Bulk Operations** — Rename entire libraries in seconds

### Modern Interface

- **PySide6 + Fluent Design** — Clean, modern tabbed interface
- **Dark &amp; Light Themes** — Easy on the eyes during long sessions
- **Real-Time Progress** — Detailed per-file and overall progress tracking
- **Queue Management** — Add, reorder, and remove jobs easily
- **Comprehensive Logging** — Exportable logs for debugging

---

## Installation

### Pre-Built Binaries (Recommended)

Download the latest release from the [Releases page](https://github.com/SirStig/EncodeForge/releases):

| Platform | Format |
|----------|--------|
| **Windows** | `.exe` installer |
| **Linux** | `.deb` (Debian/Ubuntu) or `.AppImage` |
| **macOS** | Build from source (see below) |

### From Source

**Requirements:** Python 3.10+, pip, Git

```bash
# Clone
git clone https://github.com/SirStig/EncodeForge.git
cd EncodeForge

# Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Launch GUI
python main.py
```

### Build Standalone Executable

```bash
pip install -r requirements.txt
python build_nuitka.py
```

---

## Quick Start

### GUI

1. Launch EncodeForge (`python main.py` or run the installer)
2. On first launch, the app will prompt to locate or download FFmpeg
3. Select a tab — **Encoder**, **Subtitles**, or **Renamer**
4. Add files via drag-and-drop or the file browser
5. Configure settings and click **Start**

### CLI (v0.5.0-alpha-1)

Only the GUI launcher is supported:

```bash
python cli.py gui
```

Commands `encode`, `subtitle`, and `rename` print a notice and exit until a future release. Use the desktop app for all workflows.

---

## Configuration

### API Keys (Optional)

EncodeForge works without API keys, but adding them unlocks additional metadata providers:

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| [TMDB](https://www.themoviedb.org/settings/api) | Movies &amp; TV metadata | Yes |
| [TVDB](https://thetvdb.com/dashboard/account/apikey) | TV show metadata | Yes |
| [OMDB](http://www.omdbapi.com/apikey.aspx) | Alternative movie data | Yes (1,000/day) |
| [Trakt](https://trakt.tv/oauth/applications) | Tracking &amp; metadata | Yes |
| [OpenSubtitles](https://www.opensubtitles.com/en/consumers) | Subtitle downloads | Yes (5/day) |

**Always free, no key required:** AniDB, Kitsu, Jikan/MAL, TVmaze

### Hardware Acceleration

EncodeForge auto-detects available GPU encoders on startup:

| GPU | Encoder | Minimum |
|-----|---------|---------|
| NVIDIA | NVENC | GTX 600 series+ |
| AMD | AMF | Recent Radeon (Windows) |
| Intel | Quick Sync | 6th gen Core+ |
| Apple | VideoToolbox | All modern Macs |

---

## System Requirements

| Platform | Minimum | Recommended |
|----------|---------|-------------|
| **Windows** | Windows 10 | Windows 11 |
| **macOS** | macOS 11.0 | macOS 13.0+ |
| **Linux** | Ubuntu 20.04 | Ubuntu 22.04+ |
| **RAM** | 4 GB | 8 GB (16 GB for AI subtitles) |
| **Storage** | 500 MB | 2 GB |
| **Python** | 3.10+ | 3.11+ |

---

## Roadmap

- ✅ Complete PySide6 migration (was JavaFX)
- ✅ Modern Fluent Design UI
- ✅ Shared `EncodeForgeCore` backend for the GUI (CLI planned later)
- ✅ Nuitka compilation for all platforms
- ✅ GPU-accelerated **faster-whisper** (v0.5.0+; much faster than v0.4.x)
- ⏳ Enhanced concurrent task processing
- ⏳ Plugin system architecture
- ⏳ Jellyfin &amp; Plex direct integration
- ⏳ Advanced subtitle synchronization
- ⏳ Metadata artwork grabber
- ⏳ Subtitle preview window

---

## Contributing

Contributions are welcome and greatly appreciated.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

### Development Setup

```bash
pip install -r requirements-dev.txt

pytest                # Run tests
black .               # Format code
flake8 .              # Lint
mypy .                # Type check
isort .               # Sort imports
```

---

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

---

## Acknowledgments

- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) — Fluent Design widget library
- [FFmpeg](https://ffmpeg.org/) — Multimedia processing framework
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Fast Whisper inference (v0.5.0+)
- [OpenAI Whisper](https://github.com/openai/whisper) — Model architecture and weights
- [Nuitka](https://nuitka.net/) — Python compiler
- [curl-cffi](https://github.com/lexiforest/curl_cffi) — HTTP client with browser fingerprinting
- [desktop-notifier](https://github.com/samschott/desktop-notifier) — Cross-platform desktop notifications

---

## Support

| Channel | Link |
|---------|------|
| Bug Reports | [GitHub Issues](https://github.com/SirStig/EncodeForge/issues/new?template=bug_report.yml) |
| Feature Requests | [GitHub Issues](https://github.com/SirStig/EncodeForge/issues/new?template=feature_request.yml) |
| Discussions | [GitHub Discussions](https://github.com/SirStig/EncodeForge/discussions) |

---

<div align="center">

Built by [Joshua Kac](https://github.com/SirStig)

If EncodeForge is useful to you, consider giving it a ⭐ on GitHub.

</div>
