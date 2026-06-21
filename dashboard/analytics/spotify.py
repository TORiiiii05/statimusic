# analytics/spotify.py
from __future__ import annotations

import base64
import os
import time
from io import BytesIO
from typing import Any, Dict, Optional, Tuple, Union, List

import numpy as np
import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageOps


# ============================================================
# 0) Config + caches
# ============================================================

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_API_BASE = "https://api.spotify.com/v1"

_TOKEN: Optional[str] = None
_TOKEN_EXPIRES_AT: float = 0.0  

# Caches name-based (déjà chez toi)
_CACHE_ARTIST: Dict[str, dict] = {}
_CACHE_ALBUM: Dict[Tuple[str, str], dict] = {}   # (album_norm, artist_norm) -> album object
_CACHE_TRACK: Dict[Tuple[str, str], dict] = {}   # (track_norm, artist_norm) -> track object
_CACHE_IMG: Dict[str, Image.Image] = {}          # url -> PIL image

# ✅ Caches ID-based (nouveau)
_CACHE_ARTIST_ID: Dict[str, dict] = {}
_CACHE_ALBUM_ID: Dict[str, dict] = {}
_CACHE_TRACK_ID: Dict[str, dict] = {}
_CACHE_ISRC: Dict[Tuple[str, str], dict] = {}    # (isrc, market) -> track object (raw + ids)


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


# ============================================================
# 1) Token Spotify
# ============================================================
import requests
import time
import random

def get_spotify_token(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
) -> Optional[str]:
    global _TOKEN, _TOKEN_EXPIRES_AT

    now = time.time()
    if _TOKEN and now < _TOKEN_EXPIRES_AT - 30:
        return _TOKEN

    cid = client_id or os.getenv("SPOTIFY_CLIENT_ID")
    secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET")
    if not cid or not secret:
        return None

    auth = base64.b64encode(f"{cid}:{secret}".encode("utf-8")).decode("utf-8")
    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"grant_type": "client_credentials"}

    # retry x3 sur timeout/erreur réseau
    for attempt in range(3):
        try:
            r = requests.post(SPOTIFY_TOKEN_URL, headers=headers, data=data, timeout=15)
        except requests.exceptions.Timeout:
            wait = 1.5 + attempt * 1.5 + random.uniform(0.1, 0.6)
            print(f"SPOTIFY TOKEN TIMEOUT attempt={attempt+1}/3 wait={wait:.1f}s")
            time.sleep(wait)
            continue
        except requests.exceptions.RequestException as e:
            # autre erreur réseau
            print("SPOTIFY TOKEN REQUEST ERROR:", str(e)[:200])
            return None

        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After")
            wait = int(retry_after) if (retry_after and retry_after.isdigit()) else 2
            wait = wait + random.uniform(0.1, 0.6)
            print(f"SPOTIFY TOKEN 429 wait={wait:.1f}s")
            time.sleep(wait)
            continue

        if r.status_code != 200:
            print("SPOTIFY TOKEN FAIL", r.status_code, r.text[:200])
            return None

        payload = r.json()
        _TOKEN = payload.get("access_token")
        _TOKEN_EXPIRES_AT = now + int(payload.get("expires_in", 3600))
        return _TOKEN

    return None

import time
import random
from typing import Optional

def _spotify_get(endpoint: str, token: str, params: Optional[dict] = None) -> Optional[dict]:
    url = endpoint if endpoint.startswith("http") else f"{SPOTIFY_API_BASE}{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}

    for attempt in range(4):  # 4 essais max
        try:
            r = requests.get(url, headers=headers, params=params, timeout=15)
        except requests.exceptions.Timeout:
            wait = 1.0 + attempt * 1.5 + random.uniform(0.1, 0.6)
            print(f"SPOTIFY TIMEOUT attempt={attempt+1}/4 wait={wait:.1f}s url={url}")
            time.sleep(wait)
            continue
        except requests.exceptions.RequestException as e:
            # erreur réseau autre (DNS, reset, etc.)
            wait = 0.8 + attempt * 1.2 + random.uniform(0.1, 0.6)
            print(f"SPOTIFY REQUEST ERROR attempt={attempt+1}/4 wait={wait:.1f}s url={url} err={str(e)[:120]}")
            time.sleep(wait)
            continue

        # 429: rate limit
        if r.status_code == 429:
            retry_after = r.headers.get("Retry-After")
            wait = int(retry_after) if (retry_after and retry_after.isdigit()) else 2
            wait = wait + random.uniform(0.1, 0.6)
            print(f"SPOTIFY 429 attempt={attempt+1}/4 wait={wait:.1f}s url={url}")
            time.sleep(wait)
            continue

        # 401: token invalide/expiré
        if r.status_code == 401:
            print("SPOTIFY 401:", r.text[:200])
            return None

        if r.status_code != 200:
            print("SPOTIFY FAIL", r.status_code, r.headers.get("Retry-After"), r.text[:200])
            return None

        return r.json()

    return None


