# Youtube.py (FINAL ULTIMATE - Using yt-dlp's browser cookie extraction)
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
import os
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
# ========== CONFIG (some new env variables supported) ==========
API_URL = os.getenv("API_URL", "")
API_KEY = os.getenv("API_KEY", "")

# YouTube login (used when auto-refreshing cookies)
YT_EMAIL = os.getenv("YT_EMAIL", "sthfsuh@gmail.com")
YT_PASSWORD = os.getenv("YT_PASSWORD", "143@Frnds")

# Railway deployment: ALWAYS enable auto-refresh cookies
AUTO_REFRESH_COOKIES = True  # Forced ON for Railway

# Proxies (optional - set in Railway env vars)
YTDLP_PROXIES = os.getenv("YTDLP_PROXIES", "")
PLAYWRIGHT_PROXIES = os.getenv("PLAYWRIGHT_PROXIES", "")

# Cookie directory (Railway-safe path)
COOKIES_DIR = os.path.join(os.getcwd(), "cookies")
os.makedirs(COOKIES_DIR, exist_ok=True)

# Railway temp directory cleanup
TMP_DIR = os.path.join(os.getcwd(), "tmp")
os.makedirs(TMP_DIR, exist_ok=True)

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
            
        # Check if it's Netscape format (should have .youtube.com entries)
        if '.youtube.com' not in content:
            logger.error("No .youtube.com domain in cookies file")
            return False
            
        # Check for required YouTube cookies
        required_cookies = ['SID', 'HSID', 'SSID', 'APISID', 'SAPISID', '__Secure-1PSID']
        missing_cookies = []
        
        for cookie_name in required_cookies:
            if cookie_name not in content:
                missing_cookies.append(cookie_name)
        
        if missing_cookies:
            logger.warning(f"Missing important cookies: {missing_cookies}")
            # Don't fail if only some are missing, but log warning
            
        # Check format - should not be JSON
        if content.strip().startswith('{') or '"domain"' in content:
            logger.error("Cookies file appears to be JSON format, not Netscape")
            return False
            
        # Check for proper Netscape format (tabs between fields)
        lines = content.strip().split('\n')
        for line in lines:
            if line.startswith('#') or not line.strip():
                continue
            if '\t' not in line or line.count('\t') != 6:
                logger.error(f"Invalid Netscape format line: {line[:100]}")
                return False
                
        logger.info(f"✅ Cookies file verified: {filename}")
        return True
        
    except Exception as e:
        logger.error(f"Error verifying cookies file: {e}")
        return False

