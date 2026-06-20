# analytics/artist.py
from __future__ import annotations

import calendar
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Optional

import pandas as pd
import requests
from time import perf_counter

from dashboard.analytics.spotify import (
    get_spotify_token,
    search_track,
    search_album,
    get_artist_by_id,
    hours_to_hm,
    count_artist_tracks_strict,
)

SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# ============================================================
# CACHES & LOCKS
# ============================================================
_executor = ThreadPoolExecutor(max_workers=3)
_total_tracks_lock = threading.Lock()

_total_tracks_future_id: dict[str, Future] = {}
_total_tracks_value_id: dict[str, int] = {}
_total_tracks_meta_id: dict[str, dict] = {}
_TOTAL_TRACKS_CACHE: dict[str, dict] = {}
_TOTAL_TRACKS_TTL_SECONDS = 24 * 3600

_cache_albums: dict[tuple, list] = {}
_cache_top_titles: dict[tuple, pd.DataFrame] = {}
_cache_top_albums: dict[tuple, pd.DataFrame] = {}
_catalogue_isrcs_cache: dict[str, set] = {}


def _norm_id(artist_id: str) -> str:
    return str(artist_id or "").strip()


class SpotifyRateLimitError(Exception):
    pass


# ============================================================
# HTTP SPOTIFY
# ============================================================
def spotify_get(url: str, token: str, params: dict | None = None, retries: int = 8, max_wait_seconds: int = 10) -> requests.Response:
    for attempt in range(retries + 1):
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=20)
        if r.status_code == 429:
            retry_after = int(r.headers.get("Retry-After", "1"))
            if retry_after > max_wait_seconds:
                raise SpotifyRateLimitError(f"Retry-After too high ({retry_after}s)")
            time.sleep(retry_after + 0.2)
            continue
        r.raise_for_status()
        return r
    raise requests.HTTPError(f"Spotify failed after {retries+1} tries | url={url}")


# ============================================================
# TOTAL TRACKS (async par artist_id)
# ============================================================
def _get_cached_total_tracks(artist_id: str):
    ent = _TOTAL_TRACKS_CACHE.get(artist_id)
    if not ent:
        return None
    if time.time() > ent["expires_at"]:
        _TOTAL_TRACKS_CACHE.pop(artist_id, None)
        return None
    return ent["value"]


def _set_cached_total_tracks(artist_id: str, value):
    _TOTAL_TRACKS_CACHE[artist_id] = {"value": value, "expires_at": time.time() + _TOTAL_TRACKS_TTL_SECONDS}


def get_total_tracks_cached_value_id(artist_id: str) -> int | None:
    return _total_tracks_value_id.get(_norm_id(artist_id))


def _get_albums(artist_id: str, token: str) -> list[dict]:
    key = (artist_id, "albums_singles")
    if key in _cache_albums:
        return _cache_albums[key]
    albums: list[dict] = []
    params = {"include_groups": "album,single", "limit": 50, "offset": 0}
    while True:
        r = spotify_get(f"{SPOTIFY_API_BASE}/artists/{artist_id}/albums", token=token, params=params)
        data = r.json()
        albums.extend(data.get("items", []))
        if not data.get("next"):
            break
        params["offset"] += 50
    _cache_albums[key] = albums
    return albums


def _get_full_tracks_batch(track_ids: list[str], token: str) -> list[dict]:
    results: list[dict] = []
    for i in range(0, len(track_ids), 50):
        batch = track_ids[i:i + 50]
        r = spotify_get(
            f"{SPOTIFY_API_BASE}/tracks",
            token=token,
            params={"ids": ",".join(batch)},
        )
        results.extend(t for t in (r.json().get("tracks") or []) if t)
    return results


def _get_tracks(album_id: str, token: str) -> list[dict]:
    tracks: list[dict] = []
    params = {"limit": 50, "offset": 0}
    while True:
        r = spotify_get(f"{SPOTIFY_API_BASE}/albums/{album_id}/tracks", token=token, params=params)
        data = r.json()
        tracks.extend(data.get("items", []))
        if not data.get("next"):
            break
        params["offset"] += 50
    return tracks


