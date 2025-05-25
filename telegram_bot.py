#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Modern YouTube Downloader Telegram Bot
======================================

A comprehensive Telegram bot for downloading videos from YouTube and other platforms.
Built with python-telegram-bot and yt-dlp.

This bot allows users to download videos by sending URLs, with options for different
formats and quality settings. It includes robust error handling, logging, and
configuration management.

Author: Adam Official Dev
"""

import os
import sys
import json
import logging
import datetime
import re
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Union, Any, Tuple

import yt_dlp
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot_logs.log"),
        logging.StreamHandler()
    ]
)

# Create logger
logger = logging.getLogger(__name__)

# Constants
CONFIG_FILE = "config.json"
DEFAULT_DOWNLOAD_DIR = "downloads"
DOWNLOAD_TIMEOUT = 600  # 10 minutes
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB (Telegram bot API limit)

class BotConfig:
    """Configuration manager for the Telegram bot."""

    def __init__(self, config_file: str = CONFIG_FILE, parent_app=None):
        """
        Initialize the configuration manager.

        Args:
            config_file: Path to the configuration file
            parent_app: Parent application (ModernVideoDownloader instance)
        """
        self.config_file = config_file
        self.parent_app = parent_app
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file or parent application.

        Returns:
            Dict containing configuration values
        """
        # If parent app is provided, use its configuration
        if self.parent_app and hasattr(self.parent_app, 'config'):
            config = self.parent_app.config

            # Ensure required fields exist
            if "telegram_bot_token" not in config:
                config["telegram_bot_token"] = ""
            if "admin_users" not in config:
                config["admin_users"] = []
            if "max_downloads_per_user" not in config:
                config["max_downloads_per_user"] = 5
            if "allowed_formats" not in config:
                config["allowed_formats"] = ["mp4", "mp3", "webm"]

            return config

        # Otherwise, load from file
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    config = json.load(f)

                # Ensure required fields exist
                if "telegram_bot_token" not in config:
                    config["telegram_bot_token"] = ""
                if "admin_users" not in config:
                    config["admin_users"] = []
                if "max_downloads_per_user" not in config:
                    config["max_downloads_per_user"] = 5
                if "allowed_formats" not in config:
                    config["allowed_formats"] = ["mp4", "mp3", "webm"]

                return config
            else:
                # Create default config
                default_config = {
                    "youtube_api_key": "",
                    "telegram_bot_token": "",
                    "admin_users": [],
                    "max_downloads_per_user": 5,
                    "allowed_formats": ["mp4", "mp3", "webm"]
                }

                with open(self.config_file, "w") as f:
                    json.dump(default_config, f, indent=2)

                return default_config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return {
                "telegram_bot_token": "",
                "admin_users": []
            }

    def save_config(self) -> bool:
        """
        Save current configuration to file or parent application.

        Returns:
            True if successful, False otherwise
        """
        # If parent app is provided, update its configuration
        if self.parent_app and hasattr(self.parent_app, 'config'):
            try:
                # Update parent app's config with our values
                for key, value in self.config.items():
                    self.parent_app.config[key] = value

                # Save parent app's config
                if hasattr(self.parent_app, 'save_config'):
                    self.parent_app.save_config()
                return True
            except Exception as e:
                logger.error(f"Error saving configuration to parent app: {e}")
                return False

        # Otherwise, save to file
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving configuration to file: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key doesn't exist

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Value to set
        """
        self.config[key] = value
        self.save_config()

class DownloadManager:
    """Manager for video download operations."""

    def __init__(self, download_dir: str = DEFAULT_DOWNLOAD_DIR):
        """
        Initialize the download manager.

        Args:
            download_dir: Directory to save downloads
        """
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)

    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """
        Get information about a video.

        Args:
            url: Video URL

        Returns:
            Dict containing video information

        Raises:
            Exception: If video information cannot be retrieved
        """
        # Enhanced options for better platform support
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': False,
            'force_generic_extractor': False,
            'ignoreerrors': False,
            'nocheckcertificate': True,  # Ignore SSL certificate validation
            'no_color': True,
            'geo_bypass': True,  # Try to bypass geo-restrictions
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',  # Use a common user agent
        }

        # Add special handling for TikTok
        if 'tiktok.com' in url or 'vt.tiktok.com' in url:
            logger.info(f"TikTok URL detected: {url}")
            # Add TikTok-specific options
            ydl_opts.update({
                'extractor_args': {
                    'tiktok': {
                        'embed_api': 'https://www.tiktok.com/embed',
                        'api_hostname': 'api.tiktok.com',
                        'webpage_api': 'https://www.tiktok.com/api',
                        'mobile_api': 'https://m.tiktok.com/api',
                    }
                }
            })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"Extracting info for URL: {url}")
                info = ydl.extract_info(url, download=False)
                if info:
                    logger.info(f"Successfully extracted info for: {info.get('title', 'Unknown title')}")
                return info
        except Exception as e:
            logger.error(f"Error getting video info: {e}")
            # Try with generic extractor as fallback
            try:
                logger.info(f"Retrying with generic extractor for URL: {url}")
                ydl_opts['force_generic_extractor'] = True
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if info:
                        logger.info(f"Successfully extracted info with generic extractor: {info.get('title', 'Unknown title')}")
                    return info
            except Exception as e2:
                logger.error(f"Error getting video info with generic extractor: {e2}")
                raise Exception(f"Could not extract video information: {str(e2)}")

    async def download_video(
        self,
        url: str,
        format_id: str = "best",
        extract_audio: bool = False
    ) -> Tuple[str, str]:
        """
        Download a video.

        Args:
            url: Video URL
            format_id: Format ID to download
            extract_audio: Whether to extract audio

        Returns:
            Tuple of (file_path, title)

        Raises:
            Exception: If download fails
        """
        # Create a temporary directory for this download
        temp_dir = tempfile.mkdtemp()

        try:
            # Set up enhanced yt-dlp options for better platform support
            ydl_opts = {
                'format': format_id,
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'noplaylist': True,
                'nocheckcertificate': True,  # Ignore SSL certificate validation
                'no_color': True,
                'geo_bypass': True,  # Try to bypass geo-restrictions
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'retries': 5,  # Retry up to 5 times
                'fragment_retries': 5,  # Retry fragments up to 5 times
                'ignoreerrors': False,
                'verbose': True,  # Enable verbose output for debugging
            }

            # Add special handling for TikTok
            if 'tiktok.com' in url or 'vt.tiktok.com' in url:
                logger.info(f"TikTok URL detected for download: {url}")
                # Add TikTok-specific options
                ydl_opts.update({
                    'extractor_args': {
                        'tiktok': {
                            'embed_api': 'https://www.tiktok.com/embed',
                            'api_hostname': 'api.tiktok.com',
                            'webpage_api': 'https://www.tiktok.com/api',
                            'mobile_api': 'https://m.tiktok.com/api',
                        }
                    }
                })

            if extract_audio:
                ydl_opts.update({
                    'format': 'bestaudio/best',
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                })

            # Download the video
            logger.info(f"Starting download for URL: {url} with format: {format_id}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'video')
                logger.info(f"Download completed for: {title}")

                # Find the downloaded file
                for file in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file)
                    if os.path.isfile(file_path):
                        # Move to permanent location
                        final_path = os.path.join(self.download_dir, file)
                        shutil.move(file_path, final_path)
                        logger.info(f"File saved to: {final_path}")
                        return final_path, title

            raise Exception("Downloaded file not found")
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            # Try with generic extractor as fallback
            try:
                logger.info(f"Retrying download with generic extractor for URL: {url}")
                ydl_opts['force_generic_extractor'] = True
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    title = info.get('title', 'video')
                    logger.info(f"Download completed with generic extractor for: {title}")

                    # Find the downloaded file
                    for file in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, file)
                        if os.path.isfile(file_path):
                            # Move to permanent location
                            final_path = os.path.join(self.download_dir, file)
                            shutil.move(file_path, final_path)
                            logger.info(f"File saved to: {final_path}")
                            return final_path, title

                raise Exception("Downloaded file not found")
            except Exception as e2:
                logger.error(f"Error downloading video with generic extractor: {e2}")
                raise Exception(f"Failed to download video: {str(e2)}")
        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

class TelegramBot:
    """Main Telegram bot class."""

    def __init__(self, parent_app=None):
        """
        Initialize the Telegram bot.

        Args:
            parent_app: Parent application (ModernVideoDownloader instance)
        """
        self.parent_app = parent_app
        self.config = BotConfig(parent_app=parent_app)
        self.download_manager = DownloadManager()
        self.active_downloads = {}  # Track active downloads by user
        self.start_time = datetime.datetime.now()

        # Get bot token from parent app if available, otherwise from config
        if parent_app and parent_app.config.get("telegram_bot_token"):
            self.token = parent_app.config.get("telegram_bot_token")
        else:
            self.token = self.config.get("telegram_bot_token")

        if not self.token:
            logger.error("Bot token not found in configuration")
            raise ValueError("Telegram bot token not configured")

        # Initialize bot application
        self.application = Application.builder().token(self.token).build()

        # Register handlers
        self._register_handlers()

        logger.info("Bot initialized successfully")

    def _register_handlers(self) -> None:
        """Register command and message handlers."""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("about", self.cmd_about))
        self.application.add_handler(CommandHandler("download", self.cmd_download))
        self.application.add_handler(CommandHandler("audio", self.cmd_audio))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("menu", self.cmd_menu))

        # Admin commands
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))
        self.application.add_handler(CommandHandler("logs", self.cmd_logs))
        self.application.add_handler(CommandHandler("testblock", self.cmd_test_block))

        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Callback query handler
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

        # Error handler
        self.application.add_error_handler(self.error_handler)

    async def _set_bot_commands(self) -> None:
        """Set up bot commands for the menu."""
        commands = [
            BotCommand("start", "Start the bot"),
            BotCommand("menu", "Show the menu ☰"),
            BotCommand("download", "Download a video"),
            BotCommand("audio", "Extract audio from a video"),
            BotCommand("status", "Check your download status"),
            BotCommand("help", "Show help information"),
            BotCommand("about", "About this bot")
        ]

        try:
            await self.application.bot.set_my_commands(commands)
            logger.info("Bot commands set successfully")
        except Exception as e:
            logger.error(f"Error setting bot commands: {e}")

    def _create_main_menu_keyboard(self) -> ReplyKeyboardMarkup:
        """Create the main menu keyboard."""
        keyboard = [
            [KeyboardButton("📥 Download Video"), KeyboardButton("🎵 Extract Audio")],
            [KeyboardButton("📊 Status"), KeyboardButton("ℹ️ Help")],
            [KeyboardButton("🤖 About")]
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /start command.

        Args:
            update: Update object
            context: Context object
        """
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) started the bot")

        # Check if user is blocked
        logger.info(f"Checking if user {user.id} is blocked for /start command")
        if self.is_user_blocked(user.id):
            logger.warning(f"User {user.id} ({user.username}) is blocked, sending block message")
            blocked_message = (
                "🚫 **AKSES DITOLAK**\n\n"
                "❌ Maaf, akun Anda telah diblokir oleh administrator.\n"
                "🔒 Anda tidak dapat menggunakan layanan bot ini saat ini.\n\n"
                "📞 **Untuk mengajukan banding:**\n"
                "• Hubungi administrator bot\n"
                "• Jelaskan alasan Anda ingin akses dikembalikan\n"
                "• Tunggu keputusan dari admin\n\n"
                "⚠️ Jangan spam atau membuat akun baru, hal ini dapat memperpanjang masa blokir."
            )
            try:
                await update.message.reply_text(blocked_message, parse_mode="Markdown")
                logger.info(f"Block message sent successfully to user {user.id}")
            except Exception as e:
                logger.error(f"Failed to send block message to user {user.id}: {e}")
                # Fallback without markdown
                await update.message.reply_text(blocked_message.replace("**", "").replace("*", ""))
            return

        # Update user activity for start command
        self._update_user_activity(user.id, user.username, increment_download=False)

        # Set up bot commands for the menu
        await self._set_bot_commands()

        welcome_message = (
            f"👋 Hello {user.first_name}!\n\n"
            f"Welcome to the Modern YouTube Downloader Bot. "
            f"This bot helps you download videos from YouTube and other platforms.\n\n"
            f"Send me a video URL or click the ☰ menu button to see available commands."
        )

        # Send welcome message with menu keyboard
        await update.message.reply_text(
            welcome_message,
            reply_markup=self._create_main_menu_keyboard()
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /help command.

        Args:
            update: Update object
            context: Context object
        """
        user = update.effective_user

        # Check if user is blocked
        if self.is_user_blocked(user.id):
            blocked_message = (
                "🚫 **BANTUAN TIDAK TERSEDIA**\n\n"
                "❌ Akun Anda telah diblokir oleh administrator.\n"
                "❓ Anda tidak dapat mengakses bantuan saat ini.\n\n"
                "📖 **Informasi umum:**\n"
                "• Akun Anda dalam status diblokir\n"
                "• Semua fitur bot tidak dapat diakses\n"
                "• Termasuk halaman bantuan dan panduan\n\n"
                "🔧 **Untuk mendapatkan bantuan:**\n"
                "• Hubungi administrator bot langsung\n"
                "• Jelaskan masalah atau pertanyaan Anda\n"
                "• Minta klarifikasi tentang status akun\n\n"
                "💡 **Catatan:** Admin dapat memberikan bantuan meskipun akun diblokir."
            )
            await update.message.reply_text(blocked_message, parse_mode="Markdown")
            return

        # Update user activity for help command
        self._update_user_activity(user.id, user.username, increment_download=False)
        help_text = (
            "🔍 *Available Commands:*\n\n"
            "• Send any video URL to download it\n"
            "• /menu - Show the interactive menu ☰\n"
            "• /download <url> - Download a video in best quality\n"
            "• /audio <url> - Extract audio from a video\n"
            "• /status - Check your download status\n"
            "• /about - Information about this bot\n"
            "• /help - Show this help message\n\n"

            "🔧 *How to use:*\n"
            "1. Click the ☰ menu button or use /menu to see available options\n"
            "2. Send a YouTube URL (or other supported platform)\n"
            "3. Select the format you want to download\n"
            "4. Wait for the download to complete\n"
            "5. Receive your file\n\n"

            "⚠️ *Limitations:*\n"
            "• Maximum file size: 50MB (Telegram limitation)\n"
            "• Larger files will be provided as download links\n"
            f"• Maximum concurrent downloads: {self.config.get('max_downloads_per_user', 5)} per user"
        )

        await update.message.reply_text(
            help_text,
            parse_mode="Markdown",
            reply_markup=self._create_main_menu_keyboard()
        )

    async def cmd_about(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /about command.

        Args:
            update: Update object
            context: Context object
        """
        about_text = (
            "🤖 *Modern YouTube Downloader Bot*\n\n"
            "A powerful bot for downloading videos from YouTube and other platforms.\n\n"

            "🛠 *Features:*\n"
            "• Download videos in various formats\n"
            "• Extract audio from videos\n"
            "• Support for multiple platforms\n"
            "• Fast and reliable downloads\n\n"

            "👨‍💻 *Developer:* Adam Official Dev\n"
            "🔗 *GitHub:* [modern_youtube_downloader](https://github.com/AdamOfficialDev/modern_youtube_downloader)\n\n"

            "📦 *Powered by:*\n"
            "• python-telegram-bot\n"
            "• yt-dlp\n"
            "• FFmpeg\n\n"

            "Version 1.0.0"
        )

        await update.message.reply_text(
            about_text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=self._create_main_menu_keyboard()
        )

    async def cmd_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /download command.

        Args:
            update: Update object
            context: Context object
        """
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) used /download command")

        # Check if user is blocked
        if self.is_user_blocked(user.id):
            blocked_message = (
                "🚫 **DOWNLOAD DITOLAK**\n\n"
                "❌ Akun Anda telah diblokir oleh administrator.\n"
                "📥 Anda tidak dapat mengunduh video saat ini.\n\n"
                "🔍 **Kemungkinan alasan pemblokiran:**\n"
                "• Pelanggaran terms of service\n"
                "• Penggunaan berlebihan (spam)\n"
                "• Konten yang tidak sesuai\n"
                "• Laporan dari pengguna lain\n\n"
                "📞 **Untuk mengajukan banding:**\n"
                "• Hubungi administrator bot\n"
                "• Jelaskan situasi Anda dengan jelas\n"
                "• Berikan bukti jika diperlukan\n\n"
                "⏳ Proses review biasanya memakan waktu 1-3 hari kerja."
            )
            await update.message.reply_text(blocked_message, parse_mode="Markdown")
            return

        # Check if URL was provided
        if not context.args:
            await update.message.reply_text(
                "⚠️ Please provide a URL.\n"
                "Example: /download https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )
            return

        url = context.args[0]

        # Validate URL
        if not self._is_valid_url(url):
            await update.message.reply_text("⚠️ Invalid URL. Please provide a valid video URL.")
            return

        # Check if user has too many active downloads
        user_id = str(user.id)
        max_downloads = self.config.get("max_downloads_per_user", 5)
        if user_id in self.active_downloads and len(self.active_downloads[user_id]) >= max_downloads:
            await update.message.reply_text(
                f"⚠️ You have reached the maximum number of concurrent downloads ({max_downloads}).\n"
                f"Please wait for your current downloads to finish."
            )
            return

        # Send processing message
        processing_message = await update.message.reply_text("🔍 Processing video URL...")

        try:
            # Get video info
            info = await self.download_manager.get_video_info(url)

            # Create format selection keyboard
            formats = self._get_available_formats(info)
            keyboard = self._create_format_keyboard(url, formats)

            # Update message with format selection
            # Escape special characters in title and uploader
            safe_title = self._escape_markdown(info['title'])
            safe_uploader = self._escape_markdown(info.get('uploader', 'Unknown'))

            await processing_message.edit_text(
                f"📹 *{safe_title}*\n\n"
                f"Channel: {safe_uploader}\n"
                f"Duration: {self._format_duration(info.get('duration', 0))}\n\n"
                f"Please select a format to download:",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )

            # Track this download
            if user_id not in self.active_downloads:
                self.active_downloads[user_id] = []
            # Store the original title (not escaped) for internal use
            self.active_downloads[user_id].append({
                "url": url,
                "title": info['title'],
                "status": "selecting_format",
                "message_id": processing_message.message_id
            })

        except Exception as e:
            logger.error(f"Error processing video: {e}")
            await processing_message.edit_text(f"❌ Error: {str(e)}")

    async def cmd_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /audio command.

        Args:
            update: Update object
            context: Context object
        """
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) used /audio command")

        # Check if user is blocked
        if self.is_user_blocked(user.id):
            blocked_message = (
                "🚫 **EKSTRAKSI AUDIO DITOLAK**\n\n"
                "❌ Akun Anda telah diblokir oleh administrator.\n"
                "🎵 Anda tidak dapat mengekstrak audio saat ini.\n\n"
                "⚖️ **Kebijakan pemblokiran:**\n"
                "• Berlaku untuk semua fitur bot\n"
                "• Termasuk download video dan audio\n"
                "• Tidak dapat diakali dengan command berbeda\n\n"
                "🔄 **Langkah selanjutnya:**\n"
                "• Tunggu hingga masa blokir berakhir, atau\n"
                "• Hubungi admin untuk klarifikasi\n"
                "• Patuhi aturan bot setelah akses dikembalikan\n\n"
                "💡 **Tips:** Baca terms of service untuk menghindari pemblokiran di masa depan."
            )
            await update.message.reply_text(blocked_message, parse_mode="Markdown")
            return

        # Check if URL was provided
        if not context.args:
            await update.message.reply_text(
                "⚠️ Please provide a URL.\n"
                "Example: /audio https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )
            return

        url = context.args[0]

        # Validate URL
        if not self._is_valid_url(url):
            await update.message.reply_text("⚠️ Invalid URL. Please provide a valid video URL.")
            return

        # Check if user has too many active downloads
        user_id = str(user.id)
        max_downloads = self.config.get("max_downloads_per_user", 5)
        if user_id in self.active_downloads and len(self.active_downloads[user_id]) >= max_downloads:
            await update.message.reply_text(
                f"⚠️ You have reached the maximum number of concurrent downloads ({max_downloads}).\n"
                f"Please wait for your current downloads to finish."
            )
            return

        # Send processing message
        processing_message = await update.message.reply_text("🔍 Processing audio extraction...")

        try:
            # Get video info
            info = await self.download_manager.get_video_info(url)

            # Start audio extraction
            safe_title = self._escape_markdown(info['title'])
            await processing_message.edit_text(f"⏳ Extracting audio from: *{safe_title}*...", parse_mode="Markdown")

            # Track this download
            if user_id not in self.active_downloads:
                self.active_downloads[user_id] = []
            self.active_downloads[user_id].append({
                "url": url,
                "title": info['title'],
                "status": "downloading",
                "message_id": processing_message.message_id,
                "is_audio": True
            })

            # Download audio
            file_path, title = await self.download_manager.download_video(url, extract_audio=True)

            # Send audio file
            await self._send_file(update, context, file_path, title, is_audio=True)

            # Update user activity
            self._update_user_activity(user.id, user.username, increment_download=True)

            # Update download status
            self._update_download_status(user_id, url, "completed")
            safe_title = self._escape_markdown(title)
            await processing_message.edit_text(f"✅ Audio extraction completed: *{safe_title}*", parse_mode="Markdown")

        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            await processing_message.edit_text(f"❌ Error: {str(e)}")
            self._update_download_status(user_id, url, "failed")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /status command.

        Args:
            update: Update object
            context: Context object
        """
        user = update.effective_user
        user_id = str(user.id)

        if user_id not in self.active_downloads or not self.active_downloads[user_id]:
            await update.message.reply_text("You don't have any active downloads.")
            return

        status_text = "📥 *Your Active Downloads:*\n\n"

        for i, download in enumerate(self.active_downloads[user_id], 1):
            status_emoji = {
                "selecting_format": "🔍",
                "downloading": "⏳",
                "completed": "✅",
                "failed": "❌"
            }.get(download["status"], "⏳")

            # Escape title for Markdown
            safe_title = self._escape_markdown(download['title'])
            status_text += (
                f"{i}. {status_emoji} *{safe_title}*\n"
                f"   Status: {download['status'].replace('_', ' ').title()}\n\n"
            )

        await update.message.reply_text(
            status_text,
            parse_mode="Markdown",
            reply_markup=self._create_main_menu_keyboard()
        )

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /stats command (admin only).

        Args:
            update: Update object
            context: Context object
        """
        user = update.effective_user

        # Check if user is admin by username
        if not user.username or user.username not in self.config.get("admin_users", []):
            await update.message.reply_text("⚠️ This command is only available to administrators.")
            return

        # Collect stats
        total_downloads = sum(len(downloads) for downloads in self.active_downloads.values())
        active_users = len(self.active_downloads)

        stats_text = (
            "📊 *Bot Statistics:*\n\n"
            f"Active Users: {active_users}\n"
            f"Active Downloads: {total_downloads}\n"
            f"Download Directory Size: {self._get_directory_size(self.download_manager.download_dir)}\n\n"
            f"Bot Uptime: {self._get_uptime()}"
        )

        await update.message.reply_text(stats_text, parse_mode="Markdown")

    async def cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /logs command (admin only).

        Args:
            update: Update object
            context: Context object
        """
        user = update.effective_user

        # Check if user is admin by username
        if not user.username or user.username not in self.config.get("admin_users", []):
            await update.message.reply_text("⚠️ This command is only available to administrators.")
            return

        # Get log file
        log_file = "bot_logs.log"
        if not os.path.exists(log_file):
            await update.message.reply_text("❌ Log file not found.")
            return

        # Send log file
        try:
            with open(log_file, "rb") as f:
                await update.message.reply_document(document=f, filename="bot_logs.log")
        except Exception as e:
            logger.error(f"Error sending log file: {e}")
            await update.message.reply_text(f"❌ Error sending log file: {str(e)}")

    async def cmd_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle the /menu command.

        Args:
            update: Update object
            context: Context object
        """
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) opened the menu")

        # Check if user is blocked
        if self.is_user_blocked(user.id):
            blocked_message = (
                "🚫 **MENU TIDAK TERSEDIA**\n\n"
                "❌ Akun Anda telah diblokir oleh administrator.\n"
                "☰ Menu dan semua fitur tidak dapat diakses.\n\n"
                "🔐 **Akses terbatas:**\n"
                "• Menu utama: Diblokir\n"
                "• Download video: Diblokir\n"
                "• Ekstraksi audio: Diblokir\n"
                "• Status download: Diblokir\n\n"
                "📞 **Hubungi admin untuk:**\n"
                "• Mengetahui alasan pemblokiran\n"
                "• Mengajukan permohonan unblock\n"
                "• Mendapatkan informasi lebih lanjut\n\n"
                "⏰ **Pemblokiran bersifat sementara dan dapat dicabut oleh admin.**"
            )
            await update.message.reply_text(blocked_message, parse_mode="Markdown")
            return

        # Update user activity for menu command
        self._update_user_activity(user.id, user.username, increment_download=False)

        menu_message = (
            "☰ *Main Menu*\n\n"
            "Please select an option from the menu below:"
        )

        await update.message.reply_text(
            menu_message,
            parse_mode="Markdown",
            reply_markup=self._create_main_menu_keyboard()
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle text messages.

        Args:
            update: Update object
            context: Context object
        """
        text = update.message.text
        user = update.effective_user

        # Check if user is blocked
        logger.info(f"Checking if user {user.id} is blocked for message: {text[:50]}...")
        if self.is_user_blocked(user.id):
            logger.warning(f"User {user.id} ({user.username}) is blocked, sending block message for text message")
            blocked_message = (
                "🚫 **PESAN DIBLOKIR**\n\n"
                "❌ Akun Anda telah diblokir oleh administrator.\n"
                "💬 Semua pesan dan command Anda tidak akan diproses.\n\n"
                "🚨 **Status akun:** DIBLOKIR\n"
                "📅 **Sejak:** Lihat riwayat dengan admin\n"
                "🔒 **Akses:** Ditangguhkan sementara\n\n"
                "📋 **Yang tidak dapat Anda lakukan:**\n"
                "• Mengirim URL untuk download\n"
                "• Menggunakan semua command bot\n"
                "• Mengakses fitur apapun\n\n"
                "📞 **Kontak admin untuk informasi lebih lanjut**\n"
                "⚠️ **Peringatan:** Jangan spam pesan, ini dapat memperburuk situasi."
            )
            try:
                await update.message.reply_text(blocked_message, parse_mode="Markdown")
                logger.info(f"Block message sent successfully to user {user.id} for text message")
            except Exception as e:
                logger.error(f"Failed to send block message to user {user.id}: {e}")
                # Fallback without markdown
                await update.message.reply_text(blocked_message.replace("**", "").replace("*", ""))
            return

        # Check if message is a URL
        if self._is_valid_url(text):
            # Treat as download command
            context.args = [text]
            await self.cmd_download(update, context)
        # Handle menu button clicks
        elif text == "📥 Download Video":
            await update.message.reply_text(
                "Please send me a video URL to download.\n"
                "Example: https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )
        elif text == "🎵 Extract Audio":
            await update.message.reply_text(
                "Please send me a video URL to extract audio from.\n"
                "Example: https://www.youtube.com/watch?v=dQw4w9WgXcQ"
            )
        elif text == "📊 Status":
            await self.cmd_status(update, context)
        elif text == "ℹ️ Help":
            await self.cmd_help(update, context)
        elif text == "🤖 About":
            await self.cmd_about(update, context)
        else:
            # Not a URL or menu option, provide help
            await update.message.reply_text(
                "Please send me a video URL, use a command, or select an option from the menu.\n"
                "Click the ☰ menu button or type /menu to see available options."
            )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle callback queries from inline keyboards.

        Args:
            update: Update object
            context: Context object
        """
        query = update.callback_query
        await query.answer()  # Acknowledge the button click

        # Parse callback data using pipe character as separator
        data = query.data.split("|")
        action = data[0]

        # Import base64 for decoding
        import base64

        if action == "download":
            # Format: download|encoded_url|format_id
            if len(data) < 3:
                await query.edit_message_text("❌ Invalid callback data")
                return

            # Decode the URL from base64
            try:
                encoded_url = data[1]
                url = base64.b64decode(encoded_url.encode('utf-8')).decode('utf-8')
                format_id = data[2]
            except Exception as e:
                logger.error(f"Error decoding URL: {e}")
                await query.edit_message_text("❌ Error decoding URL")
                return

            # Start download
            safe_format = self._escape_markdown(format_id)
            await query.edit_message_text(f"⏳ Downloading video in {safe_format} format...", parse_mode="Markdown")

            user = update.effective_user
            user_id = str(user.id)

            # Update download status
            self._update_download_status(user_id, url, "downloading")

            try:
                # Download video
                file_path, title = await self.download_manager.download_video(url, format_id)

                # Send video file
                await self._send_file(update, context, file_path, title)

                # Update user activity
                self._update_user_activity(user.id, user.username, increment_download=True)

                # Update download status
                self._update_download_status(user_id, url, "completed")
                safe_title = self._escape_markdown(title)
                await query.edit_message_text(f"✅ Download completed: *{safe_title}*", parse_mode="Markdown")

            except Exception as e:
                logger.error(f"Error downloading video: {e}")
                await query.edit_message_text(f"❌ Error: {str(e)}")
                self._update_download_status(user_id, url, "failed")

        elif action == "cancel":
            # Format: cancel|encoded_url
            if len(data) < 2:
                await query.edit_message_text("❌ Invalid callback data")
                return

            # Decode the URL from base64
            try:
                encoded_url = data[1]
                url = base64.b64decode(encoded_url.encode('utf-8')).decode('utf-8')
            except Exception as e:
                logger.error(f"Error decoding URL: {e}")
                await query.edit_message_text("❌ Error decoding URL")
                return

            user_id = str(update.effective_user.id)

            # Remove download from active downloads
            self._remove_download(user_id, url)

            await query.edit_message_text("❌ Download cancelled")

    async def _send_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE, file_path: str, title: str, is_audio: bool = False) -> None:
        """
        Send a file to the user.

        Args:
            update: Update object
            context: Context object
            file_path: Path to the file
            title: Title of the video/audio
            is_audio: Whether the file is audio
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = os.path.getsize(file_path)

        # Check if file is too large for Telegram
        if file_size > MAX_FILE_SIZE:
            # File is too large, provide download link
            # In a real implementation, you would upload to a file hosting service
            # and provide a download link
            await update.effective_message.reply_text(
                f"⚠️ File is too large to send via Telegram ({file_size / (1024 * 1024):.1f} MB).\n"
                f"Please download it from the server directly."
            )
            return

        # Send file based on type
        try:
            if is_audio:
                with open(file_path, "rb") as f:
                    await update.effective_message.reply_audio(
                        audio=f,
                        title=title,
                        performer="YouTube Downloader Bot",
                        caption=f"🎵 {title}"
                    )
            else:
                with open(file_path, "rb") as f:
                    await update.effective_message.reply_video(
                        video=f,
                        caption=f"📹 {title}",
                        supports_streaming=True
                    )
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            # If sending as video fails, try sending as document
            try:
                with open(file_path, "rb") as f:
                    await update.effective_message.reply_document(
                        document=f,
                        caption=f"📁 {title}"
                    )
            except Exception as e2:
                logger.error(f"Error sending file as document: {e2}")
                raise Exception(f"Failed to send file: {str(e2)}")

    def _update_download_status(self, user_id: str, url: str, status: str) -> None:
        """
        Update the status of a download.

        Args:
            user_id: User ID
            url: Video URL
            status: New status
        """
        if user_id in self.active_downloads:
            # Find the download by URL, handling potential URL encoding differences
            for download in self.active_downloads[user_id]:
                # Compare URLs in a normalized way
                if self._normalize_url(download["url"]) == self._normalize_url(url):
                    download["status"] = status
                    break

    def _remove_download(self, user_id: str, url: str) -> None:
        """
        Remove a download from active downloads.

        Args:
            user_id: User ID
            url: Video URL
        """
        if user_id in self.active_downloads:
            # Filter out the download with the matching URL, handling potential URL encoding differences
            normalized_url = self._normalize_url(url)
            self.active_downloads[user_id] = [
                d for d in self.active_downloads[user_id]
                if self._normalize_url(d["url"]) != normalized_url
            ]

    def _normalize_url(self, url: str) -> str:
        """
        Normalize a URL for comparison.

        Args:
            url: URL to normalize

        Returns:
            Normalized URL
        """
        # Simple normalization - remove trailing slashes and lowercase
        # This could be expanded with more sophisticated URL normalization if needed
        return url.rstrip('/').lower()

    def _get_available_formats(self, info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get available formats for a video.

        Args:
            info: Video information

        Returns:
            List of available formats
        """
        formats = []

        # Add best video+audio format
        formats.append({
            "format_id": "best",
            "ext": info.get("ext", "mp4"),
            "resolution": "Best Quality",
            "description": "Best Quality (Video + Audio)"
        })

        # Add best audio format
        formats.append({
            "format_id": "bestaudio",
            "ext": "mp3",
            "resolution": "Audio Only",
            "description": "Best Audio Quality (MP3)"
        })

        # Add some specific formats if available
        if "formats" in info:
            # Filter for common formats with both video and audio
            video_formats = [
                f for f in info["formats"]
                if f.get("vcodec", "none") != "none" and f.get("acodec", "none") != "none"
                and f.get("height", 0) in [360, 480, 720, 1080]
            ]

            # Sort by height (resolution)
            video_formats.sort(key=lambda x: x.get("height", 0))

            # Add unique resolutions
            added_resolutions = set()
            for fmt in video_formats:
                height = fmt.get("height", 0)
                if height and height not in added_resolutions:
                    formats.append({
                        "format_id": fmt["format_id"],
                        "ext": fmt.get("ext", "mp4"),
                        "resolution": f"{height}p",
                        "description": f"{height}p ({fmt.get('ext', 'mp4')})"
                    })
                    added_resolutions.add(height)

        return formats

    def _create_format_keyboard(self, url: str, formats: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
        """
        Create an inline keyboard for format selection.

        Args:
            url: Video URL
            formats: List of available formats

        Returns:
            InlineKeyboardMarkup
        """
        keyboard = []

        # Use base64 encoding to safely encode the URL in callback data
        import base64
        encoded_url = base64.b64encode(url.encode('utf-8')).decode('utf-8')

        # Add a button for each format
        for fmt in formats:
            keyboard.append([
                InlineKeyboardButton(
                    text=fmt["description"],
                    callback_data=f"download|{encoded_url}|{fmt['format_id']}"
                )
            ])

        # Add cancel button
        keyboard.append([
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=f"cancel|{encoded_url}"
            )
        ])

        return InlineKeyboardMarkup(keyboard)

    def _is_valid_url(self, url: str) -> bool:
        """
        Check if a URL is valid.

        Args:
            url: URL to check

        Returns:
            True if valid, False otherwise
        """
        # Simple URL validation
        url_pattern = re.compile(
            r'^(?:http|https)://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        return bool(url_pattern.match(url))

    def _format_duration(self, seconds: int) -> str:
        """
        Format duration in seconds to HH:MM:SS.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if not seconds:
            return "Unknown"

        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

    def _escape_markdown(self, text: str) -> str:
        """
        Escape Markdown special characters in text.

        Args:
            text: Text to escape

        Returns:
            Escaped text safe for Markdown parsing
        """
        # Characters that need to be escaped in Markdown v2: _ * [ ] ( ) ~ ` > # + - = | { } . !
        # For Markdown (v1) we need to escape: _ * [ ] ( ) `
        escape_chars = ['_', '*', '[', ']', '(', ')', '`']

        for char in escape_chars:
            text = text.replace(char, f"\\{char}")

        return text

    def _get_directory_size(self, path: str) -> str:
        """
        Get the size of a directory in human-readable format.

        Args:
            path: Directory path

        Returns:
            Size string
        """
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp):
                    total_size += os.path.getsize(fp)

        # Convert to MB or GB
        if total_size > 1024 * 1024 * 1024:
            return f"{total_size / (1024 * 1024 * 1024):.2f} GB"
        else:
            return f"{total_size / (1024 * 1024):.2f} MB"

    def _get_uptime(self) -> str:
        """
        Get bot uptime.

        Returns:
            Uptime string
        """
        if hasattr(self, 'start_time'):
            now = datetime.datetime.now()
            delta = now - self.start_time

            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            parts = []
            if days > 0:
                parts.append(f"{days} day{'s' if days != 1 else ''}")
            if hours > 0:
                parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
            if minutes > 0:
                parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
            if seconds > 0 and not parts:  # Only show seconds if no other parts
                parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

            return ", ".join(parts)
        else:
            return "Since last restart"

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Handle errors in the dispatcher.

        Args:
            update: Update object
            context: Context object
        """
        logger.error(f"Exception while handling an update: {context.error}")

        # Log the error to chat for debugging
        if update and isinstance(update, Update) and update.effective_message:
            error_message = f"❌ An error occurred: {str(context.error)}"
            await update.effective_message.reply_text(error_message)

    def run(self) -> None:
        """Run the bot."""
        # Set up post-init callback to set bot commands
        async def post_init(application: Application) -> None:
            await self._set_bot_commands()

        self.application.post_init = post_init

        # Start the bot
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    def stop(self) -> None:
        """Stop the bot."""
        if self.application:
            # Stop the application
            self.application.stop()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get bot statistics.

        Returns:
            Dictionary containing bot statistics
        """
        try:
            # Load user data
            user_data = self._load_user_data()

            total_users = len(user_data)
            active_users = 0
            total_downloads = 0

            # Calculate statistics
            current_time = datetime.datetime.now()
            for user in user_data:
                downloads = user.get('download_count', 0)
                total_downloads += downloads

                # Check if user was active in last 30 days
                last_activity = user.get('last_activity')
                if last_activity:
                    try:
                        last_activity_date = datetime.datetime.fromisoformat(last_activity)
                        if (current_time - last_activity_date).days <= 30:
                            active_users += 1
                    except:
                        pass

            return {
                'total_users': total_users,
                'active_users': active_users,
                'total_downloads': total_downloads,
                'uptime': (current_time - self.start_time).total_seconds() if hasattr(self, 'start_time') else 0
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'total_users': 0,
                'active_users': 0,
                'total_downloads': 0,
                'uptime': 0
            }

    def get_user_stats(self) -> List[Dict[str, Any]]:
        """
        Get user statistics.

        Returns:
            List of user data dictionaries
        """
        try:
            return self._load_user_data()
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return []

    def _load_user_data(self) -> List[Dict[str, Any]]:
        """Load user data from file."""
        try:
            user_data_file = "bot_users.json"
            if os.path.exists(user_data_file):
                with open(user_data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading user data: {e}")
        return []

    def _save_user_data(self, user_data: List[Dict[str, Any]]) -> None:
        """Save user data to file."""
        try:
            user_data_file = "bot_users.json"
            with open(user_data_file, 'w', encoding='utf-8') as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving user data: {e}")

    def _update_user_activity(self, user_id: int, username: str = None, increment_download: bool = True) -> None:
        """Update user activity in database."""
        try:
            user_data = self._load_user_data()
            current_time = datetime.datetime.now().isoformat()

            # Find existing user or create new one
            user_found = False
            for user in user_data:
                if user.get('user_id') == user_id:
                    user['last_activity'] = current_time
                    if username:
                        user['username'] = username
                    if increment_download:
                        user['download_count'] = user.get('download_count', 0) + 1
                    user_found = True
                    break

            if not user_found:
                # Add new user
                new_user = {
                    'user_id': user_id,
                    'username': username or f"user_{user_id}",
                    'last_activity': current_time,
                    'download_count': 1 if increment_download else 0,
                    'status': 'Aktif'
                }
                user_data.append(new_user)

            self._save_user_data(user_data)
            logger.info(f"User activity updated: {username} (ID: {user_id}) - Download: {increment_download}")
        except Exception as e:
            logger.error(f"Error updating user activity: {e}")

    def update_user_status(self, user_id: int, new_status: str) -> bool:
        """Update user status (for blocking/unblocking)."""
        try:
            user_data = self._load_user_data()
            user_found = False

            for user in user_data:
                if user.get('user_id') == user_id:
                    user['status'] = new_status
                    user_found = True
                    break

            if user_found:
                self._save_user_data(user_data)
                logger.info(f"User {user_id} status updated to {new_status}")
                return True
            else:
                logger.warning(f"User {user_id} not found for status update")
                return False

        except Exception as e:
            logger.error(f"Error updating user status: {e}")
            return False

    def is_user_blocked(self, user_id: int) -> bool:
        """Check if user is blocked."""
        try:
            user_data = self._load_user_data()
            logger.info(f"Checking block status for user {user_id}. Total users in data: {len(user_data)}")

            for user in user_data:
                if user.get('user_id') == user_id:
                    status = user.get('status')
                    is_blocked = status == 'Diblokir'
                    logger.info(f"User {user_id} found with status: {status}, blocked: {is_blocked}")
                    return is_blocked

            logger.info(f"User {user_id} not found in user data, treating as not blocked")
            return False
        except Exception as e:
            logger.error(f"Error checking user block status: {e}")
            return False

    def create_test_blocked_user(self, user_id: int, username: str = "test_user") -> None:
        """Create a test blocked user for debugging purposes."""
        try:
            user_data = self._load_user_data()

            # Remove existing user if exists
            user_data = [user for user in user_data if user.get('user_id') != user_id]

            # Add blocked test user
            blocked_user = {
                'user_id': user_id,
                'username': username,
                'last_activity': datetime.datetime.now().isoformat(),
                'download_count': 0,
                'status': 'Diblokir'
            }
            user_data.append(blocked_user)

            self._save_user_data(user_data)
            logger.info(f"Created test blocked user: {user_id} ({username})")

        except Exception as e:
            logger.error(f"Error creating test blocked user: {e}")

    async def cmd_test_block(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Test command to block current user for testing purposes."""
        user = update.effective_user
        logger.info(f"User {user.id} ({user.username}) used /testblock command")

        # Block the current user for testing
        self.create_test_blocked_user(user.id, user.username or f"user_{user.id}")

        await update.message.reply_text(
            f"✅ User {user.username or user.id} has been blocked for testing.\n"
            f"Try sending any message or command to test the block messages.\n"
            f"Use the admin panel to unblock yourself."
        )

    def integrate_with_main_app(self) -> None:
        """
        Integrate the bot with the main application.

        This method should be called after the bot is initialized
        to set up any necessary connections with the main app.
        """
        if not self.parent_app:
            logger.warning("No parent application provided for integration")
            return

        # Use the parent app's download functionality
        logger.info("Integrating Telegram bot with main application")

def main() -> None:
    """Main function."""
    # Create and run the bot
    bot = TelegramBot()
    bot.run()

if __name__ == "__main__":
    main()
