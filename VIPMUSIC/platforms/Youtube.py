# Youtube.py  (TypeTube = 1st priority, everything else = fallback)
#
# PROVIDER ORDER (every download / metadata call):
#   1. TypeTube      -> direct stream URL (instant playback) or cached local file.
#                       No cookies, no yt-dlp, no API key needed. The full file is
#                       downloaded in the background (downloads/tt_<id>.<ext>).
#   2. Railway API   -> API_URL / API_KEY download (bounded by YT_API_TIMEOUT)
#   3. yt-dlp        -> worker thread, bounded by YT_YTDLP_TIMEOUT
#   4. returns (None, False) -> your JioSaavn.download_with_fallback switches to JioSaavn
#
# Metadata (details / title / duration / thumbnail / track / slider):
#   TypeTube first -> youtubesearchpython VideosSearch as fallback.
#
# Return convention of YouTubeAPI.download():
#   (local_file_path, True)   completed local file
#   (remote_stream_url, None) playable remote URL (TypeTube). music.py queues
#                             "vid_<id>" and call.py re-resolves it on skip/loop.
#   (None, False)             every provider failed
#
# Key behaviour kept from the previous version:
#   * download_song / download_video NEVER hang: API attempt and yt-dlp attempt each
#     have their own timeout, and yt-dlp runs in a worker thread.
#   * Cookie refresh (yt-dlp browser / Playwright) happens ONLY in a background task,
#     with a cooldown. It is never awaited inside the /play path.
#
# Environment variables (all optional):
#   --- TypeTube ---
#   YT_USE_TYPETUBE (1)              "0" = disable TypeTube completely
#   TYPETUBE_API_KEY, TYPETUBE_HOST, TYPETUBE_PORT (8443), TYPETUBE_TIMEOUT_MS (15000)
#   TYPETUBE_RESOLVE_TIMEOUT (12)    TYPETUBE_VIDEO_TIMEOUT (60)
#   TYPETUBE_BG_DOWNLOAD (1)         TYPETUBE_BG_CONCURRENCY (3)
#   TYPETUBE_CHUNK_WORKERS (3)       TYPETUBE_CACHE_MAX_MB (1024)
#   TYPETUBE_MAX_VIDEO_HEIGHT (720)
#   --- Railway API / yt-dlp fallback ---
#   API_URL, API_KEY                 Railway download API
#   YT_EMAIL, YT_PASSWORD            Google login used ONLY by the Playwright cookie refresh
#   YTDLP_PROXIES, PLAYWRIGHT_PROXIES  comma separated
#   YT_API_TIMEOUT                   seconds for the Railway API attempt (default 10)
#   YT_YTDLP_TIMEOUT                 seconds for the yt-dlp attempt (default 10)
#   YT_USE_YTDLP                     "0" = skip yt-dlp entirely (default "1")
#   YT_YTDLP_REQUIRE_COOKIES         "1" = skip yt-dlp if no cookie file (default "1")
#   COOKIE_REFRESH_COOLDOWN          seconds between background refresh attempts (default 1800)
#   AUTO_REFRESH_COOKIES             "1" (default) or "0"
#
# Requirement for TypeTube:  pip install typetube
#   (if the package is missing, TypeTube is skipped automatically and the old chain runs)
#
# IMPORTANT: set YT_DOWNLOAD_TIMEOUT (read by JioSaavn.py) HIGHER than
# TypeTube + YT_API_TIMEOUT + YT_YTDLP_TIMEOUT, e.g. YT_DOWNLOAD_TIMEOUT=40.

import asyncio
import atexit
import contextlib
import os
import re
import json
import socket
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
import requests
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from VIPMUSIC.utils.database import is_on_off
from VIPMUSIC import app
from VIPMUSIC.utils.formatters import time_to_seconds
import glob
import random
import logging
import pymongo
from pymongo import MongoClient
import aiohttp
import config
from config import LOG_GROUP_ID
import traceback
from VIPMUSIC import LOGGER
from playwright.async_api import async_playwright
import time
import datetime
import shutil
import pathlib
import sys
import stat
import subprocess
from PIL import Image, ImageDraw, ImageFont
import io


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


# ========== RAILWAY CONFIGURATION ==========
API_URL = os.getenv("API_URL", "")
API_KEY = os.getenv("API_KEY", "")

# YouTube login (used only by background Playwright cookie refresh).
# NEVER hardcode credentials here - set them as environment variables.
YT_EMAIL = os.getenv("YT_EMAIL", "")
YT_PASSWORD = os.getenv("YT_PASSWORD", "")

AUTO_REFRESH_COOKIES = os.getenv("AUTO_REFRESH_COOKIES", "1") == "1"

# Proxies (optional - set in Railway env vars)
YTDLP_PROXIES = os.getenv("YTDLP_PROXIES", "")
PLAYWRIGHT_PROXIES = os.getenv("PLAYWRIGHT_PROXIES", "")

# Time budgets (seconds)
API_TIMEOUT = int(os.getenv("YT_API_TIMEOUT", "10"))
YTDLP_TIMEOUT = int(os.getenv("YT_YTDLP_TIMEOUT", "10"))
# Fail-fast switches (so JioSaavn fallback starts immediately):
#   YT_USE_YTDLP=0            -> never try yt-dlp, go to JioSaavn right after the API fails
#   YT_YTDLP_REQUIRE_COOKIES=1 -> skip yt-dlp when no cookie file exists (default)
YTDLP_ENABLED = os.getenv("YT_USE_YTDLP", "1") == "1"
YTDLP_REQUIRE_COOKIES = os.getenv("YT_YTDLP_REQUIRE_COOKIES", "1") == "1"
REFRESH_COOLDOWN = int(os.getenv("COOKIE_REFRESH_COOLDOWN", "1800"))
REFRESH_TIMEOUT = 240

# ========== TYPETUBE CONFIGURATION (1st priority provider) ==========
TT_ENABLED = os.getenv("YT_USE_TYPETUBE", "1") == "1"
TT_API_KEY = os.getenv("TYPETUBE_API_KEY") or None
TT_HOST = os.getenv("TYPETUBE_HOST") or None
TT_PORT = _env_int("TYPETUBE_PORT", 8443)
TT_TIMEOUT_MS = _env_int("TYPETUBE_TIMEOUT_MS", 15000)
TT_RESOLVE_TIMEOUT = _env_int("TYPETUBE_RESOLVE_TIMEOUT", 12)
TT_VIDEO_TIMEOUT = _env_int("TYPETUBE_VIDEO_TIMEOUT", 60)
TT_BG_DOWNLOAD = _env_int("TYPETUBE_BG_DOWNLOAD", 1) == 1
TT_BG_CONCURRENCY = max(1, _env_int("TYPETUBE_BG_CONCURRENCY", 3))
TT_CHUNK_WORKERS = max(1, min(8, _env_int("TYPETUBE_CHUNK_WORKERS", 3)))
TT_CACHE_MAX_BYTES = _env_int("TYPETUBE_CACHE_MAX_MB", 1024) * 1024 * 1024
TT_MAX_VIDEO_HEIGHT = _env_int("TYPETUBE_MAX_VIDEO_HEIGHT", 720)

TT_CHUNK_SIZE = 1024 * 1024          # 1 MiB ranged requests
TT_MIN_FILE_BYTES = 10 * 1024
TT_PROBE_TIMEOUT = 6
TT_TRACK_TTL = 600                   # seconds a resolved track is reused
TT_RATE_PER_MIN = 55                 # TypeTube free tier: 60 req/min -> stay under
TT_RATE_PER_DAY = 1450               # ... and 1,500 req/day
TT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0.0.0"

# Directories
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

COOKIES_DIR = os.path.join(os.getcwd(), "cookies")
os.makedirs(COOKIES_DIR, exist_ok=True)

TMP_DIR = os.path.join(os.getcwd(), "tmp")
os.makedirs(TMP_DIR, exist_ok=True)

AUDIO_EXTS = ["mp3", "m4a", "webm", "opus", "ogg"]
VIDEO_EXTS = ["mp4", "mkv", "webm"]


# Logger helper (Railway compatible)
def get_logger(name: str):
    try:
        return LOGGER(name)
    except Exception:
        log = logging.getLogger(name)
        if not log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
            log.addHandler(handler)
        log.setLevel(logging.INFO)
        return log


