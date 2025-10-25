#!/usr/bin/env python3
"""
EncodeForge CLI
Command-line interface for batch video processing
Keeping CLI support while removing WebUI
"""

import sys
import click
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core import ffmpeg_manager, subtitle_manager, metadata_grabber

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.5.0")
def cli():
    """EncodeForge - FFmpeg GUI and CLI for video encoding, subtitles, and renaming"""
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
    """Encode video files with FFmpeg"""
    logger.info(f"Encoding {input_path} with {codec} codec")
    click.echo(f"Starting encoding: {input_path}")
    click.echo(f"Codec: {codec}, Preset: {preset}, CRF: {crf}")
    
    if use_nvenc:
        click.echo("Using NVIDIA NVENC hardware acceleration")
    elif use_qsv:
        click.echo("Using Intel Quick Sync hardware acceleration")
    
    # TODO: Integrate with existing core.ffmpeg_manager
    click.echo("Encoding complete!")


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--language', '-l', default='en', help='Subtitle language code')
@click.option('--generate', is_flag=True, help='Generate subtitles using Whisper AI')
@click.option('--model', default='base', help='Whisper model (tiny, base, small, medium, large)')
@click.option('--provider', help='Subtitle provider (opensubtitles, addic7ed, etc.)')
def subtitle(input_path, language, generate, model, provider):
    """Download or generate subtitles for video files"""
    logger.info(f"Processing subtitles for {input_path}")
    click.echo(f"Processing: {input_path}")
    
    if generate:
        click.echo(f"Generating subtitles with Whisper ({model} model)")
        # TODO: Integrate with core.subtitle_manager.whisper_manager
    else:
        click.echo(f"Searching for {language} subtitles using {provider or 'all providers'}")
        # TODO: Integrate with core.subtitle_manager
    
    click.echo("Subtitle processing complete!")


@cli.command()
@click.argument('input_path', type=click.Path(exists=True))
@click.option('--tmdb-key', help='TMDB API key')
@click.option('--tvdb-key', help='TVDB API key')
@click.option('--pattern', help='Custom naming pattern')
@click.option('--preview', is_flag=True, help='Preview changes without renaming')
@click.option('--type', type=click.Choice(['movie', 'tv', 'anime', 'auto']), default='auto')
def rename(input_path, tmdb_key, tvdb_key, pattern, preview, type):
    """Rename media files using metadata providers"""
    logger.info(f"Renaming files in {input_path}")
    click.echo(f"Processing: {input_path}")
    click.echo(f"Content type: {type}")
    
    if preview:
        click.echo("Preview mode - no files will be renamed")
    
    # TODO: Integrate with core.metadata_grabber
    click.echo("Renaming complete!")


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
