#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Modern YouTube Downloader Telegram Bot — Enhanced Edition
==========================================================

A comprehensive, production-grade Telegram bot for downloading videos
from YouTube and 1000+ other platforms via yt-dlp.

New in Enhanced Edition:
  - Async download queue with worker pool
  - Real-time progress tracking with live message updates
  - Rate limiting (per-user & global)
  - Playlist/channel download support
  - User preferences (quality, format, audio-only mode)
  - Admin broadcast, ban/unban with reason & duration
  - Rich admin dashboard with inline controls
  - Decorator-based middleware (auth, block check, rate limit)
  - Graceful shutdown & cleanup
  - Structured logging with rotation
  - Pydantic-validated config
  - Full type hints throughout

Author : Adam Official Dev
Version: 2.0.0
Python : 3.11+
"""

from __future__ import annotations

import asyncio
import base64
import datetime
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

import yt_dlp
from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ─────────────────────────────── Logging Setup ────────────────────────────────

def _setup_logging() -> logging.Logger:
    """Configure rotating file + stream logging."""
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt)

    file_handler = RotatingFileHandler(
        "bot_logs.log", maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    # Force UTF-8 on Windows console — prevents UnicodeEncodeError for non-ASCII filenames
    import io
    _stdout = (io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
               if hasattr(sys.stdout, "buffer") else sys.stdout)
    stream_handler = logging.StreamHandler(_stdout)
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)

    return logging.getLogger(__name__)


logger = _setup_logging()

# ──────────────────────────────── Constants ───────────────────────────────────

CONFIG_FILE = Path("config.json")
USERS_FILE = Path("bot_users.json")
HISTORY_FILE = Path("download_history.json")
DEFAULT_DOWNLOAD_DIR = Path("downloads")
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024
DOWNLOAD_TIMEOUT = 900          # 15 minutes
QUEUE_WORKER_COUNT = 3          # Concurrent download workers
RATE_LIMIT_WINDOW = 60          # seconds
RATE_LIMIT_MAX_REQUESTS = 10    # per window per user
PROGRESS_UPDATE_INTERVAL = 3.0  # seconds between progress edits
SUPPORTED_PLATFORMS = [
    "YouTube", "TikTok", "Instagram", "Twitter/X", "Facebook",
    "Vimeo", "Dailymotion", "Twitch", "Reddit", "SoundCloud",
    "Bilibili", "NicoNico", "Odysee", "Rumble", "+1000 more",
]


# ──────────────────────────────── Enums / Types ───────────────────────────────

class DownloadStatus(str, Enum):
    QUEUED = "queued"
    FETCHING_INFO = "fetching_info"
    SELECTING_FORMAT = "selecting_format"
    DOWNLOADING = "downloading"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UserStatus(str, Enum):
    ACTIVE = "active"
    BANNED = "banned"
    PREMIUM = "premium"


class QualityPreset(str, Enum):
    BEST = "best"
    HIGH = "1080p"
    MEDIUM = "720p"
    LOW = "480p"
    LOWEST = "360p"
    AUDIO_ONLY = "audio"


# ─────────────────────────────── Data Models ──────────────────────────────────

@dataclass
class UserPreferences:
    """Per-user download preferences."""
    quality: QualityPreset = QualityPreset.BEST
    audio_format: str = "mp3"
    audio_quality: str = "192"
    auto_send_as_doc: bool = False
    notification_on_complete: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quality": self.quality.value,
            "audio_format": self.audio_format,
            "audio_quality": self.audio_quality,
            "auto_send_as_doc": self.auto_send_as_doc,
            "notification_on_complete": self.notification_on_complete,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserPreferences":
        return cls(
            quality=QualityPreset(data.get("quality", QualityPreset.BEST.value)),
            audio_format=data.get("audio_format", "mp3"),
            audio_quality=data.get("audio_quality", "192"),
            auto_send_as_doc=data.get("auto_send_as_doc", False),
            notification_on_complete=data.get("notification_on_complete", True),
        )


# Migration map lives at module level — safe from dataclass mutable-default restriction
_USER_STATUS_MIGRATION: Dict[str, str] = {
    "Aktif": "active",    "aktif": "active",    "AKTIF": "active",
    "Diblokir": "banned", "diblokir": "banned", "DIBLOKIR": "banned",
    "blocked": "banned",  "Blocked": "banned",
    "Premium": "premium",
}


@dataclass
class UserRecord:
    """User database record."""
    user_id: int
    username: str
    first_name: str
    status: UserStatus = UserStatus.ACTIVE
    download_count: int = 0
    total_bytes: int = 0
    joined_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    last_activity: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    ban_reason: Optional[str] = None
    ban_until: Optional[str] = None      # ISO datetime or None (permanent)
    preferences: UserPreferences = field(default_factory=UserPreferences)

    def is_banned(self) -> bool:
        if self.status != UserStatus.BANNED:
            return False
        # Check if temporary ban has expired
        if self.ban_until:
            try:
                expiry = datetime.datetime.fromisoformat(self.ban_until)
                if datetime.datetime.now() >= expiry:
                    self.status = UserStatus.ACTIVE
                    self.ban_reason = None
                    self.ban_until = None
                    return False
            except ValueError:
                pass
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "first_name": self.first_name,
            "status": self.status.value,
            "download_count": self.download_count,
            "total_bytes": self.total_bytes,
            "joined_at": self.joined_at,
            "last_activity": self.last_activity,
            "ban_reason": self.ban_reason,
            "ban_until": self.ban_until,
            "preferences": self.preferences.to_dict(),
        }

    @classmethod
    def _resolve_status(cls, raw: str) -> UserStatus:
        """Resolve status string, migrating legacy Indonesian values gracefully."""
        normalized = _USER_STATUS_MIGRATION.get(raw, raw)
        try:
            return UserStatus(normalized)
        except ValueError:
            logger.warning("Unknown UserStatus value %r -- defaulting to active", raw)
            return UserStatus.ACTIVE

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserRecord":
        return cls(
            user_id=data["user_id"],
            username=data.get("username", ""),
            first_name=data.get("first_name", ""),
            status=cls._resolve_status(data.get("status", UserStatus.ACTIVE.value)),
            download_count=data.get("download_count", 0),
            total_bytes=data.get("total_bytes", 0),
            joined_at=data.get("joined_at", datetime.datetime.now().isoformat()),
            last_activity=data.get("last_activity", datetime.datetime.now().isoformat()),
            ban_reason=data.get("ban_reason"),
            ban_until=data.get("ban_until"),
            preferences=UserPreferences.from_dict(data.get("preferences", {})),
        )


@dataclass
class DownloadTask:
    """A single download job in the queue."""
    task_id: str
    user_id: int
    chat_id: int
    message_id: int           # status message to edit
    url: str
    format_id: str
    extract_audio: bool
    title: str = ""
    status: DownloadStatus = DownloadStatus.QUEUED
    progress_pct: float = 0.0
    speed_str: str = ""
    eta_str: str = ""
    file_size_str: str = ""
    error_msg: str = ""
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None


# ─────────────────────────────── Config ───────────────────────────────────────

class BotConfig:
    """
    Configuration manager backed by JSON.
    Falls back gracefully to env variables for the bot token.
    """

    _DEFAULTS: Dict[str, Any] = {
        "telegram_bot_token": "",
        "admin_user_ids": [],            # List[int]  (preferred — IDs, not usernames)
        "admin_users": [],               # List[str]  (legacy username list, still supported)
        "max_concurrent_per_user": 2,
        "max_queue_size": 50,
        "allowed_formats": ["mp4", "mp3", "webm", "mkv"],
        "download_dir": str(DEFAULT_DOWNLOAD_DIR),
        "cleanup_after_send": True,
        "max_playlist_items": 25,
        "youtube_api_key": "",
        "rate_limit_enabled": True,
        "rate_limit_requests": RATE_LIMIT_MAX_REQUESTS,
        "rate_limit_window": RATE_LIMIT_WINDOW,
        "welcome_message": "",
        "maintenance_mode": False,
        "maintenance_message": "🛠️ Bot sedang dalam maintenance. Silakan coba lagi nanti.",
    }

    def __init__(self, config_file: Path = CONFIG_FILE, parent_app: Any = None) -> None:
        self.config_file = config_file
        self.parent_app = parent_app
        self._data: Dict[str, Any] = self._load()

    # ── private ──────────────────────────────────────────────────────────────

    def _load(self) -> Dict[str, Any]:
        """Load config from parent app, file, or create defaults."""
        if self.parent_app and hasattr(self.parent_app, "config"):
            data = {**self._DEFAULTS, **self.parent_app.config}
        elif self.config_file.exists():
            try:
                with self.config_file.open("r", encoding="utf-8") as fh:
                    data = {**self._DEFAULTS, **json.load(fh)}
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("Config load failed: %s — using defaults", exc)
                data = dict(self._DEFAULTS)
        else:
            data = dict(self._DEFAULTS)
            self._write(data)

        # Env override for token
        data["telegram_bot_token"] = (
            os.environ.get("TELEGRAM_BOT_TOKEN") or data.get("telegram_bot_token", "")
        )
        return data

    def _write(self, data: Dict[str, Any]) -> None:
        try:
            self.config_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:
            logger.error("Config write failed: %s", exc)

    # ── public ───────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._write(self._data)
        if self.parent_app and hasattr(self.parent_app, "config"):
            self.parent_app.config[key] = value

    def is_admin(self, user_id: int, username: Optional[str] = None) -> bool:
        """Check admin by ID (preferred) or legacy username.

        Converts IDs to int before comparison — JSON may deserialise them as
        strings if they were saved that way by an older version of the GUI.
        """
        raw_ids = self._data.get("admin_user_ids", [])
        # Coerce every entry to int — silently skip anything non-numeric
        admin_ids: List[int] = []
        for entry in raw_ids:
            try:
                admin_ids.append(int(entry))
            except (ValueError, TypeError):
                pass

        admin_names: List[str] = self._data.get("admin_users", [])
        if user_id in admin_ids:
            return True
        if username and username in admin_names:
            return True
        return False


# ──────────────────────────── User Database ───────────────────────────────────

class UserDatabase:
    """
    Simple JSON-backed user store.
    Uses an in-memory dict keyed by user_id for fast lookups.
    """

    def __init__(self, file: Path = USERS_FILE) -> None:
        self.file = file
        self._db: Dict[int, UserRecord] = {}
        self._load()

    # ── private ──────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self.file.exists():
            try:
                raw: List[Dict[str, Any]] = json.loads(
                    self.file.read_text(encoding="utf-8")
                )
                self._db = {r["user_id"]: UserRecord.from_dict(r) for r in raw}
                logger.info("Loaded %d users from database", len(self._db))
            except (json.JSONDecodeError, KeyError, OSError) as exc:
                logger.error("User DB load error: %s", exc)

    def _save(self) -> None:
        try:
            data = [rec.to_dict() for rec in self._db.values()]
            self.file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:
            logger.error("User DB save error: %s", exc)

    # ── public ───────────────────────────────────────────────────────────────

    def get_or_create(self, user_id: int, username: str, first_name: str) -> UserRecord:
        if user_id not in self._db:
            self._db[user_id] = UserRecord(
                user_id=user_id, username=username, first_name=first_name
            )
            self._save()
            logger.info("New user registered: %s (ID: %d)", username, user_id)
        return self._db[user_id]

    def get(self, user_id: int) -> Optional[UserRecord]:
        return self._db.get(user_id)

    def touch(self, user_id: int, username: str, first_name: str) -> None:
        rec = self.get_or_create(user_id, username, first_name)
        rec.last_activity = datetime.datetime.now().isoformat()
        rec.username = username
        rec.first_name = first_name
        self._save()

    def increment_downloads(self, user_id: int, file_bytes: int = 0) -> None:
        if rec := self._db.get(user_id):
            rec.download_count += 1
            rec.total_bytes += file_bytes
            self._save()

    def ban(
        self,
        user_id: int,
        reason: str = "No reason given",
        duration_hours: Optional[int] = None,
    ) -> bool:
        if rec := self._db.get(user_id):
            rec.status = UserStatus.BANNED
            rec.ban_reason = reason
            rec.ban_until = (
                (datetime.datetime.now() + datetime.timedelta(hours=duration_hours)).isoformat()
                if duration_hours
                else None
            )
            self._save()
            return True
        return False

    def unban(self, user_id: int) -> bool:
        if rec := self._db.get(user_id):
            rec.status = UserStatus.ACTIVE
            rec.ban_reason = None
            rec.ban_until = None
            self._save()
            return True
        return False

    def is_banned(self, user_id: int) -> bool:
        rec = self._db.get(user_id)
        return rec.is_banned() if rec else False

    def all_users(self) -> List[UserRecord]:
        return list(self._db.values())

    def stats(self) -> Dict[str, Any]:
        all_recs = self.all_users()
        now = datetime.datetime.now()
        cutoff_30d = now - datetime.timedelta(days=30)
        active_30d = sum(
            1 for r in all_recs
            if datetime.datetime.fromisoformat(r.last_activity) >= cutoff_30d
        )
        return {
            "total": len(all_recs),
            "active_30d": active_30d,
            "banned": sum(1 for r in all_recs if r.status == UserStatus.BANNED),
            "premium": sum(1 for r in all_recs if r.status == UserStatus.PREMIUM),
            "total_downloads": sum(r.download_count for r in all_recs),
            "total_bytes": sum(r.total_bytes for r in all_recs),
        }


# ────────────────────────────── Rate Limiter ──────────────────────────────────

class RateLimiter:
    """
    Token-bucket-style per-user rate limiter using a sliding window.
    Thread-safe for asyncio (single-threaded event loop).
    """

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window = window_seconds
        self._windows: Dict[int, Deque[float]] = defaultdict(deque)

    def is_allowed(self, user_id: int) -> Tuple[bool, int]:
        """
        Returns (allowed, retry_after_seconds).
        retry_after is 0 when allowed.
        """
        now = time.monotonic()
        window_start = now - self.window
        dq = self._windows[user_id]

        # Remove old timestamps
        while dq and dq[0] < window_start:
            dq.popleft()

        if len(dq) >= self.max_requests:
            retry_after = int(self.window - (now - dq[0])) + 1
            return False, retry_after

        dq.append(now)
        return True, 0


# ──────────────────────────── Download Manager ────────────────────────────────

class DownloadManager:
    """
    Handles yt-dlp operations: info fetching and downloading.
    All public methods are async-friendly (run blocking I/O in executor).
    """

    # Base yt-dlp options shared across calls
    _BASE_OPTS: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "no_color": True,
        "geo_bypass": True,
        "retries": 5,
        "fragment_retries": 5,
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, download_dir: Path = DEFAULT_DOWNLOAD_DIR) -> None:
        self.download_dir = download_dir
        self.download_dir.mkdir(parents=True, exist_ok=True)

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_opts(extra: Dict[str, Any]) -> Dict[str, Any]:
        return {**DownloadManager._BASE_OPTS, **extra}

    @staticmethod
    def _tiktok_args() -> Dict[str, Any]:
        return {
            "extractor_args": {
                "tiktok": {
                    "api_hostname": "api16-normal-c-useast1a.tiktokv.com",
                }
            }
        }

    # ── public API ───────────────────────────────────────────────────────────

    async def get_video_info(self, url: str) -> Dict[str, Any]:
        """
        Fetch video metadata without downloading.

        Raises:
            ValueError: if info extraction fails completely.
        """
        opts = self._build_opts({"skip_download": True, "extract_flat": False})
        if "tiktok.com" in url:
            opts.update(self._tiktok_args())

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._extract_info_sync, url, opts)

    def _extract_info_sync(self, url: str, opts: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise ValueError("No info returned by yt-dlp")
                return info
        except yt_dlp.utils.DownloadError as exc:
            logger.warning("Primary extraction failed for %s: %s", url, exc)
            # Fallback: generic extractor
            opts_fb = {**opts, "force_generic_extractor": True}
            with yt_dlp.YoutubeDL(opts_fb) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise ValueError("Generic extractor returned no info")
                return info

    async def download_video(
        self,
        url: str,
        format_id: str = "best",
        extract_audio: bool = False,
        progress_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
        max_playlist_items: int = 1,
    ) -> Tuple[List[Path], str]:
        """
        Download video/audio to a temp dir then move to download_dir.

        Returns:
            (list_of_file_paths, title)
        Raises:
            Exception: on download failure.
        """
        temp_dir = Path(tempfile.mkdtemp())
        try:
            outtmpl = str(temp_dir / "%(title).100s.%(ext)s")

            if extract_audio:
                fmt = "bestaudio/best"
                postprocessors: List[Dict[str, Any]] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            else:
                fmt = format_id
                postprocessors = []

            extra: Dict[str, Any] = {
                "format": fmt,
                "outtmpl": outtmpl,
                "noplaylist": max_playlist_items == 1,
                "playlistend": max_playlist_items,
                "merge_output_format": "mp4",
                "verbose": False,
            }
            if postprocessors:
                extra["postprocessors"] = postprocessors
            if progress_hook:
                extra["progress_hooks"] = [progress_hook]
            if "tiktok.com" in url:
                extra.update(self._tiktok_args())

            opts = self._build_opts(extra)
            loop = asyncio.get_running_loop()
            title = await loop.run_in_executor(
                None, self._download_sync, url, opts, temp_dir
            )

            # Move files to permanent location
            files: List[Path] = []
            for f in temp_dir.iterdir():
                if f.is_file():
                    dest = self.download_dir / f.name
                    shutil.move(str(f), str(dest))
                    files.append(dest)
                    logger.info("Saved: %s", dest)

            if not files:
                raise FileNotFoundError("No output files found after download")

            return files, title
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _download_sync(self, url: str, opts: Dict[str, Any], temp_dir: Path) -> str:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return info.get("title", "video") if info else "video"

    # ── format helpers ────────────────────────────────────────────────────────

    @staticmethod
    def get_available_formats(info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build a curated list of selectable formats from raw yt-dlp info."""
        formats: List[Dict[str, Any]] = []

        # Always offer best + audio options
        formats.append({
            "format_id": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "ext": "mp4",
            "resolution": "🏆 Best",
            "label": "🏆 Best Quality (MP4)",
        })
        formats.append({
            "format_id": "bestaudio/best",
            "ext": "mp3",
            "resolution": "🎵 Audio",
            "label": "🎵 Audio Only (MP3)",
            "is_audio": True,
        })

        if "formats" not in info:
            return formats

        seen_heights: set = set()
        target_heights = [2160, 1440, 1080, 720, 480, 360]
        icons = {2160: "4K", 1440: "2K", 1080: "HD", 720: "HD", 480: "SD", 360: "SD"}

        # Collect video-only streams and combine with audio
        for height in target_heights:
            matching = [
                f for f in info["formats"]
                if f.get("height") == height
                and f.get("vcodec", "none") not in ("none", None)
            ]
            if not matching:
                continue
            best = max(matching, key=lambda x: x.get("tbr", 0) or 0)
            label_tag = icons.get(height, "")
            formats.append({
                "format_id": f"bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={height}]",
                "ext": "mp4",
                "resolution": f"{height}p",
                "label": f"{'📺' if height >= 1080 else '📹'} {height}p {label_tag}",
                "filesize": best.get("filesize") or best.get("filesize_approx", 0),
            })
            seen_heights.add(height)

        return formats


