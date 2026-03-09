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
        Stop the Telegram bot gracefully.

        The correct shutdown sequence for python-telegram-bot is:
          1. Call application.stop() on the SAME event loop the bot runs on
             (NOT a new loop — that causes the Conflict error on next start)
          2. Wait for the bot thread to exit naturally
          3. Only then clear references so the next start gets a clean slate
        """
        if not self.is_running:
            logger.warning("Bot is not running")
            return False

        try:
            self.is_running = False

            # ── Signal the running application to stop via its own event loop ──
            if (self.bot_instance
                    and hasattr(self.bot_instance, "application")
                    and self.bot_instance.application):
                app = self.bot_instance.application
                loop = getattr(app, "_loop", None)   # PTB stores the loop internally
                if loop is None and hasattr(app, "update_queue"):
                    # Fallback: schedule stop via updater
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = None

                if loop and loop.is_running():
                    # Schedule coroutine on the bot's own loop — this is the safe way
                    asyncio.run_coroutine_threadsafe(app.stop(), loop)
                    logger.info("Stop signal sent to bot event loop")
                else:
                    # Loop not available — set a stop flag via updater if possible
                    try:
                        if hasattr(app, "updater") and app.updater:
                            asyncio.run_coroutine_threadsafe(
                                app.updater.stop(), asyncio.get_event_loop()
                            )
                    except Exception:
                        pass

            # ── Wait for the bot thread to finish (up to 10s) ──────────────────
            if self.bot_thread and self.bot_thread.is_alive():
                logger.info("Waiting for bot thread to stop…")
                self.bot_thread.join(timeout=10)
                if self.bot_thread.is_alive():
                    logger.warning("Bot thread still alive after 10s — marking stopped anyway")

            # ── Extra safety delay so Telegram releases the getUpdates slot ────
            import time
            time.sleep(1)

            self.bot_instance = None
            self.bot_thread = None
            logger.info("Telegram bot stopped")
            return True

        except Exception as e:
            logger.error(f"Failed to stop Telegram bot: {e}")
            self.is_running = False
            self.bot_instance = None
            self.bot_thread = None
            return True

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