def get_total_tracks_by_artist_id(artist_id: str, token: str | None = None) -> int:
    tok = token or get_spotify_token()
    if not tok:
        return 0
    aid = _norm_id(artist_id)
    if not aid:
        return 0
    cache_key = f"id:{aid}"
    if cache_key in _total_tracks_value_id:
        return _total_tracks_value_id[cache_key]
    albums = _get_albums(aid, tok)
    album_ids = [a["id"] for a in albums if a.get("id")]
    track_ids: list[str] = []
    with ThreadPoolExecutor(max_workers=10) as exe:
        for track_list in exe.map(lambda alb_id: _get_tracks(alb_id, tok), album_ids):
            for t in track_list:
                if aid in [art["id"] for art in t.get("artists", [])]:
                    if t.get("id"):
                        track_ids.append(t["id"])
    full_tracks = _get_full_tracks_batch(track_ids, tok)
    unique_keys: set[str] = set()
    for t in full_tracks:
        isrc = (t.get("external_ids") or {}).get("isrc", "").strip()
        if isrc:
            unique_keys.add(isrc)
        else:
            name = (t.get("name") or "").strip().lower()
            if name:
                unique_keys.add(f"__name__{name}")
    _catalogue_isrcs_cache[aid] = unique_keys
    total = len(unique_keys)
    _total_tracks_value_id[cache_key] = total
    return total


def ensure_total_tracks_job_id(artist_id: str, token: str | None = None) -> None:
    key = _norm_id(artist_id)
    if not key or key in _total_tracks_value_id:
        return
    with _total_tracks_lock:
        if key in _total_tracks_value_id:
            return
        meta = _total_tracks_meta_id.get(key)
        if isinstance(meta, dict):
            cooldown_until = meta.get("cooldown_until")
            if isinstance(cooldown_until, (int, float)) and time.time() < float(cooldown_until):
                return
        fut = _total_tracks_future_id.get(key)
        if fut is not None and not fut.done():
            return
        tok = token or get_spotify_token()
        if not tok:
            return
        _total_tracks_meta_id[key] = {"status": "pending", "cooldown_until": None}

        def _job():
            try:
                value = get_total_tracks_by_artist_id(key, token=tok)
                with _total_tracks_lock:
                    if isinstance(value, int):
                        _total_tracks_value_id[key] = value
                        _total_tracks_meta_id[key] = {"status": "done", "cooldown_until": None}
                return value
            except SpotifyRateLimitError as e:
                retry_after = getattr(e, "retry_after", 60)
                with _total_tracks_lock:
                    _total_tracks_meta_id[key] = {"status": "rate_limited", "cooldown_until": time.time() + float(retry_after)}
                return None
            except Exception:
                with _total_tracks_lock:
                    _total_tracks_meta_id[key] = {"status": "error", "cooldown_until": None}
                return None

        _total_tracks_future_id[key] = _executor.submit(_job)


# ============================================================
# KPI HELPERS (sans .copy())
# ============================================================
def get_artist_rank(df_tracks: pd.DataFrame, artist_name: str) -> Optional[int]:
    if df_tracks is None or df_tracks.empty:
        return None
    if not {"artiste", "temps_écoute"}.issubset(df_tracks.columns):
        return None
    grp = (
        df_tracks.assign(
            artiste=df_tracks["artiste"].astype(str).str.strip(),
            temps_écoute=pd.to_numeric(df_tracks["temps_écoute"], errors="coerce").fillna(0)
        )
        .groupby("artiste", as_index=False)["temps_écoute"]
        .sum()
        .sort_values("temps_écoute", ascending=False)
        .reset_index(drop=True)
    )
    pattern = rf"(?i)(^|,\s*){re.escape(artist_name.strip())}(\s*,|$)"
    hit = grp.index[grp["artiste"].str.contains(pattern, regex=True, na=False)].tolist()
    return int(hit[0] + 1) if hit else None


