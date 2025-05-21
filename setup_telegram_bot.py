#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Setup script for the Modern YouTube Downloader Telegram Bot.
This script updates the config.json file with the Telegram bot token.
"""

import os
import json
import sys

def setup_telegram_bot():
    """Set up the Telegram bot configuration."""
    print("=" * 50)
    print("Modern YouTube Downloader Telegram Bot Setup")
    print("=" * 50)
    print("\nThis script will update your config.json file with Telegram bot settings.\n")

    # Check if config.json exists
    if not os.path.exists('config.json'):
        print("Error: config.json not found. Please run this script from the project root directory.")
        return False

    # Load existing config
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except Exception as e:
        print(f"Error loading config.json: {e}")
        return False

    # Get Telegram bot token
    print("\nYou need a Telegram bot token to use this bot.")
    print("If you don't have one, create a new bot using @BotFather on Telegram.")
    print("Visit: https://t.me/BotFather\n")

    token = input("Enter your Telegram bot token: ").strip()
    if not token:
        print("Error: Bot token cannot be empty.")
        return False

    # Get admin usernames
    print("\nYou can specify admin users who will have access to admin commands.")
    print("Admin users can view logs and statistics.")
    print("Enter Telegram usernames WITHOUT the @ symbol (e.g., 'username' not '@username')")
    admin_input = input("Enter admin Telegram usernames (comma-separated, or leave empty): ").strip()

    admin_users = []
    if admin_input:
        admin_users = [user.strip() for user in admin_input.split(',')]

        # Remove @ symbol if present
        admin_users = [user[1:] if user.startswith('@') else user for user in admin_users]

    # Update config
    config['telegram_bot_token'] = token
    config['admin_users'] = admin_users

    if 'max_downloads_per_user' not in config:
        config['max_downloads_per_user'] = 5

    if 'allowed_formats' not in config:
        config['allowed_formats'] = ["mp4", "mp3", "webm"]

    # Save config
    try:
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=2)
        print("\nConfiguration updated successfully!")
        print("You can now run the bot with: python telegram_bot.py")
        return True
    except Exception as e:
        print(f"Error saving config.json: {e}")
        return False

if __name__ == "__main__":
    success = setup_telegram_bot()
    sys.exit(0 if success else 1)
