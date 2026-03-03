# 📦 Panduan Lengkap: Membuat File EXE dari Modern YouTube Downloader

## 🎯 Metode yang Direkomendasikan: PyInstaller

PyInstaller adalah pilihan terbaik untuk proyek PyQt6 Anda karena paling stabil dan kompatibel.

---

## ⚡ Cara Cepat (5 Menit)

### Langkah 1: Salin file ke folder proyek
Salin `build_exe.bat` dan `modern_downloader.spec` ke **folder yang sama** dengan `main.py` Anda.

### Langkah 2: Jalankan build script
Double-click `build_exe.bat` dan tunggu prosesnya selesai.

### Langkah 3: Ambil hasilnya
File EXE ada di: `dist\ModernVideoDownloader\ModernVideoDownloader.exe`

---

## 📋 Langkah-Langkah Manual (Jika Script Gagal)

### Install PyInstaller
```cmd
pip install pyinstaller
```

### Build dengan satu perintah
```cmd
pyinstaller --name "ModernVideoDownloader" ^
    --windowed ^
    --onedir ^
    --clean ^
    --hidden-import "PyQt6" ^
    --hidden-import "yt_dlp" ^
    --hidden-import "yt_dlp.extractor" ^
    --hidden-import "googleapiclient.discovery" ^
    --hidden-import "PIL" ^
    --hidden-import "telegram" ^
    --hidden-import "telegram.ext" ^
    --add-data "src;src" ^
    main.py
```

---

## 📁 Struktur Folder Setelah Build

```
dist/
└── ModernVideoDownloader/          ← Folder ini yang didistribusikan
    ├── ModernVideoDownloader.exe   ← File utama (double-click untuk buka)
    ├── config.json                 ← Konfigurasi aplikasi
    ├── settings.json               ← Pengaturan tema
    ├── _internal/                  ← Library Python (jangan dihapus!)
    ├── cookies/                    ← Folder cookies YouTube
    ├── ffmpeg/                     ← FFmpeg binary
    └── downloads/                  ← Folder download default
```

> ⚠️ **Penting:** Seluruh folder `ModernVideoDownloader` harus disalin bersama,
> bukan hanya file .exe-nya saja!

---

## 🔧 Opsi Build: --onefile vs --onedir

### `--onedir` (DIREKOMENDASIKAN untuk proyek ini)
- ✅ Startup lebih cepat
- ✅ Lebih mudah di-debug
- ✅ Lebih stabil dengan PyQt6
- ❌ Distribusi berupa folder (bukan 1 file)

### `--onefile` (1 file, tapi ada trade-off)
- ✅ Satu file saja yang dibagikan
- ❌ Startup lambat (ekstrak dulu ke temp)
- ❌ Kadang error dengan PyQt6
- ❌ Antivirus sering flag sebagai suspicious

Untuk `--onefile`, gunakan perintah:
```cmd
pyinstaller --name "ModernVideoDownloader" --windowed --onefile main.py
```

---

## 🖼️ Menambahkan Icon (.ico)

### 1. Konversi gambar ke .ico
- Gunakan: https://convertio.co/png-ico/
- Atau: https://www.icoconverter.com/
- Ukuran rekomendasi: 256x256 px

### 2. Tambahkan ke perintah build
```cmd
pyinstaller --icon="icon.ico" --name "ModernVideoDownloader" --windowed main.py
```

### 3. Atau edit file .spec
Uncomment baris ini di `modern_downloader.spec`:
```python
# icon='icon.ico',
```
Menjadi:
```python
icon='icon.ico',
```

---

## 🐛 Troubleshooting Masalah Umum

### ❌ Error: "ModuleNotFoundError: No module named 'xxx'"

**Solusi:** Tambahkan hidden import
```cmd
pyinstaller --hidden-import "nama_modul" main.py
```

Atau tambahkan ke file .spec di bagian `hiddenimports`:
```python
hiddenimports=['nama_modul', 'modul_lain'],
```

---

### ❌ Error: "FileNotFoundError" saat aplikasi berjalan