def _spotify_search(q: str, search_type: str, token: str, limit: int = 1, market: Optional[str] = "FR") -> Optional[dict]:
    params = {"q": q, "type": search_type, "limit": limit}
    if market:
        params["market"] = market
    return _spotify_get("/search", token=token, params=params)


# ============================================================
# 2) GET by Spotify ID (✅ indispensable pour "IDs only")
# ============================================================

def get_artist_by_id(artist_id: str, token: Optional[str] = None) -> Optional[dict]:
    artist_id = (artist_id or "").strip()
    if not artist_id:
        return None
    if artist_id in _CACHE_ARTIST_ID:
        return _CACHE_ARTIST_ID[artist_id]

    tok = token or get_spotify_token()
    if not tok:
        return None

    raw = _spotify_get(f"/artists/{artist_id}", token=tok)
    if not raw:
        return None

    images = raw.get("images") or []
    obj = {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "image_url": images[0].get("url") if images else None,
        "url": (raw.get("external_urls") or {}).get("spotify"),
        "raw": raw,
    }
    _CACHE_ARTIST_ID[artist_id] = obj
    return obj


def get_album_by_id(album_id: str, token: Optional[str] = None, market: str = "FR") -> Optional[dict]:
    album_id = (album_id or "").strip()
    if not album_id:
        return None
    if album_id in _CACHE_ALBUM_ID:
        return _CACHE_ALBUM_ID[album_id]

    tok = token or get_spotify_token()
    if not tok:
        return None

    raw = _spotify_get(f"/albums/{album_id}", token=tok, params={"market": market})
    if not raw:
        return None

    images = raw.get("images") or []
    obj = {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "image_url": images[0].get("url") if images else None,
        "url": (raw.get("external_urls") or {}).get("spotify"),
        "raw": raw,
    }
    _CACHE_ALBUM_ID[album_id] = obj
    return obj


def get_track_by_id(track_id: str, token: Optional[str] = None, market: str = "FR") -> Optional[dict]:
    track_id = (track_id or "").strip()
    if not track_id:
        return None
    if track_id in _CACHE_TRACK_ID:
        return _CACHE_TRACK_ID[track_id]

    tok = token or get_spotify_token()
    if not tok:
        return None

    raw = _spotify_get(f"/tracks/{track_id}", token=tok, params={"market": market})
    if not raw:
        return None

    album = raw.get("album") or {}
    images = album.get("images") or []
    obj = {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "artists": [a.get("name") for a in (raw.get("artists") or []) if a.get("name")],
        "artist_ids": [a.get("id") for a in (raw.get("artists") or []) if a.get("id")],
        "album": album.get("name"),
        "album_id": album.get("id"),
        "image_url": images[0].get("url") if images else None,
        "isrc": (raw.get("external_ids") or {}).get("isrc"),
        "url": (raw.get("external_urls") or {}).get("spotify"),
        "raw": raw,
    }
    _CACHE_TRACK_ID[track_id] = obj
    return obj


# ============================================================
# 3) Recherche Spotify (name-based) – conservé
# ============================================================