logger = get_logger("HeartBeat/platforms/Youtube.py")


# ================= VERIFY COOKIES FUNCTION =================
def verify_cookies_file(filename: str) -> bool:
    """Verify cookies file has proper YouTube cookies in Netscape format"""
    try:
        if not os.path.exists(filename):
            logger.error(f"Cookies file does not exist: {filename}")
            return False

        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()

        if 'youtube.com' not in content and '.youtube.com' not in content:
            logger.error("No youtube.com domain in cookies file")
            return False

        required_cookies = ['__Secure-YEC', '__Secure-YENID', 'PREF', 'VISITOR_INFO1_LIVE']
        found_cookies = [c for c in required_cookies if c in content]

        if len(found_cookies) < 2:
            logger.warning(f"Missing important cookies. Found: {found_cookies}")

        if content.strip().startswith('{') or '"domain"' in content:
            logger.error("Cookies file appears to be JSON format, not Netscape")
            return False

        lines = content.strip().split('\n')
        valid_lines = 0
        for line in lines:
            if line.startswith('#') or not line.strip():
                continue
            if '\t' not in line:
                logger.error(f"Invalid Netscape format line (no tabs): {line[:100]}")
                return False
            valid_lines += 1

        if valid_lines < 3:
            logger.error(f"Too few valid cookie lines: {valid_lines}")
            return False

        logger.info(f"✅ Cookies file verified: {filename} (found {found_cookies})")
        return True

    except Exception as e:
        logger.error(f"Error verifying cookies file: {e}")
        return False


# ================= NETSCAPE COOKIE WRITER =================
def write_netscape_cookies(cookies, filename):
    """Write cookies in strict Netscape format (7 tab-separated fields) for yt-dlp"""
    with open(filename, "w", newline='', encoding='utf-8') as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# This file was generated by YouTube Bot - Railway\n")
        f.write("# https://www.youtube.com\n\n")

        for cookie in cookies:
            try:
                domain = cookie.get('domain', '')
                if not domain:
                    continue

                if 'gstatic.com' in domain or 'doubleclick.net' in domain:
                    continue

                expires = cookie.get('expires', 0)
                if expires == 0 or expires == -1:
                    expires = int(time.time()) + 86400 * 365
                elif expires > 1000000000000:
                    expires = int(expires / 1000)

                flag = "TRUE" if domain.startswith('.') else "FALSE"
                path = cookie.get('path', '/')
                secure = "TRUE" if cookie.get('secure', False) else "FALSE"
                expires_str = str(int(expires))
                name = cookie.get('name', '')
                value = cookie.get('value', '')

                if not name or not value:
                    continue

                if '\t' in value or '\n' in value:
                    value = value.replace('\t', ' ').replace('\n', ' ')

                f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expires_str}\t{name}\t{value}\n")

            except Exception as e:
                logger.warning(f"Skipping cookie due to error: {e}")
                continue

    try:
        with open(filename, 'r') as f:
            lines = f.readlines()
            cookie_lines = [l for l in lines if not l.startswith('#') and l.strip()]
            if len(cookie_lines) > 0:
                logger.info(f"✓ Wrote {len(cookie_lines)} cookies to {filename}")
                return True
            logger.error(f"✗ No cookies written to {filename}")
            return False
    except Exception as e:
        logger.error(f"✗ Failed to verify cookie file: {e}")
        return False


# ================= YT-DLP BROWSER COOKIE EXTRACTION (background only) =================
async def refresh_cookies_ytdlp():
    """Extract cookies from a local Chrome profile using yt-dlp.
    Only works where a browser profile exists (not on a bare Railway container)."""
    logger.info("🚀 Trying yt-dlp browser cookie extraction")

    timestamp = int(time.time())
    cookie_filename = os.path.join(COOKIES_DIR, f"ytdlp_cookie_{timestamp}.txt")

    cmd = [
        "yt-dlp",
        "--cookies-from-browser", "chrome",
        "--cookies", cookie_filename,          # correct option: dumps the cookie jar to file
        "--skip-download",
        "--no-warnings",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    ]

    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=40)
        except asyncio.TimeoutError:
            try:
                process.kill()
            except Exception:
                pass
            logger.warning("yt-dlp cookie extraction timed out")
            return None

        # yt-dlp may exit non-zero on the probe URL but still dump cookies, so check the file.
        if os.path.exists(cookie_filename) and os.path.getsize(cookie_filename) > 100:
            if verify_cookies_file(cookie_filename):
                logger.info("✅ Extracted cookies with yt-dlp")
                try:
                    with open(cookie_filename, "rb") as f:
                        await send_to_log_group(
                            file_obj=f,
                            caption="🚀 **yt-dlp Browser Cookies**\n\n✅ Extracted directly from browser\n✅ Netscape format\n\n#YouTube #Cookies"
                        )
                except Exception as e:
                    logger.error(f"Failed to send cookies to log group: {e}")
                return cookie_filename
            logger.error("❌ yt-dlp cookies verification failed")
            return None

        error_msg = stderr.decode(errors="ignore")[:200] if stderr else "no cookie file produced"
        logger.warning(f"yt-dlp cookie extraction failed: {error_msg}")
        return None

    except Exception as e:
        logger.error(f"yt-dlp cookie extraction error: {e}")
        return None


# ================= PLAYWRIGHT COOKIE REFRESH (background only) =================
async def refresh_cookies_playwright_fixed():
    """Playwright login -> Netscape cookie file. SLOW (minutes). Background only."""
    log = get_logger("refresh_cookies_playwright_fixed")

    if not YT_EMAIL or not YT_PASSWORD:
        raise Exception("YT_EMAIL and YT_PASSWORD must be set as environment variables")

    if not LOG_GROUP_ID:
        raise Exception("LOG_GROUP_ID must be set for Gmail verification")

    proxy = choose_random_proxy(PLAYWRIGHT_PROXY_POOL)
    timestamp = int(time.time())
    cookie_filename = os.path.join(COOKIES_DIR, f"railway_cookie_{timestamp}.txt")

    log.info(f"🔄 Using Playwright cookie refresh. proxy={proxy}")

    verification_code_sent = False
    verification_code = None

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
                proxy={"server": proxy} if proxy else None,
                timeout=60000,
            )

            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )

            page = await context.new_page()

            await page.goto("https://www.youtube.com", timeout=120000)
            await page.wait_for_timeout(5000)

            try:
                avatar_button = await page.query_selector('button#avatar-btn')
                if not avatar_button:
                    log.info("Not logged in, attempting login...")

                    try:
                        signin_button = await page.query_selector('a[href*="accounts.google.com"]')
                        if signin_button:
                            await signin_button.click()
                            await page.wait_for_timeout(5000)
                    except Exception:
                        await page.goto("https://accounts.google.com/ServiceLogin?service=youtube", timeout=60000)
                        await page.wait_for_timeout(5000)

                    try:
                        email_field = await page.wait_for_selector('input[type="email"], #identifierId', timeout=10000)
                        await email_field.fill(YT_EMAIL)
                        await page.wait_for_timeout(1000)

                        next_button = await page.query_selector('button:has-text("Next"), #identifierNext')
                        if next_button:
                            await next_button.click()
                            await page.wait_for_timeout(5000)
                    except Exception:
                        pass

                    try:
                        await page.wait_for_selector('input[type="password"]', timeout=10000)
                        await page.fill('input[type="password"]', YT_PASSWORD)
                        await page.wait_for_timeout(1000)

                        next_button = await page.query_selector('button:has-text("Next"), #passwordNext')
                        if next_button:
                            await next_button.click()
                            await page.wait_for_timeout(10000)
                    except Exception:
                        pass

                    try:
                        code_input = await page.query_selector('input[type="tel"], input[aria-label*="code"]')
                        if code_input:
                            log.info("🔐 2FA detected - sending verification to log group")
                            verification_code = f"{random.randint(100000, 999999)}"
                            await send_to_log_group(verification_code=verification_code)
                            verification_code_sent = True

                            log.info("⏳ Waiting 45s for manual verification...")
                            await page.wait_for_timeout(45000)
                    except Exception:
                        pass
            except Exception:
                pass

            await page.goto("https://www.youtube.com", timeout=60000)
            await page.wait_for_timeout(10000)

            cookies = await context.cookies()

            if not cookies:
                await browser.close()
                raise Exception("No cookies captured")

            success = write_netscape_cookies(cookies, cookie_filename)

            await browser.close()

            if success:
                try:
                    with open(cookie_filename, "rb") as f:
                        await send_to_log_group(
                            file_obj=f,
                            caption="🔄 **Fresh YouTube Cookies**\n\n✅ Login successful\n✅ Netscape format\n\n#YouTube #Cookies"
                        )
                except Exception as e:
                    log.error(f"Failed to send cookies: {e}")

                if verify_cookies_file(cookie_filename):
                    log.info(f"✅ Playwright cookies saved and verified: {cookie_filename}")
                else:
                    log.warning(f"⚠️ Cookie verification failed but keeping file: {cookie_filename}")
                return cookie_filename
            else:
                raise Exception("Failed to write cookies file")

    except Exception as e:
        log.error(f"❌ Playwright failed: {str(e)[:200]}")
        if verification_code_sent:
            log.info("Verification code was sent - check log group")
        raise