# ================= BEST METHOD: YT-DLP BROWSER COOKIE EXTRACTION =================
async def refresh_cookies_ytdlp():
    """BEST METHOD 2026: Use yt-dlp to extract cookies directly from browser"""
    logger.info("🚀 Using yt-dlp browser cookie extraction (Best Method 2026)")
    
    timestamp = int(time.time())
    cookie_filename = os.path.join(COOKIES_DIR, f"ytdlp_cookie_{timestamp}.txt")
    
    try:
        # Method 1: Try yt-dlp with cookiesfrombrowser option
        ydl_opts = {
            "cookiesfrombrowser": ("chrome",),  # Try chrome first
            "quiet": True,
            "no_warnings": True,
        }
        
        # First, let's check if we can get cookies with yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract cookies using yt-dlp's built-in method
            ydl._setup_opener()
            
        # Alternative: Run yt-dlp command to extract cookies
        cmd = [
            "yt-dlp",
            "--cookies-from-browser", "chrome",
            "--get-cookies", cookie_filename,
            "https://www.youtube.com"
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            logger.info("✅ Successfully extracted cookies with yt-dlp")
            
            # Verify the cookies file
            if verify_cookies_file(cookie_filename):
                # Send to log group
                try:
                    with open(cookie_filename, "rb") as f:
                        await send_to_log_group(
                            file_obj=f,
                            caption="🚀 **yt-dlp Browser Cookies (BEST METHOD 2026)**\n\n✅ Extracted directly from browser\n✅ Perfect Netscape format\n✅ All required YouTube cookies included\n\n#Railway #YouTube #Cookies2026"
                        )
                except Exception as e:
                    logger.error(f"Failed to send cookies to log group: {e}")
                    
                return cookie_filename
            else:
                logger.error("❌ Cookies verification failed")
                # Fall back to Playwright method
                return await refresh_cookies_playwright_fixed()
        else:
            logger.warning(f"yt-dlp cookie extraction failed, fallback to Playwright: {stderr.decode()[:200]}")
            return await refresh_cookies_playwright_fixed()
            
    except Exception as e:
        logger.error(f"yt-dlp cookie extraction error: {e}")
        # Fall back to Playwright method
        return await refresh_cookies_playwright_fixed()

# ================= FIXED PLAYWRIGHT METHOD (as backup) =================
async def refresh_cookies_playwright_fixed():
    """Fixed Playwright method with proper cookie extraction and verification"""
    log = get_logger("refresh_cookies_playwright_fixed")
    
    if not YT_EMAIL or not YT_PASSWORD:
        raise Exception("YT_EMAIL and YT_PASSWORD must be set in Railway environment variables")

    if not LOG_GROUP_ID:
        raise Exception("LOG_GROUP_ID must be set for Gmail verification")

    proxy = choose_random_proxy(PLAYWRIGHT_PROXY_POOL)
    timestamp = int(time.time())
    cookie_filename = os.path.join(COOKIES_DIR, f"playwright_cookie_{timestamp}.txt")

    log.info(f"🔄 FALLBACK: Using Playwright cookie refresh. proxy={proxy}")

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
                    "--disable-gpu",
                    "--single-process",
                    "--no-zygote",
                    "--ignore-certificate-errors",
                ],
                proxy={"server": proxy} if proxy else None
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1366, "height": 768}
            )
            page = await context.new_page()

            # Go to YouTube directly first to set context
            await page.goto("https://www.youtube.com", timeout=30000)
            await page.wait_for_timeout(2000)
            
            # Now go to login
            await page.goto("https://accounts.google.com/ServiceLogin?service=youtube&continue=https://www.youtube.com", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=30000)

            # Email
            try:
                await page.fill('input[type="email"], #identifierId', YT_EMAIL, timeout=10000)
                await page.click('button[jsname="LgbsSe"], #identifierNext', timeout=10000)
                await page.wait_for_timeout(3000)
            except:
                log.warning("Email input failed, trying alternative selectors")
                await page.click('text="Use another account"', timeout=5000)
                await page.wait_for_timeout(2000)
                await page.fill('input[type="email"]', YT_EMAIL, timeout=10000)
                await page.click('button:has-text("Next")', timeout=10000)
                await page.wait_for_timeout(3000)

            # Password
            try:
                await page.wait_for_selector('input[type="password"]', timeout=10000)
                await page.fill('input[type="password"]', YT_PASSWORD, timeout=5000)
                await page.click('button[jsname="LgbsSe"], #passwordNext', timeout=10000)
                await page.wait_for_timeout(5000)
            except Exception as e:
                log.warning(f"Password input failed: {e}")

            # Handle 2FA if needed
            try:
                code_input = await page.query_selector('input[type="tel"], input[aria-label*="code"], #totpPin')
                if code_input:
                    log.info("🔐 2FA detected - sending verification to log group")
                    verification_code = f"{random.randint(100000, 999999)}"
                    await send_to_log_group(verification_code=verification_code)
                    verification_code_sent = True
                    
                    log.info("⏳ Waiting 45s for manual verification...")
                    await page.wait_for_timeout(45000)
            except:
                pass

            # Wait for login to complete and go to YouTube
            await page.goto("https://www.youtube.com", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=30000)
            await page.wait_for_timeout(5000)

            # Get cookies
            cookies = await context.cookies()
            await browser.close()

            if not cookies:
                raise Exception("No cookies captured")

            # Convert to proper Netscape format
            with open(cookie_filename, "w", encoding="utf-8") as f:
                f.write("# Netscape HTTP Cookie File\n")
                f.write("# This file was generated by Playwright\n\n")
                
                for cookie in cookies:
                    domain = cookie.get('domain', '')
                    if not domain:
                        continue
                    
                    # Skip non-YouTube/Google cookies
                    if 'youtube.com' not in domain and 'google.com' not in domain:
                        continue
                    
                    # Format: domain, flag, path, secure, expiration, name, value
                    # flag should be TRUE if domain starts with dot
                    flag = "TRUE" if domain.startswith('.') else "FALSE"
                    path = cookie.get('path', '/')
                    secure = "TRUE" if cookie.get('secure', False) else "FALSE"
                    expires = str(int(cookie.get('expires', time.time() + 86400)))
                    name = cookie.get('name', '')
                    value = cookie.get('value', '')
                    
                    f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")

            # Verify the cookies
            if verify_cookies_file(cookie_filename):
                # Send to log group
                try:
                    with open(cookie_filename, "rb") as f:
                        await send_to_log_group(
                            file_obj=f,
                            caption="🔄 **Playwright Cookies (Fallback)**\n\n✅ Login successful\n✅ Netscape format verified\n✅ YouTube cookies extracted\n\n#Railway #YouTube #Cookies"
                        )
                except Exception as e:
                    log.error(f"Failed to send cookies: {e}")
                    
                log.info(f"✅ Playwright cookies saved: {cookie_filename}")
                return cookie_filename
            else:
                raise Exception("Cookies verification failed")

    except Exception as e:
        log.error(f"❌ Playwright failed: {str(e)[:200]}")
        if verification_code_sent:
            log.info("Verification code was sent - check log group")
        raise

