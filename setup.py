"""
EncodeForge Setup Script
For packaging and distribution
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
if requirements_path.exists():
    with open(requirements_path, encoding="utf-8") as f:
        requirements = [line.strip() for line in f 
                       if line.strip() and not line.startswith("#")]
else:
    requirements = []

setup(
    name="encodeforge",
    version="0.5.0",
    author="SirStig",
    description="FFmpeg GUI for batch video encoding, AI subtitles, and media file renaming",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SirStig/EncodeForge",
    project_urls={
        "Bug Reports": "https://github.com/SirStig/EncodeForge/issues",
        "Source": "https://github.com/SirStig/EncodeForge",
        "Documentation": "https://github.com/SirStig/EncodeForge/wiki",
    },
    packages=find_packages(exclude=["tests*", "docs*", "EncodeForge*"]),
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "encodeforge=main:main",
            "encodeforge-cli=cli:cli",
        ],
        "gui_scripts": [
            "encodeforge-gui=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["resources/**/*"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Video :: Conversion",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Environment :: X11 Applications :: Qt",
    ],
    keywords="ffmpeg video encoding subtitles pyside6 qt gui",
    license="MIT",
)
