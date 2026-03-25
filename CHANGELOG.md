# Changelog

All notable changes to EncodeForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.1] - 2025-10-24

### Highlights

- Major JavaFX UI refresh with reorganized logs, settings views, and modernized tables for a smoother workflow ([`eb3c43f`](https://github.com/SirStig/EncodeForge/commit/eb3c43f))
- Swing-based splash screen that surfaces startup progress and initialization errors before JavaFX loads ([`8ba1fca`](https://github.com/SirStig/EncodeForge/commit/8ba1fca))

### Fixes

- Adjusted Maven configuration to resolve the macOS launch hang affecting JavaFX initialization ([`dc70838`](https://github.com/SirStig/EncodeForge/commit/dc70838))

### CI/CD

- Updated macOS artifact workflow so the packaged JAR carries the 0.4.1 version label ([`82a168e`](https://github.com/SirStig/EncodeForge/commit/82a168e))

### Release Links

- **Full Changelog**: [0.4.0...0.4.1](https://github.com/SirStig/EncodeForge/compare/0.4.0...0.4.1)

---

## [0.4.0] - 2025-10-23

### Major Release - Audio Normalization & Performance Improvements

This release consolidates features developed across branches v0.3.2 and v0.3.3 into a stable production release. Version 0.4.0 focuses on audio normalization capabilities, GPU-accelerated AI subtitle generation, UI/UX polish, and significant performance optimizations.

**Note:** Versions 0.3.2 and 0.3.3 were development branches and were never officially released. All their features are included in this 0.4.0 release.

---

### Added

#### Audio Normalization

- **Audio Normalization Support** - New flag for FFmpeg/encoding to normalize audio levels ([`998f7ae`](https://github.com/SirStig/EncodeForge/commit/998f7ae))
  - Ensures consistent audio volume across media files
  - Integrated into encoding workflow
  - Configurable through settings

#### GPU-Accelerated AI Subtitle Generation

- **Intelligent PyTorch Installation** - Smart GPU detection and PyTorch installation for Whisper AI ([`fa8d13a`](https://github.com/SirStig/EncodeForge/commit/fa8d13a))
  - Automatically detects available GPU (NVIDIA CUDA, AMD ROCm, Apple Silicon)
  - Downloads appropriate PyTorch version with GPU support
  - Falls back to CPU version if no GPU detected
  - **10x-20x speed improvement** for AI subtitle generation on supported hardware

- **Enhanced Whisper Processing** - Device detection and resource optimization ([`e34463c`](https://github.com/SirStig/EncodeForge/commit/e34463c))
  - macOS Apple Silicon GPU support
  - NVIDIA CUDA GPU support
  - AMD GPU support
  - Intelligent device selection based on available hardware

### UI/UX Improvements

- **Enhanced Visual Depth** - Improved styling throughout the application ([`1687422`](https://github.com/SirStig/EncodeForge/commit/1687422))
  - Added visual depth to UI components
  - Implemented minimum sizes for most components
  - Better component scaling and layout
  - Improved dark theme consistency

### Performance Optimizations

- **Lazy Initialization** - Refactored core modules for better startup performance ([`9de93c6`](https://github.com/SirStig/EncodeForge/commit/9de93c6), [`ed3800e`](https://github.com/SirStig/EncodeForge/commit/ed3800e))
  - Lazy loading for Whisper manager
  - Lazy loading for core Python modules
  - Reduced initial memory footprint
  - Faster application startup time
  - Enhanced process handling in Python API

### Bug Fixes

- **Whisper AI Setup** - Fixed issues with Whisper AI initialization ([`eed524c`](https://github.com/SirStig/EncodeForge/commit/eed524c))
  - Resolved setup dialog issues
  - Improved error handling during Whisper installation

### Technical Improvements

- **Version Bump to 0.4.0** - Updated all version references across the application ([`c2ba20a`](https://github.com/SirStig/EncodeForge/commit/c2ba20a))
  - Java source files
  - Build configurations (Maven POM, Manifest)
  - Documentation (README, BUILD.md)
  - CI/CD workflows
  - Issue templates

---

### Development History (Unreleased Versions)

#### v0.3.3 (Development Branch - Not Released)

- Branch: [`v0.3.3`](https://github.com/SirStig/EncodeForge/tree/v0.3.3)
- Focus: Audio normalization features and UI polish
- Commits merged into 0.4.0

#### v0.3.2 (Development Branch - Not Released)

- Branch: [`v0.3.2`](https://github.com/SirStig/EncodeForge/tree/v0.3.2)
- Focus: GPU-accelerated Whisper AI and performance optimizations
- Commits merged into 0.4.0

---

### What's Next (Roadmap)

Future releases will focus on:

- **Plugin Support** (v1.0) - Extensible architecture for custom processing plugins and themes
- **Jellyfin Integration** - Direct integration with Jellyfin media servers
- **Plex Integration** - Direct integration with Plex media servers
- **Preview Window** - Visual preview of applied subtitles
- **Full Metadata Grabber** - Grab all missing metadata info for files, including artwork
- **Audio Syncing** - Intelligent audio/subtitle synchronization fixes

---

### Statistics

- **8 commits** since v0.3.1
- **Development period**: ~1 day (consolidated from multiple development branches)
- **Lines of code changed**: Significant refactoring across Python and Java codebases

---

### Links

- **Release Tag**: [v0.4.0](https://github.com/SirStig/EncodeForge/releases/tag/v0.4.0)
- **Full Changelog**: [v0.3.1...v0.4.0](https://github.com/SirStig/EncodeForge/compare/v0.3.1...v0.4.0)
- **Issues**: [GitHub Issues](https://github.com/SirStig/EncodeForge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/SirStig/EncodeForge/discussions)

---

## [0.3.1] - 2024

### Initial Public Release

First stable public release of EncodeForge (formerly FFmpeg Batch Transcoder).

#### Features

- **Video Encoding**
  - Hardware acceleration (NVENC, AMF, Quick Sync, VideoToolbox)
  - Batch processing with queue management
  - Real-time progress tracking
  - Smart codec selection

- **Subtitle Management**
  - AI-powered subtitle generation (OpenAI Whisper)
  - 9 subtitle provider integrations
  - Multi-language support
  - Subtitle download and application

- **Smart File Renaming**
  - 10 metadata providers (TMDB, TVDB, OMDB, Trakt, Fanart.tv, etc.)
  - 4 free providers (AniDB, Kitsu, Jikan/MAL, TVmaze)
  - Custom naming patterns
  - Preview mode

- **Modern Interface**
  - Dark theme
  - JavaFX-based desktop application
  - Cross-platform support (Windows, macOS, Linux)
  - Comprehensive logging

---

## Version Naming Convention

- **Major.Minor.Patch** (Semantic Versioning)
- **Development branches** (v0.3.2, v0.3.3) are consolidated into production releases
- **Stable releases** receive version tags (v0.3.1, v0.4.0, etc.)

---

[Star us on GitHub](https://github.com/SirStig/EncodeForge) • [Report a Bug](https://github.com/SirStig/EncodeForge/issues) • [Request a Feature](https://github.com/SirStig/EncodeForge/discussions)
