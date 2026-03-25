## Contributing to EncodeForge

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Getting Started

1. **Fork the repository** and clone your fork locally
2. **Set up your development environment**:
   - Install Python 3.10 or later
   - Install Git
   - FFmpeg will be auto-downloaded on first run (or install manually)

3. **Create a new branch** for your feature or fix:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Setup

### PySide6 Application Development
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run the GUI application
python main.py

# Run the CLI
python cli.py --help
```

### Building with Nuitka
```bash
# Build for your platform
python build_nuitka.py

# Or use platform-specific scripts
.\build.bat           # Windows
./build.sh            # macOS/Linux
```

## Code Style

### Python
- Follow PEP 8 style guidelines
- Use 4 spaces for indentation
- Add docstrings for functions and classes
- Use type hints where appropriate
- Format code with `black`
- Lint with `flake8`
- Type check with `mypy`

### PySide6/Qt
- Follow Qt naming conventions for UI elements
- Use signals/slots for communication
- Keep UI and business logic separated
- Document custom widgets thoroughly

## Making Changes

1. **Write clean, readable code** with appropriate comments
2. **Test your changes thoroughly** on your platform
3. **Update documentation** if you're changing functionality
4. **Follow the existing code structure** and patterns
5. **Keep commits focused** - one logical change per commit
6. **Add docstrings** for new functions and classes
7. **Add type hints** for function parameters and return values
8. **For UI changes**: Test on different screen resolutions and ensure responsiveness
9. **For backend changes**: Test with various file formats and codecs

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov=core --cov=utils

# Run specific test file
pytest tests/test_encoder.py -v
```

## Code Quality

Before submitting, ensure your code passes:

```bash
# Format code
black .

# Lint
flake8 app/ core/ utils/

# Type check
mypy app/ core/ utils/ --ignore-missing-imports
```

## Commit Messages

Write clear, descriptive commit messages:
```
Add feature: Brief description of what was added

More detailed explanation if needed. Explain why the change
was made, not just what was changed.

Fixes #123
```

## Submitting Changes

1. **Push your changes** to your fork
2. **Create a Pull Request** with a clear title and description
3. **Reference any related issues** in the PR description
4. **Be responsive** to feedback and questions
5. **Ensure CI passes** before requesting review

## Reporting Bugs

Use the bug report template when creating issues. Include:
- Clear description of the bug
- Steps to reproduce
- Expected vs actual behavior
- Environment details (OS, Python version, PySide6 version, etc.)
- Screenshots or logs if applicable
- Installation method (Nuitka binary, pip, from source)

## Feature Requests

Use the feature request template. Explain:
- What problem the feature solves
- How you envision it working
- Why it would be valuable
- Any UI mockups or designs (if applicable)

## Code Review Process

- All submissions require review before merging
- Reviewers may request changes or ask questions
- Be patient and respectful during the review process
- Address all feedback before the PR can be merged
- CI must pass for PR to be approved

## Testing Guidelines

Test your changes with:
- Various file formats (mp4, mkv, avi, mov, etc.)
- Different codecs (h264, h265, vp9, av1)
- Hardware acceleration (NVENC, AMF, Quick Sync, VideoToolbox)
- CPU encoding fallback
- Multiple platforms (Windows/macOS/Linux if possible)
- Edge cases (large files, special characters in filenames, etc.)
- UI responsiveness and thread safety
- Subtitle providers (OpenSubtitles, Whisper, etc.)
- Metadata providers (TMDB, TVDB, AniDB, etc.)
- Notification system
- Log file generation

## Project Structure

```
app/          # PySide6 UI components
core/         # Business logic
  providers/  # External service providers
  handlers/   # Operation handlers
utils/        # Utility functions
resources/    # Icons, styles, assets
```

## Questions?

Feel free to open an issue for questions or reach out to the maintainers in Discussions.

Thank you for contributing!

