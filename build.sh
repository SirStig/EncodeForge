#!/bin/bash
# EncodeForge Nuitka Build Script for macOS/Linux
# Requires Python 3.10+ and Nuitka installed

echo "Building EncodeForge..."
echo

python3 build_nuitka.py

if [ $? -eq 0 ]; then
    echo
    echo "Build complete! Check the dist/ folder."
else
    echo
    echo "Build failed! Check the error messages above."
    exit 1
fi