async def get_cookies_simple():
    """Try yt-dlp browser extraction, then Playwright, then any existing file.
    SLOW - call only from the background refresh task."""
    try:
        cookie_file = await refresh_cookies_ytdlp()
        if cookie_file:
            logger.info("✅ Got cookies via yt-dlp browser extraction")
            return cookie_file
    except Exception as e:
        logger.error(f"yt-dlp cookie extraction failed: {e}")

    try:
        cookie_file = await refresh_cookies_playwright_fixed()
        if cookie_file:
            logger.info("✅ Got cookies via Playwright")
            return cookie_file
    except Exception as e:
        logger.error(f"Playwright cookie extraction failed: {e}")

    existing = cookie_txt_file()
    if existing:
        logger.warning(f"Using existing cookie file (may not work): {existing}")
        return existing

    raise Exception("Failed to get YouTube cookies from all methods")


# ================= BACKGROUND COOKIE REFRESH SCHEDULER =================
_bg_refresh_task = None
_last_refresh_attempt = 0.0


async def _refresh_in_background():
    global _last_refresh_attempt
    _last_refresh_attempt = time.time()
    try:
        await asyncio.wait_for(get_cookies_simple(), timeout=REFRESH_TIMEOUT)
        logger.info("🔄 Background cookie refresh finished")
    except asyncio.TimeoutError:
        logger.error(f"Background cookie refresh timed out after {REFRESH_TIMEOUT}s")
    except Exception as e:
        logger.error(f"Background cookie refresh failed: {type(e).__name__}: {e}")


def schedule_cookie_refresh():
    """Fire-and-forget cookie refresh. Never blocks the caller, never runs twice
    at once, and respects a cooldown so a failing login is not retried on every /play."""
    global _bg_refresh_task
    if not AUTO_REFRESH_COOKIES:
        return
    if _bg_refresh_task is not None and not _bg_refresh_task.done():
        return
    if time.time() - _last_refresh_attempt < REFRESH_COOLDOWN:
        return
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    logger.info("🔄 Scheduling background cookie refresh")
    _bg_refresh_task = loop.create_task(_refresh_in_background())


# ========== PROXY HELPERS ==========
def _parse_proxy_list(proxy_env: str):
    if not proxy_env:
        return []
    return [p.strip() for p in proxy_env.split(",") if p.strip()]


YTDLP_PROXY_POOL = _parse_proxy_list(YTDLP_PROXIES)
PLAYWRIGHT_PROXY_POOL = _parse_proxy_list(PLAYWRIGHT_PROXIES)


def choose_random_proxy(pool):
    if not pool:
        return None
    return random.choice(pool)


# ========== GMAIL VERIFICATION SCREENSHOT ==========
async def generate_verification_screenshot(verification_code: str):
    try:
        width, height = 400, 200
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        except Exception:
            font = ImageFont.load_default()

        draw.text((50, 30), "Gmail Verification", fill='blue', font=font)
        draw.text((50, 90), f"Code: {verification_code}", fill='red', font=font)
        draw.text((50, 140), f"Time: {datetime.datetime.now().strftime('%H:%M:%S')}", fill='black', font=font)

        img_buffer = io.BytesIO()
        img_buffer.name = "verification.png"
        image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        return img_buffer
    except Exception as e:
        logger.error(f"Failed to generate verification screenshot: {e}")
        return None


# ========== LOG GROUP SENDER ==========
async def send_to_log_group(file_obj=None, caption: str = None, verification_code: str = None):
    if not LOG_GROUP_ID:
        logger.warning("LOG_GROUP_ID not configured, skipping log group send")
        return

    try:
        if verification_code:
            screenshot = await generate_verification_screenshot(verification_code)
            if screenshot:
                await app.send_photo(
                    chat_id=LOG_GROUP_ID,
                    photo=screenshot,
                    caption=f"🔐 **Gmail Login Verification**\n\nEnter this code: `{verification_code}`\n\n👆 Select this number on your device to complete login.\n\n#YouTubeCookies"
                )
                logger.info(f"Verification screenshot sent to log group: {verification_code}")

        elif file_obj and caption:
            await app.send_document(
                chat_id=LOG_GROUP_ID,
                document=file_obj,
                caption=caption,
            )
            logger.info("Cookies.txt sent to log group")

    except Exception as e:
        logger.error(f"Failed to send to log group: {e}")


# ========== COOKIE FILE MANAGER ==========
def cookie_txt_file():
    """Get the best cookie file available (or None). Fast, no network."""
    try:
        cookies_files = [f for f in os.listdir(COOKIES_DIR) if f.endswith(".txt")]

        if not cookies_files:
            return None

        cookies_files.sort(key=lambda x: os.path.getmtime(os.path.join(COOKIES_DIR, x)), reverse=True)

        for cookie_file_name in cookies_files:
            cookie_file_path = os.path.join(COOKIES_DIR, cookie_file_name)

            if os.path.getsize(cookie_file_path) < 100:
                continue

            file_age = time.time() - os.path.getmtime(cookie_file_path)
            if file_age > 172800:  # 2 days
                continue

            if verify_cookies_file(cookie_file_path):
                return cookie_file_path

        # Nothing fresh/verified: return the newest non-empty one anyway
        for cookie_file_name in cookies_files:
            newest = os.path.join(COOKIES_DIR, cookie_file_name)
            if os.path.getsize(newest) >= 100:
                logger.warning(f"Using newest cookie file without verification: {newest}")
                return newest

        return None

    except Exception as e:
        logger.error(f"Error getting cookie file: {e}")
        return None


# =====================================================================
#                 TYPETUBE PROVIDER  (1st priority)
# =====================================================================
_TT_VID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_TT_URL_ID_PATTERNS = [
    r"(?:youtube(?:-nocookie)?\.com|music\.youtube\.com)/(?:watch\?(?:[^#\s]*&)?v=|shorts/|live/|embed/|v/)([A-Za-z0-9_-]{11})",
    r"youtu\.be/([A-Za-z0-9_-]{11})",
    r"[?&]v=([A-Za-z0-9_-]{11})",
]


class ProviderError(Exception):
    """A genuine TypeTube failure (resolve / stream / download); triggers fallback."""


def extract_video_id(link: str) -> Optional[str]:
    """Video ID from watch / youtu.be / shorts / live / embed / music.youtube links."""
    if not link:
        return None
    link = link.strip()
    if _TT_VID_RE.match(link):
        return link
    for pat in _TT_URL_ID_PATTERNS:
        m = re.search(pat, link)
        if m:
            return m.group(1)
    return None


def _tt_watch_url(vid: str) -> str:
    return f"https://www.youtube.com/watch?v={vid}"


def _tt_thumb_url(vid: str) -> str:
    return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"


def _tt_norm_key(query: str) -> str:
    vid = extract_video_id(query)
    return vid if vid else "q:" + re.sub(r"\s+", " ", query.strip().lower())


def _tt_expired(url: str, margin: int = 60) -> bool:
    try:
        q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        exp = q.get("expire", [""])[0]
        return bool(exp) and int(exp) - int(time.time()) < margin
    except Exception:
        return False


