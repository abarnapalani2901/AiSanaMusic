# Youtube.py (FIXED - non-blocking downloads, bounded timeouts, background cookie refresh)
#
# Key behaviour:
#   * download_song / download_video NEVER hang: API attempt and yt-dlp attempt each
#     have their own timeout, and yt-dlp runs in a worker thread (it no longer blocks
#     the event loop, so asyncio.wait_for in JioSaavn.download_with_fallback can fire).
#   * Cookie refresh (yt-dlp browser / Playwright) happens ONLY in a background task,
#     with a cooldown. It is never awaited inside the /play path.
#   * On any failure download_* returns None -> YouTube.download returns (None, False)
#     -> download_with_fallback switches to JioSaavn.
#
# Environment variables (all optional):
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
# IMPORTANT: set YT_DOWNLOAD_TIMEOUT (read by JioSaavn.py) HIGHER than
# YT_API_TIMEOUT + YT_YTDLP_TIMEOUT, e.g. YT_DOWNLOAD_TIMEOUT=25.

import asyncio
import os
import re
import json
from typing import Union
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


# ========== DOWNLOAD FUNCTIONS ==========
async def download_song(link: str) -> str:
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
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["title"]

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["duration"]

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            return result["thumbnails"][0]["url"].split("?")[0]

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
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
        if videoid:
            link = self.base + link

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