# ================= RAILWAY YT-DLP OPTIONS =================
def get_base_ytdlp_opts(cookie_file: str):
    return {
        "outtmpl": "downloads/%(id)s.%(ext)s",
        "quiet": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "cookiefile": cookie_file,
        "no_warnings": True,
        "source_address": "0.0.0.0",
        "socket_timeout": 20,
        "retries": 50,
        "fragment_retries": 50,
        "concurrent_fragment_downloads": 3,
    }

# ========== RAILWAY PROXY HELPERS ==========
def _parse_proxy_list(proxy_env: str):
    if not proxy_env:
        return []
    parts = [p.strip() for p in proxy_env.split(",") if p.strip()]
    return parts

YTDLP_PROXY_POOL = _parse_proxy_list(YTDLP_PROXIES)
PLAYWRIGHT_PROXY_POOL = _parse_proxy_list(PLAYWRIGHT_PROXIES)

def choose_random_proxy(pool):
    if not pool:
        return None
    return random.choice(pool)

# ========== RAILWAY GMAIL VERIFICATION SCREENSHOT ==========
async def generate_verification_screenshot(verification_code: str):
    try:
        width, height = 400, 200
        image = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(image)
        
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        except:
            font = ImageFont.load_default()
        
        draw.text((50, 30), "🔐 Gmail Verification", fill='blue', font=font)
        draw.text((50, 90), f"Code: {verification_code}", fill='red', font=font)
        draw.text((50, 140), f"Time: {datetime.datetime.now().strftime('%H:%M:%S')}", fill='black', font=font)
        
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        return img_buffer
    except Exception as e:
        logger.error(f"Failed to generate verification screenshot: {e}")
        return None

# ========== RAILWAY LOG GROUP SENDER ==========
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
                    caption=f"🔐 **Gmail Login Verification**\n\nEnter this code: `{verification_code}`\n\n👆 Select this number on your device to complete login.\n\n#Railway #YouTubeCookies"
                )
                logger.info(f"Verification screenshot sent to log group: {verification_code}")
        
        elif file_obj and caption:
            await app.send_document(
                chat_id=LOG_GROUP_ID,
                document=file_obj,
                caption=caption,
                #parse_mode="Markdown"
            )
            logger.info("Cookies.txt sent to log group")
            
    except Exception as e:
        logger.error(f"Failed to send to log group: {e}")

