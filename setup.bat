@echo off
title Modern YouTube Downloader Setup
mode con: cols=70 lines=30
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

:: Animasi Loading
echo    [*] Initializing setup...
ping localhost -n 2 >nul
echo    [*] Checking system requirements...
ping localhost -n 2 >nul

:: Check if Python is installed
echo    [*] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo.
    echo    [X] Python is not installed on your system!
    echo    [!] Please install Python from python.org first
    echo.
    echo  ================================================================
    echo    Press any key to exit...
    echo  ================================================================
    pause >nul
    exit
) else (
    echo    [√] Python is installed!
)
ping localhost -n 2 >nul

:: Create necessary directories if they don't exist
echo.
echo    [*] Checking directories...
if not exist "bundled" (
    echo    [*] Creating bundled directory...
    mkdir "bundled"
    echo    [√] Created bundled directory
) else (
    echo    [√] Bundled directory exists
)

:: Create cookies directory for YouTube authentication
if not exist "cookies" (
    echo    [*] Creating cookies directory...
    mkdir "cookies"
    echo    [√] Created cookies directory
) else (
    echo    [√] Cookies directory exists
)

:: Install required packages
echo.
echo    [*] Installing required packages...
echo.
pip install -r requirements.txt
if errorlevel 1 (
    color 0C
    echo.
    echo    [X] Failed to install required packages!
    echo    [!] Please check your internet connection and try again
    echo.
    echo  ================================================================
    echo    Press any key to exit...
    echo  ================================================================
    pause >nul
    exit
) else (
    echo.
    echo    [√] All packages installed successfully!
)
ping localhost -n 2 >nul

:: Check and Download FFmpeg
echo.
echo    [*] Checking FFmpeg...
if exist "bundled\ffmpeg.zip" (
    echo    [√] FFmpeg already exists in bundled/ffmpeg.zip
) else (
    echo    [*] Downloading FFmpeg...
    echo.
    python download_ffmpeg.py
    if errorlevel 1 (
        echo.
        echo    [X] Failed to download FFmpeg!
        echo    [!] Please download manually from:
        echo        https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip
        echo    [!] Rename it to ffmpeg.zip and place it in the bundled folder
        echo.
        echo  ================================================================
        echo    Press any key to exit...
        echo  ================================================================
        pause >nul
        exit
    ) else (
        echo.
        echo    [√] FFmpeg downloaded successfully
    )
)

:: Check if ffmpeg directory exists
if not exist "ffmpeg" (
    echo    [*] Creating ffmpeg directory...
    mkdir "ffmpeg"
    echo    [√] Created ffmpeg directory
) else (
    echo    [√] FFmpeg directory exists
)

:: Create src directory if it doesn't exist
if not exist "src" (
    echo    [*] Creating src directory...
    mkdir "src"
    echo    [√] Created src directory
) else (
    echo    [√] src directory exists
)

:: Create config.json with proper structure if it doesn't exist
if not exist "config.json" (
    echo    [*] Creating config.json with default structure...
    echo { "ffmpeg_path": null, "youtube_api_key": "", "telegram_bot_token": "", "admin_users": [] } > config.json
    echo    [√] Created config.json with unified configuration
) else (
    echo    [*] Updating config.json structure...
    :: Check if config.json has the required fields
    python -c "import json; f=open('config.json', 'r'); data=json.load(f); f.close(); data.setdefault('youtube_api_key', ''); data.setdefault('telegram_bot_token', ''); data.setdefault('admin_users', []); f=open('config.json', 'w'); json.dump(data, f, indent=4); f.close(); print('[√] Updated config.json with unified configuration')"
)

:: Setup complete
color 0A
echo.
echo  ================================================================
echo    ^|^|              Setup completed successfully!              ^|^|
echo  ================================================================
echo.
echo    [√] Python is installed
echo    [√] All required packages are installed
echo    [√] FFmpeg is downloaded and configured
echo    [√] Configuration files are created
echo    [√] YouTube authentication support is configured
echo    [√] Your system is ready to use Modern YouTube Downloader!
echo.
echo    NOTE: To bypass YouTube's anti-bot protection, go to the Settings
echo    tab and use the YouTube Authentication section to extract cookies
echo    from your browser.
echo.
echo  ================================================================
echo    Press any key to exit...
echo  ================================================================
pause >nul
