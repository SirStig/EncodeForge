<div align="center">

# EncodeForge

<img src="resources/icons/app-icon.png" alt="EncodeForge Logo" width="128" height="128">

### Video Encoding, AI Subtitles & Smart Media Renaming — all in one place

*A free, open-source desktop app for Windows, macOS, and Linux*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)](https://sirstig.github.io/EncodeForge/downloads.html)
[![GitHub release](https://img.shields.io/github/v/release/SirStig/EncodeForge)](https://github.com/SirStig/EncodeForge/releases/latest)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

[Features](#features) • [Installation](#installation) • [Quick Start](#quick-start) • [Configuration](#configuration) • [Contributing](#contributing)

</div>

---

## About

**EncodeForge** is a free, open-source FFmpeg GUI that brings professional video encoding, AI subtitle generation, and smart media file renaming together in a single, clean desktop application — no command-line experience required.

It pairs a modern desktop interface with GPU-accelerated encoding via NVENC/AMF/Quick Sync/VideoToolbox, and local AI subtitles powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — fast transcription in 90+ languages that runs entirely on your machine.

### Why EncodeForge?

- **Batch Processing** — Convert entire video libraries while you sleep
- **Hardware Accelerated** — Leverage your GPU for fast encoding via NVENC, AMF, Quick Sync, or VideoToolbox
- **AI Subtitles** — Local transcription via faster-whisper with GPU acceleration; no cloud required
- **Smart Renaming** — Pull metadata from 10+ sources and rename your library in seconds
- **Modern UI** — Clean Fluent Design interface with dark & light theme support
- **Cross-Platform** — Windows, macOS, and Linux

### Built With

- [PySide6](https://doc.qt.io/qtforpython/) — Qt 6 for Python
- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) — Fluent Design UI components
- [FFmpeg](https://ffmpeg.org/) — Industry-standard multimedia processing
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Fast local AI subtitle generation
- [Nuitka](https://nuitka.net/) — Python compiler for standalone distribution

---

## Features

### Video Encoding

- **Hardware Acceleration** — NVIDIA NVENC, AMD AMF, Intel Quick Sync, Apple VideoToolbox
- **Smart Codec Detection** — Automatically picks the best encoder available on your system
- **Batch Processing** — Queue multiple files with real-time progress tracking
- **Stream Preservation** — Copy streams without re-encoding when possible
- **Audio Normalization** — Consistent volume levels across all output files

### Subtitle Generation

- **Local AI Transcription** — faster-whisper with GPU acceleration; runs completely offline
- **90+ Languages** — Full multilingual transcription support
- **8 Download Providers** — OpenSubtitles, Addic7ed, SubDL, Subf2m, YIFY, Podnapisi, SubDivX, Jimaku
- **Anime Support** — Jimaku provider for English/Japanese anime subtitles
- **Format Support** — SRT, ASS, SSA, VTT, and more

### Smart File Renaming

- **10+ Metadata Providers** — TMDB, TVDB, OMDB, Trakt, Fanart.tv, AniDB, Kitsu, Jikan/MAL, TVmaze
- **Auto-Detection** — Recognizes movies, TV shows, and anime automatically
- **Custom Patterns** — Define your own naming conventions with template variables
- **Preview Mode** — Review all changes before applying them
- **Bulk Operations** — Rename entire libraries in seconds

### Modern Interface

- **Fluent Design** — Clean, modern tabbed layout
- **Dark & Light Themes** — Easy on the eyes during long sessions
- **Real-Time Progress** — Detailed per-file and overall progress tracking
- **Queue Management** — Add, reorder, and remove jobs at any time
- **Comprehensive Logging** — Exportable logs for troubleshooting

---

## Installation

### Pre-Built Binaries (Recommended)

**Download links and version history live on the [EncodeForge website](https://sirstig.github.io/EncodeForge/)** so they stay accurate without editing this README for every release.

- **[Downloads](https://sirstig.github.io/EncodeForge/downloads.html)** — versions are listed **newest first**; the latest is marked **(Latest)**. **0.5.0 Alpha 2** ([release](https://github.com/SirStig/EncodeForge/releases/tag/v0.5.0-alpha-2)) includes **Windows** (.zip), **macOS Apple Silicon** (.zip), **Linux** (.deb, .rpm, AppImage). Older **0.4.x** builds are listed too. Anything not yet on GitHub shows as “coming soon.” The page pulls live data from [GitHub Releases](https://github.com/SirStig/EncodeForge/releases) when available.
- **[Changelog](https://sirstig.github.io/EncodeForge/changelog.html)** — web version of `CHANGELOG.md`. Add a hash to jump to a version section when it exists, e.g. [`changelog.html#release-0-5-0-alpha-2`](https://sirstig.github.io/EncodeForge/changelog.html#release-0-5-0-alpha-2), [`#release-0-4-1`](https://sirstig.github.io/EncodeForge/changelog.html#release-0-4-1).

> FFmpeg is required but not bundled. EncodeForge will prompt you to set it up on first launch.

### From Source

**Requirements:** Python 3.10+, pip, Git

```bash
git clone https://github.com/SirStig/EncodeForge.git
cd EncodeForge

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
python main.py
```

### Build a Standalone Executable

```bash
pip install -r requirements.txt
python build_nuitka.py
```

---

## Quick Start

1. Launch EncodeForge (`python main.py` or run the downloaded binary)
2. On first launch, the app will help you locate or download FFmpeg
3. Pick a tab — **Encoder**, **Subtitles**, or **Renamer**
4. Add files via drag-and-drop or the file browser
5. Configure your settings and click **Start**

That's it. Most options have sensible defaults, so you can dive straight in.

---

## Configuration

### API Keys (Optional)

EncodeForge works out of the box without any API keys. Adding them just unlocks a few extra metadata providers:

| Service | Purpose | Free Tier |
|---------|---------|-----------|
| [TMDB](https://www.themoviedb.org/settings/api) | Movies & TV metadata | Yes |
| [TVDB](https://thetvdb.com/dashboard/account/apikey) | TV show metadata | Yes |
| [OMDB](http://www.omdbapi.com/apikey.aspx) | Alternative movie data | Yes (1,000/day) |
| [Trakt](https://trakt.tv/oauth/applications) | Tracking & metadata | Yes |
| [OpenSubtitles](https://www.opensubtitles.com/en/consumers) | Subtitle downloads | Yes (5/day) |

**Always free, no key needed:** AniDB, Kitsu, Jikan/MAL, TVmaze

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

| | Minimum | Recommended |
|--|---------|-------------|
| **Windows** | Windows 10 | Windows 11 |
| **macOS** | macOS 11.0 | macOS 13.0+ |
| **Linux** | Ubuntu 20.04 | Ubuntu 22.04+ |
| **RAM** | 4 GB | 8 GB (16 GB for AI subtitles) |
| **Storage** | 500 MB | 2 GB |
| **Python** | 3.10+ | 3.11+ |

---

## Roadmap

- ✅ Modern Fluent Design desktop UI
- ✅ GPU-accelerated faster-whisper for local AI subtitles
- ✅ Shared core backend (GUI & CLI)
- ✅ Nuitka compilation for all platforms
- ⏳ Full CLI support (`encode`, `subtitle`, `rename` commands)
- ⏳ Enhanced concurrent task processing
- ⏳ Plugin system architecture
- ⏳ Jellyfin & Plex direct integration
- ⏳ Advanced subtitle synchronization
- ⏳ Metadata artwork grabber
- ⏳ Subtitle preview window

---

## Contributing

Contributions are welcome! Whether it's a bug fix, a new feature, or improved docs — all help is appreciated.

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes: `git commit -m 'Add my feature'`
4. Push: `git push origin feature/my-feature`
5. Open a Pull Request

### Dev Setup

```bash
pip install -r requirements-dev.txt

pytest          # Run tests
black .         # Format code
flake8 .        # Lint
mypy .          # Type check
isort .         # Sort imports
```

---

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

---

## Acknowledgments

- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) — Fluent Design widget library
- [FFmpeg](https://ffmpeg.org/) — Multimedia processing framework
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — Fast local Whisper inference
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

If EncodeForge saves you time, consider giving it a ⭐ on GitHub — it really helps.

</div>