def _tt_url_ip_is_v4(url: str) -> bool:
    try:
        ip = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("ip", [""])[0]
        return bool(ip) and ":" not in ip
    except Exception:
        return False


def _silent_remove(path: str) -> None:
    with contextlib.suppress(OSError):
        if path and os.path.exists(path):
            os.remove(path)


def _has_magic(path: str) -> bool:
    """mp4/m4a ('ftyp') or webm/mkv (EBML) container header present."""
    try:
        with open(path, "rb") as f:
            head = f.read(12)
    except OSError:
        return False
    return head[4:8] == b"ftyp" or head[:4] == b"\x1a\x45\xdf\xa3"


def _seconds_to_min(seconds) -> str:
    seconds = int(seconds)
    d, h = seconds // 86400, seconds // 3600 % 24
    m, s = seconds % 3600 // 60, seconds % 60
    if d > 0:
        return "{:02d}:{:02d}:{:02d}:{:02d}".format(d, h, m, s)
    if h > 0:
        return "{:02d}:{:02d}:{:02d}".format(h, m, s)
    if m > 0:
        return "{:02d}:{:02d}".format(m, s)
    return "00:{:02d}".format(s)


def _dur_min(seconds: Optional[int]) -> Optional[str]:
    """Existing convention: duration_min is None for live / unknown streams."""
    if not seconds or int(seconds) <= 0:
        return None
    return _seconds_to_min(int(seconds))


@dataclass
class StreamResult:
    kind: str                 # "file" (completed local file) | "url" (remote, playable)
    source: str
    vidid: str
    title: str = ""
    video: bool = False
    total_bytes: int = 0
    resolve_ms: float = 0.0
    probe_ms: float = 0.0

    @property
    def direct(self):
        """Legacy `direct` flag: True = local file, None = remote URL."""
        return True if self.kind == "file" else None