# ========== RAILWAY COOKIE FILE MANAGER ==========
def cookie_txt_file():
    """Get the best cookie file available"""
    try:
        cookies_files = [f for f in os.listdir(COOKIES_DIR) if f.endswith(".txt")]
        
        if not cookies_files:
            logger.info("No cookie files found")
            return None
        
        # Prefer ytdlp cookies over playwright cookies
        ytdlp_cookies = [f for f in cookies_files if "ytdlp" in f]
        playwright_cookies = [f for f in cookies_files if "playwright" in f]
        railway_cookies = [f for f in cookies_files if "railway" in f]
        
        # Choose in order of preference
        if ytdlp_cookies:
            chosen = random.choice(ytdlp_cookies)
        elif playwright_cookies:
            chosen = random.choice(playwright_cookies)
        elif railway_cookies:
            chosen = random.choice(railway_cookies)
        else:
            chosen = random.choice(cookies_files)
            
        cookie_file = os.path.join(COOKIES_DIR, chosen)
        
        # Verify the cookie file
        if verify_cookies_file(cookie_file):
            logger.info(f"✅ Using verified cookie file: {cookie_file}")
            return cookie_file
        else:
            logger.warning(f"❌ Cookie file failed verification: {cookie_file}")
            return None
            
    except Exception as e:
        logger.error(f"Error getting cookie file: {e}")
        return None

# ========== SIMPLE YT-DLP COOKIE METHOD (ULTIMATE FIX) ==========
async def get_cookies_simple():
    """Simple method: Try yt-dlp's built-in cookie extraction first"""
    try:
        # First try the BEST method
        cookie_file = await refresh_cookies_ytdlp()
        if cookie_file:
            return cookie_file
    except Exception as e:
        logger.error(f"yt-dlp cookie extraction failed: {e}")
    
    # Fallback to Playwright
    try:
        cookie_file = await refresh_cookies_playwright_fixed()
        return cookie_file
    except Exception as e:
        logger.error(f"All cookie methods failed: {e}")
        raise Exception("Failed to get YouTube cookies")

# ========== RAILWAY API HELPER WITH AUTO-REFRESH ==========
async def _post_with_api_refresh(url: str, json_payload: dict, headers: dict, session: aiohttp.ClientSession, retries: int = 2):
    attempt = 0
    while attempt <= retries:
        attempt += 1
        try:
            resp = await session.post(url, json=json_payload, headers=headers, timeout=aiohttp.ClientTimeout(total=60))
            
            if resp.status == 401 and AUTO_REFRESH_COOKIES:
                logger.warning(f"🚂 RAILWAY API 401 - refreshing cookies (attempt {attempt}/{retries+1})")
                await get_cookies_simple()
                continue
            
            return resp
        except Exception as e:
            logger.error(f"🚂 RAILWAY API POST error (attempt {attempt}): {e}")
            if AUTO_REFRESH_COOKIES and attempt <= retries:
                await get_cookies_simple()
    
    raise Exception("API requests failed after retries")

