@echo off
title Modern Multi-Platform Video Downloader
color 0B
cls

echo.
echo  ========================================================
echo    ^|^|  Modern Multi-Platform Video Downloader - Main  ^|^|
echo  ========================================================
echo.
echo    Created by: Adam Official Dev
echo    Version: 1.0.0
echo.
echo  ========================================================
echo.
echo    [*] Detecting Python installation...
set "PYTHON_CMD="

:: Try different Python commands
python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    echo    [√] Using 'python' command
    goto :python_found
)

py --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    echo    [√] Using 'py' command
    goto :python_found
)

python3 --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python3"
    echo    [√] Using 'python3' command
    goto :python_found
)

:: If no Python found
color 0C
echo.
echo    [X] Python is not installed or not in PATH!
echo    [!] Please run setup.bat first or install Python
echo.
echo  ========================================================
echo    Press any key to exit...
echo  ========================================================
pause >nul
exit

:python_found
echo    [*] Starting application...
echo.
timeout /t 2 >nul

%PYTHON_CMD% main.py

echo.
echo  ========================================================
echo    Press any key to exit...
echo  ========================================================
pause >nul