def search_artist(artist_name: str, token: Optional[str] = None, market: str = "FR") -> Optional[dict]:
    key = _norm(artist_name)
    if key in _CACHE_ARTIST:
        return _CACHE_ARTIST[key]

    tok = token or get_spotify_token()
    if not tok:
        return None

    data = _spotify_search(q=artist_name, search_type="artist", token=tok, limit=5, market=market)
    items = (data or {}).get("artists", {}).get("items", []) if data else []
    if not items:
        return None

    best = None
    best_score = -1
    for a in items:
        name = a.get("name") or ""
        images = a.get("images") or []
        has_img = 1 if images else 0

        score = 0
        if _norm(name) == key:
            score += 100
        elif key in _norm(name) or _norm(name) in key:
            score += 40
        score += has_img * 10

        if score > best_score:
            best_score = score
            best = a

    if not best:
        return None

    images = best.get("images") or []
    obj = {
        "id": best.get("id"),
        "name": best.get("name"),
        "image_url": images[0].get("url") if images else None,
        "url": (best.get("external_urls") or {}).get("spotify"),
        "raw": best,
    }
    _CACHE_ARTIST[key] = obj
    return obj


def search_album(album_name: str, artist_name: str, token: Optional[str] = None, market: str = "FR") -> Optional[dict]:
    key = (_norm(album_name), _norm(artist_name))
    if key in _CACHE_ALBUM:
        return _CACHE_ALBUM[key]

    tok = token or get_spotify_token()
    if not tok:
        return None

    q1 = f'album:"{album_name}" artist:"{artist_name}"'
    data = _spotify_search(q=q1, search_type="album", token=tok, limit=5, market=market)
    items = (data or {}).get("albums", {}).get("items", []) if data else []

    if not items:
        q2 = f"{album_name} {artist_name}"
        data2 = _spotify_search(q=q2, search_type="album", token=tok, limit=5, market=market)
        items = (data2 or {}).get("albums", {}).get("items", []) if data2 else []

    if not items:
        return None

    # Cherche le meilleur match par nom
    best = None
    best_score = -1
    for al in items:
        name = _norm(al.get("name") or "")
        album_norm = _norm(album_name)
        score = 0
        if name == album_norm:
            score += 100
        elif album_norm in name or name in album_norm:
            score += 40
        # Bonus si l'artiste correspond
        artists = [_norm(a.get("name", "")) for a in (al.get("artists") or [])]
        if any(_norm(artist_name) in a or a in _norm(artist_name) for a in artists):
            score += 20
        if score > best_score:
            best_score = score
            best = al

    if not best:
        return None

    al = best
    images = al.get("images") or []
    obj = {
        "id": al.get("id"),
        "name": al.get("name"),
        "image_url": images[0].get("url") if images else None,
        "url": (al.get("external_urls") or {}).get("spotify"),
        "raw": al,
    }
    _CACHE_ALBUM[key] = obj
    return obj


def search_track(track_name: str, artist_name: str, token: Optional[str] = None, market: str = "FR") -> Optional[dict]:
    key = (_norm(track_name), _norm(artist_name))
    if key in _CACHE_TRACK:
        return _CACHE_TRACK[key]

    tok = token or get_spotify_token()
    if not tok:
        return None

    q1 = f'track:"{track_name}" artist:"{artist_name}"' if artist_name else f'track:"{track_name}"'
    data = _spotify_search(q=q1, search_type="track", token=tok, limit=5, market=market)
    items = (data or {}).get("tracks", {}).get("items", []) if data else []

    if not items:
        q2 = f"{track_name} {artist_name}".strip()
        data2 = _spotify_search(q=q2, search_type="track", token=tok, limit=5, market=market)
        items = (data2 or {}).get("tracks", {}).get("items", []) if data2 else []

    if not items:
        return None

    t = items[0]
    album = t.get("album") or {}
    images = album.get("images") or []
    obj = {
        "id": t.get("id"),
        "name": t.get("name"),
        "artist": (t.get("artists") or [{}])[0].get("name") if t.get("artists") else None,
        "artists": [a.get("name") for a in (t.get("artists") or []) if a.get("name")],
        "artist_ids": [a.get("id") for a in (t.get("artists") or []) if a.get("id")],
        "album": album.get("name"),
        "album_id": album.get("id"),
        "image_url": images[0].get("url") if images else None,
        "isrc": (t.get("external_ids") or {}).get("isrc"),
        "url": (t.get("external_urls") or {}).get("spotify"),
        "raw": t,
    }
    _CACHE_TRACK[key] = obj
    return obj


# ============================================================
# 4) ISRC lookup (✅ base pour routes track)
# ============================================================