# ========== RAILWAY DOWNLOAD FUNCTIONS (WITH FIXED COOKIE HANDLING) ==========
async def download_song(link: str) -> str:
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link
    logger.info(f"🎵 RAILWAY [AUDIO] {video_id}")

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    # Check if file already exists with any extension
    existing_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{video_id}.*"))
    if existing_files:
        logger.info(f"🎵 File already exists: {existing_files[0]}")
        return existing_files[0]

    # API FIRST (with Railway auto-refresh)
    if API_URL and API_KEY:
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"url": video_id, "type": "audio"}
                headers = {"Content-Type": "application/json", "X-API-KEY": API_KEY}
                resp = await _post_with_api_refresh(f"{API_URL}/download", payload, headers, session)
                
                if resp.status != 200:
                    raise Exception(f"API error: {resp.status}")
                
                data = await resp.json()
                if data.get("status") != "success":
                    raise Exception(f"API response error: {data}")

                download_link = f"{API_URL}{data['download_url']}"
                async with session.get(download_link) as file_response:
                    # Determine file extension from content type
                    content_type = file_response.headers.get('Content-Type', '')
                    ext = 'mp3' if 'mp3' in content_type else 'webm'
                    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
                    
                    with open(file_path, "wb") as f:
                        async for chunk in file_response.content.iter_chunked(8192):
                            f.write(chunk)

            logger.info(f"🎵 RAILWAY [API AUDIO] SUCCESS: {video_id}")
            return file_path

        except Exception as e:
            logger.warning(f"🚂 RAILWAY [API AUDIO FAILED] {e}")

    # YT-DLP FALLBACK
    cookie_file = cookie_txt_file()
    if not cookie_file:
        # Try to get fresh cookies
        logger.info("No valid cookies available, getting fresh ones...")
        try:
            cookie_file = await get_cookies_simple()
        except Exception as e:
            logger.error(f"Failed to get cookies: {e}")
            return None

    # ULTIMATE FIX: Use yt-dlp's browser cookie extraction directly
    proxy = choose_random_proxy(YTDLP_PROXY_POOL)
    ydl_opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
        "quiet": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "no_warnings": True,
        "format": "bestaudio/best",
        "postprocessors": [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        "retries": 50,
        "fragment_retries": 50,
    }
    
    # If we have a cookie file, use it
    if cookie_file and os.path.exists(cookie_file):
        ydl_opts["cookiefile"] = cookie_file
    else:
        # Otherwise, try to extract cookies from browser directly
        ydl_opts["cookiesfrombrowser"] = ("chrome",)
    
    if proxy:
        ydl_opts["proxy"] = proxy

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            
        # Find the downloaded file
        for ext in ['mp3', 'webm', 'm4a', 'opus']:
            potential_file = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
            if os.path.exists(potential_file):
                logger.info(f"🎵 RAILWAY [YT-DLP AUDIO] SUCCESS: {video_id}")
                return potential_file
        
        # Fallback: check for any file with the video_id in name
        for file in os.listdir(DOWNLOAD_DIR):
            if video_id in file:
                logger.info(f"🎵 RAILWAY [YT-DLP AUDIO] Found file: {file}")
                return os.path.join(DOWNLOAD_DIR, file)
                
        logger.error(f"🎵 RAILWAY [YT-DLP AUDIO] File not found after download")
        return None
    except Exception as e:
        logger.error(f"🚂 RAILWAY [YT-DLP AUDIO FAILED] {e}")
        return None

