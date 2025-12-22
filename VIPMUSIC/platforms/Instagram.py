# Instagram.py
import asyncio
import os
import re
import json
import random
import logging
import time
import aiohttp
import yt_dlp
from typing import Union
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from playwright.async_api import async_playwright

from VIPMUSIC import LOGGER
from VIPMUSIC.utils.formatters import time_to_seconds

# ========== CONFIG ==========
API_URL = os.getenv("API_URL", "https://teaminflex.xyz")
API_KEY = os.getenv("API_KEY", "INFLEX93454428D")

# Instagram credentials (if you want to automate login for cookies)
INSTA_USER = os.getenv("INSTA_USER", "")
INSTA_PASSWORD = os.getenv("INSTA_PASSWORD", "")

AUTO_REFRESH_COOKIES = os.getenv("AUTO_REFRESH_COOKIES", "false").lower() in ("1", "true", "yes")
YTDLP_PROXIES = os.getenv("YTDLP_PROXIES", "")
PLAYWRIGHT_PROXIES = os.getenv("PLAYWRIGHT_PROXIES", "")

COOKIES_DIR = os.path.join(os.getcwd(), "cookies")
os.makedirs(COOKIES_DIR, exist_ok=True)

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

logger = get_logger("HeartBeat/platforms/Instagram.py")

# ========== Proxy Helpers ==========
def _parse_proxy_list(proxy_env: str):
    if not proxy_env: return []
    return [p.strip() for p in proxy_env.split(",") if p.strip()]

YTDLP_PROXY_POOL = _parse_proxy_list(YTDLP_PROXIES)
PLAYWRIGHT_PROXY_POOL = _parse_proxy_list(PLAYWRIGHT_PROXIES)

def choose_random_proxy(pool):
    if not pool: return None
    return random.choice(pool)

# ========== Cookie Helpers ==========
def get_insta_cookie():
    """Returns a random instagram cookie file if exists."""
    cookie_files = [f for f in os.listdir(COOKIES_DIR) if f.startswith("insta_") and f.endswith(".txt")]
    if not cookie_files:
        return None
    return os.path.join(COOKIES_DIR, random.choice(cookie_files))

# ========== Playwright Instagram Refresh (Skeleton) ==========
async def refresh_instagram_cookies_playwright(proxy: str = None, headless: bool = True):
    """
    Experimental: Attempts to login to Instagram to generate cookies.
    Instagram has heavy bot detection; use high-quality residential proxies.
    """
    if not INSTA_USER or not INSTA_PASSWORD:
        logger.warning("INSTA_USER/PASS not set. Skipping auto-refresh.")
        return None

    if not proxy:
        proxy = choose_random_proxy(PLAYWRIGHT_PROXY_POOL)

    timestamp = int(time.time())
    cookie_filename = os.path.join(COOKIES_DIR, f"insta_{timestamp}.txt")
    
    try:
        async with async_playwright() as p:
            browser_args = {"headless": headless, "args": ["--no-sandbox"]}
            if proxy:
                browser_args["proxy"] = {"server": proxy}
            
            browser = await p.chromium.launch(**browser_args)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = await context.new_page()
            
            await page.goto("https://www.instagram.com/accounts/login/")
            await page.wait_for_timeout(2000)
            await page.fill('input[name="username"]', INSTA_USER)
            await page.fill('input[name="password"]', INSTA_PASSWORD)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            
            cookies = await context.cookies()
            with open(cookie_filename, "w") as f:
                f.write("# Netscape HTTP Cookie File\n")
                for c in cookies:
                    domain = c['domain'] if c['domain'].startswith('.') else '.' + c['domain']
                    f.write(f"{domain}\tTRUE\t{c['path']}\t{'TRUE' if c['secure'] else 'FALSE'}\t{int(c.get('expires', time.time()+3600))}\t{c['name']}\t{c['value']}\n")
            
            await browser.close()
            return cookie_filename
    except Exception as e:
        logger.error(f"Insta Cookie Refresh Failed: {e}")
        return None

# ========== Download Logic ==========
async def download_instagram_video(link: str) -> str:
    """Downloads Instagram Reel/Video using yt-dlp."""
    match = re.search(r"/(?:reels?|p|tv)/([A-Za-z0-9_-]+)", link)
    content_id = match.group(1) if match else str(int(time.time()))
    
    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"insta_{content_id}.mp4")

    if os.path.exists(file_path):
        return file_path

    # Attempt via API first (Following your YouTube.py pattern)
    try:
        async with aiohttp.ClientSession() as session:
            payload = {"url": link, "type": "video"}
            headers = {"X-API-KEY": API_KEY}
            async with session.post(f"{API_URL}/download", json=payload, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("status") == "success":
                        d_link = f"{API_URL}{data['download_url']}"
                        async with session.get(d_link) as f_resp:
                            with open(file_path, "wb") as f:
                                f.write(await f_resp.read())
                        return file_path
    except:
        pass

    # Fallback to yt-dlp
    cookie_file = get_insta_cookie()
    proxy = choose_random_proxy(YTDLP_PROXY_POOL)
    
    ydl_opts = {
        "format": "best",
        "outtmpl": file_path,
        "quiet": True,
        "no_warnings": True,
    }
    if cookie_file: ydl_opts["cookiefile"] = cookie_file
    if proxy: ydl_opts["proxy"] = proxy

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).download([link]))
        return file_path if os.path.exists(file_path) else None
    except Exception as e:
        logger.error(f"Insta Download Failed: {e}")
        return None

# ========== Instagram API Class ==========
class InstagramAPI:
    def __init__(self):
        self.regex = r"(?:instagram\.com)"

    async def exists(self, link: str):
        return bool(re.search(self.regex, link))

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            entities = message.entities or message.caption_entities
            if entities:
                for entity in entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        return text[entity.offset: entity.offset + entity.length]
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        return None

    async def details(self, link: str):
        proxy = choose_random_proxy(YTDLP_PROXY_POOL)
        cookie_file = get_insta_cookie()
        ydl_opts = {"quiet": True, "no_warnings": True}
        if proxy: ydl_opts["proxy"] = proxy
        if cookie_file: ydl_opts["cookiefile"] = cookie_file

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(link, download=False))
            title = info.get("description") or info.get("title") or "Instagram Media"
            if len(title) > 50: title = title[:47] + "..."
            duration_sec = int(info.get("duration", 0))
            duration_min = time.strftime('%M:%S', time.gmtime(duration_sec))
            thumbnail = info.get("thumbnail")
            vidid = info.get("id")
            return title, duration_min, duration_sec, thumbnail, vidid
        except Exception as e:
            logger.error(f"Details failed: {e}")
            return "Instagram Post", "00:00", 0, None, "insta"

    async def video(self, link: str):
        try:
            file = await download_instagram_video(link)
            return (1, file) if file else (0, "Failed to download Instagram video.")
        except Exception as e:
            return 0, str(e)

    async def download(self, link: str, mystic, video: bool = False, **kwargs):
        # Mirroring the YouTubeAPI download structure
        try:
            file_path = await download_instagram_video(link)
            if file_path:
                return file_path, True
            return None, False
        except Exception as e:
            logger.error(f"Download error: {e}")
            return None, False
