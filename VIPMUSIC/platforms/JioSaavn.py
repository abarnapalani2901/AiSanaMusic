import asyncio
import base64
import html
import json
import os
import re
from typing import Union
from urllib.parse import quote

import aiohttp
from Crypto.Cipher import DES  # pip install pycryptodome

from VIPMUSIC.utils.formatters import seconds_to_min

API = "https://www.jiosaavn.com/api.php"
DES_KEY = b"38346591"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.jiosaavn.com/",
}
BASE_PARAMS = {
    "_format": "json",
    "_marker": "0",
    "api_version": "4",
    "ctx": "web6dot0",
}
QUALITIES = ("320", "160", "96")


def _decrypt_media_url(enc: str) -> str:
    cipher = DES.new(DES_KEY, DES.MODE_ECB)
    raw = cipher.decrypt(base64.b64decode(enc))
    raw = raw[: -raw[-1]]  # remove PKCS padding
    return raw.decode("utf-8")


def _clean(text) -> str:
    return html.unescape(str(text or "")).strip()


def _normalize(song: dict) -> dict:
    more = song.get("more_info") or {}
    duration = int(more.get("duration") or song.get("duration") or 0)
    thumb = (song.get("image") or "").replace("150x150", "500x500")
    thumb = thumb.replace("50x50", "500x500")
    return {
        "id": song.get("id"),
        "title": _clean(song.get("title") or song.get("song")),
        "link": song.get("perma_url"),
        "duration_sec": duration,
        "duration_min": seconds_to_min(duration) if duration else "0:00",
        "thumb": thumb,
        "enc": more.get("encrypted_media_url") or song.get("encrypted_media_url"),
    }


