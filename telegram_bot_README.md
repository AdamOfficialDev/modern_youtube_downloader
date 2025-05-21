# Modern YouTube Downloader Telegram Bot

A comprehensive Telegram bot for downloading videos from YouTube and other platforms. Built with python-telegram-bot and yt-dlp.

## Features

- Download videos from YouTube and other supported platforms
- Extract audio from videos
- Multiple format and quality options
- Interactive hamburger menu (☰) for easy command access
- User-friendly interface with inline keyboards
- Robust error handling and logging
- Admin commands for monitoring and management
- Comprehensive documentation

## Requirements

- Python 3.8+
- python-telegram-bot
- yt-dlp
- FFmpeg

## Installation

1. Clone the repository:

```bash
git clone https://github.com/AdamOfficialDev/modern_youtube_downloader.git
cd modern_youtube_downloader
```

2. Install the required dependencies:

```bash
pip install -r Requirements.txt
```

3. Set up your Telegram bot token:

   - Create a new bot using [@BotFather](https://t.me/BotFather) on Telegram
   - Get your bot token
   - Add the token to `config.json`:

   ```json
   {
     "telegram_bot_token": "YOUR_BOT_TOKEN_HERE",
     "admin_users": ["YOUR_TELEGRAM_USER_ID"],
     "max_downloads_per_user": 5,
     "allowed_formats": ["mp4", "mp3", "webm"]
   }
   ```

4. Run the bot:

```bash
python telegram_bot.py
```

## Usage

### User Commands

- `/start` - Start the bot and get a welcome message
- `/menu` - Show the interactive hamburger menu (☰)
- `/help` - Show available commands and usage instructions
- `/download <url>` - Download a video with format selection
- `/audio <url>` - Extract audio from a video
- `/status` - Check your active downloads
- `/about` - Show information about the bot

### Admin Commands

- `/stats` - Show bot statistics
- `/logs` - Get the log file

### Direct Usage

- Simply send a video URL to the bot, and it will process it as a download request
- Use the hamburger menu (☰) to access all commands through an interactive interface
- Click on menu buttons to quickly access common functions

## Configuration

The bot uses `config.json` for configuration:

- `telegram_bot_token`: Your Telegram bot token
- `admin_users`: List of Telegram user IDs with admin privileges
- `max_downloads_per_user`: Maximum concurrent downloads per user
- `allowed_formats`: List of allowed video/audio formats

## Logging

The bot logs all activities to both console and a file (`bot_logs.log`). This includes:

- User interactions
- Download requests
- Errors and exceptions
- Bot status changes

## Error Handling

The bot includes comprehensive error handling for:

- Invalid URLs
- Failed downloads
- API errors
- File size limitations
- User input validation

## Limitations

- Maximum file size for Telegram is 50MB
- Larger files will need to be downloaded directly from the server
- Some websites may have anti-bot protection

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [FFmpeg](https://ffmpeg.org/)

## Author

Adam Official Dev - [GitHub](https://github.com/AdamOfficialDev)
