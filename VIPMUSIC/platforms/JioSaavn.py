"""
VIPMUSIC/platforms/Jiosaavn.py

JioSaavn fallback for /play when YouTube (yt-dlp) fails
(bot check, missing cookies, extraction errors, network errors, timeouts).

Talks to a JioSaavn-compatible REST API that YOU configure. There is NO
built-in default host: a dead public host is what caused the original
"Name or service not known" failure.

Environment variables
---------------------
SAAVN_API_URLS        Comma separated API base URLs, tried in order.
                      e.g. https://my-saavn.onrender.com/api
SAAVN_API_KEY         Optional. Sent as the X-API-Key header (only useful if
                      your API sits behind a proxy/gateway that checks it).
SAAVN_TIMEOUT         Per API request timeout, seconds (default 30).
SAAVN_MAX_RETRIES     Retries per API URL on 429 / 5xx / timeouts (default 2).
SAAVN_MIN_SCORE       Minimum match confidence 0..1 (default 0.55).
SAAVN_DOWNLOAD_TIMEOUT  Audio file download timeout, seconds (default 120).
SAAVN_MAX_FILE_MB     Maximum audio file size in MB (default 60).
SAAVN_QUALITY_ORDER   Comma separated preference
                      (default 160kbps,320kbps,96kbps,48kbps,12kbps).
YT_DOWNLOAD_TIMEOUT   YouTube attempt timeout before fallback (default 30).
"""

import asyncio
import difflib
import html
import logging
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiohttp

log = logging.getLogger("VIPMUSIC.JioSaavn")

DOWNLOAD_DIR = "downloads"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


API_URLS: List[str] = [
    u.strip().rstrip("/")
    for u in os.getenv("SAAVN_API_URLS", "").split(",")
    if u.strip()
]
API_KEY: str = os.getenv("SAAVN_API_KEY", "").strip()
API_TIMEOUT: int = _env_int("SAAVN_TIMEOUT", 30)
MAX_RETRIES: int = max(0, _env_int("SAAVN_MAX_RETRIES", 2))
MIN_SCORE: float = _env_float("SAAVN_MIN_SCORE", 0.55)
DOWNLOAD_TIMEOUT: int = _env_int("SAAVN_DOWNLOAD_TIMEOUT", 120)
MAX_FILE_BYTES: int = _env_int("SAAVN_MAX_FILE_MB", 60) * 1024 * 1024
MIN_FILE_BYTES: int = 10 * 1024
QUALITY_ORDER: List[str] = [
    q.strip()
    for q in os.getenv(
        "SAAVN_QUALITY_ORDER", "160kbps,320kbps,96kbps,48kbps,12kbps"
    ).split(",")
    if q.strip()
]
YT_TIMEOUT: int = _env_int("YT_DOWNLOAD_TIMEOUT", 30)

_BACKOFF_BASE = 0.5  # seconds; tests set this to 0
_EARLY_STOP_SCORE = 0.85

# --------------------------------------------------------------------------
# Query cleaning
# --------------------------------------------------------------------------

# Whole-word noise found in YouTube titles that hurts a JioSaavn search.
_NOISE_WORDS = {
    "4k", "8k", "hd", "hq", "uhd", "1080p", "720p", "480p", "360p", "2160p",
    "official", "video", "videos", "audio", "lyric", "lyrics", "lyrical",
    "song", "songs", "music", "full", "remaster", "remastered", "remix",
    "version", "new", "latest", "hit", "hits", "ft", "feat", "featuring",
    "status", "whatsapp", "bgm", "trailer", "teaser", "promo", "with",
    "sound", "dolby", "atmos", "stereo", "digital", "original", "ost",
}
# Descriptive words that follow artist names in titles
# ("K.S Chithra Female Solo Love Melody").
_DESCRIPTOR_WORDS = {
    "female", "male", "solo", "duet", "love", "melody", "melodies", "romantic",
    "sad", "happy", "emotional", "feel", "feeling", "vibe", "mood", "classic",
    "evergreen", "super", "superhit", "blockbuster", "best", "top", "special",
    "tamil", "telugu", "hindi", "malayalam", "kannada", "punjabi", "english",
    "movie", "film", "cinema", "version", "cover", "unplugged", "acoustic",
}
_SIZE_OR_DOLBY = re.compile(r"\b\d+(\.\d+)?\s*(k|p|kbps|hz)\b", re.IGNORECASE)
_SURROUND = re.compile(r"\b\d\.\d\b")  # 5.1, 7.1
_BRACKETS = re.compile(r"\(.*?\)|\[.*?\]|\{.*?\}")