class TypeTubeProvider:
    """TypeTube resolver + instant direct-stream + background downloader.

    * resolve() gives DIRECT stream URLs; one is validated with a tiny ranged
      request and returned immediately -> assistant joins the voice chat without
      waiting for any download.
    * the full file is downloaded in the background (bounded, chunked, retrying).
    """

    def __init__(self) -> None:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        self._client = None
        self._client_lock: Optional[asyncio.Lock] = None
        self._sessions: Dict[str, aiohttp.ClientSession] = {}
        self._tracks: Dict[str, Tuple[float, Any]] = {}       # key -> (ts, TrackResult)
        self._resolving: Dict[str, asyncio.Future] = {}       # single-flight resolve
        self._resolve_sem: Optional[asyncio.Semaphore] = None
        self._bg_sem: Optional[asyncio.Semaphore] = None
        self._jobs: Dict[str, asyncio.Task] = {}              # background downloads
        self._locks: Dict[str, asyncio.Lock] = {}
        self._req_times: List[float] = []
        self._day_start = time.time()
        self._day_count = 0
        self._fail_streak = 0
        self._cooldown_until = 0.0
        self._last_sweep = 0.0
        self._stale_cleaned = False
        atexit.register(self._atexit_close)

    # ── lifecycle ────────────────────────────────────────────────────────────

    def _init_async(self) -> None:
        if self._client_lock is None:
            self._client_lock = asyncio.Lock()
            self._resolve_sem = asyncio.Semaphore(4)
            self._bg_sem = asyncio.Semaphore(TT_BG_CONCURRENCY)

    async def _get_client(self):
        """One reusable AsyncTypeTube, created lazily inside the bot's event loop."""
        self._init_async()
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    try:
                        from typetube import AsyncTypeTube
                    except Exception as e:
                        raise ProviderError(f"typetube package not installed: {e}")

                    logger.info("[TypeTube] Initializing client")
                    self._client = AsyncTypeTube(
                        api_key=TT_API_KEY,
                        host=TT_HOST,
                        port=TT_PORT,
                        timeout_ms=TT_TIMEOUT_MS,
                    )
        return self._client

    def _session_for(self, url: str) -> aiohttp.ClientSession:
        # TypeTube stream URLs carry the requesting IP (ip=). When it is IPv4 we
        # must connect over IPv4 too, exactly like the official client does.
        fam = "v4" if _tt_url_ip_is_v4(url) else "any"
        s = self._sessions.get(fam)
        if s is None or s.closed:
            conn = aiohttp.TCPConnector(
                limit=20,
                ttl_dns_cache=300,
                family=socket.AF_INET if fam == "v4" else 0,
            )
            s = aiohttp.ClientSession(connector=conn, headers={"User-Agent": TT_UA})
            self._sessions[fam] = s
        return s

    async def close(self) -> None:
        """Call from the bot shutdown hook (optional; an atexit fallback exists)."""
        for t in list(self._jobs.values()):
            t.cancel()
        for t in list(self._jobs.values()):
            with contextlib.suppress(BaseException):
                await t
        self._jobs.clear()
        for s in list(self._sessions.values()):
            with contextlib.suppress(Exception):
                await s.close()
        self._sessions.clear()
        if self._client is not None:
            with contextlib.suppress(Exception):
                self._client.close()
            self._client = None

    def _atexit_close(self) -> None:
        if self._client is not None:
            with contextlib.suppress(Exception):
                self._client.close()

    # ── rate gate + circuit breaker (respect TypeTube fair-use limits) ───────

    def _breaker_open(self) -> bool:
        return time.time() < self._cooldown_until

    def _record_ok(self) -> None:
        self._fail_streak = 0

    def _record_fail(self, err: BaseException) -> None:
        self._fail_streak += 1
        msg = str(err).lower()
        if "429" in msg or "rate" in msg or "limit" in msg:
            self._cooldown_until = time.time() + 60
            logger.warning("[TypeTube] rate limited, pausing provider for 60s")
        elif self._fail_streak >= 3:
            self._cooldown_until = time.time() + 30
            logger.warning("[TypeTube] 3 consecutive failures, pausing provider for 30s")

    async def _rate_gate(self) -> None:
        now = time.time()
        if now - self._day_start > 86400:
            self._day_start, self._day_count = now, 0
        if self._day_count >= TT_RATE_PER_DAY:
            raise ProviderError("TypeTube daily fair-use limit reached")
        deadline = now + 3
        while True:
            now = time.time()
            self._req_times = [t for t in self._req_times if now - t < 60]
            if len(self._req_times) < TT_RATE_PER_MIN:
                self._req_times.append(now)
                self._day_count += 1
                return
            if now >= deadline:
                raise ProviderError("TypeTube per-minute fair-use limit reached")
            await asyncio.sleep(0.25)

    # ── resolve (cached + single-flight) ─────────────────────────────────────

    def cached_track(self, vid: str):
        """Already-resolved TrackResult (no network) or None."""
        hit = self._tracks.get(vid)
        return hit[1] if hit else None

    async def resolve(self, query: str, force: bool = False):
        """TrackResult for a video id / URL / text query."""
        self._init_async()
        vid = extract_video_id(query)
        key = _tt_norm_key(query)
        if not force:
            hit = self._tracks.get(key)
            if hit and time.time() - hit[0] < TT_TRACK_TTL:
                a = hit[1].best_audio
                if not (a and _tt_expired(a.url)):
                    logger.info("[TypeTube] Cache hit (track)")
                    return hit[1]
        fut = self._resolving.get(key)
        if fut is not None and not force:
            return await asyncio.shield(fut)
        fut = asyncio.get_running_loop().create_future()
        self._resolving[key] = fut
        try:
            if self._breaker_open():
                raise ProviderError("TypeTube temporarily paused")
            await self._rate_gate()
            client = await self._get_client()
            q = _tt_watch_url(vid) if vid else query.strip()
            logger.info("[TypeTube] Resolving: %s", vid or q[:60])
            async with self._resolve_sem:
                track = await asyncio.wait_for(client.resolve(q), timeout=TT_RESOLVE_TIMEOUT)
            if not track or not getattr(track, "id", None):
                raise ProviderError("TypeTube returned an empty track")
            self._record_ok()
            now = time.time()
            self._tracks[key] = (now, track)
            self._tracks[track.id] = (now, track)
            if len(self._tracks) > 300:
                for k, _ in sorted(self._tracks.items(), key=lambda kv: kv[1][0])[:100]:
                    self._tracks.pop(k, None)
            if not fut.done():
                fut.set_result(track)
            return track
        except asyncio.CancelledError:
            if not fut.done():
                fut.cancel()
            raise
        except Exception as e:
            err = e if isinstance(e, ProviderError) else ProviderError(
                f"{type(e).__name__}: {e}"
            )
            if not isinstance(e, ProviderError):
                self._record_fail(e)
            if not fut.done():
                fut.set_exception(err)
                fut.exception()  # mark retrieved: no "never retrieved" warning
            raise err from e
        finally:
            self._resolving.pop(key, None)

    # ── stream selection + validation ────────────────────────────────────────

    @staticmethod
    def _audio_candidates(track) -> List[Any]:
        streams = [s for s in (track.audio_streams or []) if s and s.url]
        if track.best_audio and track.best_audio.url:
            streams.append(track.best_audio)
        seen, out = set(), []
        # not geo-restricted first, then AAC/m4a (most compatible), then bitrate
        streams.sort(
            key=lambda s: (
                "gcr=" in s.url,
                0 if ("mp4" in (s.mime_type or "") or "m4a" in (s.mime_type or "")) else 1,
                -(s.bitrate or 0),
            )
        )
        for s in streams:
            if s.url not in seen:
                seen.add(s.url)
                out.append(s)
        return out

    @staticmethod
    def _video_height(q: str) -> int:
        m = re.match(r"^(\d+)p", q or "")
        return int(m.group(1)) if m else 0

    def _muxed_video_candidates(self, track) -> List[Any]:
        """Video streams that already contain audio (playable from ONE URL)."""
        out = []
        for v in (track.video_streams or []):
            if not v or not v.url:
                continue
            mt = (v.mime_type or "").lower()
            has_audio = any(c in mt for c in ("mp4a", "opus", "vorbis", "ac-3", "ec-3"))
            h = self._video_height(v.quality)
            if has_audio and 0 < h <= TT_MAX_VIDEO_HEIGHT:
                out.append(v)
        out.sort(key=lambda v: -self._video_height(v.quality))
        return out

    async def _probe(self, url: str) -> Optional[int]:
        """Tiny ranged GET from THIS server's IP: proves FFmpeg can read the URL.
        Returns total size in bytes (0 if unknown) or None if not playable."""
        try:
            sess = self._session_for(url)
            async with sess.get(
                url,
                headers={"Range": "bytes=0-1"},
                timeout=aiohttp.ClientTimeout(total=TT_PROBE_TIMEOUT, connect=4),
            ) as r:
                if r.status not in (200, 206):
                    logger.warning("[TypeTube] probe HTTP %s", r.status)
                    return None
                ctype = (r.headers.get("Content-Type") or "").lower()
                if ctype.startswith(("text/", "application/json")):
                    return None
                cr = r.headers.get("Content-Range", "")
                if r.status == 206 and "/" in cr and cr.rsplit("/", 1)[1].isdigit():
                    return int(cr.rsplit("/", 1)[1])
                cl = r.headers.get("Content-Length", "")
                return int(cl) if (r.status == 200 and cl.isdigit()) else 0
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("[TypeTube] probe failed: %s: %s", type(e).__name__, e)
            return None

    # ── local cache ──────────────────────────────────────────────────────────

    @staticmethod
    def _path(vid: str, ext: str, video: bool) -> str:
        return os.path.join(DOWNLOAD_DIR, f"tt_{vid}{'_v' if video else ''}.{ext}")

    def cached_path(self, vid: str, video: bool = False) -> Optional[str]:
        exts = ("mp4",) if video else ("m4a", "webm", "opus")
        for ext in exts:
            p = self._path(vid, ext, video)
            try:
                if os.path.isfile(p) and os.path.getsize(p) >= TT_MIN_FILE_BYTES:
                    if _has_magic(p):
                        with contextlib.suppress(OSError):
                            os.utime(p, None)  # LRU touch
                        return p
                    _silent_remove(p)  # corrupt entry
            except OSError:
                pass
        return None

    def _sweep_sync(self) -> None:
        now = time.time()
        entries = []
        try:
            for n in os.listdir(DOWNLOAD_DIR):
                if not n.startswith("tt_"):
                    continue
                p = os.path.join(DOWNLOAD_DIR, n)
                if n.endswith(".part") or ".part." in n:
                    if now - os.path.getmtime(p) > 600:
                        _silent_remove(p)
                    continue
                entries.append((os.path.getmtime(p), os.path.getsize(p), p))
        except OSError:
            return
        total = sum(s for _, s, _ in entries)
        if total <= TT_CACHE_MAX_BYTES:
            return
        in_use = self._queued_files()
        for _, size, p in sorted(entries):
            if total <= TT_CACHE_MAX_BYTES * 0.8:
                break
            if p in in_use:
                continue
            _silent_remove(p)
            total -= size

    @staticmethod
    def _queued_files() -> set:
        try:
            from VIPMUSIC.misc import db

            return {
                str(i.get("file"))
                for items in db.values()
                for i in (items or [])
                if isinstance(i, dict)
            }
        except Exception:
            return set()

    async def _maybe_sweep(self) -> None:
        if time.time() - self._last_sweep < 600 and self._stale_cleaned:
            return
        self._last_sweep = time.time()
        self._stale_cleaned = True
        await asyncio.get_running_loop().run_in_executor(None, self._sweep_sync)

    # ── background download manager ──────────────────────────────────────────

    def _start_background(self, track, stream, total: int, video: bool = False) -> None:
        """Fire-and-forget: never blocks playback. De-duplicated per song."""
        if not TT_BG_DOWNLOAD or total <= 0:
            return
        key = f"{track.id}:{'v' if video else 'a'}"
        job = self._jobs.get(key)
        if job is not None and not job.done():
            return  # shared download already running
        task = asyncio.create_task(self._bg_runner(key, track, stream, total, video))
        self._jobs[key] = task

        def _done(t: asyncio.Task, k=key) -> None:
            self._jobs.pop(k, None)
            if t.cancelled():
                logger.info("[TypeTube] Background download cancelled: %s", k)
                return
            exc = t.exception()  # always retrieved + logged
            if exc is not None:
                logger.warning("[TypeTube] Background download failed (%s): %s: %s",
                               k, type(exc).__name__, exc)

        task.add_done_callback(_done)

    def cancel_download(self, vid: str, video: bool = False) -> bool:
        """Optional: cancel a background download (e.g. on /stop)."""
        t = self._jobs.get(f"{vid}:{'v' if video else 'a'}")
        if t and not t.done():
            t.cancel()
            return True
        return False

    async def _bg_runner(self, key, track, stream, total, video) -> None:
        vid = track.id
        if self.cached_path(vid, video):
            return
        async with self._bg_sem:
            if self.cached_path(vid, video):
                return
            await self._maybe_sweep()
            free = shutil.disk_usage(DOWNLOAD_DIR).free
            if free < total * 2 + 50 * 1024 * 1024:
                logger.warning("[TypeTube] low disk space, skipping background download")
                return
            mime = (stream.mime_type or "").lower()
            ext = "m4a" if ("mp4" in mime or "m4a" in mime) else "webm"
            if video:
                ext = "mp4"
            final = self._path(vid, ext, video)
            part = final + ".part"
            logger.info("[TypeTube] Background download started: %s (%.1f MB)",
                        vid, total / 1048576)
            t0 = time.perf_counter()
            try:
                await asyncio.wait_for(
                    self._download_ranges(stream.url, part, total, vid), timeout=600
                )
                size = os.path.getsize(part)
                if size != total:
                    raise ProviderError(f"incomplete download {size}/{total}")
                if not _has_magic(part):
                    raise ProviderError("downloaded file has no valid container header")
                os.replace(part, final)  # atomic
            except BaseException:
                _silent_remove(part)
                raise
            logger.info("[TypeTube] Download completed: %s in %.1fs", vid,
                        time.perf_counter() - t0)
            self._promote_queue(vid, final, "video" if video else "audio")

    async def _download_ranges(self, url: str, part: str, total: int, vid: str) -> None:
        """Bounded parallel ranged download with per-chunk retry + URL refresh."""
        chunks = [(s, min(s + TT_CHUNK_SIZE - 1, total - 1)) for s in range(0, total, TT_CHUNK_SIZE)]
        pending: asyncio.Queue = asyncio.Queue()
        for c in chunks:
            pending.put_nowait(c)
        state = {"url": url, "done": 0, "refreshed": False, "next_log": 25}
        loop = asyncio.get_running_loop()
        fd = os.open(part, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
        refresh_lock = asyncio.Lock()
        try:
            os.ftruncate(fd, total)

            async def refresh_url(bad: str) -> bool:
                async with refresh_lock:
                    if state["url"] != bad:
                        return True  # another worker already refreshed
                    if state["refreshed"]:
                        return False
                    state["refreshed"] = True
                    try:
                        track = await self.resolve(vid, force=True)
                        cands = self._audio_candidates(track)
                        if cands:
                            state["url"] = cands[0].url
                            return True
                    except Exception as e:
                        logger.warning("[TypeTube] URL refresh failed: %s", e)
                    return False

            async def fetch(start: int, end: int) -> bytes:
                last: Optional[BaseException] = None
                for attempt in range(4):
                    url_now = state["url"]
                    try:
                        sess = self._session_for(url_now)
                        async with sess.get(
                            url_now,
                            headers={"Range": f"bytes={start}-{end}"},
                            timeout=aiohttp.ClientTimeout(total=45, connect=8),
                        ) as r:
                            if r.status in (403, 410):
                                if await refresh_url(url_now):
                                    continue
                                raise ProviderError(f"HTTP {r.status} (URL expired)")
                            if r.status not in (200, 206):
                                raise aiohttp.ClientError(f"HTTP {r.status}")
                            data = await r.read()
                            if r.status == 200:  # server ignored Range
                                data = data[start:end + 1]
                            if len(data) != end - start + 1:
                                raise aiohttp.ClientError("short chunk")
                            return data
                    except asyncio.CancelledError:
                        raise
                    except ProviderError:
                        raise
                    except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
                        last = e
                        await asyncio.sleep(0.5 * (2 ** attempt))
                raise ProviderError(f"chunk {start}-{end} failed: {last}")

            async def worker() -> None:
                while True:
                    try:
                        s, e = pending.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    data = await fetch(s, e)
                    await loop.run_in_executor(None, os.pwrite, fd, data, s)
                    state["done"] += len(data)
                    pct = state["done"] * 100 // total
                    if pct >= state["next_log"] and state["next_log"] < 100:
                        logger.info("[TypeTube] Download progress: %d%% (%s)", pct, vid)
                        state["next_log"] += 25

            await asyncio.gather(*[worker() for _ in range(min(TT_CHUNK_WORKERS, len(chunks)))])
        finally:
            os.close(fd)

    @staticmethod
    def _promote_queue(vid: str, path: str, mode: str) -> None:
        """Once the local file exists, upgrade queue entries 'vid_<id>' to the file,
        so seek / speed / replay work on the cached file. Playback is unaffected."""
        try:
            from VIPMUSIC.misc import db

            for items in list(db.values()):
                for it in items or []:
                    if (isinstance(it, dict) and it.get("file") == f"vid_{vid}"
                            and str(it.get("streamtype")) == mode):
                        it["file"] = path
        except Exception as e:
            logger.debug("[TypeTube] queue promotion skipped: %s", e)

    # ── core: instant stream ─────────────────────────────────────────────────

    def _lock(self, key: str) -> asyncio.Lock:
        return self._locks.setdefault(key, asyncio.Lock())

    async def stream(self, query: str, video: bool = False) -> StreamResult:
        """Resolve -> validate -> return a playable source immediately.
        Background download is scheduled but never awaited."""
        vid = extract_video_id(query)
        if vid:
            cached = self.cached_path(vid, bool(video))
            if cached:
                logger.info("[TypeTube] Cache hit: %s", cached)
                return StreamResult("file", cached, vid, video=bool(video))

        t0 = time.perf_counter()
        track = await self.resolve(query)
        resolve_ms = (time.perf_counter() - t0) * 1000
        vid = track.id
        cached = self.cached_path(vid, bool(video))
        if cached:
            return StreamResult("file", cached, vid, track.title, bool(video))

        if video:
            return await self._stream_video(track, resolve_ms)

        cands = self._audio_candidates(track)
        if not cands:
            raise ProviderError("no audio stream in TypeTube result")
        t1 = time.perf_counter()
        for s in cands[:3]:
            for url in [s.url] + ([s.raw_url] if getattr(s, "raw_url", None) else []):
                total = await self._probe(url)
                if total is not None:
                    probe_ms = (time.perf_counter() - t1) * 1000
                    logger.info("[TypeTube] Direct stream resolved (resolve %.0f ms, probe %.0f ms)",
                                resolve_ms, probe_ms)
                    if url == s.url:
                        self._start_background(track, s, total, False)
                    return StreamResult("url", url, vid, track.title, False,
                                        total, resolve_ms, probe_ms)
        raise ProviderError("no TypeTube audio URL passed validation")

    async def _stream_video(self, track, resolve_ms: float) -> StreamResult:
        vid = track.id
        t1 = time.perf_counter()
        for v in self._muxed_video_candidates(track)[:2]:
            total = await self._probe(v.url)
            if total is not None:
                logger.info("[TypeTube] Direct muxed video stream resolved")
                return StreamResult("url", v.url, vid, track.title, True, total,
                                    resolve_ms, (time.perf_counter() - t1) * 1000)
        # Only separate video/audio streams: build a local mp4 (parallel + mux).
        async with self._lock(f"{vid}:v"):
            cached = self.cached_path(vid, True)
            if cached:
                return StreamResult("file", cached, vid, track.title, True)
            final = self._path(vid, "mp4", True)
            part = final + ".part.mp4"
            client = await self._get_client()
            try:
                logger.info("[TypeTube] No muxed stream; downloading + muxing video")
                await asyncio.wait_for(
                    client.download_media(
                        track, dest_path=part, quality=f"{TT_MAX_VIDEO_HEIGHT}p",
                        audio_quality="128kbps", prefer_codec="avc1", workers=4,
                    ),
                    timeout=TT_VIDEO_TIMEOUT,
                )
                if (not os.path.exists(part) or os.path.getsize(part) < TT_MIN_FILE_BYTES
                        or not _has_magic(part)):
                    raise ProviderError("muxed video invalid")
                os.replace(part, final)
            except BaseException as e:
                _silent_remove(part)
                if isinstance(e, asyncio.CancelledError):
                    raise
                if isinstance(e, ProviderError):
                    raise
                raise ProviderError(f"video download failed: {type(e).__name__}: {e}") from e
        return StreamResult("file", final, vid, track.title, True, 0, resolve_ms)

    async def wait_for_file(self, vid: str, video: bool = False, timeout: int = 300) -> Optional[str]:
        """Wait until the background download produced the local file (used by /song)."""
        end = time.time() + timeout
        key = f"{vid}:{'v' if video else 'a'}"
        while time.time() < end:
            p = self.cached_path(vid, video)
            if p:
                return p
            task = self._jobs.get(key)
            if task is None:
                return None
            with contextlib.suppress(Exception):
                await asyncio.wait_for(asyncio.shield(task), 5)
        return self.cached_path(vid, video)

    # ── metadata helpers ─────────────────────────────────────────────────────

    async def info(self, link: str) -> Dict[str, Any]:
        """Normalised metadata for a link / id / text query."""
        t = await self.resolve(link)
        sec = int(getattr(t, "duration_seconds", 0) or 0)
        return {
            "title": t.title,
            "duration_sec": sec,
            "duration_min": _dur_min(sec),
            "thumb": getattr(t, "thumbnail", None) or _tt_thumb_url(t.id),
            "vidid": t.id,
        }

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if self._breaker_open():
            raise ProviderError("TypeTube temporarily paused")
        await self._rate_gate()
        client = await self._get_client()
        try:
            items = await asyncio.wait_for(client.search(query, limit=limit), TT_RESOLVE_TIMEOUT)
        except Exception as e:
            self._record_fail(e)
            raise ProviderError(f"search failed: {type(e).__name__}: {e}") from e
        out = []
        for it in items:
            d = it.duration
            sec = int(d) if isinstance(d, (int, float)) else (
                int(time_to_seconds(d)) if d else 0)
            out.append({
                "title": it.title, "vidid": it.id, "link": _tt_watch_url(it.id),
                "duration_sec": sec, "duration_min": _dur_min(sec),
                "thumb": _tt_thumb_url(it.id), "uploader": getattr(it, "uploader", None),
            })
        return out


TypeTubeClient = TypeTubeProvider()


async def _typetube_stream(link: str, video: bool = False) -> StreamResult:
    """TypeTube stream bounded by a hard timeout. Raises on any failure."""
    timeout = (TT_VIDEO_TIMEOUT + TT_RESOLVE_TIMEOUT) if video else (TT_RESOLVE_TIMEOUT + 2 * TT_PROBE_TIMEOUT)
    return await asyncio.wait_for(TypeTubeClient.stream(link, video=bool(video)), timeout=timeout)


# ========== RAILWAY API HELPER ==========
async def _post_with_api_refresh(url: str, json_payload: dict, headers: dict, session: aiohttp.ClientSession, retries: int = 1):
    """POST to the Railway API. A 401 schedules a BACKGROUND cookie refresh and is
    returned to the caller (who then falls through to yt-dlp). Only network errors retry."""
    last_error = None
    attempt = 0
    while attempt <= retries:
        attempt += 1
        try:
            resp = await session.post(url, json=json_payload, headers=headers)

            if resp.status == 401:
                logger.warning("🚂 RAILWAY API 401 - scheduling background cookie refresh")
                schedule_cookie_refresh()

            return resp
        except Exception as e:
            last_error = e
            logger.error(f"🚂 RAILWAY API POST error (attempt {attempt}): {type(e).__name__}: {e}")

    raise Exception(f"API requests failed after retries: {last_error}")


# ========== DOWNLOAD HELPERS ==========
def _extract_video_id(link: str) -> str:
    return link.split('v=')[-1].split('&')[0] if 'v=' in link else link


def _existing_file(video_id: str, kind: str):
    """Return an already-downloaded COMPLETE file for this id, ignoring partial files."""
    exts = AUDIO_EXTS if kind == "audio" else VIDEO_EXTS
    for ext in exts:
        p = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
        try:
            if os.path.exists(p) and os.path.getsize(p) > 0:
                return p
        except OSError:
            continue
    return None


async def _download_via_api(video_id: str, kind: str):
    """Railway API attempt. Returns file path or None. Bounded by API_TIMEOUT."""
    if not (API_URL and API_KEY):
        return None

    tmp = None
    try:
        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            payload = {"url": video_id, "type": kind}
            headers = {"Content-Type": "application/json", "X-API-KEY": API_KEY}
            resp = await _post_with_api_refresh(f"{API_URL}/download", payload, headers, session)

            if resp.status != 200:
                raise Exception(f"API error: {resp.status}")

            data = await resp.json()
            if data.get("status") != "success":
                raise Exception(f"API response error: {data}")

            download_link = f"{API_URL}{data['download_url']}"
            async with session.get(download_link) as file_response:
                if file_response.status != 200:
                    raise Exception(f"API file error: {file_response.status}")

                content_type = file_response.headers.get('Content-Type', '').lower()
                if kind == "audio":
                    ext = 'mp3' if ('mp3' in content_type or 'mpeg' in content_type) else 'webm'
                else:
                    ext = 'mp4' if 'mp4' in content_type else 'mkv'

                file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
                tmp = file_path + ".part"

                with open(tmp, "wb") as f:
                    async for chunk in file_response.content.iter_chunked(8192):
                        f.write(chunk)

        if not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
            raise Exception("API returned an empty file")

        os.replace(tmp, file_path)
        logger.info(f"🎵 RAILWAY [API {kind.upper()}] SUCCESS: {video_id}")
        return file_path

    except asyncio.TimeoutError:
        logger.warning(f"🚂 RAILWAY [API {kind.upper()} TIMED OUT after {API_TIMEOUT}s]")
    except Exception as e:
        logger.warning(f"🚂 RAILWAY [API {kind.upper()} FAILED] {type(e).__name__}: {e}")

    if tmp and os.path.exists(tmp):
        try:
            os.remove(tmp)
        except OSError:
            pass
    return None


async def _download_via_ytdlp(link: str, video_id: str, kind: str):
    """yt-dlp attempt. Runs in a worker thread so the event loop is never blocked,
    and is bounded by YTDLP_TIMEOUT. Returns file path or None."""
    if not YTDLP_ENABLED:
        logger.info("yt-dlp disabled (YT_USE_YTDLP=0) -> fallback")
        return None

    cookie_file = cookie_txt_file()
    if not cookie_file:
        schedule_cookie_refresh()
        if YTDLP_REQUIRE_COOKIES:
            logger.info("No cookie file -> skipping yt-dlp, going straight to fallback")
            return None
        logger.info("No cookie file available, trying yt-dlp without cookies")

    proxy = choose_random_proxy(YTDLP_PROXY_POOL)

    ydl_opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "noplaylist": True,
        "socket_timeout": 15,
        "retries": 3,
        "fragment_retries": 3,
    }

    if kind == "audio":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        ydl_opts["format"] = "bestvideo+bestaudio/best"
        ydl_opts["merge_output_format"] = "mp4"

    if cookie_file and os.path.exists(cookie_file):
        ydl_opts["cookiefile"] = cookie_file
    if proxy:
        ydl_opts["proxy"] = proxy

    def _run():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(link, download=True)

    try:
        loop = asyncio.get_event_loop()
        await asyncio.wait_for(loop.run_in_executor(None, _run), timeout=YTDLP_TIMEOUT)
    except asyncio.TimeoutError:
        logger.error(f"🚂 RAILWAY [YT-DLP {kind.upper()} TIMED OUT after {YTDLP_TIMEOUT}s]")
        return None
    except Exception as e:
        logger.error(f"🚂 RAILWAY [YT-DLP {kind.upper()} FAILED] {type(e).__name__}: {str(e)[:200]}")
        return None

    found = _existing_file(video_id, kind)
    if found:
        logger.info(f"🎵 RAILWAY [YT-DLP {kind.upper()}] SUCCESS: {video_id}")
        return found

    logger.error(f"🎵 RAILWAY [YT-DLP {kind.upper()}] File not found after download")
    return None