def get_first_listen_date(df_tracks: pd.DataFrame, artist_name: str) -> Optional[pd.Timestamp]:
    if df_tracks is None or df_tracks.empty:
        return None
    if not {"artiste", "date_écoute"}.issubset(df_tracks.columns):
        return None
    mask = df_tracks["artiste"].astype(str).str.strip() == artist_name.strip()
    sub = df_tracks.loc[mask, "date_écoute"]
    if sub.empty:
        return None
    d = pd.to_datetime(sub, errors="coerce").min()
    return d if pd.notna(d) else None


def get_total_listen_minutes(df_tracks: pd.DataFrame, artist_name: str) -> int:
    if df_tracks is None or df_tracks.empty:
        return 0
    if not {"artiste", "temps_écoute"}.issubset(df_tracks.columns):
        return 0
    pattern = rf"(?i)(^|,\s*){re.escape(artist_name.strip())}(\s*,|$)"
    mask = df_tracks["artiste"].astype(str).str.contains(pattern, regex=True, na=False)
    total = pd.to_numeric(df_tracks.loc[mask, "temps_écoute"], errors="coerce").fillna(0).sum()
    return int(round(float(total) / 60.0))


def get_most_listened_month(df_tracks: pd.DataFrame, artist_name: str) -> Optional[str]:
    if df_tracks is None or df_tracks.empty:
        return None
    if not {"artiste", "temps_écoute", "date_écoute"}.issubset(df_tracks.columns):
        return None
    mask = df_tracks["artiste"].astype(str).str.strip() == artist_name.strip()
    sub = df_tracks.loc[mask].copy()
    sub["date_écoute"] = pd.to_datetime(sub["date_écoute"], errors="coerce")
    sub = sub[sub["date_écoute"].notna()]
    if sub.empty:
        return None
    sub["ym"] = sub["date_écoute"].dt.to_period("M")
    grp = sub.groupby("ym")["temps_écoute"].sum().sort_values(ascending=False)
    if grp.empty:
        return None
    best = grp.index[0]
    return f"{calendar.month_abbr[int(best.month)]} {int(best.year)}"


def _format_followers_fr(n: int) -> str:
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}".replace(".", ",") + "m"
    if n >= 1_000:
        return f"{n/1_000:.1f}".replace(".", ",") + "k"
    return str(n)


def _format_coverage_pill(ratio: float | None) -> str:
    if ratio is None:
        return "—"
    try:
        pct = int(round(max(0.0, min(1.0, ratio)) * 100))
        return f"{pct}%"
    except Exception:
        return "—"


def get_artist_genres_by_id(artist_id: str, token: str | None = None, market: str = "FR") -> list[str]:
    tok = token or get_spotify_token()
    if not tok:
        return []
    a = get_artist_by_id(artist_id, token=tok)
    raw = (a or {}).get("raw") or {}
    return list(raw.get("genres") or [])


def get_artist_followers_by_id(artist_id: str, token: str | None = None, market: str = "FR") -> int:
    tok = token or get_spotify_token()
    if not tok:
        return 0
    a = get_artist_by_id(artist_id, token=tok)
    raw = (a or {}).get("raw") or {}
    return int((raw.get("followers") or {}).get("total") or 0)


def get_discography_coverage_by_id(df_tracks: pd.DataFrame, artist_id: str, artist_name: str, token: str | None = None) -> float | None:
    if not artist_id:
        return None
    tok = token or get_spotify_token()
    if not tok:
        return None
    aid = _norm_id(artist_id)
    if aid not in _catalogue_isrcs_cache:
        get_total_tracks_by_artist_id(aid, token=tok)
    catalogue_keys = _catalogue_isrcs_cache.get(aid, set())
    catalogue_isrcs = {k for k in catalogue_keys if not k.startswith("__name__")}
    if not catalogue_isrcs:
        return None
    if df_tracks is None or df_tracks.empty or "ISRC" not in df_tracks.columns:
        return 0.0
    pattern = rf"(?i)(^|,\s*){re.escape(artist_name.strip())}(\s*,|$)"
    mask = df_tracks["artiste"].astype(str).str.contains(pattern, regex=True, na=False)
    listened_isrcs = set(df_tracks.loc[mask, "ISRC"].astype(str).str.strip().unique()) - {"", "nan"}
    intersection = listened_isrcs & catalogue_isrcs
    return len(intersection) / len(catalogue_isrcs)


