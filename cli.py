#!/usr/bin/env python3
"""
EncodeForge CLI

v0.5.0 ships the desktop app only. Commands other than ``gui`` are placeholders
and exit with a notice; full CLI may return in a later release.
"""

import sys
import click
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app import __version__ as APP_VERSION

# Setup logging
try:
    from utils.logging_config import setup_logging
    setup_logging()
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=APP_VERSION)
def cli():
    """EncodeForge — desktop app (v0.5.0); CLI encode/subtitle/rename not implemented yet."""
    pass


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output directory')
@click.option('--codec', '-c', default='h264', help='Video codec (h264, h265, av1)')
@click.option('--preset', '-p', default='medium', help='Encoding preset')
@click.option('--use-nvenc', is_flag=True, help='Use NVIDIA NVENC hardware acceleration')
@click.option('--use-qsv', is_flag=True, help='Use Intel Quick Sync hardware acceleration')
@click.option('--crf', type=int, default=23, help='Quality (CRF) value (0-51, lower is better)')
def encode(input_path, output, codec, preset, use_nvenc, use_qsv, crf):
    """Encode video files with FFmpeg (not available in v0.5.0 — use the GUI)."""
    click.echo(
        click.style("The encode command is not implemented in v0.5.0.", fg="yellow", bold=True)
    )
    click.echo("Use the desktop application: python main.py   or   python cli.py gui")
    raise SystemExit(2)


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--language', '-l', default='en', help='Subtitle language code')
@click.option('--generate', is_flag=True, help='Generate subtitles using Whisper AI')
@click.option('--model', default='base', help='Whisper model (tiny, base, small, medium, large)')
@click.option('--provider', help='Subtitle provider (opensubtitles, addic7ed, etc.)')
def subtitle(input_path, language, generate, model, provider):
    """Download or generate subtitles (not available in v0.5.0 — use the GUI)."""
    click.echo(
        click.style("The subtitle command is not implemented in v0.5.0.", fg="yellow", bold=True)
    )
    click.echo("Use the desktop application: python main.py   or   python cli.py gui")
    raise SystemExit(2)


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--tmdb-key', help='TMDB API key')
@click.option('--tvdb-key', help='TVDB API key')
@click.option('--pattern', help='Custom naming pattern')
@click.option('--preview', is_flag=True, help='Preview changes without renaming')
@click.option('--type', type=click.Choice(['movie', 'tv', 'anime', 'auto']), default='auto')
def rename(input_path, tmdb_key, tvdb_key, pattern, preview, type):
    """Rename media files using metadata (not available in v0.5.0 — use the GUI)."""
    click.echo(
        click.style("The rename command is not implemented in v0.5.0.", fg="yellow", bold=True)
    )
    click.echo("Use the desktop application: python main.py   or   python cli.py gui")
    raise SystemExit(2)


@cli.command()
def gui():
    """Launch the PySide6 GUI application"""
    logger.info("Launching GUI")
    click.echo("Starting EncodeForge GUI...")
    
    # Import and run GUI
    from main import main
    main()


if __name__ == '__main__':
    cli()