class JioSaavnAPI:
    def __init__(self):
        self.base = "https://www.jiosaavn.com/song/"
        self.regex = r"(?:jiosaavn\.com|saavn\.com)"
        self.song_regex = r"(?:jiosaavn\.com|saavn\.com)/song/[^/]+/([^/?#]+)"
        self.playlist_regex = (
            r"(?:jiosaavn\.com|saavn\.com)/(?:s/playlist|featured|album)/[^/]+/([^/?#]+)"
        )
        self._cache = {}  # id / link / query  ->  normalized song

    # ------------------------------------------------------------------ #
    #  Low level helpers
    # ------------------------------------------------------------------ #
    async def _get(self, **params):
        query = {**BASE_PARAMS, **params}
        timeout = aiohttp.ClientTimeout(total=25)
        try:
            async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as s:
                async with s.get(API, params=query) as r:
                    if r.status != 200:
                        return None
                    return json.loads(await r.text())
        except Exception:
            return None

    def _remember(self, song: dict):
        for key in (song["id"], song["link"]):
            if key:
                self._cache[key] = song

    async def _search(self, query: str, limit: int = 10) -> list:
        data = await self._get(
            __call="search.getResults", q=query, p="1", n=str(limit)
        )
        if not data:
            return []
        results = data.get("results") or []
        songs = [_normalize(x) for x in results]
        for s in songs:
            self._remember(s)
        return songs

    async def _by_id(self, song_id: str):
        if song_id in self._cache:
            return self._cache[song_id]
        data = await self._get(__call="song.getDetails", cc="in", pids=song_id)
        if not data:
            return None
        item = None
        if isinstance(data.get("songs"), list) and data["songs"]:
            item = data["songs"][0]
        elif isinstance(data.get(song_id), dict):
            item = data[song_id]
        if not item:
            return None
        song = _normalize(item)
        self._remember(song)
        return song

    async def _by_link(self, link: str):
        if link in self._cache:
            return self._cache[link]
        m = re.search(self.song_regex, link)
        if not m:
            return None
        token = m.group(1)
        data = await self._get(
            __call="webapi.get", token=token, type="song", includeMetaTags="0"
        )
        if not data or not data.get("songs"):
            return None
        song = _normalize(data["songs"][0])
        self._remember(song)
        self._cache[link] = song
        return song

    async def _resolve(self, link: str, videoid: Union[bool, str] = None):
        """link can be: song id (videoid=True), jiosaavn url, or a search text."""
        link = (link or "").strip()
        if videoid:
            return await self._by_id(link)
        if re.search(self.regex, link):
            link = link.split("&")[0]
            song = await self._by_link(link)
            if song:
                return song
        if link in self._cache:
            return self._cache[link]
        results = await self._search(link, limit=1)
        if results:
            self._cache[link] = results[0]
            return results[0]
        return None

    async def _direct_url(self, song: dict):
        enc = song.get("enc")
        if not enc:
            fresh = await self._by_id(song["id"])
            enc = fresh and fresh.get("enc")
        if not enc:
            return None
        try:
            base_url = _decrypt_media_url(enc)
        except Exception:
            return None
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as s:
            for q in QUALITIES:
                url = re.sub(r"_\d+\.mp4", f"_{q}.mp4", base_url)
                try:
                    async with s.head(url, allow_redirects=True) as r:
                        if r.status == 200:
                            return url
                except Exception:
                    continue
        return base_url

    # ------------------------------------------------------------------ #
    #  Interface compatible with the YouTube platform class
    # ------------------------------------------------------------------ #
    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            return True
        return bool(re.search(self.regex, link or ""))

    async def url(self, message_1) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        for message in messages:
            text = message.text or message.caption or ""
            m = re.search(r"https?://(?:www\.)?(?:jiosaavn|saavn)\.com/\S+", text)
            if m:
                return m.group(0)
        return None

    async def details(self, link: str, videoid: Union[bool, str] = None):
        song = await self._resolve(link, videoid)
        if not song:
            raise ValueError("JioSaavn: song not found")
        return (
            song["title"],
            song["duration_min"],
            song["duration_sec"],
            song["thumb"],
            song["id"],
        )

    async def title(self, link: str, videoid: Union[bool, str] = None):
        song = await self._resolve(link, videoid)
        return song["title"] if song else ""

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        song = await self._resolve(link, videoid)
        return song["duration_min"] if song else "0:00"

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        song = await self._resolve(link, videoid)
        return song["thumb"] if song else ""

    async def video(self, link: str, videoid: Union[bool, str] = None):
        # JioSaavn is audio only
        return 0, "JioSaavn supports audio only."

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        m = re.search(self.playlist_regex, link or "")
        if not m:
            return []
        token = m.group(1)
        kind = "album" if "/album/" in link else "playlist"
        data = await self._get(
            __call="webapi.get",
            token=token,
            type=kind,
            p="1",
            n=str(limit),
            includeMetaTags="0",
        )
        if not data:
            return []
        items = data.get("list") or data.get("songs") or []
        ids = []
        for item in items[: int(limit)]:
            song = _normalize(item)
            self._remember(song)
            if song["id"]:
                ids.append(song["id"])
        return ids

    async def track(self, link: str, videoid: Union[bool, str] = None):
        song = await self._resolve(link, videoid)
        if not song:
            raise ValueError("JioSaavn: song not found")
        track_details = {
            "title": song["title"],
            "link": song["link"] or (self.base + song["id"]),
            "vidid": song["id"],
            "duration_min": song["duration_min"],
            "thumb": song["thumb"],
        }
        return track_details, song["id"]

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        return [], link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        query = link if not videoid else (await self.title(link, True))
        results = await self._search(query, limit=10)
        if not results:
            raise ValueError("JioSaavn: no results")
        song = results[query_type % len(results)]
        return song["title"], song["duration_min"], song["thumb"], song["id"]

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
    ):
        if songvideo or video:
            return None  # audio only

        song = await self._resolve(link, videoid)
        if not song:
            return None

        os.makedirs("downloads", exist_ok=True)
        if songaudio and title:
            safe = re.sub(r'[\\/:*?"<>|]', "", str(title))
            fpath = f"downloads/{safe}.mp3"
        else:
            fpath = f"downloads/{song['id']}.mp3"

        if os.path.exists(fpath) and os.path.getsize(fpath) > 0:
            return (fpath, True) if not songaudio else fpath

        url = await self._direct_url(song)
        if not url:
            return None

        tmp = fpath + ".part"
        timeout = aiohttp.ClientTimeout(total=300)
        try:
            async with aiohttp.ClientSession(headers=HEADERS, timeout=timeout) as s:
                async with s.get(url) as r:
                    if r.status != 200:
                        return None
                    with open(tmp, "wb") as f:
                        async for chunk in r.content.iter_chunked(64 * 1024):
                            f.write(chunk)
            os.replace(tmp, fpath)
        except Exception:
            if os.path.exists(tmp):
                os.remove(tmp)
            return None

        if songaudio:
            return fpath
        return fpath, True