File eksternal (config.json, dll) tidak ikut terbundle.

**Solusi:** Ubah cara baca file di kode Python.

Tambahkan fungsi ini di `main.py` (sebelum class `ModernVideoDownloader`):
```python
import sys
import os

def get_base_path():
    """Mendapatkan base path yang benar saat jadi EXE maupun saat development."""
    if getattr(sys, 'frozen', False):
        # Saat jalan sebagai EXE
        return os.path.dirname(sys.executable)
    else:
        # Saat development
        return os.path.dirname(os.path.abspath(__file__))

BASE_PATH = get_base_path()
```

Kemudian ganti semua path absolut:
```python
# SEBELUM (bisa error di EXE):
config_path = 'config.json'

# SESUDAH (aman di EXE):
config_path = os.path.join(BASE_PATH, 'config.json')
```

---

### ❌ Aplikasi langsung close tanpa pesan error

Ubah `--windowed` menjadi `--console` sementara untuk debug:
```cmd
pyinstaller --console --name "ModernVideoDownloader" main.py
```
Ini akan menampilkan error di console window.

---

### ❌ Antivirus mendeteksi sebagai virus (False Positive)

Ini normal untuk file EXE buatan PyInstaller. Solusi:
1. Tambahkan ke whitelist antivirus Anda
2. Gunakan Code Signing Certificate (berbayar)
3. Upload ke VirusTotal.com untuk verifikasi

---

### ❌ EXE sangat besar (>100MB)

**Solusi:** Gunakan virtual environment bersih
```cmd
python -m venv venv_build
venv_build\Scripts\activate
pip install PyQt6 yt-dlp Pillow requests google-api-python-client python-telegram-bot tqdm
pip install pyinstaller
pyinstaller modern_downloader.spec
```

---

## 🚀 Alternatif Lain: cx_Freeze

Jika PyInstaller bermasalah, coba cx_Freeze:

```cmd
pip install cx_Freeze
```

Buat file `setup_cx.py`:
```python
from cx_Freeze import setup, Executable

build_exe_options = {
    "packages": ["PyQt6", "yt_dlp", "PIL", "requests", "googleapiclient"],
    "excludes": ["tkinter"],
    "include_files": ["src/", "config.json", "settings.json"],
}

setup(
    name="Modern Video Downloader",
    version="1.0",
    description="Modern Multi-Platform Video Downloader",
    options={"build_exe": build_exe_options},
    executables=[Executable(
        "main.py",
        base="Win32GUI",  # Tanpa console window
        target_name="ModernVideoDownloader.exe",
    )]
)
```

Jalankan:
```cmd
python setup_cx.py build
```

---

## 📊 Perbandingan Tools

| Tool | Ukuran | Kecepatan | Kompatibilitas PyQt6 | Kemudahan |
|------|--------|-----------|----------------------|-----------|
| **PyInstaller** | Sedang | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| cx_Freeze | Kecil | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Nuitka | Kecil | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| py2exe | Kecil | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |

---

## ✅ Checklist Sebelum Distribusi

- [ ] Test EXE di komputer yang **tidak ada Python**-nya
- [ ] Pastikan ffmpeg ikut terbundle atau ada di folder
- [ ] Cek config.json ada di folder dist
- [ ] Test di Windows 10 dan Windows 11
- [ ] Ukuran file wajar (50-200MB untuk proyek ini)
- [ ] Tidak ada console window yang muncul (--windowed)
- [ ] Semua fitur berfungsi normal

---

## 💡 Tips Tambahan

### Buat installer dengan NSIS (gratis)
Setelah punya folder dist, bisa buat installer .exe dengan NSIS:
- Download: https://nsis.sourceforge.io/
- Buat installer profesional dengan wizard

### Buat installer dengan Inno Setup (gratis, lebih mudah)
- Download: https://jrsoftware.org/isinfo.php
- Point ke folder `dist\ModernVideoDownloader`
- Compile → dapat file installer .exe

---

*Dibuat untuk Modern YouTube Downloader v1.0 by Adam Official Dev*