# ============================================================
# KPI ARTISTE BY ID
# ============================================================
def get_artist_kpis_by_id(df_tracks: pd.DataFrame, df_artists: pd.DataFrame, artist_id: str, market: str = "FR") -> dict:
    tok = get_spotify_token()
    a = get_artist_by_id(artist_id, token=tok) if tok else None
    artist_name = (a.get("name") if a else "") or "—"

    rank = get_artist_rank(df_tracks, artist_name)
    first_dt = get_first_listen_date(df_tracks, artist_name)
    discover_date = first_dt.strftime("%d/%m/%y") if first_dt is not None else "—"
    total_min = get_total_listen_minutes(df_tracks, artist_name)
    listen_minutes_pill = f"{total_min} min"
    most_month = get_most_listened_month(df_tracks, artist_name) or "—"

    raw = (a or {}).get("raw") or {}
    genres = list(raw.get("genres") or [])
    genres_pill = ", ".join(genres[:2]) if genres else "—"
    followers = int((raw.get("followers") or {}).get("total") or 0)
    followers_pill = f"{_format_followers_fr(followers)} followers" if followers else "—"

    total_tracks_spotify = None
    if tok:
        try:
            ensure_total_tracks_job_id(artist_id, token=tok)
            total_tracks_spotify = get_total_tracks_cached_value_id(artist_id)
        except Exception:
            pass

    nb_sons_pill = f"{total_tracks_spotify} sons" if isinstance(total_tracks_spotify, int) else "—"
    coverage_pill = "—"
    if isinstance(total_tracks_spotify, int) and total_tracks_spotify > 0:
        try:
            ratio = get_discography_coverage_by_id(df_tracks, artist_id, artist_name, token=tok)
            coverage_pill = _format_coverage_pill(ratio)
        except Exception:
            pass

    # Vide les caches mémoire après calcul
    _cache_top_titles.clear()
    _cache_top_albums.clear()

    return {
        "artist_id": artist_id,
        "artist_name": artist_name,
        "rank": rank,
        "nb_sons_pill": nb_sons_pill,
        "genres_pill": genres_pill,
        "followers_pill": followers_pill,
        "discover_date": discover_date,
        "most_listened_month": most_month,
        "listen_minutes_pill": listen_minutes_pill,
        "coverage_pill": coverage_pill,
        "total_tracks_spotify": total_tracks_spotify,
    }