def search_track_by_isrc(isrc: str, token: str, market: str = "FR") -> Optional[dict]:
    isrc = (isrc or "").strip()
    market = (market or "FR").strip().upper()
    if not isrc or not token:
        return None

    cache_key = (isrc, market)
    if cache_key in _CACHE_ISRC:
        return _CACHE_ISRC[cache_key]

    params = {"q": f"isrc:{isrc}", "type": "track", "limit": 1, "market": market}
    data = _spotify_get("/search", token=token, params=params)
    if not data:
        return None

    items = (((data.get("tracks") or {}).get("items")) or [])
    if not items:
        return None

    raw = items[0]  # <- track complet Spotify (avec album dict, artists dicts)

    album = raw.get("album") or {}
    images = album.get("images") or []
    image_url = images[0].get("url") if images and isinstance(images[0], dict) else None

    out = {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "duration_ms": raw.get("duration_ms"),
        # on garde les deux formats, comme ça ton app survit
        "artists": raw.get("artists") or [],  # <- dicts (id, name)
        "artist_names": [a.get("name") for a in (raw.get("artists") or []) if isinstance(a, dict) and a.get("name")],
        "artist_ids": [a.get("id") for a in (raw.get("artists") or []) if isinstance(a, dict) and a.get("id")],
        "album": album,                        # <- dict (id, images, release_date)
        "album_id": album.get("id"),
        "album_name": album.get("name"),
        "image_url": image_url,
        "release_date": album.get("release_date"),
        "raw": raw,
    }

    _CACHE_ISRC[cache_key] = out
    return out


def resolve_isrc(isrc: str, market: str = "FR") -> Optional[dict]:
    """
    Helper pratique: 1 appel -> toutes les infos essentielles à partir d'un ISRC.
    Retourne:
      track_id, track_name, album_id, album_name, artist_ids, artist_names, isrc, matches
    """
    tok = get_spotify_token()
    if not tok:
        return None

    t = search_track_by_isrc(isrc, token=tok, market=market)
    if not t:
        return None

    return {
        "isrc": t.get("isrc"),
        "matches": t.get("matches", 1),
        "track_id": t.get("id"),
        "track_name": t.get("name"),
        "album_id": t.get("album_id"),
        "album_name": t.get("album"),
        "artist_ids": t.get("artist_ids") or [],
        "artist_names": t.get("artists") or [],
    }


# ============================================================
# 5) Image getter + PIL helpers (inchangé)
# ============================================================

def image_getter(image_url: str, *, timeout: int = 20, use_cache: bool = True) -> Optional[Image.Image]:
    if not image_url:
        return None

    if use_cache and image_url in _CACHE_IMG:
        return _CACHE_IMG[image_url].copy()

    try:
        r = requests.get(image_url, timeout=timeout)
        if r.status_code != 200:
            return None
        img = Image.open(BytesIO(r.content)).convert("RGBA")
    except Exception:
        return None

    if use_cache:
        _CACHE_IMG[image_url] = img.copy()
    return img


def _make_circle_rgba(pil_img: Image.Image) -> Image.Image:
    pil_img = pil_img.convert("RGBA")
    s = min(pil_img.size)
    pil_img = ImageOps.fit(pil_img, (s, s), method=Image.LANCZOS, centering=(0.5, 0.5))

    k = 4
    mask = Image.new("L", (s * k, s * k), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, s * k, s * k), fill=255)
    mask = mask.resize((s, s), Image.LANCZOS)

    pil_img.putalpha(mask)
    return pil_img


def _make_rounded_square_rgba(pil_img: Image.Image, radius_ratio: float = 0.18) -> Image.Image:
    pil_img = pil_img.convert("RGBA")
    s = min(pil_img.size)
    pil_img = ImageOps.fit(pil_img, (s, s), method=Image.LANCZOS, centering=(0.5, 0.5))

    r = int(s * float(radius_ratio))
    mask = Image.new("L", (s, s), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, s, s), radius=r, fill=255)
    pil_img.putalpha(mask)
    return pil_img


