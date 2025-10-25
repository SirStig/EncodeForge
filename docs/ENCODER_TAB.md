# Encoder Tab Implementation

## Overview
The encoder tab provides a complete video encoding interface with:
- Drag-and-drop file management
- Queue-based batch processing
- Real-time progress tracking
- Comprehensive encoder settings
- Hardware acceleration support
- Beautiful macOS-inspired UI

## Architecture

### Components

#### EncoderTab (`app/widgets/encoder_tab.py`)
Main widget containing:
- **File Panel** (left): File list table with drag-drop support, toolbar buttons
- **Settings Panel** (right): Codec, quality, hardware acceleration, output settings
- **Queue Management**: Start/Pause/Stop controls with progress tracking

### Threading System (`utils/workers.py`)

#### Worker Classes
- **Worker**: Base QRunnable with signals for progress/result/error
- **EncoderWorker**: Specialized for video encoding tasks
- **SubtitleWorker**: Specialized for subtitle generation/download
- **RenamerWorker**: Specialized for file renaming operations

#### Signals
- `started`: Emitted when work begins
- `progress(current, total, message)`: Progress updates
- `result(data)`: Success result
- `error(exc_type, value, traceback)`: Error information
- `finished`: Work completed (success or failure)

### Integration with Main Window

The encoder tab connects to the main window's status bar:
- `encode_started`: Updates status label
- `encode_progress`: Updates progress label with percentage
- `encode_completed`: Shows completion status
- `encode_error`: Displays error messages

## Features

### File Management
- Add files via dialog or drag-drop
- Add entire folders recursively
- Remove selected files
- Clear all queued files
- Displays file size and status
- Shows output path when encoding

### Encoder Settings

#### Codec Settings
- Video Codec: H.264, H.265/HEVC, AV1, VP9, Copy
- Preset: ultrafast → veryslow (quality vs speed)

#### Quality Settings
- CRF slider (0-51, default 23)
- Audio codec: AAC, Opus, MP3, Copy
- Audio bitrate: 64-512 kbps

#### Hardware Acceleration
- NVENC (NVIDIA)
- AMF (AMD)
- QuickSync (Intel)
- VideoToolbox (macOS)

#### Output Settings
- Container format: MP4, MKV, WebM, AVI
- 2-pass encoding option
- Preserve metadata option

### Queue Processing
- Parallel processing via QThreadPool
- Progress bars for each file
- Status tracking: Queued → Encoding → Completed/Error
- Cooperative cancellation support
- Batch completion notification

## Styling

### macOS-Inspired Theme
- Dark background (#2d2d2d, #1e1e1e)
- Blue accent color (#0a84ff) for active elements
- Rounded corners (6-8px border-radius)
- Semi-transparent scrollbars
- Smooth hover transitions
- Modern typography (13px, weight 500/600)

### Components
- Buttons: Blue with hover/press states
- Tables: Alternating rows, selected highlighting
- Group boxes: Bordered with uppercase titles
- Combo boxes: Dark with blue hover
- Sliders: Blue handles with rounded groove
- Progress bars: Blue chunks on dark background
- Checkboxes: Blue when checked

## File Support

### Supported Video Formats
- MP4, MKV, AVI, MOV, WMV, FLV
- WebM, M4V, MPG, MPEG, 3GP

## Future Enhancements

### Planned Features
- [ ] Profile presets (Web, Archive, Mobile, etc.)
- [ ] Batch output folder selection
- [ ] Queue save/load
- [ ] Advanced filters (crop, scale, denoise)
- [ ] Two-pass progress tracking
- [ ] FFmpeg command preview
- [ ] Estimated time remaining
- [ ] GPU usage monitoring
- [ ] Queue reordering (drag to reorder)

### Integration Points
- Connect to actual FFmpeg backend (core.ffmpeg_core)
- Implement desktop notifications (async context)
- Add profile management (load/save encoder presets)
- Hardware acceleration detection
- FFmpeg capability detection

## Code Quality

### Best Practices
✅ Type hints throughout
✅ Comprehensive docstrings
✅ Proper signal/slot architecture
✅ Error handling with logging
✅ Separation of concerns
✅ Clean method organization
✅ Resource cleanup
✅ No circular dependencies

### Testing Considerations
- Mock FFmpeg for unit tests
- Test drag-drop with QMimeData
- Test worker signals/slots
- Test queue state transitions
- Test error handling paths
