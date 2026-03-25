# Changelog

All notable changes to EncodeForge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.5.0] — 2026-03-24

### Highlights

**Complete rewrite from JavaFX to PySide6.** EncodeForge has been rebuilt from the ground up using Python and PySide6 with Fluent Design components. The legacy JavaFX/Java codebase has been retired entirely. The GUI and CLI now share a single core (`EncodeForgeCore`) with no logic duplication.

---

### Added

#### Architecture

- **`EncodeForgeCore`** — New single entry point for all GUI and CLI operations. Lazily initializes handlers on first use via a thread lock, keeping startup fast even with heavy dependencies like Whisper.
- **Handler layer** — `ConversionHandler`, `FileHandler`, `SubtitleHandler`, `RenamingHandler` contain all business logic; no UI code in core.
- **Provider layer** — Abstract-base + concrete-implementation pattern for both metadata (8+ providers) and subtitle (9+ providers) subsystems.
- **`SettingsManager`** — JSON-backed nested dataclass settings (`EncoderSettings`, `SubtitleSettings`, `RenamerSettings`, `UISettings`).
- **`DownloadManager`** — Resumable downloads with SHA256 hash verification and progress callbacks.
- **`ThemeManager`** — Glassmorphism CSS theming with dark/light mode support.
- **`WorkerPool`** — QThread-based worker pool with signal/slot progress integration.

#### GUI (PySide6 + PyQt-Fluent-Widgets)

- Tabbed `MainWindow` — Encoder, Subtitles, Renamer, Processes, and Settings tabs.
- Real-time per-file and overall progress bars.
- Drag-and-drop file addition across all tabs.
- Comprehensive log viewer with export support.
- `FFmpegSetupDialog` — Detects, downloads, and configures FFmpeg on first launch.
- `SettingsDialog` — Full settings UI with API key management and hardware acceleration toggle.

#### CLI

- Full CLI built with Click, sharing `EncodeForgeCore` with the GUI.
- Commands: `encode`, `subtitle`, `rename`, `gui`.
- `encodeforge`, `encodeforge-cli`, `encodeforge-gui` entry points via `setup.py`.

#### Metadata Providers

- TMDB, TVDB, OMDB, Trakt, Fanart.tv, AniDB, Kitsu, Jikan/MAL, TVmaze
- `MetadataGrabber` aggregates providers and returns best match with fallback chain.

#### Subtitle Providers

- OpenSubtitles, Addic7ed, Jimaku, SubDL, Subscene, BSPlayer, Yify, Podnapisi, Opensubtitles.org
- `WhisperManager` for local AI subtitle generation with GPU device selection (CUDA, ROCm, MPS, CPU).
- `SubtitleManager` tries providers in configured order; returns first successful result.

#### Build

- Nuitka build system (`build_nuitka.py`) produces self-contained executables for Windows and Linux.
- GitHub Actions CI for automated cross-platform builds.

---

### Removed

- **JavaFX / Java codebase** — Fully retired. The previous JavaFX implementation is no longer maintained or distributed.
- Maven build system — replaced by Python packaging (`setup.py`) and Nuitka.
- JAR packaging — replaced by Nuitka-compiled native executables.

---

### Changed

- Application rebranded from a Java desktop app to a Python/PySide6 desktop app.
- All version references updated to `0.5.0`.
- `setup.py` classifiers updated to reflect PySide6/Qt6 environment.

---

### Release Links

- **Tag**: [v0.5.0](https://github.com/SirStig/EncodeForge/releases/tag/v0.5.0)
- **Full Changelog**: [v0.4.1...v0.5.0](https://github.com/SirStig/EncodeForge/compare/v0.4.1...v0.5.0)

---

## [0.4.1] — 2025-10-24

> **Note:** This was the final JavaFX release. JavaFX has since been replaced by PySide6 in v0.5.0.

### Highlights

- Major UI refresh: reorganized logs, settings views, and modernized tables.
- Swing-based splash screen to surface startup progress and initialization errors before the main window loads.

### Fixes

- Resolved macOS launch hang affecting JavaFX initialization.

### CI/CD

- Updated macOS artifact workflow so the packaged JAR carried the 0.4.1 version label.

### Release Links

- **Full Changelog**: [0.4.0...0.4.1](https://github.com/SirStig/EncodeForge/compare/0.4.0...0.4.1)

---

## [0.4.0] — 2025-10-23

> **Note:** Final major JavaFX release. Consolidated from development branches v0.3.2 and v0.3.3.

### Added

#### Audio Normalization

- New FFmpeg flag to normalize audio levels during encoding.
- Configurable via settings; integrated into the encoding workflow.

#### GPU-Accelerated AI Subtitle Generation

- Intelligent PyTorch installation: auto-detects NVIDIA CUDA, AMD ROCm, or Apple Silicon and downloads the appropriate PyTorch build.
- Falls back to CPU if no GPU is detected.
- **10–20x speed improvement** for Whisper AI subtitle generation on supported hardware.

### Changed

- **Enhanced visual depth** — improved dark theme consistency and component minimum sizes.
- **Lazy initialization** — Whisper manager and core Python modules deferred to first use; faster startup, lower idle memory.

### Fixes

- Resolved Whisper AI setup dialog issues and improved error handling during installation.

### Release Links

- **Full Changelog**: [v0.3.1...v0.4.0](https://github.com/SirStig/EncodeForge/compare/v0.3.1...v0.4.0)

---

## [0.3.1] — 2024

### Initial Public Release

First stable public release of EncodeForge (formerly FFmpeg Batch Transcoder). Built on JavaFX.

#### Features

- Hardware-accelerated video encoding — NVENC, AMF, Quick Sync, VideoToolbox
- Batch processing with queue management and real-time progress
- AI subtitle generation via OpenAI Whisper
- 9 subtitle provider integrations
- Smart file renaming with 10 metadata providers (TMDB, TVDB, OMDB, Trakt, AniDB, Kitsu, Jikan/MAL, TVmaze, Fanart.tv)
- Custom naming patterns with preview mode
- Dark-themed JavaFX desktop application for Windows, macOS, and Linux

---

[GitHub Releases](https://github.com/SirStig/EncodeForge/releases) · [Report a Bug](https://github.com/SirStig/EncodeForge/issues) · [Request a Feature](https://github.com/SirStig/EncodeForge/discussions)