def cover_getter(
    *,
    artist_name: Optional[str] = None,
    album_name: Optional[str] = None,
    track_name: Optional[str] = None,
    market: str = "FR",
    shape: str = "square",   # "square" | "rounded" | "circle"
    rounded_radius_ratio: float = 0.18,
) -> Optional[Image.Image]:
    tok = get_spotify_token()
    if not tok:
        return None

    img_url = None

    if track_name and artist_name:
        t = search_track(track_name, artist_name, token=tok, market=market)
        img_url = t.get("image_url") if t else None

    if not img_url and album_name and artist_name:
        al = search_album(album_name, artist_name, token=tok, market=market)
        img_url = al.get("image_url") if al else None

    if not img_url and artist_name:
        a = search_artist(artist_name, token=tok, market=market)
        img_url = a.get("image_url") if a else None

    img = image_getter(img_url) if img_url else None
    if img is None:
        return None

    if shape == "circle":
        return _make_circle_rgba(img)
    if shape == "rounded":
        return _make_rounded_square_rgba(img, radius_ratio=rounded_radius_ratio)
    return img


def covers_getter(
    df: pd.DataFrame,
    *,
    mode: str,
    market: str = "FR",
    shape: str = "rounded",
    img_size: int = 160,
    rounded_radius_ratio: float = 0.18,
    col_artist: str = "artiste",
    col_album: str = "album",
    col_track: str = "titre",
    out_col: str = "cover",
) -> pd.DataFrame:
    df2 = df.copy()

    def _get_row_cover(row) -> Optional[Image.Image]:
        artist = row.get(col_artist) if col_artist in row else None
        album = row.get(col_album) if col_album in row else None
        track = row.get(col_track) if col_track in row else None

        if mode == "artist":
            img = cover_getter(artist_name=artist, market=market, shape=shape, rounded_radius_ratio=rounded_radius_ratio)
        elif mode == "album":
            img = cover_getter(artist_name=artist, album_name=album, market=market, shape=shape, rounded_radius_ratio=rounded_radius_ratio)
        elif mode == "track":
            img = cover_getter(artist_name=artist, track_name=track, market=market, shape=shape, rounded_radius_ratio=rounded_radius_ratio)
        else:
            img = None

        if img is None:
            return None

        try:
            return img.resize((img_size, img_size), Image.LANCZOS)
        except Exception:
            return img

    df2[out_col] = df2.apply(_get_row_cover, axis=1)
    return df2


# ============================================================
# 6) Conversions temps
# ============================================================

def hours_to_hm(hours: float) -> str:
    h = int(hours)
    m = int(round((hours - h) * 60))
    if m == 60:
        h += 1
        m = 0
    return f"{h}h{m:02d}"


def seconds_to_mmss(seconds: Optional[Union[int, float]]) -> Optional[str]:
    if seconds is None or pd.isna(seconds):
        return None
    s = int(seconds)
    minutes = s // 60
    sec = s % 60
    return f"{minutes}:{sec:02d}"


# ============================================================
# 7) ISRC resolution batch (Spotify import)
# ============================================================

def resolve_spotify_isrcs(df: pd.DataFrame, sp_token: str) -> pd.DataFrame:
    """
    Pour les lignes source='spotify' sans ISRC, résout les ISRCs via /tracks?ids=...
    Retourne un nouveau DataFrame avec la colonne ISRC remplie autant que possible.
    """
    if "source" not in df.columns or "spotify_uri" not in df.columns:
        return df

    mask = (df["source"] == "spotify") & df["ISRC"].isna() & df["spotify_uri"].notna()
    if not mask.any():
        return df

    df = df.copy()

    uris = df.loc[mask, "spotify_uri"].dropna().unique().tolist()
    track_ids = [
        uri.split(":")[-1]
        for uri in uris
        if uri.startswith("spotify:track:") and uri.split(":")[-1]
    ]

    if not track_ids:
        return df

    isrc_map: Dict[str, str] = {}
    for i in range(0, len(track_ids), 50):
        batch = track_ids[i:i + 50]
        data = _spotify_get("/tracks", token=sp_token, params={"ids": ",".join(batch)})
        tracks = (data or {}).get("tracks") or []
        for t in tracks:
            if not isinstance(t, dict):
                continue
            tid = t.get("id")
            isrc = (t.get("external_ids") or {}).get("isrc")
            if tid and isrc:
                isrc_map[tid] = isrc

    def _resolve(uri):
        if not isinstance(uri, str) or not uri.startswith("spotify:track:"):
            return None
        return isrc_map.get(uri.split(":")[-1])

    df.loc[mask, "ISRC"] = df.loc[mask, "spotify_uri"].apply(_resolve)
    return df


