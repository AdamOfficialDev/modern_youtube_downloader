@echo off
title Modern YouTube Downloader - Build to EXE
color 0B
cls

echo.
echo  ================================================================
echo    ^|^|     Modern YouTube Downloader - Build EXE Script       ^|^|
echo  ================================================================
echo.
echo    Menggunakan PyInstaller untuk membuat file .exe
echo.

:: ===============================================================
:: LANGKAH 1: Deteksi Python
:: ===============================================================
echo    [*] Mendeteksi instalasi Python...
set "PYTHON_CMD="

python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :python_found
)

py --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    goto :python_found
)

echo    [X] Python tidak ditemukan! Install Python terlebih dahulu.
pause >nul
exit

:python_found
echo    [OK] Python ditemukan!

:: ===============================================================
:: LANGKAH 2: Install PyInstaller
:: ===============================================================
echo.
echo    [*] Menginstall/Update PyInstaller...
%PYTHON_CMD% -m pip install pyinstaller --upgrade -q
if errorlevel 1 (
    echo    [X] Gagal menginstall PyInstaller!
    pause >nul
    exit
)
echo    [OK] PyInstaller siap!

:: ===============================================================
:: LANGKAH 3: Install semua dependensi
:: ===============================================================
echo.
echo    [*] Memastikan semua dependensi terinstall...
%PYTHON_CMD% -m pip install -r Requirements.txt -q
echo    [OK] Dependensi siap!

:: ===============================================================
:: LANGKAH 4: Bersihkan build sebelumnya
:: ===============================================================
echo.
echo    [*] Membersihkan build sebelumnya...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
echo    [OK] Direktori bersih!

:: ===============================================================
:: LANGKAH 5: Build dengan PyInstaller
:: ===============================================================
echo.
echo    [*] Memulai proses build (ini mungkin memakan waktu 3-10 menit)...
echo    [*] Harap tunggu...
echo.

:: Gunakan spec file jika ada, kalau tidak gunakan perintah langsung
if exist "modern_downloader.spec" (
    echo    [*] Menggunakan file .spec...
    %PYTHON_CMD% -m PyInstaller modern_downloader.spec --clean
) else (
    echo    [*] Build langsung dari main.py...
    %PYTHON_CMD% -m PyInstaller ^
        --name "ModernVideoDownloader" ^
        --windowed ^
        --onedir ^
        --clean ^
        --noconfirm ^
        --hidden-import "PyQt6" ^
        --hidden-import "PyQt6.QtWidgets" ^
        --hidden-import "PyQt6.QtCore" ^
        --hidden-import "PyQt6.QtGui" ^
        --hidden-import "yt_dlp" ^
        --hidden-import "yt_dlp.extractor" ^
        --hidden-import "googleapiclient" ^
        --hidden-import "googleapiclient.discovery" ^
        --hidden-import "PIL" ^
        --hidden-import "PIL.Image" ^
        --hidden-import "requests" ^
        --hidden-import "telegram" ^
        --hidden-import "telegram.ext" ^
        --add-data "src;src" ^
        --exclude-module "tkinter" ^
        --exclude-module "matplotlib" ^
        main.py
)

:: ===============================================================
:: LANGKAH 6: Cek hasil build
:: ===============================================================
echo.
if exist "dist\ModernVideoDownloader\ModernVideoDownloader.exe" (
    echo  ================================================================
    echo    [OK] BUILD BERHASIL!
    echo  ================================================================
    echo.
    echo    File EXE tersedia di:
    echo    dist\ModernVideoDownloader\ModernVideoDownloader.exe
    echo.
    echo    [*] Menyalin file konfigurasi ke folder dist...
    
    :: Salin file konfigurasi penting
    if exist "config.json" copy "config.json" "dist\ModernVideoDownloader\" >nul
    if exist "settings.json" copy "settings.json" "dist\ModernVideoDownloader\" >nul
    if exist "bot_users.json" copy "bot_users.json" "dist\ModernVideoDownloader\" >nul
    
    :: Buat folder yang diperlukan
    if not exist "dist\ModernVideoDownloader\cookies" mkdir "dist\ModernVideoDownloader\cookies"
    if not exist "dist\ModernVideoDownloader\ffmpeg" mkdir "dist\ModernVideoDownloader\ffmpeg"
    if not exist "dist\ModernVideoDownloader\downloads" mkdir "dist\ModernVideoDownloader\downloads"
    
    :: Salin cookies jika ada
    if exist "cookies" xcopy /s /q "cookies" "dist\ModernVideoDownloader\cookies\" >nul
    
    :: Salin ffmpeg jika ada
    if exist "ffmpeg\ffmpeg.exe" copy "ffmpeg\ffmpeg.exe" "dist\ModernVideoDownloader\ffmpeg\" >nul
    if exist "ffmpeg\ffprobe.exe" copy "ffmpeg\ffprobe.exe" "dist\ModernVideoDownloader\ffmpeg\" >nul
    
    echo    [OK] File konfigurasi disalin!
    echo.
    echo    Folder dist\ModernVideoDownloader siap didistribusikan!
    
    :: Tanya apakah ingin membuat ZIP
    echo.
    set /p MAKE_ZIP="Buat file ZIP untuk distribusi? (y/n): "
    if /i "%MAKE_ZIP%"=="y" (
        echo    [*] Membuat file ZIP...
        %PYTHON_CMD% -c "import shutil; shutil.make_archive('ModernVideoDownloader_v1.0', 'zip', 'dist', 'ModernVideoDownloader')"
        echo    [OK] ZIP berhasil dibuat: ModernVideoDownloader_v1.0.zip
    )
    
) else (
    echo  ================================================================
    echo    [X] BUILD GAGAL!
    echo  ================================================================
    echo.
    echo    Kemungkinan penyebab:
    echo    1. Error dalam kode Python
    echo    2. Dependensi tidak lengkap
    echo    3. Import yang tidak ditemukan
    echo.
    echo    Cek output error di atas untuk detail lebih lanjut.
    echo    Coba jalankan: python main.py untuk mengecek error.
)

echo.
echo  ================================================================
echo    Tekan sembarang tombol untuk keluar...
echo  ================================================================
pause >nul
