#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Telegram Bot Manager for Modern YouTube Downloader
=================================================

This module manages the Telegram bot integration with the main application.
It handles bot initialization, shutdown, and communication with the main app.

Author: Adam Official Dev
"""

import os
import sys
import json
import logging
import threading
import asyncio
from typing import Dict, List, Optional, Union, Any, Tuple

import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

class TelegramBotManager:
    """Manager for the Telegram bot integration with the main application."""

    def __init__(self, parent=None):
        """
        Initialize the Telegram bot manager.

        Args:
            parent: Parent application (ModernVideoDownloader instance)
        """
        self.parent = parent
        self.bot_instance = None
        self.bot_thread = None
        self.is_running = False

    def start_bot(self) -> bool:
        """
        Start the Telegram bot in a separate thread.

        Returns:
            True if the bot was started successfully, False otherwise
        """
        if self.is_running:
            logger.warning("Bot is already running")
            return False

        # Check if token is configured
        if not self.parent or not self.parent.config.get("telegram_bot_token"):
            logger.error("Telegram bot token not configured")
            return False

        try:
            # Record start time
            import datetime
            self.start_time = datetime.datetime.now()

            # Create and start the bot thread
            self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
            self.bot_thread.start()
            self.is_running = True
            logger.info("Telegram bot started")
            return True
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
            return False

    def stop_bot(self) -> bool:
        """
        Stop the Telegram bot.

        Returns:
            True if the bot was stopped successfully, False otherwise
        """
        if not self.is_running:
            logger.warning("Bot is not running")
            return False

        try:
            # Mark as stopping to prevent new operations
            self.is_running = False

            # Stop the bot instance in a non-blocking way
            if self.bot_instance:
                try:
                    # Signal the bot to stop
                    if hasattr(self.bot_instance, 'application') and self.bot_instance.application:
                        # Use a separate thread to stop the application to avoid blocking
                        import threading
                        def stop_application():
                            try:
                                import asyncio
                                # Get the existing event loop from the bot thread
                                if hasattr(self.bot_instance, 'application'):
                                    # Create a new event loop for stopping
                                    loop = asyncio.new_event_loop()
                                    asyncio.set_event_loop(loop)
                                    loop.run_until_complete(self.bot_instance.application.stop())
                                    loop.close()
                            except Exception as e:
                                logger.error(f"Error in stop thread: {e}")

                        stop_thread = threading.Thread(target=stop_application, daemon=True)
                        stop_thread.start()
                        stop_thread.join(timeout=3)  # Wait max 3 seconds

                except Exception as e:
                    logger.error(f"Error stopping bot application: {e}")

            # Wait for the main bot thread to finish
            if self.bot_thread and self.bot_thread.is_alive():
                logger.info("Waiting for bot thread to finish...")
                self.bot_thread.join(timeout=5)  # Reduced timeout to prevent long freeze

                # If still alive, just mark as stopped (don't force kill)
                if self.bot_thread.is_alive():
                    logger.warning("Bot thread did not stop gracefully within timeout, marking as stopped")

            # Clean up
            self.bot_instance = None
            self.bot_thread = None
            logger.info("Telegram bot stopped")
            return True

        except Exception as e:
            logger.error(f"Failed to stop Telegram bot: {e}")
            # Always mark as stopped to prevent stuck state
            self.is_running = False
            self.bot_instance = None
            self.bot_thread = None
            return True  # Return True to indicate we've handled the stop request

    def _run_bot(self) -> None:
        """Run the Telegram bot in a separate thread."""
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Create and run the bot
            from telegram_bot import TelegramBot
            self.bot_instance = TelegramBot(parent_app=self.parent)
            self.bot_instance.run()
        except Exception as e:
            logger.error(f"Error in bot thread: {e}")
            self.is_running = False

    def is_bot_running(self) -> bool:
        """
        Check if the bot is running.

        Returns:
            True if the bot is running, False otherwise
        """
        return self.is_running
