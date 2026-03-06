# 🎥 Modern YouTube Downloader

<div align="center">

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![PyQt Version](https://img.shields.io/badge/PyQt-6.4.0%2B-green)
![License](https://img.shields.io/badge/license-MIT-blue)
![Status](https://img.shields.io/badge/status-active-success)
![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Activation](https://img.shields.io/badge/activation-required-red)

</div>

<div align="center">
  <h3>Powerful YouTube Video Downloader with Modern GUI</h3>
  <p>Download videos, music, and playlists from YouTube with ease!</p>
  <p>
    <a href="#-license-activation">🔑 License Activation</a> ·
    <a href="#-features">✨ Features</a> ·
    <a href="#-installation">📥 Installation</a> ·
    <a href="#-usage-guide">🎮 Usage Guide</a> ·
    <a href="https://github.com/AdamOfficialDev/modern-youtube-downloder-code-activation#readme">🌐 License Server Docs</a>
  </p>
</div>

---

## 📋 Table of Contents

- [License Activation](#-license-activation)
- [Features](#-features)
- [Installation](#-installation)
- [Usage Guide](#-usage-guide)
- [Configuration](#-configuration)
- [Troubleshooting](#-troubleshooting)
- [Development](#-development)
- [FAQ](#-faq)
- [License](#-license)
- [Contact](#-contact)

---

## 🔑 License Activation

> ⚠️ **This application requires a valid license key to run.**  
> A license key is bound to **1 device** and is verified online at startup.

### How to Activate

1. Run the application — an **activation dialog** will appear automatically
2. Enter your license key (format: `XXXX-XXXX-XXXX-XXXX`)
3. Click **"Activate"**
4. If successful, the app will open immediately ✅

### License Plans

| Plan | Duration | Description |
|---|---|---|
| 🟡 **Trial** | 7 days | Try before you buy |
| 🔵 **Basic** | 30 days | Personal use |
| 🟣 **Pro** | 90 days | Full features |
| 🟢 **Enterprise** | 1 year | Power users |
| 🔴 **Lifetime** | Forever | One-time purchase |

### Offline Grace Period

The app continues to run for up to **72 hours** without an internet connection.  
After 72 hours, an online check is required to re-verify your license.

### Switching / Reinstalling PC?

Contact the developer to reset your machine binding — your old key will be revoked and a new one issued.  
See [Contact →](#-contact)

> 📌 **For admins / developers:** Full documentation on managing license keys, the admin dashboard, and deploying the license server is available at:  
> 👉 **[github.com/AdamOfficialDev/modern-youtube-downloder-code-activation](https://github.com/AdamOfficialDev/modern-youtube-downloder-code-activation#readme)**

---

## ✨ Features

### 🎯 Core Features

- **Multi-Format Downloads**
  - High-quality video (up to 8K)
  - Audio-only extraction (MP3, M4A)
  - Custom quality selection
  - Subtitle downloads
- **Batch Processing**

  - Playlist downloads
  - Multiple URL processing
  - Queue management
  - Parallel downloads

- **Smart Search**
  - Integrated YouTube search
  - Real-time suggestions
  - Filter by duration/quality
  - Thumbnail previews

### 🎨 Modern Interface

- **Sleek Design**

  - Dark/Light theme support
  - Responsive layout
  - Custom color schemes
  - Modern animations

- **User Experience**
  - Drag & drop support
  - Progress tracking
  - Speed monitoring
  - ETA calculation

### 🛠 Advanced Features

- **Download Management**

  - Pause/Resume support
  - Speed limits
  - Auto-retry on fail
  - Download history

- **Format Options**
  - Custom output templates
  - Metadata preservation
  - Thumbnail embedding
  - Chapter markers

---

## 📥 Installation

### Prerequisites

- Python 3.12 (recommended)
- Windows 7/8/10/11
- Internet connection
- 500MB free space

### Quick Install

1. **Download & Extract**

   ```bash
   git clone https://github.com/AdamOfficialDev/modern_youtube_downloader.git
   cd modern_youtube_downloader
   ```

2. **Run Setup**

   - Double-click `setup.bat`
   - Wait for automatic installation
   - Follow on-screen instructions

3. **Launch Application**
   - Double-click `run.bat`
   - Or via command line:
     ```bash
     run.bat
     ```

   > On first launch, a **license activation dialog** will appear automatically.  
   > Enter your license key to continue. [How to activate →](#-license-activation)

### Manual Installation

1. **Install Dependencies**

   ```bash
   pip install -r Requirements.txt
   ```

2. **FFmpeg Setup**
   - Create `bundled` folder
   - Download FFmpeg
   - Rename to `ffmpeg.zip`
   - Place in `bundled` folder

---

## 🎮 Usage Guide

### Basic Download

1. Launch application
2. Paste YouTube URL
3. Select quality
4. Choose output folder
5. Click Download

### Batch Download

1. Go to Batch tab
2. Add multiple URLs
3. Configure settings
4. Start batch process

### Search & Download

1. Open Search tab
2. Enter keywords
3. Browse results
4. Select videos
5. Configure download

### History Management

- View download history
- Export to CSV
- Filter by date/status
- Clear history

---

## ⚙️ Configuration

### General Settings

- Default download path
- Preferred quality
- Language selection
- Update preferences

### Download Settings

- Connection limits
- Bandwidth control
- Retry attempts
- Output templates

### Search Settings

- API configuration
- Result filters
- Display options
- Cache settings

---

## 🔧 Troubleshooting

### Common Issues

1. **Download Fails**

   - Check internet
   - Verify URL
   - Update yt-dlp
   - Check permissions

2. **FFmpeg Issues**

   - Verify installation
   - Check bundled folder
   - Update FFmpeg
   - Check logs

3. **Performance Issues**
   - Clear cache
   - Update Python
   - Check resources
   - Limit concurrent downloads

### License Issues

| Error Message | Solution |
|---|---|
| "License key not found" | Double-check the key, contact developer if correct |
| "Already activated on another device" | Contact developer to reset machine binding |
| "License expired" | Renew your license — contact developer |
| "Cannot connect to server" | Check your internet connection and try again |
| "License revoked" | Contact developer for assistance |

---

## 💻 Development

### Project Structure

```
modern_youtube_downloader/
├── bundled/                  # FFmpeg folder
│   └── ffmpeg.zip            # FFmpeg binary
├── main.py                   # Main application entry point
├── download_ffmpeg.py        # FFmpeg downloader script
├── setup.bat                 # Setup script
├── run.bat                   # Run script
├── Requirements.txt          # Python dependencies
├── .gitignore                # Git ignore file
│
├── src/
│   ├── license_manager.py    # License validation & server connection
│   └── license_dialog.py     # Activation dialog UI
│
└── README.md                 # This document
```

> 📌 License server source code and full deployment guide:  
> 👉 **[github.com/AdamOfficialDev/modern-youtube-downloder-code-activation](https://github.com/AdamOfficialDev/modern-youtube-downloder-code-activation#readme)**

### Key Components

- **Main Application**: `main.py` — Core application with PyQt6 UI
- **License Manager**: `src/license_manager.py` — Handles online validation, caching, and revoke detection
- **License Dialog**: `src/license_dialog.py` — Activation UI shown on first launch
- **Setup Scripts**:
  - `setup.bat` — Automated installation
  - `download_ffmpeg.py` — FFmpeg downloader
- **Dependencies**:
  - `Requirements.txt` — Python packages
  - `bundled/ffmpeg.zip` — FFmpeg binary

### Contributing

1. Fork repository
2. Create feature branch
3. Implement changes
4. Submit pull request

---

## ❓ FAQ

### General Questions

1. **Is it free?**

   - The source code is open source (MIT), but running the app requires a purchased license key.

2. **Supported platforms?**

   - Windows (primary)
   - Linux (experimental)

3. **Update frequency?**
   - Monthly feature updates
   - Weekly bug fixes

### License Questions

1. **Can I use one key on multiple PCs?**

   - No — each key is bound to one device. Contact the developer for multi-seat options.

2. **What happens if I'm offline?**

   - The app continues working for up to 72 hours without internet.

3. **Can I transfer my license to a new PC?**

   - Yes — contact the developer to reset your machine binding.

### Technical Questions

1. **Maximum quality?**

   - Up to 8K (if available)
   - Depends on source

2. **Download speed?**
   - Based on connection
   - Multiple threads supported

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) file.  
Usage of this application requires a valid commercial license key purchased from the developer.

---

## 📞 Contact

### Developer

- **Adam Official Dev**
  - GitHub: [@AdamOfficialDev](https://github.com/AdamOfficialDev)
  - Email: [contact@adamofficial.dev](mailto:contact@adamofficial.dev)

### Community

- GitHub Issues
- Discord Server
- Twitter Updates

---

<div align="center">
  Made with ❤️ by Adam Official Dev
  <br>
  &copy; 2024 Modern YouTube Downloader
  <br><br>
  <a href="https://github.com/AdamOfficialDev/modern-youtube-downloder-code-activation#readme">🌐 License Server Documentation →</a>
</div>