def get_cover_by_spotify_uri(spotify_uri: str, token: Optional[str] = None) -> Optional[str]:
    """Retourne l'image_url d'un titre à partir de son URI spotify:track:XXX."""
    if not spotify_uri or not spotify_uri.startswith("spotify:track:"):
        return None
    track_id = spotify_uri.split(":")[-1]
    tok = token or get_spotify_token()
    if not tok:
        return None
    t = get_track_by_id(track_id, token=tok)
    return (t or {}).get("image_url")


# ============================================================
# 8) Debug / reset caches
# ============================================================

def clear_spotify_caches() -> None:
    global _TOKEN, _TOKEN_EXPIRES_AT
    _TOKEN = None
    _TOKEN_EXPIRES_AT = 0.0

    _CACHE_ARTIST.clear()
    _CACHE_ALBUM.clear()
    _CACHE_TRACK.clear()
    _CACHE_IMG.clear()

    _CACHE_ARTIST_ID.clear()
    _CACHE_ALBUM_ID.clear()
    _CACHE_TRACK_ID.clear()
    _CACHE_ISRC.clear()


# =========================
# 🎨 Variables globales (thème)
# =========================

PLOT_BG = "#0B0F19"
PAPER_BG = "#0B0F19"
TEXT_COLOR = "#E5E7EB"

BASE_COLOR = "#7C3AED"
YEAR_LIGHT_LOW = 0.55
YEAR_LIGHT_HIGH = 1.22

FIG_HEIGHT = 420


from typing import List, Set, Dict, Optional

def list_artist_album_ids_strict(artist_id: str, token: str, market: str = "FR") -> List[str]:
    album_ids: List[str] = []
    seen: Set[str] = set()

    offset = 0
    limit = 50

    while True:
        data = _spotify_get(
            f"/artists/{artist_id}/albums",
            token=token,
            params={
                "include_groups": "album,single",  # définition stricte
                "market": market,
                "limit": limit,
                "offset": offset,
            },
        )
        if not data:
            break

        items = data.get("items") or []
        for it in items:
            aid = (it or {}).get("id")
            if aid and aid not in seen:
                seen.add(aid)
                album_ids.append(aid)

        # pagination
        if len(items) < limit:
            break
        offset += limit

        # sécurité anti-folie (tu peux monter/descendre)
        if offset > 2000:
            break

    return album_ids


def count_artist_tracks_strict(artist_id: str, token: str, market: str = "FR", hard_cap: int = 2000) -> Dict[str, object]:
    """
    Compte les tracks où l'artiste est principal (track.artists[0].id == artist_id),
    en se basant sur albums+singles uniquement.
    Dédup par track.id.
    hard_cap: coupe le calcul si ça explose (Kanye, coucou).
    """
    album_ids = list_artist_album_ids_strict(artist_id, token=token, market=market)

    seen_tracks: Set[str] = set()
    total = 0

    for album_id in album_ids:
        offset = 0
        limit = 50

        while True:
            data = _spotify_get(
                f"/albums/{album_id}/tracks",
                token=token,
                params={"market": market, "limit": limit, "offset": offset},
            )
            if not data:
                break

            items = data.get("items") or []
            for tr in items:
                if not isinstance(tr, dict):
                    continue

                tid = tr.get("id")
                if not tid or tid in seen_tracks:
                    continue

                artists = tr.get("artists") or []
                if artists and isinstance(artists[0], dict) and artists[0].get("id") == artist_id:
                    seen_tracks.add(tid)
                    total += 1

                    # coupe-circuit pour éviter l’acharnement
                    if total >= hard_cap:
                        return {"value": total, "capped": True, "hard_cap": hard_cap}

            if len(items) < limit:
                break
            offset += limit

        # coupe-circuit aussi si l'ensemble devient trop gros
        if total >= hard_cap:
            return {"value": total, "capped": True, "hard_cap": hard_cap}

    return {"value": total, "capped": False}