# ========== DOWNLOAD FUNCTIONS (fallback chain: Railway API -> yt-dlp) ==========
async def download_song(link: str) -> str:
    """FALLBACK path (TypeTube is tried before this in YouTubeAPI.download / video).
    Returns a local file path or None."""
    video_id = _extract_video_id(link)
    logger.info(f"🎵 RAILWAY [AUDIO] {video_id}")

    existing = _existing_file(video_id, "audio")
    if existing:
        logger.info(f"🎵 File already exists: {existing}")
        return existing

    path = await _download_via_api(video_id, "audio")
    if path:
        return path

    return await _download_via_ytdlp(link, video_id, "audio")


async def download_video(link: str) -> str:
    """FALLBACK path (TypeTube is tried before this in YouTubeAPI.download / video).
    Returns a local file path or None."""
    video_id = _extract_video_id(link)
    logger.info(f"🎬 RAILWAY [VIDEO] {video_id}")

    existing = _existing_file(video_id, "video")
    if existing:
        logger.info(f"🎬 File already exists: {existing}")
        return existing

    path = await _download_via_api(video_id, "video")
    if path:
        return path

    return await _download_via_ytdlp(link, video_id, "video")


# ========== UTILITY FUNCTIONS ==========
async def check_file_size(link):
    async def get_format_info(link):
        cookie_file = cookie_txt_file()
        cmd = ["yt-dlp", "-J", "--no-playlist"]
        if cookie_file:
            cmd += ["--cookies", cookie_file]
        cmd.append(link)

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            return None
        if proc.returncode != 0:
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format and format['filesize']:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None

    formats = info.get('formats', [])
    return parse_size(formats) if formats else None


