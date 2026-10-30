"""
VIPMUSIC/platforms/Jiosaavn.py

JioSaavn fallback for /play when YouTube (yt-dlp) fails, e.g.
"Sign in to confirm you're not a bot" / missing cookies.

Uses plain HTTP (aiohttp) against an unofficial JioSaavn API.
No youtube-dl, no yt-dlp, no cookies.

Optional env var (comma separated, tried in order):
    SAAVN_API_URLS=https://saavn.dev/api,https://your-own-instance.vercel.app/api
Self-hosting is the most reliable option:
    https://github.com/sumitkolhe/jiosaavn-api
"""

import asyncio
import html
import os
import re
from typing import Optional

import aiohttp

DOWNLOAD_DIR = "downloads"
DEFAULT_APIS = ["https://saavn.dev/api"]
API_URLS = [
    u.strip().rstrip("/")
    for u in os.getenv("SAAVN_API_URLS", ",".join(DEFAULT_APIS)).split(",")
    if u.strip()
]

# words that appear in YouTube titles but hurt a JioSaavn search
_NOISE = re.compile(
    r"\(.*?\)|\[.*?\]|official|video|audio|lyrics?|lyrical|full song|"
    r"hd|4k|1080p|720p|music video|ft\.?|feat\.?|\|.*$",
    re.IGNORECASE,
)

_TIMEOUT = aiohttp.ClientTimeout(total=60)


def clean_query(title: str) -> str:
    title = html.unescape(title or "")
    title = _NOISE.sub(" ", title)
    title = re.sub(r"[^\w\s]", " ", title, flags=re.UNICODE)
    return re.sub(r"\s+", " ", title).strip()


def _tokens(text: str) -> set:
    return set(re.findall(r"\w+", (text or "").lower()))


class JioSaavnAPI:
    def __init__(self):
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    async def _get_json(self, session, path: str, params: dict) -> Optional[dict]:
        for base in API_URLS:
            try:
                async with session.get(f"{base}{path}", params=params) as r:
                    if r.status == 200:
                        data = await r.json(content_type=None)
                        if data and data.get("success", True):
                            return data
            except Exception as e:
                print(f"[JioSaavn] API {base} failed: {type(e).__name__}: {e}")
                continue  # try next API instance
        print("[JioSaavn] all API instances failed")
        return None

    @staticmethod
    def _best_url(song: dict) -> Optional[str]:
        """Pick 160kbps if available, else the best listed quality."""
        links = song.get("downloadUrl") or []
        if not links:
            return None
        by_q = {l.get("quality"): l.get("url") for l in links}
        for q in ("160kbps", "320kbps", "96kbps", "48kbps", "12kbps"):
            if by_q.get(q):
                return by_q[q]
        return links[-1].get("url")

    async def search(self, query: str, duration: Optional[int] = None) -> Optional[dict]:
        """Return the best matching song dict (or None)."""
        q = clean_query(query) or query
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            data = await self._get_json(
                session, "/search/songs", {"query": q, "limit": 5}
            )
        results = ((data or {}).get("data") or {}).get("results") or []
        results = [s for s in results if self._best_url(s)]
        if not results:
            print(f"[JioSaavn] no results for query: {q!r}")
            return None

        want = _tokens(q)

        def score(s: dict) -> float:
            name = _tokens(s.get("name", ""))
            sc = len(want & name) / (len(want) or 1)
            if duration and s.get("duration"):
                try:
                    diff = abs(int(s["duration"]) - int(duration))
                    sc -= min(diff / 60, 1) * 0.5  # penalise very different lengths
                except (TypeError, ValueError):
                    pass
            return sc

        return max(results, key=score)

    async def download(
        self, query: str, duration: Optional[int] = None
    ) -> Optional[str]:
        """Search JioSaavn and download the audio. Returns local file path."""
        song = await self.search(query, duration)
        if not song:
            return None
        url = self._best_url(song)
        path = os.path.join(DOWNLOAD_DIR, f"saavn_{song['id']}.m4a")

        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path  # cached

        tmp = path + ".part"
        try:
            async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
                async with session.get(url) as r:
                    if r.status != 200:
                        return None
                    with open(tmp, "wb") as f:
                        async for chunk in r.content.iter_chunked(64 * 1024):
                            f.write(chunk)
            os.replace(tmp, path)
            return path
        except Exception as e:
            print(f"[JioSaavn] file download failed: {type(e).__name__}: {e}")
            if os.path.exists(tmp):
                os.remove(tmp)
            return None


JioSaavn = JioSaavnAPI()


YT_TIMEOUT = int(os.getenv("YT_DOWNLOAD_TIMEOUT", "30"))  # seconds


async def download_with_fallback(youtube, vidid, mystic, title=None, video=None):
    """
    Drop-in replacement for:
        file_path, direct = await YouTube.download(vidid, mystic, videoid=True, video=video)
    Tries YouTube first (with a timeout, so a hang also triggers the fallback);
    on error / timeout / empty result, falls back to JioSaavn using `title`.
    Audio only. Returns (file_path, direct) like YouTube.download does.
    """
    try:
        file_path, direct = await asyncio.wait_for(
            youtube.download(vidid, mystic, videoid=True, video=video),
            timeout=YT_TIMEOUT,
        )
        if file_path:
            return file_path, direct
        print("[YouTube] returned no file")
    except asyncio.TimeoutError:
        print(f"[YouTube] timed out after {YT_TIMEOUT}s -> trying JioSaavn")
    except Exception as e:
        print(f"[YouTube failed -> trying JioSaavn] {type(e).__name__}: {e}")

    if video:
        raise Exception("YouTube failed and JioSaavn has no video")
    if not title:
        raise Exception("No title available for JioSaavn search")

    print(f"[JioSaavn] searching for: {title!r}")
    path = await JioSaavn.download(title)
    if not path:
        raise Exception("YouTube and JioSaavn both failed")
    print(f"[JioSaavn] playing from: {path}")
    return path, True