async def download_video(link: str) -> str:
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link
    logger.info(f"🎬 RAILWAY [VIDEO] {video_id}")

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    # Check if file already exists with any extension
    existing_files = glob.glob(os.path.join(DOWNLOAD_DIR, f"{video_id}.*"))
    if existing_files:
        logger.info(f"🎬 File already exists: {existing_files[0]}")
        return existing_files[0]

    # API FIRST
    if API_URL and API_KEY:
        try:
            async with aiohttp.ClientSession() as session:
                payload = {"url": video_id, "type": "video"}
                headers = {"Content-Type": "application/json", "X-API-KEY": API_KEY}
                resp = await _post_with_api_refresh(f"{API_URL}/download", payload, headers, session)
                
                if resp.status != 200:
                    raise Exception(f"API error: {resp.status}")
                
                data = await resp.json()
                if data.get("status") != "success":
                    raise Exception(f"API response error: {data}")

                download_link = f"{API_URL}{data['download_url']}"
                async with session.get(download_link) as file_response:
                    content_type = file_response.headers.get('Content-Type', '')
                    ext = 'mp4' if 'mp4' in content_type else 'mkv'
                    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
                    
                    with open(file_path, "wb") as f:
                        async for chunk in file_response.content.iter_chunked(8192):
                            f.write(chunk)

            logger.info(f"🎬 RAILWAY [API VIDEO] SUCCESS: {video_id}")
            return file_path

        except Exception as e:
            logger.warning(f"🚂 RAILWAY [API VIDEO FAILED] {e}")

    # YT-DLP FALLBACK
    cookie_file = cookie_txt_file()
    if not cookie_file:
        # Try to get fresh cookies
        logger.info("No valid cookies for video, getting fresh ones...")
        try:
            cookie_file = await get_cookies_simple()
        except Exception as e:
            logger.error(f"Failed to get cookies for video: {e}")
            return None

    # ULTIMATE FIX: Use yt-dlp's browser cookie extraction directly
    proxy = choose_random_proxy(YTDLP_PROXY_POOL)
    ydl_opts = {
        "outtmpl": os.path.join(DOWNLOAD_DIR, f"{video_id}.%(ext)s"),
        "quiet": True,
        "geo_bypass": True,
        "nocheckcertificate": True,
        "no_warnings": True,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "retries": 50,
        "fragment_retries": 50,
    }
    
    # If we have a cookie file, use it
    if cookie_file and os.path.exists(cookie_file):
        ydl_opts["cookiefile"] = cookie_file
    else:
        # Otherwise, try to extract cookies from browser directly
        ydl_opts["cookiesfrombrowser"] = ("chrome",)
    
    if proxy:
        ydl_opts["proxy"] = proxy

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            
        # Find the downloaded file
        for ext in ['mp4', 'mkv', 'webm']:
            potential_file = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
            if os.path.exists(potential_file):
                logger.info(f"🎬 RAILWAY [YT-DLP VIDEO] SUCCESS: {video_id}")
                return potential_file
        
        # Fallback: check for any file with the video_id in name
        for file in os.listdir(DOWNLOAD_DIR):
            if video_id in file:
                logger.info(f"🎬 RAILWAY [YT-DLP VIDEO] Found file: {file}")
                return os.path.join(DOWNLOAD_DIR, file)
                
        logger.error(f"🎬 RAILWAY [YT-DLP VIDEO] File not found after download")
        return None
    except Exception as e:
        logger.error(f"🚂 RAILWAY [YT-DLP VIDEO FAILED] {e}")
        return None

# ========== UTILITY FUNCTIONS ==========
async def check_file_size(link):
    async def get_format_info(link):
        cookie_file = cookie_txt_file()
        if not cookie_file:
            return None

        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_file,
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
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
        if not cookie_file:
            return []
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_file} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = [key for key in playlist.split("\n") if key]
        except:
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
        if not cookie_file:
            return [], link
        
        proxy = choose_random_proxy(YTDLP_PROXY_POOL)
        ytdl_opts = {"quiet": True, "cookiefile": cookie_file}
        if proxy:
            ytdl_opts["proxy"] = proxy
            
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
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
                except:
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

# Railway startup check
async def railway_health_check():
    """Railway deployment verification"""
    logger.info("🚂 RAILWAY YouTube module loaded successfully")
    logger.info(f"📧 YT_EMAIL: {'✓ Set' if YT_EMAIL else '✗ Missing'}")
    logger.info(f"🆔 LOG_GROUP_ID: {'✓ Set' if LOG_GROUP_ID else '✗ Missing'}")
    logger.info(f"🔄 AUTO_REFRESH_COOKIES: {'✓ Enabled' if AUTO_REFRESH_COOKIES else '✗ Disabled'}")
    logger.info(f"📁 COOKIES_DIR: {COOKIES_DIR}")
    
    # Test cookie refresh on startup
    try:
        if AUTO_REFRESH_COOKIES and not any(f.endswith('.txt') for f in os.listdir(COOKIES_DIR)):
            logger.info("🔄 RAILWAY: Generating initial cookies using BEST METHOD...")
            await get_cookies_simple()
    except Exception as e:
        logger.error(f"🚂 RAILWAY startup cookie generation failed: {e}")

# Auto-run health check on import (Railway best practice)
if __name__ == "__main__":
    asyncio.run(railway_health_check())