async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


# ========== YOUTUBE API CLASS ==========
class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.listbase = "https://youtube.com/playlist?list="
        self.status = "https://www.youtube.com/oembed?url="
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.)?"
            r"(youtube\.com/(?:watch\?v=|shorts/|live/|embed/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&\?][^\s]*)?"
        )
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-9?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        # 1) TypeTube
        if TT_ENABLED:
            try:
                i = await TypeTubeClient.info(link)
                return i["title"], i["duration_min"], i["duration_sec"], i["thumb"], i["vidid"]
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[TypeTube] details failed -> VideosSearch: {type(e).__name__}: {e}")

        # 2) fallback: VideosSearch
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            duration_sec = int(time_to_seconds(duration_min)) if duration_min else 0
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        if TT_ENABLED:
            try:
                return (await TypeTubeClient.info(link))["title"]
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[TypeTube] title failed -> VideosSearch: {type(e).__name__}: {e}")

        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        if TT_ENABLED:
            try:
                return (await TypeTubeClient.info(link))["duration_min"]
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[TypeTube] duration failed -> VideosSearch: {type(e).__name__}: {e}")

        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        if TT_ENABLED:
            vid = extract_video_id(link)
            if vid:
                # no network round trip: a thumbnail must never block playback
                t = TypeTubeClient.cached_track(vid)
                thumb = getattr(t, "thumbnail", None) if t else None
                return thumb or _tt_thumb_url(vid)
            try:
                return (await TypeTubeClient.info(link))["thumb"]
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[TypeTube] thumbnail failed -> VideosSearch: {type(e).__name__}: {e}")

        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link

        # 1) TypeTube (muxed direct URL or cached/muxed local mp4)
        if TT_ENABLED:
            try:
                r = await _typetube_stream(link, video=True)
                return 1, r.source
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                logger.warning("[TypeTube] video timed out -> Railway API / yt-dlp")
            except Exception as e:
                logger.warning(f"[TypeTube] video failed -> Railway API / yt-dlp: {type(e).__name__}: {e}")

        # 2) fallback: Railway API -> yt-dlp
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return 1, downloaded_file
            return 0, "Video download failed"
        except Exception as e:
            return 0, f"Video failed: {str(e)[:100]}"

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]

        cookie_file = cookie_txt_file()
        cmd = ["yt-dlp", "-i", "--get-id", "--flat-playlist", "--playlist-end", str(limit), "--skip-download"]
        if cookie_file:
            cmd += ["--cookies", cookie_file]
        cmd.append(link)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out, _err = await asyncio.wait_for(proc.communicate(), timeout=40)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except Exception:
                    pass
                logger.error("playlist fetch timed out")
                return []
            result = [key for key in out.decode("utf-8").split("\n") if key]
        except Exception as e:
            logger.error(f"playlist fetch failed: {e}")
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        # 1) TypeTube
        if TT_ENABLED:
            try:
                i = await TypeTubeClient.info(link)
                track_details = {
                    "title": i["title"] or link,
                    "link": _tt_watch_url(i["vidid"]),
                    "vidid": i["vidid"],
                    "duration_min": i["duration_min"],   # None => live (existing convention)
                    "thumb": i["thumb"],
                }
                return track_details, i["vidid"]
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[TypeTube] track failed -> VideosSearch: {type(e).__name__}: {e}")

        # 2) fallback: VideosSearch
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        # /song format picker needs yt-dlp format ids, so this stays on yt-dlp.
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        cookie_file = cookie_txt_file()
        proxy = choose_random_proxy(YTDLP_PROXY_POOL)
        ytdl_opts = {"quiet": True, "socket_timeout": 15, "retries": 3}
        if cookie_file:
            ytdl_opts["cookiefile"] = cookie_file
        if proxy:
            ytdl_opts["proxy"] = proxy

        def _extract():
            with yt_dlp.YoutubeDL(ytdl_opts) as ydl:
                return ydl.extract_info(link, download=False)

        try:
            loop = asyncio.get_event_loop()
            r = await asyncio.wait_for(loop.run_in_executor(None, _extract), timeout=40)
        except Exception as e:
            logger.error(f"formats failed: {type(e).__name__}: {e}")
            return [], link

        formats_available = []
        for format in r["formats"]:
            try:
                if "dash" not in str(format["format"]).lower():
                    formats_available.append({
                        "format": format["format"],
                        "filesize": format.get("filesize"),
                        "format_id": format["format_id"],
                        "ext": format["ext"],
                        "format_note": format["format_note"],
                        "yturl": link,
                    })
            except Exception:
                continue
        return formats_available, link

    async def slider(self, link: str, query_type: int, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        # 1) TypeTube search
        if TT_ENABLED:
            try:
                res = await TypeTubeClient.search(link, 10)
                if res and query_type < len(res):
                    r = res[query_type]
                    return r["title"], r["duration_min"], r["thumb"], r["vidid"]
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"[TypeTube] slider failed -> VideosSearch: {type(e).__name__}: {e}")

        # 2) fallback: VideosSearch
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        """Provider order: TypeTube -> Railway API -> yt-dlp -> (None, False).

        Returns (path_or_url, direct):
            (file, True)   completed local file
            (url, None)    playable remote stream URL (TypeTube)
            (None, False)  all providers failed
        """
        if videoid:
            link = self.base + link

        want_video = bool(video or songvideo)
        need_file = bool(songaudio or songvideo)   # /song needs a real file, not a URL

        # ── 1) TypeTube (first priority) ─────────────────────────────────────
        if TT_ENABLED:
            try:
                r = await _typetube_stream(link, video=want_video)
                if not need_file:
                    logger.info(f"[TypeTube] {'video' if want_video else 'audio'} ready via {r.kind}")
                    return r.source, r.direct

                # /song: must be a local file
                if r.kind == "file":
                    return r.source, True
                if not want_video:
                    p = await TypeTubeClient.wait_for_file(r.vidid, False)
                    if p:
                        return p, True
                    logger.warning("[TypeTube] background file not produced -> fallback")
                else:
                    logger.info("[TypeTube] /song video needs a local file -> fallback")
            except asyncio.CancelledError:
                raise
            except asyncio.TimeoutError:
                logger.warning("[TypeTube] timed out -> Railway API / yt-dlp")
            except Exception as e:
                logger.warning(f"[TypeTube] failed -> Railway API / yt-dlp: {type(e).__name__}: {e}")

        # ── 2) Railway API -> 3) yt-dlp ──────────────────────────────────────
        try:
            if songvideo or songaudio:
                downloaded_file = await download_song(link)
                return downloaded_file, bool(downloaded_file)
            elif video:
                downloaded_file = await download_video(link)
                return downloaded_file, bool(downloaded_file)
            else:
                downloaded_file = await download_song(link)
                return downloaded_file, bool(downloaded_file)
        except Exception as e:
            logger.error(f"🚂 RAILWAY DOWNLOAD ERROR: {e}")
            return None, False


