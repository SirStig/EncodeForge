<div align="center">

# EncodeForge

<img src="resources/icons/app-icon.png" alt="EncodeForge Logo" width="128" height="128">

### Professional FFmpeg GUI for Video Encoding, AI Subtitles & Media Management

*A powerful cross-platform application built with Python & PySide6*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-blue)](https://github.com/SirStig/EncodeForge/releases)
[![GitHub release](https://img.shields.io/github/v/release/SirStig/EncodeForge)](https://github.com/SirStig/EncodeForge/releases/latest)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

[Features](#-features) • [Installation](#-installation) • [Quick Start](#-quick-start) • [Documentation](#-documentation) • [Contributing](#-contributing)

</div>

---

## 🎯 About The Project

## 🎯 About The Project

**EncodeForge** is a free, open-source **FFmpeg GUI** built with Python and PySide6. It's designed to make professional video encoding, subtitle generation, and media file management accessible to everyone - no command-line experience required.

### Why EncodeForge?

- 🎬 **Batch Processing** - Convert entire video libraries while you sleep
- ⚡ **Hardware Accelerated** - Leverage your GPU for lightning-fast encoding
- 🤖 **AI-Powered** - Generate high-quality subtitles in 90+ languages locally
- 🎨 **Modern UI** - Clean, intuitive PySide6 interface with dark theme
- 🌍 **Cross-Platform** - Works on Windows, macOS, and Linux
- 📦 **Self-Contained** - Compiled with Nuitka for easy distribution

### Built With

- [PySide6](https://github.com/PySide/pyside-setup) - Qt for Python framework
- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) - Modern UI components
- [FFmpeg](https://ffmpeg.org/) - Industry-standard video processing
- [OpenAI Whisper](https://github.com/openai/whisper) - State-of-the-art speech recognition
- [Nuitka](https://github.com/Nuitka/Nuitka) - Python compiler for distribution

---

## ✨ Features

### 🎞️ Video Encoding

- **Hardware Acceleration** - NVIDIA NVENC, AMD AMF, Intel Quick Sync, Apple VideoToolbox
- **Smart Codec Selection** - Automatic best-codec detection for your hardware
- **Batch Processing** - Queue multiple files with real-time progress tracking
- **Stream Preservation** - Copy streams without re-encoding when possible
- **Audio Normalization** - Consistent volume levels across all media

### 📝 Subtitle Generation

- **AI-Powered Subtitles** - Generate subtitles using OpenAI Whisper (90+ languages)
- **GPU Acceleration** - 10x-20x faster with NVIDIA, AMD, or Apple Silicon
- **9 Subtitle Providers** - Download from multiple sources including anime-specific providers
- **Multi-Language** - Handle multiple audio tracks and subtitle languages
- **Format Support** - SRT, ASS, SSA, VTT, and more

### 🏷️ Smart File Renaming

- **10 Metadata Providers** - TMDB, TVDB, OMDB, Trakt, Fanart.tv, and 5 free providers
- **Auto-Detection** - Intelligent movie, TV show, and anime recognition
- **Custom Patterns** - Define naming conventions with powerful template variables
- **Preview Mode** - See changes before applying
- **Bulk Operations** - Rename entire libraries in seconds

### 🎨 Modern Interface

- **Dark Theme** - Easy on the eyes during long processing sessions
- **Tabbed Interface** - Encoder, Subtitles, and Renamer in one window
- **Real-Time Progress** - Detailed progress bars and logs
- **Queue Management** - Add, remove, and reorder jobs easily
- **Responsive Design** - Scales beautifully across screen sizes

---

## 📦 Installation

### Pre-Built Binaries (Recommended)

Download the latest release for your platform from the [Releases page](https://github.com/SirStig/EncodeForge/releases):

- **Windows**: `.exe` installer or portable
- **macOS**: `.dmg` package or `.app` bundle
- **Linux**: `.AppImage` (universal) or distribution-specific packages

### From Source

#### Requirements

- Python 3.10 or higher
- pip (Python package manager)
- Git (optional, for cloning)

#### Steps

```bash
# Clone the repository
git clone https://github.com/SirStig/EncodeForge.git
cd EncodeForge

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Command Line Interface

```bash
# Install CLI globally
pip install encodeforge

# Or run directly
python cli.py --help
```

---

## 🚀 Quick Start

### GUI Application

1. **Launch** EncodeForge
2. **Select Mode** - Choose Encoder, Subtitles, or Renamer tab
3. **Add Files** - Drag and drop or use the file browser
4. **Configure** - Set your encoding options, subtitle preferences, or renaming patterns
5. **Process** - Click Start and watch real-time progress

### CLI Usage

```bash
# Encode videos with hardware acceleration
encodeforge-cli encode /path/to/videos --use-nvenc --codec h265

# Generate AI subtitles
encodeforge-cli subtitle /path/to/videos --generate --model medium

# Rename media files
encodeforge-cli rename /path/to/media --tmdb-key YOUR_KEY --preview

# Launch GUI from CLI
encodeforge-cli gui
```

---

## 🔧 Configuration

### API Keys (Optional)

While EncodeForge works great without API keys, adding them unlocks additional metadata providers:

| Service | Purpose | Free Tier | Get Key |
|---------|---------|-----------|---------|
| TMDB | Movies & TV metadata | Yes | [Get API Key](https://www.themoviedb.org/settings/api) |
| TVDB | TV show metadata | Yes | [Get API Key](https://thetvdb.com/dashboard/account/apikey) |
| OMDB | Alternative movie data | Yes | [Get API Key](http://www.omdbapi.com/apikey.aspx) |
| Trakt | Tracking & stats | Yes | [Get API Key](https://trakt.tv/oauth/applications) |
| OpenSubtitles | Subtitle downloads | 5/day free | [Get API Key](https://www.opensubtitles.com/en/consumers) |

**Free Providers (Always Available):**
- AniDB, Kitsu, Jikan/MAL, TVmaze - No API key required!

### Hardware Acceleration

EncodeForge automatically detects available hardware encoders:

- **NVIDIA** - GTX 600 series and newer (NVENC)
- **AMD** - Recent Radeon cards on Windows (AMF)
- **Intel** - 6th generation processors and newer (Quick Sync)
- **Apple** - All modern Macs (VideoToolbox)

---

## 📸 Screenshots

<div align="center">


</div>

---

## 🗺️ Roadmap

- ✅ Complete Java to PySide6 migration
- ✅ Modern Qt-based UI with Fluent Design
- ✅ Nuitka compilation for all platforms
- ✅ CLI interface preservation
- ⏳ Enhanced concurrent task processing
- ⏳ Plugin system architecture
- ⏳ Jellyfin & Plex integration
- ⏳ Advanced subtitle synchronization
- ⏳ Metadata artwork grabber
- ⏳ Preview window for subtitles

See the [open issues](https://github.com/SirStig/EncodeForge/issues) for a full list of proposed features and known issues.

---

##  Contributing

Contributions make the open source community an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**!

### How to Contribute

1. **Fork** the Project
2. **Create** your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** your Changes (`git commit -m 'Add some AmazingFeature'`)
4. **Push** to the Branch (`git push origin feature/AmazingFeature`)
5. **Open** a Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Format code
black .

# Type checking
mypy .
```

---

##  System Requirements

| Platform | Minimum | Recommended |
|----------|---------|-------------|
| **Windows** | Windows 10 | Windows 11 |
| **macOS** | macOS 11.0 | macOS 13.0+ |
| **Linux** | Ubuntu 20.04 | Ubuntu 22.04+ |
| **RAM** | 4 GB | 8 GB (16 GB for AI) |
| **Storage** | 500 MB | 2 GB |
| **Python** | 3.10+ | 3.11+ |

---

##  License

Distributed under the MIT License. See `LICENSE` for more information.

---

##  Acknowledgments

- [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets) - Beautiful Fluent Design widgets
- [curl-cffi](https://github.com/lexiforest/curl_cffi) - HTTP client with browser impersonation
- [desktop-notifier](https://github.com/samschott/desktop-notifier) - Cross-platform notifications
- [Nuitka](https://github.com/Nuitka/Nuitka) - The Python compiler
- [FFmpeg](https://ffmpeg.org/) - Multimedia processing framework
- [OpenAI Whisper](https://github.com/openai/whisper) - Speech recognition model

---

##  Support

- **Bug Reports**: [GitHub Issues](https://github.com/SirStig/EncodeForge/issues/new?template=bug_report.yml)
- **Feature Requests**: [GitHub Issues](https://github.com/SirStig/EncodeForge/issues/new?template=feature_request.yml)
- **Discussions**: [GitHub Discussions](https://github.com/SirStig/EncodeForge/discussions)
- **Documentation**: [Wiki](https://github.com/SirStig/EncodeForge/wiki)

---

<div align="center">

**Star If you find EncodeForge useful, please consider giving it a star!**

Made by [SirStig](https://github.com/SirStig)

</div>
