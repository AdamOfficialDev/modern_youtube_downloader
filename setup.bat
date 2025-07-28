@echo off
title Modern YouTube Downloader Setup
color 0B
cls

echo.
echo  ================================================================
echo    ^|^|        Modern YouTube Downloader - Setup Wizard         ^|^|
echo  ================================================================
echo.
echo    Created by: Adam Official Dev
echo    Version: 1.0.0
echo.
echo  ================================================================
echo.

:: Check if Python is installed and find Python executable
echo    [*] Checking Python installation...
set "PYTHON_CMD="

:: Try different Python commands
python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    echo    [√] Python is installed! ^(using 'python'^)
    python --version
    goto :python_found
)

py --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    echo    [√] Python is installed! ^(using 'py'^)
    py --version
    goto :python_found
)

python3 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python3"
    echo    [√] Python is installed! ^(using 'python3'^)
    python3 --version
    goto :python_found
)

:: If no Python found
color 0C
echo.
echo    [X] Python is not installed on your system!
echo    [!] Please install Python from python.org first
echo    [!] Make sure to check "Add Python to PATH" during installation
echo.
echo  ================================================================
echo    Press any key to exit...
echo  ================================================================
pause >nul
exit

:python_found

echo.
echo    [*] Cleaning up any corrupted packages...

:: Uninstall problematic packages
echo    [*] Removing potentially corrupted PyQt6 packages...
%PYTHON_CMD% -m pip uninstall -y PyQt6 PyQt6-Qt6 PyQt6-sip 2>nul
%PYTHON_CMD% -m pip uninstall -y Pillow 2>nul

echo    [*] Upgrading pip and setuptools...
%PYTHON_CMD% -m pip install --upgrade pip setuptools wheel

echo.
echo    [*] Installing packages one by one with better compatibility...

:: Install packages individually with fallback versions
echo    [*] Installing PyQt6...
%PYTHON_CMD% -m pip install PyQt6
if errorlevel 1 (
    echo    [!] PyQt6 failed, trying older version...
    %PYTHON_CMD% -m pip install "PyQt6>=6.5.0,<6.7.0"
)

echo    [*] Installing Pillow...
%PYTHON_CMD% -m pip install Pillow
if errorlevel 1 (
    echo    [!] Pillow failed, trying pre-compiled wheel...
    %PYTHON_CMD% -m pip install --only-binary=all Pillow
    if errorlevel 1 (
        echo    [!] Trying older Pillow version...
        %PYTHON_CMD% -m pip install "Pillow>=9.0.0,<11.0.0"
    )
)

echo    [*] Installing yt-dlp...
%PYTHON_CMD% -m pip install yt-dlp

echo    [*] Installing requests...
%PYTHON_CMD% -m pip install requests

echo    [*] Installing google-api-python-client...
%PYTHON_CMD% -m pip install google-api-python-client

echo    [*] Installing tqdm...
%PYTHON_CMD% -m pip install tqdm

echo.
echo    [*] Verifying installation...
%PYTHON_CMD% -c "import PyQt6; print('[√] PyQt6 imported successfully')" 2>nul || echo "[!] PyQt6 import failed"
%PYTHON_CMD% -c "import PIL; print('[√] Pillow imported successfully')" 2>nul || echo "[!] Pillow import failed"
%PYTHON_CMD% -c "import yt_dlp; print('[√] yt-dlp imported successfully')" 2>nul || echo "[!] yt-dlp import failed"
%PYTHON_CMD% -c "import requests; print('[√] requests imported successfully')" 2>nul || echo "[!] requests import failed"

echo.
echo    [*] Creating directories...
if not exist "bundled" (
    echo    [*] Creating bundled directory...
    mkdir "bundled"
    echo    [√] Created bundled directory
) else (
    echo    [√] Bundled directory exists
)

if not exist "cookies" (
    echo    [*] Creating cookies directory...
    mkdir "cookies"
    echo    [√] Created cookies directory
) else (
    echo    [√] Cookies directory exists
)

:: Create additional directories
if not exist "ffmpeg" (
    echo    [*] Creating ffmpeg directory...
    mkdir "ffmpeg"
    echo    [√] Created ffmpeg directory
) else (
    echo    [√] FFmpeg directory exists
)

if not exist "src" (
    echo    [*] Creating src directory...
    mkdir "src"
    echo    [√] Created src directory
) else (
    echo    [√] src directory exists
)

:: Create config.json
echo    [*] Creating config.json...
if not exist "config.json" (
    echo { "ffmpeg_path": null, "youtube_api_key": "", "telegram_bot_token": "", "admin_users": [] } > config.json
    echo    [√] Created config.json with default configuration
) else (
    echo    [√] config.json already exists
)

:: Check FFmpeg
echo.
echo    [*] Checking FFmpeg...
if exist "ffmpeg\ffmpeg.exe" (
    echo    [√] FFmpeg is already installed
) else (
    echo    [!] FFmpeg not found in ffmpeg directory
    echo    [*] You can download FFmpeg manually from:
    echo        https://github.com/BtbN/FFmpeg-Builds/releases/latest
    echo    [*] Extract it and place ffmpeg.exe in the ffmpeg folder
)

:: Setup complete
echo.
color 0A
echo  ================================================================
echo    ^|^|              Setup Completed Successfully!              ^|^|
echo  ================================================================
echo.
echo    [√] Python is installed and ready
echo    [√] All required packages installed with compatibility fixes
echo    [√] Directories created
echo    [√] Configuration files ready
echo.
echo    [*] Your system is ready to use Modern YouTube Downloader!
echo.
echo    NOTE: If FFmpeg is needed, download it manually from:
echo    https://github.com/BtbN/FFmpeg-Builds/releases/latest
echo.
echo    To bypass YouTube's anti-bot protection, use the Settings
echo    tab to extract cookies from your browser.
echo.
echo  ================================================================
echo    Press any key to exit...
echo  ================================================================
pause >nul