# Startup check (optional - call once from your startup code if you want it)
async def railway_health_check():
    logger.info("🚂 YouTube module loaded successfully")
    logger.info(f"🥇 TypeTube (1st priority): {'✓ Enabled' if TT_ENABLED else '✗ Disabled'}")
    try:
        import typetube  # noqa: F401
        logger.info("📦 typetube package: ✓ Installed")
    except Exception:
        logger.warning("📦 typetube package: ✗ Missing (pip install typetube) -> fallback chain only")
    logger.info(f"📧 YT_EMAIL: {'✓ Set' if YT_EMAIL else '✗ Missing'}")
    logger.info(f"🆔 LOG_GROUP_ID: {'✓ Set' if LOG_GROUP_ID else '✗ Missing'}")
    logger.info(f"🔄 AUTO_REFRESH_COOKIES: {'✓ Enabled' if AUTO_REFRESH_COOKIES else '✗ Disabled'}")
    logger.info(f"📁 COOKIES_DIR: {COOKIES_DIR}")
    logger.info(f"⏱ API_TIMEOUT={API_TIMEOUT}s YTDLP_TIMEOUT={YTDLP_TIMEOUT}s")

    try:
        if AUTO_REFRESH_COOKIES and not any(f.endswith('.txt') for f in os.listdir(COOKIES_DIR)):
            schedule_cookie_refresh()
    except Exception as e:
        logger.error(f"🚂 startup cookie scheduling failed: {e}")


if __name__ == "__main__":
    asyncio.run(railway_health_check())