def _strip_symbols(text: str) -> str:
    """
    Keep letters, digits, combining marks and spaces. Everything else
    (punctuation, emoji, symbols) becomes a space.

    Combining marks (category M*) MUST be kept: Tamil, Hindi etc. store vowel
    signs and virama as marks, and a plain `\\w` regex deletes them, which
    corrupts the text (e.g. "உன்னோடு").
    """
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if ch.isalnum() or cat.startswith("M"):
            out.append(ch)
        else:
            out.append(" ")
    return re.sub(r"\s+", " ", "".join(out)).strip()


def _is_latin_text(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return True
    latin = sum(1 for c in letters if "LATIN" in unicodedata.name(c, ""))
    return latin / len(letters) >= 0.8


def _clean_segment(seg: str, extra_drop: Optional[set] = None) -> str:
    seg = html.unescape(seg or "")
    seg = _BRACKETS.sub(" ", seg)
    seg = _SURROUND.sub(" ", seg)
    seg = _SIZE_OR_DOLBY.sub(" ", seg)
    # "K.S" -> "K S" so initials stay separate tokens
    seg = seg.replace(".", " ")
    seg = _strip_symbols(seg)
    drop = set(_NOISE_WORDS)
    if extra_drop:
        drop |= extra_drop
    words = [w for w in seg.split() if w.lower() not in drop]
    return " ".join(words).strip()


def build_queries(title: str) -> List[str]:
    """
    Build search variants, best first.

    'Unnodu Vaazha 4K Video Song 5.1 Remaster | உன்னோடு வாழாத | K.S Chithra
     Female Solo Love Melody'
      -> ['Unnodu Vaazha K S Chithra', 'உன்னோடு வாழாத', 'Unnodu Vaazha']
    """
    raw = html.unescape(title or "").strip()
    if not raw:
        return []

    segments = [s.strip() for s in raw.split("|") if s.strip()]
    latin_title = ""
    native_title = ""
    artist = ""

    for i, seg in enumerate(segments):
        if i == 0:
            latin_title = _clean_segment(seg)
            if not _is_latin_text(latin_title):
                native_title = latin_title
                latin_title = ""
            continue
        if not _is_latin_text(seg):
            if not native_title:
                native_title = _clean_segment(seg)
            continue
        cleaned = _clean_segment(seg, _DESCRIPTOR_WORDS)
        if cleaned and not artist:
            artist = cleaned

    variants: List[str] = []
    if latin_title and artist:
        variants.append(f"{latin_title} {artist}")
    if native_title:
        variants.append(native_title)
    if latin_title:
        variants.append(latin_title)
    if not variants:
        variants.append(_clean_segment(raw))

    seen, result = set(), []
    for v in variants:
        key = v.lower()
        if v and key not in seen:
            seen.add(key)
            result.append(v)
    return result


def clean_query(title: str) -> str:
    """Backward compatible single-query helper (primary variant)."""
    q = build_queries(title)
    return q[0] if q else ""


def _tokens(text: str) -> List[str]:
    return _strip_symbols((text or "").lower().replace(".", " ")).split()


# --------------------------------------------------------------------------
# Response normalisation
# --------------------------------------------------------------------------


def _to_int(value: Any) -> Optional[int]:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _artist_names(raw: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    artists = raw.get("artists")
    if isinstance(artists, dict):
        for key in ("primary", "featured"):
            for a in artists.get(key) or []:
                if isinstance(a, dict) and a.get("name"):
                    names.append(str(a["name"]))
    elif isinstance(artists, list):
        for a in artists:
            if isinstance(a, dict) and a.get("name"):
                names.append(str(a["name"]))
            elif isinstance(a, str):
                names.append(a)
    if not names:
        for key in ("primaryArtists", "primary_artists", "singers"):
            val = raw.get(key)
            if isinstance(val, str) and val.strip():
                names.extend(p.strip() for p in val.split(",") if p.strip())
                break
            if isinstance(val, list):
                names.extend(str(x.get("name") if isinstance(x, dict) else x) for x in val)
                break
    seen, out = set(), []
    for n in names:
        if n and n.lower() not in seen:
            seen.add(n.lower())
            out.append(html.unescape(n))
    return out


def _pick_audio(raw: Dict[str, Any]) -> Optional[str]:
    """
    Return a direct audio URL from the upstream `downloadUrl` list only.
    Never falls back to the song page URL and never builds a URL.
    """
    links = raw.get("downloadUrl")
    if not isinstance(links, list) or not links:
        return None
    by_quality: Dict[str, str] = {}
    for item in links:
        if isinstance(item, dict):
            url = item.get("url") or item.get("link")
            q = item.get("quality")
            if isinstance(url, str) and url.startswith(("http://", "https://")):
                by_quality[str(q)] = url
    if not by_quality:
        return None
    page = raw.get("url")
    for q in QUALITY_ORDER:
        url = by_quality.get(q)
        if url and url != page:
            return url
    for url in by_quality.values():
        if url != page:
            return url
    return None


def normalize_song(raw: Any) -> Optional[Dict[str, Any]]:
    """Convert one upstream song object into the internal structure."""
    if not isinstance(raw, dict):
        return None
    song_id = raw.get("id")
    title = raw.get("name") or raw.get("title")
    if not song_id or not title:
        return None
    album = raw.get("album")
    if isinstance(album, dict):
        album = album.get("name")
    image = raw.get("image")
    if isinstance(image, list) and image:
        last = image[-1]
        image = last.get("url") if isinstance(last, dict) else last
    audio = _pick_audio(raw)
    return {
        "id": str(song_id),
        "title": html.unescape(str(title)),
        "artists": _artist_names(raw),
        "album": html.unescape(str(album)) if album else None,
        "duration": _to_int(raw.get("duration")),
        "language": raw.get("language"),
        "image": image if isinstance(image, str) else None,
        "url": raw.get("url") if isinstance(raw.get("url"), str) else None,
        "audio": audio,
        "available": bool(audio),
    }


def _extract_results(payload: Any) -> List[Any]:
    """Pull the song list out of the supported upstream shapes."""
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("results", "songs"):
            if isinstance(data.get(key), list):
                return data[key]
        if data.get("id"):
            return [data]
    return []


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------


def _token_overlap(want: List[str], have: List[str]) -> float:
    """Fuzzy token overlap 0..1 (handles 'vaazha' vs 'vaazhaa')."""
    if not want:
        return 0.0
    if not have:
        return 0.0
    total = 0.0
    for w in want:
        best = max(difflib.SequenceMatcher(None, w, h).ratio() for h in have)
        if best >= 0.8:
            total += best
    return total / len(want)


def score_song(
    song: Dict[str, Any],
    title_tokens: List[str],
    artist_tokens: List[str],
    native_tokens: List[str],
    duration: Optional[int] = None,
) -> float:
    name_tokens = _tokens(song["title"])
    title_score = max(
        _token_overlap(title_tokens, name_tokens),
        _token_overlap(native_tokens, name_tokens),
    )
    # Penalise extra unrelated words in the candidate title a little.
    if name_tokens and title_tokens:
        extra = max(0, len(name_tokens) - len(title_tokens))
        title_score -= min(extra * 0.03, 0.12)

    if artist_tokens:
        have: List[str] = []
        for a in song.get("artists") or []:
            have.extend(_tokens(a))
        have.extend(_tokens(song.get("album") or ""))
        artist_score = _token_overlap(artist_tokens, have)
        score = 0.75 * title_score + 0.25 * artist_score
    else:
        score = title_score

    if duration and song.get("duration"):
        diff = abs(int(song["duration"]) - int(duration))
        score -= min(diff / 60.0, 1.0) * 0.2
    return max(0.0, min(1.0, score))


def _split_variant(variant: str, title: str) -> Tuple[List[str], List[str], List[str]]:
    """Return (title_tokens, artist_tokens, native_tokens) for scoring."""
    variants = build_queries(title)
    native = [v for v in variants if not _is_latin_text(v)]
    latin = [v for v in variants if _is_latin_text(v)]
    native_tokens = _tokens(native[0]) if native else []
    if not latin:
        return [], [], native_tokens
    shortest = min(latin, key=len)  # title only
    longest = max(latin, key=len)  # title + artist
    title_tokens = _tokens(shortest)
    artist_tokens = _tokens(longest)[len(title_tokens):] if longest != shortest else []
    return title_tokens, artist_tokens, native_tokens


# --------------------------------------------------------------------------
# API client
# --------------------------------------------------------------------------


class JioSaavnAPI:
    def __init__(self) -> None:
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        self._session: Optional[aiohttp.ClientSession] = None
        self._locks: Dict[str, asyncio.Lock] = {}

    # -- session lifecycle -------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(
                    total=API_TIMEOUT, connect=min(10, API_TIMEOUT)
                )
            )
        return self._session

    async def close(self) -> None:
        """Call from your bot shutdown hook."""
        if self._session is not None and not self._session.closed:
            await self._session.close()
        self._session = None

    @staticmethod
    def configured() -> bool:
        return bool(API_URLS)

    # -- low level request -------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "VIPMUSIC/1.0"}
        if API_KEY:
            headers["X-API-Key"] = API_KEY
        return headers

    async def _get_json(self, path: str, params: Dict[str, Any]) -> Optional[dict]:
        if not API_URLS:
            log.error(
                "[JioSaavn] SAAVN_API_URLS is not set; no API configured. "
                "Set it to your self-hosted API base URL."
            )
            return None

        session = await self._get_session()
        for base in API_URLS:
            for attempt in range(MAX_RETRIES + 1):
                last = attempt == MAX_RETRIES
                try:
                    async with session.get(
                        f"{base}{path}", params=params, headers=self._headers()
                    ) as r:
                        status = r.status
                        if status == 429:
                            wait = _parse_retry_after(r.headers.get("Retry-After"))
                            log.warning("[JioSaavn] %s HTTP 429 (attempt %d)", base, attempt + 1)
                            if last:
                                break
                            await asyncio.sleep(wait)
                            continue
                        if 500 <= status <= 599:
                            log.warning("[JioSaavn] %s HTTP %d (attempt %d)", base, status, attempt + 1)
                            if last:
                                break
                            await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))
                            continue
                        if status != 200:
                            log.warning("[JioSaavn] %s HTTP %d, trying next API", base, status)
                            break
                        try:
                            data = await r.json(content_type=None)
                        except (ValueError, aiohttp.ContentTypeError) as e:
                            log.warning("[JioSaavn] %s returned invalid JSON: %s", base, e)
                            break
                        if not isinstance(data, dict) or not data:
                            log.warning("[JioSaavn] %s returned empty/non-object JSON", base)
                            break
                        if data.get("success") is False:
                            log.warning(
                                "[JioSaavn] %s reported failure: %s",
                                base, str(data.get("message"))[:200],
                            )
                            break
                        return data
                except asyncio.TimeoutError:
                    log.warning("[JioSaavn] %s timed out (attempt %d)", base, attempt + 1)
                    if last:
                        break
                    await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))
                except aiohttp.ClientConnectorDNSError as e:
                    log.error("[JioSaavn] %s DNS failure: %s (host does not resolve)", base, e)
                    break  # retrying DNS failure is pointless
                except aiohttp.ClientConnectorCertificateError as e:
                    log.error("[JioSaavn] %s SSL certificate error: %s", base, e)
                    break
                except aiohttp.ClientSSLError as e:
                    log.error("[JioSaavn] %s SSL error: %s", base, e)
                    break
                except aiohttp.ClientConnectionError as e:
                    log.warning("[JioSaavn] %s connection error: %s: %s", base, type(e).__name__, e)
                    if last:
                        break
                    await asyncio.sleep(_BACKOFF_BASE * (2 ** attempt))
                except aiohttp.ClientError as e:
                    log.warning("[JioSaavn] %s client error: %s: %s", base, type(e).__name__, e)
                    break
        log.error("[JioSaavn] all configured API instances failed for %s", path)
        return None

    # -- search ------------------------------------------------------------

    async def _search_one(self, query: str) -> List[Dict[str, Any]]:
        data = await self._get_json("/search/songs", {"query": query, "limit": 10})
        if not data:
            return []
        songs = []
        for raw in _extract_results(data):
            song = normalize_song(raw)
            if song:
                songs.append(song)
        return songs

    async def search(
        self, query: str, duration: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Return the best matching normalised song, or None when confidence
        is below SAAVN_MIN_SCORE. The song dict gains a `score` key.
        """
        variants = build_queries(query) or [query]
        title_tokens, artist_tokens, native_tokens = _split_variant(variants[0], query)
        if not title_tokens and not native_tokens:
            title_tokens = _tokens(variants[0])

        best: Optional[Dict[str, Any]] = None
        best_score = -1.0
        seen_ids = set()

        for variant in variants:
            log.info("[JioSaavn] Search query: %s", variant)
            songs = await self._search_one(variant)
            log.info("[JioSaavn] Found %d results", len(songs))
            for song in songs:
                if song["id"] in seen_ids:
                    continue
                seen_ids.add(song["id"])
                s = score_song(song, title_tokens, artist_tokens, native_tokens, duration)
                if s > best_score:
                    best, best_score = song, s
            if best is not None and best_score >= _EARLY_STOP_SCORE:
                break

        if best is None:
            log.warning("[JioSaavn] no results for %r", query)
            return None
        log.info(
            "[JioSaavn] Best match: %s (match confidence: %.2f, min %.2f)",
            best["title"], best_score, MIN_SCORE,
        )
        if best_score < MIN_SCORE:
            log.warning("[JioSaavn] confidence too low, rejecting match")
            return None
        best = dict(best)
        best["score"] = round(best_score, 3)
        return best

    async def _ensure_audio(self, song: Dict[str, Any]) -> Dict[str, Any]:
        """If the search result had no audio link, ask the song-details endpoint."""
        if song.get("audio"):
            return song
        data = await self._get_json(f"/songs/{song['id']}", {})
        for raw in _extract_results(data or {}):
            detail = normalize_song(raw)
            if detail and detail["id"] == song["id"] and detail.get("audio"):
                merged = dict(song)
                merged.update({"audio": detail["audio"], "available": True})
                return merged
        return song

    # -- download ----------------------------------------------------------

    @staticmethod
    def _safe_id(song_id: str) -> str:
        return re.sub(r"[^A-Za-z0-9_-]", "", str(song_id))[:64]

    def _cached_path(self, safe_id: str) -> Optional[str]:
        for ext in (".m4a", ".mp3", ".ogg", ".flac", ".wav"):
            p = os.path.join(DOWNLOAD_DIR, f"saavn_{safe_id}{ext}")
            if os.path.isfile(p) and os.path.getsize(p) >= MIN_FILE_BYTES:
                try:
                    with open(p, "rb") as f:
                        if _detect_ext(f.read(16)):
                            return p
                except OSError:
                    pass
                _silent_remove(p)  # corrupt cache entry
        return None

    async def _download_file(self, url: str, song_id: str) -> Optional[str]:
        safe_id = self._safe_id(song_id)
        if not safe_id:
            log.error("[JioSaavn] invalid song id %r", song_id)
            return None
        if urlparse(url).scheme not in ("http", "https"):
            log.error("[JioSaavn] refusing non-http audio URL")
            return None

        lock = self._locks.setdefault(safe_id, asyncio.Lock())
        try:
            async with lock:
                cached = self._cached_path(safe_id)
                if cached:
                    log.info("[JioSaavn] using cached file %s", cached)
                    return cached
                return await self._stream_to_disk(url, safe_id)
        finally:
            if not lock.locked() and not getattr(lock, "_waiters", None):
                self._locks.pop(safe_id, None)

    async def _stream_to_disk(self, url: str, safe_id: str) -> Optional[str]:
        base = os.path.abspath(DOWNLOAD_DIR)
        tmp = os.path.join(DOWNLOAD_DIR, f"saavn_{safe_id}.part")
        if os.path.dirname(os.path.abspath(tmp)) != base:  # traversal guard
            return None
        try:
            session = await self._get_session()
            timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT, connect=15)
            async with session.get(url, timeout=timeout) as r:
                if r.status != 200:
                    log.error("[JioSaavn] audio download HTTP %d", r.status)
                    return None
                ctype = (r.headers.get("Content-Type") or "").lower()
                if ctype.startswith(("text/", "application/json")):
                    log.error("[JioSaavn] audio URL returned %s, not audio", ctype)
                    return None
                expected = _to_int(r.headers.get("Content-Length"))
                if expected and expected > MAX_FILE_BYTES:
                    log.error("[JioSaavn] file too large (%d bytes)", expected)
                    return None
                size = 0
                head = b""
                with open(tmp, "wb") as f:
                    async for chunk in r.content.iter_chunked(64 * 1024):
                        if not head:
                            head = chunk[:16]
                        size += len(chunk)
                        if size > MAX_FILE_BYTES:
                            log.error("[JioSaavn] file exceeded max size, aborting")
                            _silent_remove(tmp)
                            return None
                        f.write(chunk)

            if size < MIN_FILE_BYTES:
                log.error("[JioSaavn] downloaded file too small (%d bytes)", size)
                _silent_remove(tmp)
                return None
            if expected and size != expected:
                log.error("[JioSaavn] partial download (%d of %d bytes)", size, expected)
                _silent_remove(tmp)
                return None
            ext = _detect_ext(head)
            if not ext:
                log.error("[JioSaavn] unrecognised media container, discarding")
                _silent_remove(tmp)
                return None
            final = os.path.join(DOWNLOAD_DIR, f"saavn_{safe_id}{ext}")
            os.replace(tmp, final)
            return final
        except asyncio.CancelledError:
            _silent_remove(tmp)
            raise
        except asyncio.TimeoutError:
            log.error("[JioSaavn] audio download timed out after %ds", DOWNLOAD_TIMEOUT)
        except aiohttp.ClientError as e:
            log.error("[JioSaavn] audio download failed: %s: %s", type(e).__name__, e)
        except OSError as e:
            log.error("[JioSaavn] file write failed: %s", e)
        _silent_remove(tmp)
        return None

    async def download(
        self, query: str, duration: Optional[int] = None
    ) -> Optional[str]:
        """Search JioSaavn and download the audio. Returns local file path."""
        song = await self.search(query, duration)
        if not song:
            return None
        song = await self._ensure_audio(song)
        if not song.get("audio"):
            log.warning("[JioSaavn] Audio resource unavailable for %s", song["title"])
            return None
        return await self._download_file(song["audio"], song["id"])


def _parse_retry_after(value: Optional[str]) -> float:
    try:
        return min(max(float(value), 0.0), 5.0)
    except (TypeError, ValueError):
        return min(_BACKOFF_BASE * 2, 5.0)


def _detect_ext(head: bytes) -> Optional[str]:
    if len(head) >= 8 and head[4:8] == b"ftyp":
        return ".m4a"
    if head[:3] == b"ID3" or (len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0):
        return ".mp3"
    if head[:4] == b"OggS":
        return ".ogg"
    if head[:4] == b"fLaC":
        return ".flac"
    if head[:4] == b"RIFF":
        return ".wav"
    return None


def _silent_remove(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


JioSaavn = JioSaavnAPI()


# --------------------------------------------------------------------------
# Drop-in replacement for YouTube.download in the /play pipeline
# --------------------------------------------------------------------------


async def download_with_fallback(
    youtube, vidid, mystic, title=None, video=None, duration=None
):
    """
    Drop-in replacement for:
        file_path, direct = await YouTube.download(vidid, mystic, videoid=True, video=video)

    YouTube is always tried first (with a timeout). JioSaavn is only used when
    YouTube raises, times out or returns no file. Audio only.
    `duration` (seconds) is optional and improves matching if you have it.
    Returns (file_path, direct) like YouTube.download does.
    """
    yt_error: Optional[BaseException] = None
    try:
        file_path, direct = await asyncio.wait_for(
            youtube.download(vidid, mystic, videoid=True, video=video),
            timeout=YT_TIMEOUT,
        )
        if file_path:
            return file_path, direct
        log.warning("[YouTube] returned no file")
    except asyncio.TimeoutError as e:
        yt_error = e
        log.warning("[YouTube] timed out after %ds", YT_TIMEOUT)
    except Exception as e:  # noqa: BLE001 - logged with traceback, then fallback
        yt_error = e
        log.warning("[YouTube] download failed: %s: %s", type(e).__name__, e, exc_info=True)

    log.info("[JioSaavn] Fallback initiated")
    if video:
        raise Exception("YouTube failed and JioSaavn has no video") from yt_error
    if not title:
        raise Exception("No title available for JioSaavn search") from yt_error
    if not JioSaavn.configured():
        raise Exception(
            "YouTube failed and SAAVN_API_URLS is not configured"
        ) from yt_error

    path = await JioSaavn.download(title, duration)
    if not path:
        log.warning("[JioSaavn] Fallback completed: no playable result")
        raise Exception("YouTube and JioSaavn both failed") from yt_error
    log.info("[JioSaavn] Fallback completed: playing from %s", path)
    return path, True
