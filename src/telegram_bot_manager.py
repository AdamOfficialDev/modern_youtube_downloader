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
            # Stop the bot
            if self.bot_instance:
                asyncio.run_coroutine_threadsafe(self.bot_instance.stop(), self.bot_instance.loop)
                
            # Wait for the thread to finish
            if self.bot_thread and self.bot_thread.is_alive():
                self.bot_thread.join(timeout=5)
                
            self.is_running = False
            self.bot_instance = None
            logger.info("Telegram bot stopped")
            return True
        except Exception as e:
            logger.error(f"Failed to stop Telegram bot: {e}")
            return False
            
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