# ───────────────────────── Async Download Queue ───────────────────────────────

class DownloadQueue:
    """
    A bounded async queue with multiple worker coroutines.
    Dispatches DownloadTask objects and updates their status live.
    """

    def __init__(self, manager: DownloadManager, num_workers: int = QUEUE_WORKER_COUNT) -> None:
        self.manager = manager
        self.num_workers = num_workers
        self._queue: asyncio.Queue[DownloadTask] = asyncio.Queue(maxsize=50)
        self._tasks: Dict[str, DownloadTask] = {}
        self._bot_app: Optional[Application] = None
        self._workers: List[asyncio.Task] = []
        self._running = False

    def set_app(self, app: Application) -> None:
        self._bot_app = app

    async def start(self) -> None:
        self._running = True
        for i in range(self.num_workers):
            t = asyncio.create_task(self._worker(i), name=f"dl-worker-{i}")
            self._workers.append(t)
        logger.info("Download queue started with %d workers", self.num_workers)

    async def stop(self) -> None:
        self._running = False
        for t in self._workers:
            t.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        logger.info("Download queue stopped")

    async def enqueue(self, task: DownloadTask) -> bool:
        """Returns True if successfully queued, False if queue full."""
        if self._queue.full():
            return False
        self._tasks[task.task_id] = task
        await self._queue.put(task)
        return True

    def get_task(self, task_id: str) -> Optional[DownloadTask]:
        return self._tasks.get(task_id)

    def user_task_count(self, user_id: int) -> int:
        return sum(
            1 for t in self._tasks.values()
            if t.user_id == user_id
            and t.status not in (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED)
        )

    async def _worker(self, worker_id: int) -> None:
        logger.info("Worker %d started", worker_id)
        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                await self._process_task(task)
            except Exception as exc:
                logger.exception("Worker %d: unhandled error on task %s: %s", worker_id, task.task_id, exc)
                task.status = DownloadStatus.FAILED
                task.error_msg = str(exc)
            finally:
                self._queue.task_done()

        logger.info("Worker %d stopped", worker_id)

    async def _process_task(self, task: DownloadTask) -> None:
        """Core download & upload logic for a single task."""
        assert self._bot_app is not None, "Bot app not set on queue"
        bot = self._bot_app.bot

        async def edit_status(text: str) -> None:
            """
            Edit the status message whether it's a text or photo/media message.
            The user might have selected a format from a photo (thumbnail) message,
            so we must handle both edit_message_text and edit_message_caption.
            """
            try:
                await bot.edit_message_text(
                    chat_id=task.chat_id,
                    message_id=task.message_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as exc:
                err = str(exc).lower()
                if "there is no text" in err or "message has no text" in err:
                    # It's a photo/media message — use edit_message_caption instead
                    try:
                        await bot.edit_message_caption(
                            chat_id=task.chat_id,
                            message_id=task.message_id,
                            caption=text,
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass  # Caption edit also failed — message may be deleted
                elif "message is not modified" in err:
                    pass  # Harmless
                # All other errors (message deleted, etc.) are silently ignored

        last_progress_update = 0.0

        # Capture the running event loop HERE, in the async context (main thread).
        # progress_hook is called from a ThreadPoolExecutor thread where
        # asyncio.get_event_loop() raises RuntimeError in Python 3.10+.
        # Passing the loop explicitly via closure is the correct pattern.
        _loop = asyncio.get_running_loop()

        def progress_hook(d: Dict[str, Any]) -> None:
            """Called by yt-dlp from a worker thread — must not call async directly."""
            nonlocal last_progress_update
            if d.get("status") != "downloading":
                return
            now = time.monotonic()
            if now - last_progress_update < PROGRESS_UPDATE_INTERVAL:
                return
            last_progress_update = now

            pct = 0.0
            downloaded = d.get("downloaded_bytes", 0) or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            if total:
                pct = min(downloaded / total * 100, 100)

            speed = (d.get("_speed_str") or "").strip()
            eta   = (d.get("_eta_str")   or "").strip()
            task.progress_pct = pct
            task.speed_str = speed
            task.eta_str   = eta

            bar_filled = int(pct / 5)
            bar = "█" * bar_filled + "░" * (20 - bar_filled)
            progress_text = (
                f"⏬ <b>Downloading...</b>\n\n"
                f"📹 {_esc(task.title or 'Video')}\n\n"
                f"<code>[{bar}]</code> {pct:.1f}%\n"
                f"⚡ {speed}  ⏱ ETA: {eta}"
            )
            # Schedule coroutine safely from a non-async thread using the
            # captured loop — this is the only thread-safe way to bridge
            # sync→async in Python 3.10+
            asyncio.run_coroutine_threadsafe(edit_status(progress_text), _loop)

        task.status = DownloadStatus.DOWNLOADING
        await edit_status(
            f"⏬ <b>Download dimulai...</b>\n\n"
            f"📹 {_esc(task.title or task.url)}\n"
            f"<code>[░░░░░░░░░░░░░░░░░░░░]</code> 0%"
        )

        try:
            files, title = await asyncio.wait_for(
                self.manager.download_video(
                    url=task.url,
                    format_id=task.format_id,
                    extract_audio=task.extract_audio,
                    progress_hook=progress_hook,
                ),
                timeout=DOWNLOAD_TIMEOUT,
            )
        except asyncio.TimeoutError:
            task.status = DownloadStatus.FAILED
            task.error_msg = "Download timeout (15 menit)"
            await edit_status(f"❌ <b>Timeout:</b> Download melebihi batas waktu 15 menit.")
            return

        task.title = title
        task.status = DownloadStatus.UPLOADING
        await edit_status(f"📤 <b>Mengupload ke Telegram...</b>\n\n📹 {_esc(title)}")

        success_count = 0
        for file_path in files:
            try:
                await self._send_file(bot, task, file_path, title)
                success_count += 1
                if self._bot_app.bot_data.get("config", BotConfig()).get("cleanup_after_send", True):
                    try:
                        file_path.unlink(missing_ok=True)
                    except OSError:
                        pass
            except Exception as exc:
                # _send_file already retried internally — this is a genuine final failure
                logger.error("Failed to send %s after retries: %s", file_path.name, exc)
                try:
                    await bot.send_message(
                        chat_id=task.chat_id,
                        text=(
                            "❌ <b>Gagal mengirim file setelah beberapa percobaan</b>\n\n"
                            f"📁 {_esc(file_path.name)}\n"
                            f"⚠️ {_esc(str(exc)[:200])}"
                        ),
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    pass

        if success_count > 0:
            task.status = DownloadStatus.COMPLETED
            task.completed_at = time.time()
            await edit_status(
                f"✅ <b>Selesai!</b>\n\n"
                f"📹 {_esc(title)}\n"
                f"{'🎵' if task.extract_audio else '🎬'} {success_count} file dikirim."
            )
        else:
            task.status = DownloadStatus.FAILED
            await edit_status("❌ <b>Gagal mengirim semua file.</b>")

    async def _send_file(
        self, bot: Any, task: DownloadTask, file_path: Path, title: str
    ) -> None:
        """Send file with automatic retry on timeout (up to 3 attempts)."""
        if not file_path.exists():
            raise FileNotFoundError(f"File tidak ada: {file_path}")

        file_size = file_path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            size_mb = file_size / 1024 / 1024
            msg = (
                "<b>⚠️ File terlalu besar untuk Telegram</b>\n\n"
                f"📁 Ukuran: {size_mb:.1f} MB\n"
                f"📏 Batas: {MAX_FILE_SIZE_MB} MB\n\n"
                "💡 Coba pilih kualitas lebih rendah."
            )
            await bot.send_message(
                chat_id=task.chat_id, text=msg, parse_mode=ParseMode.HTML,
            )
            return

        ext = file_path.suffix.lower()
        icon = "🎵" if task.extract_audio else "🎬"
        caption = f"{icon} <b>{_esc(title)}</b>\n<i>via Modern YouTube Downloader Bot</i>"

        async def _attempt() -> None:
            with file_path.open("rb") as fh:
                if task.extract_audio or ext in (".mp3", ".m4a", ".ogg", ".flac", ".wav"):
                    await bot.send_audio(
                        chat_id=task.chat_id, audio=fh,
                        title=title[:64], caption=caption, parse_mode=ParseMode.HTML,
                    )
                elif ext in (".mp4", ".mov", ".m4v", ".webm"):
                    try:
                        await bot.send_video(
                            chat_id=task.chat_id, video=fh, caption=caption,
                            parse_mode=ParseMode.HTML, supports_streaming=True,
                        )
                    except Exception:
                        fh.seek(0)
                        await bot.send_document(
                            chat_id=task.chat_id, document=fh,
                            filename=file_path.name, caption=caption,
                            parse_mode=ParseMode.HTML,
                        )
                else:
                    await bot.send_document(
                        chat_id=task.chat_id, document=fh,
                        filename=file_path.name, caption=caption,
                        parse_mode=ParseMode.HTML,
                    )

        last_exc: Exception = RuntimeError("No attempts made")
        for attempt in range(1, 4):
            try:
                await _attempt()
                return
            except Exception as exc:
                last_exc = exc
                is_transient = any(
                    t in str(exc).lower()
                    for t in ("timed out", "timeout", "network", "connection")
                )
                if is_transient and attempt < 3:
                    wait = 2 ** attempt
                    logger.warning("Upload timeout (attempt %d/3), retry in %ds", attempt, wait)
                    await asyncio.sleep(wait)
                    continue
                raise

        raise last_exc


# ─────────────────────────────── Utilities ────────────────────────────────────

def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _fmt_duration(seconds: Optional[int]) -> str:
    if not seconds:
        return "—"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def _fmt_bytes(num_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024:
            return f"{num_bytes:.1f} {unit}"
        num_bytes //= 1024
    return f"{num_bytes} PB"


def _is_valid_url(url: str) -> bool:
    return bool(re.match(
        r"^https?://"
        r"(?:[A-Z0-9](?:[A-Z0-9\-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,}"
        r"(?::\d+)?(?:/[^\s]*)?$",
        url,
        re.IGNORECASE,
    ))


def _make_task_id(user_id: int) -> str:
    import uuid
    return f"{user_id}-{uuid.uuid4().hex[:8]}"


# ──────────────────────────── Middleware Decorators ───────────────────────────

def require_not_banned(func: Callable) -> Callable:
    """Decorator: reject banned users before entering the handler."""
    @wraps(func)
    async def wrapper(self: "TelegramBot", update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if user and self.user_db.is_banned(user.id):
            rec = self.user_db.get(user.id)
            reason = (rec.ban_reason or "Tidak ada alasan.") if rec else "—"
            ban_until = (
                f"\n⏰ Sampai: {rec.ban_until[:10]}" if rec and rec.ban_until else "\n⛔ Permanen"
            ) if rec else ""
            await update.effective_message.reply_text(
                f"🚫 <b>Akun Anda diblokir</b>\n\n"
                f"📋 Alasan: {_esc(reason)}{ban_until}\n\n"
                f"Hubungi administrator untuk mengajukan banding.",
                parse_mode=ParseMode.HTML,
            )
            return
        await func(self, update, context)
    return wrapper


def require_admin(func: Callable) -> Callable:
    """Decorator: only allow admins."""
    @wraps(func)
    async def wrapper(self: "TelegramBot", update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        if not user or not self.config.is_admin(user.id, user.username):
            await update.effective_message.reply_text(
                "⛔ Perintah ini hanya untuk administrator.", parse_mode=ParseMode.HTML
            )
            return
        await func(self, update, context)
    return wrapper


def rate_limited(func: Callable) -> Callable:
    """Decorator: enforce per-user rate limit."""
    @wraps(func)
    async def wrapper(self: "TelegramBot", update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self.config.get("rate_limit_enabled", True):
            await func(self, update, context)
            return
        user = update.effective_user
        if not user:
            await func(self, update, context)
            return
        allowed, retry_after = self.rate_limiter.is_allowed(user.id)
        if not allowed:
            await update.effective_message.reply_text(
                f"⏳ <b>Terlalu banyak permintaan.</b>\n"
                f"Coba lagi dalam {retry_after} detik.",
                parse_mode=ParseMode.HTML,
            )
            return
        await func(self, update, context)
    return wrapper


def maintenance_check(func: Callable) -> Callable:
    """Decorator: block all non-admin commands during maintenance."""
    @wraps(func)
    async def wrapper(self: "TelegramBot", update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if self.config.get("maintenance_mode", False):
            user = update.effective_user
            if user and self.config.is_admin(user.id, user.username):
                await func(self, update, context)
                return
            msg = self.config.get("maintenance_message", "🛠️ Bot dalam maintenance.")
            await update.effective_message.reply_text(msg, parse_mode=ParseMode.HTML)
            return
        await func(self, update, context)
    return wrapper


# ─────────────────────────────── Main Bot ─────────────────────────────────────

class TelegramBot:
    """
    Main Telegram bot controller.

    Responsibilities:
      - Register all command/message/callback handlers
      - Coordinate between UserDatabase, DownloadQueue, RateLimiter, BotConfig
      - Implement all command business logic
    """

    # ── init ─────────────────────────────────────────────────────────────────

    def __init__(self, parent_app: Any = None) -> None:
        self.parent_app = parent_app
        self.config = BotConfig(parent_app=parent_app)
        self.user_db = UserDatabase()
        self.dl_manager = DownloadManager(Path(self.config.get("download_dir", str(DEFAULT_DOWNLOAD_DIR))))
        self.dl_queue = DownloadQueue(self.dl_manager)
        # Maps chat_id -> prompt message_id for pending broadcast prompts
        self._broadcast_prompts: Dict[int, int] = {}
        self.rate_limiter = RateLimiter(
            max_requests=self.config.get("rate_limit_requests", RATE_LIMIT_MAX_REQUESTS),
            window_seconds=self.config.get("rate_limit_window", RATE_LIMIT_WINDOW),
        )
        self.start_time = datetime.datetime.now()

        token = self.config.get("telegram_bot_token", "")
        if not token:
            raise ValueError(
                "Telegram bot token tidak ditemukan. "
                "Set di config.json atau env var TELEGRAM_BOT_TOKEN."
            )

        self.application = (
            Application.builder()
            .token(token)
            .read_timeout(60)
            .write_timeout(300)   # 5 min for large file uploads
            .connect_timeout(30)
            .pool_timeout(30)
            .build()
        )
        self.application.bot_data["config"] = self.config
        self._register_handlers()
        logger.info("TelegramBot v2.0.0 initialized")

    # ── handler registration ──────────────────────────────────────────────────

    def _register_handlers(self) -> None:
        app = self.application

        # User commands
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("about", self.cmd_about))
        app.add_handler(CommandHandler("menu", self.cmd_menu))
        app.add_handler(CommandHandler("download", self.cmd_download))
        app.add_handler(CommandHandler("audio", self.cmd_audio))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("history", self.cmd_history))
        app.add_handler(CommandHandler("settings", self.cmd_settings))
        app.add_handler(CommandHandler("cancel", self.cmd_cancel))
        app.add_handler(CommandHandler("formats", self.cmd_formats))

        # Admin commands
        app.add_handler(CommandHandler("admin", self.cmd_admin_panel))
        app.add_handler(CommandHandler("stats", self.cmd_stats))
        app.add_handler(CommandHandler("ban", self.cmd_ban))
        app.add_handler(CommandHandler("unban", self.cmd_unban))
        app.add_handler(CommandHandler("broadcast", self.cmd_broadcast))
        app.add_handler(CommandHandler("logs", self.cmd_logs))
        app.add_handler(CommandHandler("maintenance", self.cmd_maintenance))
        app.add_handler(CommandHandler("users", self.cmd_users))

        # Message handler (auto-detect URLs)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        # Callback query handler
        app.add_handler(CallbackQueryHandler(self.handle_callback))

        # Error handler
        app.add_error_handler(self.error_handler)

    async def _post_init(self, application: Application) -> None:
        """Called after Application starts — set bot commands & start queue."""
        await self._set_bot_commands()
        self.dl_queue.set_app(application)
        await self.dl_queue.start()
        logger.info("Post-init complete")

    async def _post_shutdown(self, application: Application) -> None:
        """Graceful shutdown: stop queue workers."""
        await self.dl_queue.stop()
        logger.info("Bot shutdown complete")

    async def _set_bot_commands(self) -> None:
        commands = [
            BotCommand("start", "Mulai bot 🚀"),
            BotCommand("download", "Download video 📹"),
            BotCommand("audio", "Download audio 🎵"),
            BotCommand("formats", "Lihat format tersedia 📋"),
            BotCommand("status", "Status download aktif 📊"),
            BotCommand("history", "Riwayat download 📜"),
            BotCommand("settings", "Preferensi saya ⚙️"),
            BotCommand("cancel", "Batalkan download ❌"),
            BotCommand("help", "Bantuan 📖"),
            BotCommand("about", "Tentang bot ℹ️"),
        ]
        try:
            await self.application.bot.set_my_commands(commands)
        except Exception as exc:
            logger.warning("Could not set bot commands: %s", exc)

    # ── keyboards ─────────────────────────────────────────────────────────────

    @staticmethod
    def _main_keyboard() -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            [
                [KeyboardButton("📥 Download Video"), KeyboardButton("🎵 Download Audio")],
                [KeyboardButton("📊 Status"), KeyboardButton("⚙️ Settings")],
                [KeyboardButton("📜 History"), KeyboardButton("ℹ️ Help")],
            ],
            resize_keyboard=True,
        )

    # ── common guard helpers ───────────────────────────────────────────────────

    def _touch_user(self, update: Update) -> None:
        user = update.effective_user
        if user:
            self.user_db.touch(user.id, user.username or "", user.first_name or "")

    # ═══════════════════════════════════════════════════════════════════════
    # USER COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    @maintenance_check
    @require_not_banned
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        assert user is not None
        rec = self.user_db.get_or_create(user.id, user.username or "", user.first_name or "")
        self._touch_user(update)

        is_new = rec.download_count == 0 and rec.joined_at[:10] == datetime.date.today().isoformat()
        greeting = "🎉 Selamat datang!" if is_new else f"👋 Hei, {_esc(user.first_name)}!"

        custom_welcome = self.config.get("welcome_message", "")
        body = custom_welcome if custom_welcome else (
            "Bot ini membantu kamu download video & audio dari YouTube "
            "dan 1000+ platform lainnya.\n\n"
            "🔗 Cukup kirim link video, dan bot akan memproses semuanya!"
        )

        platform_list = " • ".join(SUPPORTED_PLATFORMS[:8]) + " • ..."

        await update.message.reply_html(
            f"{greeting}\n\n"
            f"{body}\n\n"
            f"<b>Platform didukung:</b>\n<i>{platform_list}</i>\n\n"
            f"Ketik /help untuk panduan lengkap.",
            reply_markup=self._main_keyboard(),
        )

    @maintenance_check
    @require_not_banned
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._touch_user(update)
        max_dl = self.config.get("max_concurrent_per_user", 2)
        await update.message.reply_html(
            "<b>📖 Panduan Penggunaan</b>\n\n"
            "<b>🎯 Cara termudah:</b>\n"
            "Langsung kirim link video — bot otomatis memprosesnya!\n\n"
            "<b>📋 Perintah tersedia:</b>\n"
            "• /download &lt;url&gt; — Download video\n"
            "• /audio &lt;url&gt; — Download audio (MP3)\n"
            "• /formats &lt;url&gt; — Lihat format tersedia\n"
            "• /status — Cek download aktif\n"
            "• /history — Riwayat download\n"
            "• /settings — Atur preferensi\n"
            "• /cancel — Batalkan download\n\n"
            "<b>⚙️ Preferensi:</b>\n"
            "Atur kualitas default, format audio, dll di /settings\n\n"
            f"<b>⚠️ Batasan:</b>\n"
            f"• File maks: <b>{MAX_FILE_SIZE_MB} MB</b> (batas Telegram)\n"
            f"• Max {max_dl} download bersamaan per user\n"
            f"• Playlist maks: {self.config.get('max_playlist_items', 25)} video",
            reply_markup=self._main_keyboard(),
        )

    @maintenance_check
    @require_not_banned
    async def cmd_about(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._touch_user(update)
        stats = self.user_db.stats()
        await update.message.reply_html(
            "<b>🤖 Modern YouTube Downloader Bot v2.0.0</b>\n\n"
            "Bot canggih untuk download video & audio dari ratusan platform.\n\n"
            "<b>🛠 Teknologi:</b>\n"
            "• python-telegram-bot v20+\n"
            "• yt-dlp (fork aktif dari youtube-dl)\n"
            "• FFmpeg untuk konversi & merging\n"
            "• Asyncio queue dengan multiple workers\n\n"
            f"<b>📊 Statistik Global:</b>\n"
            f"• Total pengguna: {stats['total']:,}\n"
            f"• Total download: {stats['total_downloads']:,}\n"
            f"• Data diunduh: {_fmt_bytes(stats['total_bytes'])}\n\n"
            "<b>👨‍💻 Developer:</b> Adam Official Dev\n"
            "🔗 <a href='https://github.com/AdamOfficialDev/modern_youtube_downloader'>GitHub</a>",
            disable_web_page_preview=True,
            reply_markup=self._main_keyboard(),
        )

    @maintenance_check
    @require_not_banned
    async def cmd_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._touch_user(update)
        await update.message.reply_html(
            "☰ <b>Menu Utama</b>\n\nPilih aksi dari keyboard di bawah:",
            reply_markup=self._main_keyboard(),
        )

    # ── Download flow ─────────────────────────────────────────────────────────

    @maintenance_check
    @require_not_banned
    @rate_limited
    async def cmd_download(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Entry point for video download: fetch info → show format keyboard."""
        self._touch_user(update)
        user = update.effective_user
        assert user is not None

        if not context.args:
            await update.message.reply_html(
                "⚠️ Kirim URL setelah perintah.\n"
                "<code>/download https://youtube.com/watch?v=...</code>"
            )
            return
        await self._start_info_fetch(update, context, url=context.args[0], force_audio=False)

    @maintenance_check
    @require_not_banned
    @rate_limited
    async def cmd_audio(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Entry point for audio-only download."""
        self._touch_user(update)
        if not context.args:
            await update.message.reply_html(
                "⚠️ Kirim URL setelah perintah.\n"
                "<code>/audio https://youtube.com/watch?v=...</code>"
            )
            return
        await self._start_info_fetch(update, context, url=context.args[0], force_audio=True)

    @maintenance_check
    @require_not_banned
    @rate_limited
    async def cmd_formats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show available formats for a URL without committing to download."""
        self._touch_user(update)
        if not context.args:
            await update.message.reply_html(
                "⚠️ Kirim URL setelah perintah.\n"
                "<code>/formats https://youtube.com/watch?v=...</code>"
            )
            return
        await self._start_info_fetch(update, context, url=context.args[0], force_audio=False, formats_only=True)

    async def _start_info_fetch(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        url: str,
        force_audio: bool,
        formats_only: bool = False,
    ) -> None:
        """Fetch video info and show format selection keyboard."""
        user = update.effective_user
        assert user is not None

        if not _is_valid_url(url):
            await update.message.reply_html("⚠️ URL tidak valid. Pastikan dimulai dengan http:// atau https://")
            return

        max_concurrent = self.config.get("max_concurrent_per_user", 2)
        if self.dl_queue.user_task_count(user.id) >= max_concurrent:
            await update.message.reply_html(
                f"⚠️ Kamu sudah memiliki {max_concurrent} download aktif.\n"
                f"Tunggu hingga selesai atau gunakan /cancel."
            )
            return

        status_msg = await update.message.reply_html("🔍 <b>Mengambil informasi video...</b>")

        try:
            info = await asyncio.wait_for(
                self.dl_manager.get_video_info(url), timeout=30
            )
        except asyncio.TimeoutError:
            await status_msg.edit_text("❌ Timeout saat mengambil info video. Coba lagi.", parse_mode=ParseMode.HTML)
            return
        except Exception as exc:
            logger.warning("Info fetch error for %s: %s", url, exc)
            await status_msg.edit_text(
                f"❌ <b>Gagal mengambil info:</b>\n<code>{_esc(str(exc)[:300])}</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        title = info.get("title", "Video")
        duration = _fmt_duration(info.get("duration"))
        uploader = info.get("uploader") or info.get("channel") or "Unknown"
        view_count = info.get("view_count", 0)
        view_str = f"{view_count:,}" if view_count else "—"
        thumb = info.get("thumbnail", "")

        # Store URL in user_data with a short key to keep callback_data under 64 bytes
        import hashlib
        url_key = hashlib.md5(url.encode()).hexdigest()[:16]
        if context.user_data is None:
            context.user_data = {}
        context.user_data[f"url_{url_key}"] = url

        if force_audio:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "🎵 Download MP3 (Best Quality)",
                    callback_data=f"dl|{url_key}|bestaudio/best|audio",
                )
            ], [
                InlineKeyboardButton("❌ Batal", callback_data="cancel_info"),
            ]])
        else:
            formats = self.dl_manager.get_available_formats(info)
            keyboard = self._build_format_keyboard(url_key, formats, formats_only=formats_only)

        caption = (
            f"📹 <b>{_esc(title)}</b>\n\n"
            f"👤 {_esc(uploader)}\n"
            f"⏱ Durasi: {duration}\n"
            f"👁 Views: {view_str}\n\n"
            f"{'🎵 Pilih format audio:' if force_audio else '📋 Pilih format:'}"
        )

        if formats_only:
            caption = f"📋 <b>Format tersedia untuk:</b>\n{_esc(title)}\n\n{caption.split(chr(10))[-1]}"

        status_msg_deleted = False
        try:
            if thumb:
                # Delete first, then send photo — track deletion so fallback doesn't
                # try to edit a message that no longer exists (BadRequest: Message to edit not found)
                await status_msg.delete()
                status_msg_deleted = True
                await update.message.reply_photo(
                    photo=thumb,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                )
            else:
                await status_msg.edit_text(caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        except Exception as send_exc:
            logger.warning("Thumbnail send failed (%s), falling back to text message", send_exc)
            if not status_msg_deleted:
                # Safe to edit — message still exists
                try:
                    await status_msg.edit_text(caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)
                except Exception:
                    # Last resort: send a fresh message
                    await update.message.reply_html(caption, reply_markup=keyboard)
            else:
                # Message was deleted, must send fresh
                await update.message.reply_html(caption, reply_markup=keyboard)

    @staticmethod
    def _build_format_keyboard(
        url_key: str, formats: List[Dict[str, Any]], formats_only: bool = False
    ) -> InlineKeyboardMarkup:
        """
        Build format selection keyboard.
        url_key is a short opaque key (stored in context.user_data), NOT the raw URL.
        Telegram limits callback_data to 64 bytes — storing URLs directly would exceed this.
        Max callback_data breakdown: "dl|" (3) + key (16) + "|" (1) + fmt_id (≤30) + "|video" (6) = ~56 bytes ✅
        """
        rows: List[List[InlineKeyboardButton]] = []

        for fmt in formats:
            is_audio = fmt.get("is_audio", False)
            audio_flag = "audio" if is_audio else "video"
            filesize = fmt.get("filesize", 0)
            size_str = f" (~{_fmt_bytes(filesize)})" if filesize else ""
            label = f"{fmt['label']}{size_str}"
            # Truncate format_id to 30 chars to stay safely under 64-byte limit
            safe_fmt_id = fmt["format_id"][:30]
            cb = f"dl|{url_key}|{safe_fmt_id}|{audio_flag}"
            assert len(cb.encode()) <= 64, f"callback_data too long: {cb!r}"
            rows.append([InlineKeyboardButton(label, callback_data=cb)])

        rows.append([InlineKeyboardButton("❌ Batal", callback_data="cancel_info")])
        return InlineKeyboardMarkup(rows)

    # ── Status / History / Settings ───────────────────────────────────────────

    @maintenance_check
    @require_not_banned
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        assert user is not None
        self._touch_user(update)

        active = [
            t for t in self.dl_queue._tasks.values()
            if t.user_id == user.id
            and t.status not in (DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED)
        ]

        if not active:
            await update.message.reply_html("📊 Tidak ada download aktif saat ini.\n\nKirim link video untuk mulai!")
            return

        lines = ["📊 <b>Download Aktif Kamu:</b>\n"]
        status_icons = {
            DownloadStatus.QUEUED: "🕐",
            DownloadStatus.FETCHING_INFO: "🔍",
            DownloadStatus.DOWNLOADING: "⏬",
            DownloadStatus.UPLOADING: "📤",
        }
        for t in active:
            icon = status_icons.get(t.status, "⏳")
            bar = ""
            if t.status == DownloadStatus.DOWNLOADING:
                filled = int(t.progress_pct / 5)
                bar = f"\n   <code>[{'█'*filled}{'░'*(20-filled)}]</code> {t.progress_pct:.1f}%"
            lines.append(
                f"{icon} <b>{_esc(t.title or t.url[:50])}</b>\n"
                f"   Status: {t.status.value}{bar}\n"
                f"   ID: <code>{t.task_id}</code>"
            )

        await update.message.reply_html("\n\n".join(lines))

    @maintenance_check
    @require_not_banned
    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        assert user is not None
        self._touch_user(update)

        completed = [
            t for t in self.dl_queue._tasks.values()
            if t.user_id == user.id and t.status == DownloadStatus.COMPLETED
        ][-10:]  # Last 10

        rec = self.user_db.get(user.id)
        total = rec.download_count if rec else 0
        total_bytes = _fmt_bytes(rec.total_bytes) if rec else "—"

        lines = [
            f"📜 <b>Riwayat Download</b>\n",
            f"📊 Total: <b>{total} download</b> ({total_bytes})\n",
        ]

        if completed:
            lines.append("<b>10 Download Terakhir Sesi Ini:</b>")
            for t in reversed(completed):
                dur = ""
                if t.completed_at:
                    elapsed = t.completed_at - t.created_at
                    dur = f" • {elapsed:.0f}s"
                lines.append(f"✅ {_esc(t.title or t.url[:60])}{dur}")
        else:
            lines.append("<i>Belum ada riwayat dalam sesi ini.</i>")

        await update.message.reply_html("\n".join(lines))

    @maintenance_check
    @require_not_banned
    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        assert user is not None
        self._touch_user(update)
        rec = self.user_db.get_or_create(user.id, user.username or "", user.first_name or "")
        prefs = rec.preferences

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(f"🏆 Kualitas: {prefs.quality.value}", callback_data="set|quality"),
            ],
            [
                InlineKeyboardButton(f"🎵 Audio: {prefs.audio_format.upper()}", callback_data="set|audio_fmt"),
                InlineKeyboardButton(f"⚡ Bitrate: {prefs.audio_quality}kbps", callback_data="set|audio_quality"),
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if prefs.notification_on_complete else '❌'} Notifikasi Selesai",
                    callback_data="set|notif"
                ),
            ],
            [InlineKeyboardButton("✖️ Tutup", callback_data="cancel_info")],
        ])

        await update.message.reply_html(
            f"⚙️ <b>Pengaturan Kamu</b>\n\n"
            f"🏆 Kualitas default: <b>{prefs.quality.value}</b>\n"
            f"🎵 Format audio: <b>{prefs.audio_format.upper()}</b>\n"
            f"⚡ Kualitas audio: <b>{prefs.audio_quality} kbps</b>\n"
            f"🔔 Notif selesai: <b>{'Ya' if prefs.notification_on_complete else 'Tidak'}</b>\n\n"
            f"Tap tombol untuk mengubah:",
            reply_markup=keyboard,
        )

    @maintenance_check
    @require_not_banned
    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        assert user is not None
        active = [
            t for t in self.dl_queue._tasks.values()
            if t.user_id == user.id
            and t.status in (DownloadStatus.QUEUED, DownloadStatus.FETCHING_INFO)
        ]
        if not active:
            await update.message.reply_html(
                "ℹ️ Tidak ada download yang bisa dibatalkan (yang sudah berjalan tidak bisa dihentikan)."
            )
            return
        for t in active:
            t.status = DownloadStatus.CANCELLED
        await update.message.reply_html(f"✅ {len(active)} download dibatalkan.")

    # ═══════════════════════════════════════════════════════════════════════
    # ADMIN COMMANDS
    # ═══════════════════════════════════════════════════════════════════════

    @require_admin
    async def cmd_admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        stats = self.user_db.stats()
        uptime = self._get_uptime()
        maint = self.config.get("maintenance_mode", False)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📊 Detail Stats", callback_data="admin|stats"),
                InlineKeyboardButton("👥 User List", callback_data="admin|users"),
            ],
            [
                InlineKeyboardButton("📢 Broadcast", callback_data="admin|broadcast_hint"),
                InlineKeyboardButton(f"🛠 Maintenance: {'ON' if maint else 'OFF'}", callback_data="admin|toggle_maint"),
            ],
            [
                InlineKeyboardButton("📜 Log File", callback_data="admin|logs"),
                InlineKeyboardButton("🔄 Reload Config", callback_data="admin|reload_config"),
            ],
        ])

        await update.message.reply_html(
            f"🛡 <b>Admin Panel</b>\n\n"
            f"👥 Users: <b>{stats['total']:,}</b> total | "
            f"<b>{stats['active_30d']:,}</b> aktif 30 hari\n"
            f"🚫 Banned: <b>{stats['banned']}</b>\n"
            f"📥 Total DL: <b>{stats['total_downloads']:,}</b>\n"
            f"💾 Data: <b>{_fmt_bytes(stats['total_bytes'])}</b>\n"
            f"⏱ Uptime: <b>{uptime}</b>\n"
            f"🛠 Maintenance: <b>{'ON ⚠️' if maint else 'OFF ✅'}</b>",
            reply_markup=keyboard,
        )

    @require_admin
    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        stats = self.user_db.stats()
        queue_size = self.dl_queue._queue.qsize()
        active_tasks = sum(
            1 for t in self.dl_queue._tasks.values()
            if t.status in (DownloadStatus.DOWNLOADING, DownloadStatus.UPLOADING)
        )
        dl_dir = Path(self.config.get("download_dir", str(DEFAULT_DOWNLOAD_DIR)))
        dir_size = sum(f.stat().st_size for f in dl_dir.rglob("*") if f.is_file()) if dl_dir.exists() else 0

        await update.message.reply_html(
            f"📊 <b>Statistik Bot</b>\n\n"
            f"<b>Pengguna:</b>\n"
            f"• Total: {stats['total']:,}\n"
            f"• Aktif (30 hari): {stats['active_30d']:,}\n"
            f"• Premium: {stats['premium']:,}\n"
            f"• Banned: {stats['banned']:,}\n\n"
            f"<b>Download:</b>\n"
            f"• Total historis: {stats['total_downloads']:,}\n"
            f"• Data terunduh: {_fmt_bytes(stats['total_bytes'])}\n"
            f"• Antrian saat ini: {queue_size}\n"
            f"• Aktif saat ini: {active_tasks}\n\n"
            f"<b>Sistem:</b>\n"
            f"• Uptime: {self._get_uptime()}\n"
            f"• Folder download: {_fmt_bytes(dir_size)}\n"
            f"• Workers: {self.dl_queue.num_workers}"
        )

    @require_admin
    async def cmd_ban(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Usage: /ban <user_id> [hours] [reason...]"""
        if not context.args:
            await update.message.reply_html(
                "⚠️ Penggunaan: /ban &lt;user_id&gt; [jam] [alasan]\n"
                "Contoh: /ban 123456789 24 Spam berlebihan"
            )
            return
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_html("❌ user_id harus berupa angka.")
            return

        duration: Optional[int] = None
        reason_parts = context.args[1:]
        if reason_parts and reason_parts[0].isdigit():
            duration = int(reason_parts[0])
            reason_parts = reason_parts[1:]
        reason = " ".join(reason_parts) if reason_parts else "Tidak ada alasan diberikan."

        success = self.user_db.ban(target_id, reason=reason, duration_hours=duration)
        dur_str = f"{duration} jam" if duration else "permanen"
        if success:
            await update.message.reply_html(
                f"✅ User <code>{target_id}</code> di-ban ({dur_str}).\n"
                f"📋 Alasan: {_esc(reason)}"
            )
            # Notify user
            try:
                await self.application.bot.send_message(
                    chat_id=target_id,
                    text=(
                        f"🚫 <b>Akun kamu telah diblokir</b>\n\n"
                        f"📋 Alasan: {_esc(reason)}\n"
                        f"⏰ Durasi: {dur_str}"
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
        else:
            await update.message.reply_html(
                f"❌ User <code>{target_id}</code> tidak ditemukan di database. "
                f"Mereka mungkin belum pernah menggunakan bot."
            )

    @require_admin
    async def cmd_unban(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.message.reply_html("⚠️ Penggunaan: /unban &lt;user_id&gt;")
            return
        try:
            target_id = int(context.args[0])
        except ValueError:
            await update.message.reply_html("❌ user_id harus berupa angka.")
            return

        success = self.user_db.unban(target_id)
        if success:
            await update.message.reply_html(f"✅ User <code>{target_id}</code> berhasil di-unban.")
            try:
                await self.application.bot.send_message(
                    chat_id=target_id,
                    text="✅ <b>Akun kamu telah di-unban.</b> Kamu bisa menggunakan bot kembali.",
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
        else:
            await update.message.reply_html(f"❌ User <code>{target_id}</code> tidak ditemukan.")

    @require_admin
    async def cmd_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Broadcast message to all non-banned users."""
        if not context.args:
            await update.message.reply_html(
                "⚠️ Penggunaan: /broadcast &lt;pesan&gt;\n"
                "Pesan mendukung HTML formatting."
            )
            return
        message = " ".join(context.args)
        users = [u for u in self.user_db.all_users() if not u.is_banned()]

        status_msg = await update.message.reply_html(
            f"📢 Mulai broadcast ke <b>{len(users)}</b> pengguna..."
        )

        sent = failed = 0
        for user_rec in users:
            try:
                await self.application.bot.send_message(
                    chat_id=user_rec.user_id,
                    text=f"📢 <b>Pesan dari Admin:</b>\n\n{message}",
                    parse_mode=ParseMode.HTML,
                )
                sent += 1
            except Exception:
                failed += 1
            await asyncio.sleep(0.05)  # ~20 msg/s to stay under Telegram limits

        await status_msg.edit_text(
            f"📢 <b>Broadcast selesai</b>\n\n"
            f"✅ Terkirim: {sent}\n"
            f"❌ Gagal: {failed}",
            parse_mode=ParseMode.HTML,
        )

    @require_admin
    async def cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        log_path = Path("bot_logs.log")
        if not log_path.exists():
            await update.message.reply_html("❌ File log tidak ditemukan.")
            return
        # Send last 4000 chars as message for quick viewing
        content = log_path.read_text(encoding="utf-8", errors="replace")
        snippet = content[-4000:]
        await update.message.reply_html(
            f"<pre>{_esc(snippet)}</pre>",
        )
        # Also send full file
        with log_path.open("rb") as fh:
            await update.message.reply_document(document=fh, filename="bot_logs.log")

    @require_admin
    async def cmd_maintenance(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        current = self.config.get("maintenance_mode", False)
        self.config.set("maintenance_mode", not current)
        state = "AKTIF ⚠️" if not current else "NONAKTIF ✅"
        await update.message.reply_html(f"🛠 Maintenance mode sekarang: <b>{state}</b>")

    @require_admin
    async def cmd_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        users = sorted(self.user_db.all_users(), key=lambda u: u.download_count, reverse=True)[:20]
        lines = ["👥 <b>Top 20 Pengguna (by downloads):</b>\n"]
        for i, rec in enumerate(users, 1):
            status_icon = "🚫" if rec.is_banned() else ("⭐" if rec.status == UserStatus.PREMIUM else "👤")
            lines.append(
                f"{i}. {status_icon} {_esc(rec.first_name)} "
                f"(<code>{rec.user_id}</code>)\n"
                f"   📥 {rec.download_count} DL | 💾 {_fmt_bytes(rec.total_bytes)}"
            )
        await update.message.reply_html("\n".join(lines))

    # ═══════════════════════════════════════════════════════════════════════
    # MESSAGE HANDLER
    # ═══════════════════════════════════════════════════════════════════════

    @maintenance_check
    @require_not_banned
    @rate_limited
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.message.text.strip()
        self._touch_user(update)
        user = update.effective_user
        assert user is not None

        # ── Detect pending broadcast — next message after admin clicks Broadcast ──
        chat_id = update.message.chat_id
        is_admin = self.config.is_admin(user.id, user.username or "")
        if is_admin and chat_id in self._broadcast_prompts:
            # Clear state immediately
            self._broadcast_prompts.pop(chat_id, None)
            # Execute broadcast
            users = [u for u in self.user_db.all_users() if not u.is_banned()]
            status_msg = await update.message.reply_html(
                f"📢 Mulai broadcast ke <b>{len(users)}</b> pengguna..."
            )
            sent = failed = 0
            for user_rec in users:
                try:
                    await self.application.bot.send_message(
                        chat_id=user_rec.user_id,
                        text="📢 <b>Pesan dari Admin:</b>\n\n" + text,
                        parse_mode=ParseMode.HTML,
                    )
                    sent += 1
                except Exception:
                    failed += 1
                await asyncio.sleep(0.05)
            await status_msg.edit_text(
                "📢 <b>Broadcast selesai</b>\n\n"
                f"✅ Terkirim: {sent}\n"
                f"❌ Gagal: {failed}",
                parse_mode=ParseMode.HTML,
            )
            return

        # Auto-detect URL
        if _is_valid_url(text):
            context.args = [text]
            await self.cmd_download(update, context)
            return

        # Handle keyboard buttons
        button_actions: Dict[str, Callable] = {
            "📥 Download Video": lambda: update.message.reply_html(
                "Kirim link video yang ingin kamu download! 🔗"
            ),
            "🎵 Download Audio": lambda: update.message.reply_html(
                "Kirim link video untuk diekstrak audionya! 🎵\n"
                "Atau gunakan /audio &lt;url&gt;"
            ),
            "📊 Status": lambda: self.cmd_status(update, context),
            "⚙️ Settings": lambda: self.cmd_settings(update, context),
            "📜 History": lambda: self.cmd_history(update, context),
            "ℹ️ Help": lambda: self.cmd_help(update, context),
        }

        if text in button_actions:
            result = button_actions[text]()
            if asyncio.iscoroutine(result):
                await result
            return

        # Try to extract URL from text
        url_match = re.search(r"https?://[^\s]+", text)
        if url_match:
            context.args = [url_match.group(0)]
            await self.cmd_download(update, context)
            return

        await update.message.reply_html(
            "💡 Kirim link video langsung untuk download, atau pilih opsi dari menu!\n"
            "Gunakan /help untuk panduan lengkap."
        )

    # ═══════════════════════════════════════════════════════════════════════
    # CALLBACK QUERY HANDLER
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    async def _safe_edit(query: Any, text: str, reply_markup: Any = None) -> None:
        """
        Unified message-edit helper that works for BOTH text messages and photo/media messages.

        Telegram rules:
          - edit_message_text  → only for messages that have text (no photo/video/etc.)
          - edit_message_caption → only for messages that have a caption (photo, video, doc…)
          - edit_message_reply_markup → only updates buttons, no text change

        Calling the wrong method raises BadRequest: "There is no text in the message to edit"
        or "Message is not modified". This helper picks the right method automatically.
        """
        msg = query.message
        kwargs: dict = {"parse_mode": ParseMode.HTML}
        if reply_markup is not None:
            kwargs["reply_markup"] = reply_markup
        try:
            if msg.text:
                # Pure text message → edit_message_text
                await query.edit_message_text(text, **kwargs)
            elif msg.caption is not None or msg.photo or msg.video or msg.document:
                # Media message → edit caption
                await query.edit_message_caption(caption=text, **kwargs)
            else:
                # Unknown message type — send a fresh reply as fallback
                await msg.reply_html(text, reply_markup=reply_markup)
        except Exception as exc:
            err = str(exc).lower()
            if "message is not modified" in err:
                return  # Harmless — content didn't change
            if "there is no text" in err or "message to edit not found" in err:
                # Final fallback: send new message
                try:
                    await msg.reply_html(text, reply_markup=reply_markup)
                except Exception:
                    pass
            else:
                raise  # Re-raise unexpected errors

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        data = query.data or ""
        user = update.effective_user
        assert user is not None

        # ── admin actions ─────────────────────────────────────────────────
        if data.startswith("admin|"):
            if not self.config.is_admin(user.id, user.username):
                await query.answer("⛔ Hanya admin!", show_alert=True)
                return
            action = data.split("|", 1)[1]
            await self._handle_admin_callback(query, action, context)
            return

        # ── cancel info/format message ────────────────────────────────────
        if data == "cancel_broadcast":
            self._broadcast_prompts.pop(update.effective_chat.id, None)
            await self._safe_edit(query, "❌ Broadcast dibatalkan.")
            return

        if data == "cancel_info":
            await self._safe_edit(query, "❌ Dibatalkan.")
            return

        # ── download action ───────────────────────────────────────────────
        if data.startswith("dl|"):
            parts = data.split("|")
            if len(parts) < 4:
                await self._safe_edit(query, "❌ Data tidak valid.")
                return

            url_key   = parts[1]
            format_id = parts[2]
            audio_flag = parts[3]

            # Resolve URL from user_data using the short key stored during info fetch
            url = (context.user_data or {}).get(f"url_{url_key}")
            if not url:
                await self._safe_edit(query, "❌ <b>Sesi expired.</b>\nKirim ulang link video untuk memulai lagi.")
                return

            extract_audio = audio_flag == "audio"

            # Check queue capacity
            max_concurrent = self.config.get("max_concurrent_per_user", 2)
            if self.dl_queue.user_task_count(user.id) >= max_concurrent:
                await query.answer(
                    f"⚠️ Maks {max_concurrent} download bersamaan!", show_alert=True
                )
                return

            task = DownloadTask(
                task_id=_make_task_id(user.id),
                user_id=user.id,
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                url=url,
                format_id=format_id,
                extract_audio=extract_audio,
            )

            enqueued = await self.dl_queue.enqueue(task)
            if not enqueued:
                await query.answer("⚠️ Antrian penuh, coba lagi sebentar.", show_alert=True)
                return

            # Immediately update message to show queued state
            queue_pos = self.dl_queue._queue.qsize()
            await self._safe_edit(
                query,
                f"✅ <b>Download ditambahkan ke antrian!</b>\n\n"
                f"🆔 Task ID: <code>{task.task_id}</code>\n"
                f"📋 Posisi antrian: ~{queue_pos}\n\n"
                f"Gunakan /status untuk memantau progress.",
            )

            # Track download completion to update user stats
            asyncio.create_task(self._await_task_completion(task))
            return

        # ── settings actions ───────────────────────────────────────────────
        if data.startswith("set|"):
            await self._handle_settings_callback(query, user, data[4:])
            return

        await self._safe_edit(query, "❓ Aksi tidak dikenal.")

    async def _await_task_completion(self, task: DownloadTask) -> None:
        """Wait for task completion and update user stats."""
        while task.status not in (
            DownloadStatus.COMPLETED, DownloadStatus.FAILED, DownloadStatus.CANCELLED
        ):
            await asyncio.sleep(2)

        if task.status == DownloadStatus.COMPLETED:
            self.user_db.increment_downloads(task.user_id)

    async def _handle_admin_callback(self, query: Any, action: str, context: Any) -> None:
        if action == "stats":
            await self.cmd_stats.__wrapped__(self, query, None)  # type: ignore
        elif action == "toggle_maint":
            current = self.config.get("maintenance_mode", False)
            self.config.set("maintenance_mode", not current)
            state = "AKTIF ⚠️" if not current else "NONAKTIF ✅"
            await self._safe_edit(query, f"🛠 Maintenance mode sekarang: <b>{state}</b>")
        elif action == "logs":
            log_path = Path("bot_logs.log")
            if log_path.exists():
                with log_path.open("rb") as fh:
                    await query.message.reply_document(document=fh, filename="bot_logs.log")
            else:
                await query.answer("Log file tidak ditemukan.", show_alert=True)
        elif action == "reload_config":
            self.config._data = self.config._load()
            await query.answer("✅ Config di-reload!", show_alert=True)
        elif action == "broadcast_hint":
            # Mark chat as pending broadcast - NEXT message from admin = broadcast text
            self._broadcast_prompts[query.message.chat_id] = True
            await query.message.reply_html(
                "📢 <b>Mode Broadcast Aktif</b>\n\n"
                "✏️ Ketik dan kirim pesan broadcast kamu sekarang.\n"
                "Pesan <b>berikutnya</b> yang kamu kirim akan diteruskan ke semua user.\n\n"
                "<i>HTML: &lt;b&gt;bold&lt;/b&gt;, &lt;i&gt;italic&lt;/i&gt;, dll.</i>",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("❌ Batalkan Broadcast", callback_data="cancel_broadcast")
                ]])
            )
            await query.answer("✅ Ketik pesan broadcast kamu!")
        elif action == "users":
            users = sorted(self.user_db.all_users(), key=lambda u: u.download_count, reverse=True)[:10]
            lines = ["👥 <b>Top 10 Users:</b>\n"]
            for i, rec in enumerate(users, 1):
                lines.append(f"{i}. {_esc(rec.first_name)} ({rec.user_id}) — {rec.download_count} DL")
            await query.message.reply_html("\n".join(lines))

    async def _handle_settings_callback(self, query: Any, user: Any, setting: str) -> None:
        rec = self.user_db.get_or_create(user.id, user.username or "", user.first_name or "")
        prefs = rec.preferences

        if setting == "quality":
            options = list(QualityPreset)
            current_idx = options.index(prefs.quality)
            prefs.quality = options[(current_idx + 1) % len(options)]
            self.user_db._save()
            await query.answer(f"✅ Kualitas diubah ke: {prefs.quality.value}", show_alert=False)

        elif setting == "audio_fmt":
            fmts = ["mp3", "m4a", "ogg", "flac"]
            idx = fmts.index(prefs.audio_format) if prefs.audio_format in fmts else 0
            prefs.audio_format = fmts[(idx + 1) % len(fmts)]
            self.user_db._save()
            await query.answer(f"✅ Format audio: {prefs.audio_format.upper()}", show_alert=False)

        elif setting == "audio_quality":
            qualities = ["128", "192", "256", "320"]
            idx = qualities.index(prefs.audio_quality) if prefs.audio_quality in qualities else 1
            prefs.audio_quality = qualities[(idx + 1) % len(qualities)]
            self.user_db._save()
            await query.answer(f"✅ Bitrate: {prefs.audio_quality} kbps", show_alert=False)

        elif setting == "notif":
            prefs.notification_on_complete = not prefs.notification_on_complete
            self.user_db._save()
            state = "ON" if prefs.notification_on_complete else "OFF"
            await query.answer(f"🔔 Notifikasi: {state}", show_alert=False)

        # Refresh settings message
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"🏆 Kualitas: {prefs.quality.value}", callback_data="set|quality")],
            [
                InlineKeyboardButton(f"🎵 Audio: {prefs.audio_format.upper()}", callback_data="set|audio_fmt"),
                InlineKeyboardButton(f"⚡ Bitrate: {prefs.audio_quality}kbps", callback_data="set|audio_quality"),
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if prefs.notification_on_complete else '❌'} Notifikasi Selesai",
                    callback_data="set|notif"
                )
            ],
            [InlineKeyboardButton("✖️ Tutup", callback_data="cancel_info")],
        ])
        await query.edit_message_reply_markup(reply_markup=keyboard)

    # ═══════════════════════════════════════════════════════════════════════
    # ERROR HANDLER
    # ═══════════════════════════════════════════════════════════════════════

    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.exception("Unhandled exception: %s", context.error)
        if update and isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_html(
                    "❌ <b>Terjadi kesalahan tak terduga.</b>\n"
                    "Tim kami akan segera menginvestigasi. Silakan coba lagi."
                )
            except Exception:
                pass

    # ═══════════════════════════════════════════════════════════════════════
    # UTILITY METHODS
    # ═══════════════════════════════════════════════════════════════════════

    def _get_uptime(self) -> str:
        delta = datetime.datetime.now() - self.start_time
        days, rem = divmod(int(delta.total_seconds()), 86400)
        hours, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        parts = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if mins:
            parts.append(f"{mins}m")
        parts.append(f"{secs}s")
        return " ".join(parts)

    def get_statistics(self) -> Dict[str, Any]:
        """Public API for external integrations (e.g. GUI tab)."""
        stats = self.user_db.stats()
        return {
            **stats,
            "uptime_seconds": (datetime.datetime.now() - self.start_time).total_seconds(),
            "queue_size": self.dl_queue._queue.qsize(),
        }

    def get_user_stats(self) -> List[Dict[str, Any]]:
        return [rec.to_dict() for rec in self.user_db.all_users()]

    def update_user_status(self, user_id: int, new_status: str) -> bool:
        try:
            status = UserStatus(new_status)
        except ValueError:
            return False
        rec = self.user_db.get(user_id)
        if not rec:
            return False
        rec.status = status
        self.user_db._save()
        return True

    def is_user_blocked(self, user_id: int) -> bool:
        return self.user_db.is_banned(user_id)

    def integrate_with_main_app(self) -> None:
        if self.parent_app:
            logger.info("Bot integrated with main application")

    # ═══════════════════════════════════════════════════════════════════════
    # LIFECYCLE
    # ═══════════════════════════════════════════════════════════════════════

    def run(self) -> None:
        """Start the bot with polling (blocking)."""
        logger.info("Starting bot...")
        self.application.post_init = self._post_init
        self.application.post_shutdown = self._post_shutdown
        self.application.run_polling(
            allowed_updates=["message", "callback_query", "inline_query"],
            drop_pending_updates=True,
        )

    def stop(self) -> None:
        """Request shutdown (called externally)."""
        if self.application:
            try:
                self.application.stop()
            except Exception as exc:
                logger.error("Error stopping bot: %s", exc)


# ─────────────────────────────────── Main ─────────────────────────────────────

def main() -> None:
    """Entry point when running as standalone script."""
    bot = TelegramBot()
    try:
        bot.run()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user")
    except ValueError as exc:
        logger.critical("Configuration error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
