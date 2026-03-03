# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file untuk Modern YouTube Downloader
# Jalankan dengan: pyinstaller modern_downloader.spec

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Sertakan semua file source
        ('src/*.py', 'src'),
        # Sertakan config dan settings jika ada
        ('config.json', '.') if __import__('os').path.exists('config.json') else ('', ''),
        ('settings.json', '.') if __import__('os').path.exists('settings.json') else ('', ''),
        # Sertakan cookies folder jika ada
        ('cookies', 'cookies') if __import__('os').path.exists('cookies') else ('', ''),
        # Sertakan bot_users.json jika ada
        ('bot_users.json', '.') if __import__('os').path.exists('bot_users.json') else ('', ''),
    ],
    hiddenimports=[
        # PyQt6
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.sip',
        # yt-dlp
        'yt_dlp',
        'yt_dlp.extractor',
        'yt_dlp.postprocessor',
        'yt_dlp.downloader',
        # Google API
        'googleapiclient',
        'googleapiclient.discovery',
        'googleapiclient.errors',
        'google.auth',
        'google.auth.transport',
        # Image processing
        'PIL',
        'PIL.Image',
        # Network
        'requests',
        'urllib3',
        # Telegram (opsional)
        'telegram',
        'telegram.ext',
        # Lainnya
        'json',
        'threading',
        'zipfile',
        'shutil',
        'subprocess',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude hal yang tidak diperlukan untuk mengurangi ukuran
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'sklearn',
        'tensorflow',
        'torch',
        'cv2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Filter datas yang kosong
a.datas = [(src, dst, typ) for src, dst, typ in a.datas if src]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ModernVideoDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,           # Kompres dengan UPX jika tersedia
    console=False,      # False = tidak ada jendela console (GUI only)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='icon.ico',  # Uncomment dan ganti dengan path icon Anda
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ModernVideoDownloader',
)