# ============================================================
# TOP TITRES & ALBUMS
# ============================================================
def get_top_10_titles_by_listen_time(df_tracks: pd.DataFrame, artist_name: str, top_n: int = 10, market: str = "FR", token: str | None = None) -> pd.DataFrame:
    empty_cols = ["classement", "cover", "titre", "album", "isrc", "temps_écoute"]
    if df_tracks is None or df_tracks.empty:
        return pd.DataFrame(columns=empty_cols)
    if not {"artiste", "titre", "temps_écoute"}.issubset(df_tracks.columns):
        return pd.DataFrame(columns=empty_cols)

    artist_name = str(artist_name).strip()
    cache_key = (artist_name.lower(), int(top_n), str(market).upper())
    if cache_key in _cache_top_titles:
        return _cache_top_titles[cache_key].copy()

    tok = token or get_spotify_token()
    if not tok:
        return pd.DataFrame(columns=empty_cols)

    pattern = r'(?i)(^|,\s*)' + re.escape(artist_name) + r'(\s*,|$)'
    mask = (
        df_tracks["artiste"].astype(str).str.contains(pattern, regex=True, na=False)
        & (pd.to_numeric(df_tracks["temps_écoute"], errors="coerce").fillna(0) > 0)
    )
    cols_needed = [c for c in ["titre", "artiste", "temps_écoute", "ISRC", "album"] if c in df_tracks.columns]
    df_artist = df_tracks.loc[mask, cols_needed]

    if df_artist.empty:
        return pd.DataFrame(columns=empty_cols)

    top = (
        df_artist.groupby("titre", as_index=False)["temps_écoute"]
        .sum()
        .sort_values("temps_écoute", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    top["classement"] = top.index + 1

    if "ISRC" in df_artist.columns:
        isrc_score = df_artist.groupby(["titre", "ISRC"], as_index=False)["temps_écoute"].sum()
        idx = isrc_score.groupby("titre")["temps_écoute"].idxmax()
        best_isrc = isrc_score.loc[idx, ["titre", "ISRC"]].rename(columns={"ISRC": "isrc"})
        top = top.merge(best_isrc, on="titre", how="left")
    else:
        top["isrc"] = ""

    if "album" in df_artist.columns:
        best_album = df_artist.groupby(["titre", "album"], as_index=False)["temps_écoute"].sum()
        idx = best_album.groupby("titre")["temps_écoute"].idxmax()
        best_album = best_album.loc[idx, ["titre", "album"]]
        top = top.merge(best_album, on="titre", how="left")
    else:
        top["album"] = ""

    top["temps_écoute"] = (top["temps_écoute"] / 3600).apply(hours_to_hm)

    def _cover_for_title(title: str) -> str | None:
        t = search_track(title.strip(), artist_name, token=tok, market=market)
        return (t or {}).get("image_url")

    with ThreadPoolExecutor(max_workers=5) as ex:
        top["cover"] = list(ex.map(_cover_for_title, top["titre"].astype(str).tolist()))

    out = top[["classement", "cover", "titre", "album", "isrc", "temps_écoute"]]
    _cache_top_titles[cache_key] = out.copy()
    return out


def get_top_10_albums_by_listen_time(df_tracks: pd.DataFrame, artist_name: str, top_n: int = 10, market: str = "FR", token: str | None = None) -> pd.DataFrame:
    cols = ["classement", "cover", "album", "album_id", "temps_écoute"]
    if df_tracks is None or df_tracks.empty:
        return pd.DataFrame(columns=cols)
    if not {"artiste", "album", "temps_écoute"}.issubset(df_tracks.columns):
        return pd.DataFrame(columns=cols)

    artist_name = str(artist_name).strip()
    cache_key = (artist_name.lower(), int(top_n), str(market).upper())
    if cache_key in _cache_top_albums:
        return _cache_top_albums[cache_key].copy()

    tok = token or get_spotify_token()
    if not tok:
        return pd.DataFrame(columns=cols)

    pattern = r'(?i)(^|,\s*)' + re.escape(artist_name) + r'(\s*,|$)'
    mask = (
        df_tracks["artiste"].astype(str).str.contains(pattern, regex=True, na=False)
        & (pd.to_numeric(df_tracks["temps_écoute"], errors="coerce").fillna(0) > 0)
    )
    cols_needed = [c for c in ["album", "artiste", "temps_écoute"] if c in df_tracks.columns]
    df_artist = df_tracks.loc[mask, cols_needed]

    if df_artist.empty:
        return pd.DataFrame(columns=cols)

    top = (
        df_artist.groupby("album", as_index=False)["temps_écoute"]
        .sum()
        .sort_values("temps_écoute", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    top["classement"] = top.index + 1
    top["temps_écoute"] = (top["temps_écoute"] / 3600).apply(hours_to_hm)

    def _meta_for_album(album_name: str) -> tuple:
        a = search_album(album_name.strip(), artist_name, token=tok, market=market)
        if not a:
            return None, None
        return a.get("id"), a.get("image_url")

    with ThreadPoolExecutor(max_workers=5) as ex:
        metas = list(ex.map(_meta_for_album, top["album"].astype(str).tolist()))

    top["album_id"] = [m[0] for m in metas]
    top["cover"] = [m[1] for m in metas]

    out = top[cols]
    _cache_top_albums[cache_key] = out.copy()
    return out