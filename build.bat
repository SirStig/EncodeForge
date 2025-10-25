@echo off
REM EncodeForge Nuitka Build Script for Windows
REM Requires Python 3.10+ and Nuitka installed

echo Building EncodeForge for Windows...
echo.

python build_nuitka.py

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build complete! Check the dist\ folder.
    pause
) else (
    echo.
    echo Build failed! Check the error messages above.
    pause
    exit /b %ERRORLEVEL%
)
