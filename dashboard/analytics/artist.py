# analytics/artist.py
from __future__ import annotations

import calendar
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import pandas as pd
import requests

from dashboard.analytics.spotify import (
    get_spotify_token,
    search_artist,
    search_track,
    search_album,
    get_artist_by_id,
)


from concurrent.futures import ThreadPoolExecutor, Future
import threading
import time

_total_tracks_future: dict[str, Future] = {}
_total_tracks_value: dict[str, int] = {}
_total_tracks_lock = threading.Lock()

_executor = ThreadPoolExecutor(max_workers=3)  # petit, pour ne pas bombarder Spotify

_cache_top_titles: dict[tuple[str, int, str], pd.DataFrame] = {}
_cache_top_albums: dict[tuple[str, int, str], pd.DataFrame] = {}
_total_tracks_meta: dict[str, dict] = {}

import time
from typing import Dict, Any

_TOTAL_TRACKS_CACHE: Dict[str, Dict[str, Any]] = {}
_TOTAL_TRACKS_TTL_SECONDS = 24 * 3600  # 24h

SPOTIFY_API_BASE = "https://api.spotify.com/v1"

# =========================
# Helpers - cache temp
# =========================
def _norm_key(name: str) -> str:
    return str(name).strip().lower()

# ✅ NEW: normalisation ID (artist_id Spotify)
def _norm_id(artist_id: str) -> str:
    return str(artist_id or "").strip()

def get_total_tracks_cached_value(artist_name: str) -> int | None:
    key = _norm_key(artist_name)
    return _total_tracks_value.get(key)

# ✅ NEW: cache value by artist_id (sans casser l'existant)
_total_tracks_future_id: dict[str, Future] = {}
_total_tracks_value_id: dict[str, int] = {}
_total_tracks_meta_id: dict[str, dict] = {}

def _get_cached_total_tracks(artist_id: str):
    ent = _TOTAL_TRACKS_CACHE.get(artist_id)
    if not ent:
        return None
    if time.time() > ent["expires_at"]:
        _TOTAL_TRACKS_CACHE.pop(artist_id, None)
        return None
    return ent["value"]


def _set_cached_total_tracks(artist_id: str, value):
    _TOTAL_TRACKS_CACHE[artist_id] = {
        "value": value,
        "expires_at": time.time() + _TOTAL_TRACKS_TTL_SECONDS,
    }


def get_total_tracks_cached_value_id(artist_id: str) -> int | None:
    key = _norm_id(artist_id)
    return _total_tracks_value_id.get(key)

def ensure_total_tracks_job(artist_name: str, token: str | None = None) -> None:
    """
    Lance le calcul en background si pas déjà lancé.
    Ne bloque jamais.
    Gère un cooldown en cas de rate limit (sinon on se fait massacrer par Spotify).
    """
    import time

    key = _norm_key(artist_name)

    # Déjà calculé
    if key in _total_tracks_value:
        return

    with _total_tracks_lock:
        # Re-check dans le lock
        if key in _total_tracks_value:
            return

        # Cooldown actif ?
        meta = _total_tracks_meta.get(key)
        if isinstance(meta, dict):
            cooldown_until = meta.get("cooldown_until")
            if isinstance(cooldown_until, (int, float)) and time.time() < float(cooldown_until):
                return

        # Job déjà en cours ?
        fut = _total_tracks_future.get(key)
        if fut is not None and not fut.done():
            return

        tok = token or get_spotify_token()
        if not tok:
            _total_tracks_meta[key] = {"status": "error", "cooldown_until": None, "error": "no_token"}
            return

        # Marque pending au lancement
        _total_tracks_meta[key] = {"status": "pending", "cooldown_until": None, "error": None}

        def _job():
            import time
            try:
                # ta fonction lourde existante (on ne la modifie pas)
                value = get_total_tracks(artist_name, token=tok)

                # stocke le résultat
                with _total_tracks_lock:
                    if isinstance(value, int):
                        _total_tracks_value[key] = value
                        _total_tracks_meta[key] = {"status": "done", "cooldown_until": None, "error": None}
                    else:
                        _total_tracks_meta[key] = {"status": "error", "cooldown_until": None, "error": "non_int_result"}
                return value

            except SpotifyRateLimitError as e:
                # Si tu as e.retry_after, on l'utilise. Sinon cooldown par défaut.
                retry_after = getattr(e, "retry_after", None)
                if not isinstance(retry_after, (int, float)):
                    retry_after = 60  # fallback raisonnable

                with _total_tracks_lock:
                    _total_tracks_meta[key] = {
                        "status": "rate_limited",
                        "cooldown_until": time.time() + float(retry_after),
                        "error": f"rate_limited retry_after={retry_after}",
                    }
                return None

            except Exception as e:
                with _total_tracks_lock:
                    _total_tracks_meta[key] = {"status": "error", "cooldown_until": None, "error": repr(e)}
                return None

        _total_tracks_future[key] = _executor.submit(_job)


# ✅ NEW: job async par artist_id (sans toucher au job par nom)
def ensure_total_tracks_job_id(artist_id: str, token: str | None = None) -> None:
    """
    Lance le calcul en background par artist_id Spotify.
    Ne bloque jamais.
    """
    import time

    key = _norm_id(artist_id)
    if not key:
        return

    # Déjà calculé
    if key in _total_tracks_value_id:
        return

    with _total_tracks_lock:
        if key in _total_tracks_value_id:
            return

        # Cooldown actif ?
        meta = _total_tracks_meta_id.get(key)
        if isinstance(meta, dict):
            cooldown_until = meta.get("cooldown_until")
            if isinstance(cooldown_until, (int, float)) and time.time() < float(cooldown_until):
                return

        # Job déjà en cours ?
        fut = _total_tracks_future_id.get(key)
        if fut is not None and not fut.done():
            return

        tok = token or get_spotify_token()
        if not tok:
            _total_tracks_meta_id[key] = {"status": "error", "cooldown_until": None, "error": "no_token"}
            return

        _total_tracks_meta_id[key] = {"status": "pending", "cooldown_until": None, "error": None}

        def _job():
            import time
            try:
                value = get_total_tracks_by_artist_id(key, token=tok)

                with _total_tracks_lock:
                    if isinstance(value, int):
                        _total_tracks_value_id[key] = value
                        _total_tracks_meta_id[key] = {"status": "done", "cooldown_until": None, "error": None}
                    else:
                        _total_tracks_meta_id[key] = {"status": "error", "cooldown_until": None, "error": "non_int_result"}
                return value

            except SpotifyRateLimitError as e:
                retry_after = getattr(e, "retry_after", None)
                if not isinstance(retry_after, (int, float)):
                    retry_after = 60

                with _total_tracks_lock:
                    _total_tracks_meta_id[key] = {
                        "status": "rate_limited",
                        "cooldown_until": time.time() + float(retry_after),
                        "error": f"rate_limited retry_after={retry_after}",
                    }
                return None

            except Exception as e:
                with _total_tracks_lock:
                    _total_tracks_meta_id[key] = {"status": "error", "cooldown_until": None, "error": repr(e)}
                return None

        _total_tracks_future_id[key] = _executor.submit(_job)


def get_total_tracks_job_status(artist_name: str) -> dict:
    """
    Retourne un statut lisible par l'API:
    - done + value
    - pending
    - not_started
    - rate_limited + retry_after (secondes restantes)
    - error + message
    """
    import time

    key = _norm_key(artist_name)

    if key in _total_tracks_value:
        return {"status": "done", "value": _total_tracks_value[key]}

    meta = _total_tracks_meta.get(key) or {}

    # Cooldown/rate limit
    cooldown_until = meta.get("cooldown_until")
    if isinstance(cooldown_until, (int, float)):
        remaining = float(cooldown_until) - time.time()
        if remaining > 0:
            return {"status": "rate_limited", "retry_after": int(round(remaining))}

    fut = _total_tracks_future.get(key)
    if fut is None:
        # Si on a déjà une erreur stockée, on la retourne
        if meta.get("status") == "error":
            return {"status": "error", "error": meta.get("error", "unknown")}
        return {"status": "not_started"}

    if not fut.done():
        return {"status": "pending"}

    # done
    try:
        value = fut.result()
        if isinstance(value, int):
            return {"status": "done", "value": value}
        # si c'était un rate limit / error, meta dira quoi faire
        if meta.get("status") == "rate_limited":
            # recalcul du retry_after déjà géré plus haut, donc ici on retombe en pending/error
            return {"status": "rate_limited", "retry_after": 60}
        if meta.get("status") == "error":
            return {"status": "error", "error": meta.get("error", "unknown")}
        return {"status": "error", "error": "non_int_result"}
    except Exception as e:
        return {"status": "error", "error": repr(e)}


# ✅ NEW: job status by artist_id (sans toucher à ton API actuelle)
from dashboard.analytics.spotify import get_spotify_token, count_artist_tracks_strict

def get_total_tracks_job_status_id(artist_id: str) -> dict:
    # 1) Cache TTL
    cached = _get_cached_total_tracks(artist_id)
    if cached is not None:
        return {"status": "done", "value": cached, "retry_after": None}

    tok = get_spotify_token()
    if not tok:
        return {"status": "error", "value": None, "retry_after": None, "error": "no_token"}

    market = os.getenv("SPOTIFY_MARKET", "FR")

    # 2) Calcul strict + anti-Kanye
    res = count_artist_tracks_strict(artist_id, token=tok, market=market, hard_cap=2000)

    value = res.get("value")
    capped = res.get("capped", False)

    # 3) Format “humain” si cap
    # (sinon tu vas afficher un chiffre faux comme si c’était exact)
    final_value = f">{value}" if capped else int(value)

    _set_cached_total_tracks(artist_id, final_value)
    return {"status": "done", "value": final_value, "retry_after": None}



# =========================
# CACHES (comme notebook)
# =========================
_cache_artist_id: dict[str, str] = {}
_cache_albums: dict[tuple[str, str], list[dict]] = {}
_cache_tracks: dict[str, int] = {}


def clear_artist_caches() -> None:
    """Utile quand tu modifies la logique et tu veux forcer un recompute."""
    _cache_artist_id.clear()
    _cache_albums.clear()
    _cache_tracks.clear()
    _cache_top_titles.clear()
    _cache_top_albums.clear()
    # ✅ NEW: clear ID-job caches aussi (ne supprime rien, juste utile)
    _total_tracks_future_id.clear()
    _total_tracks_value_id.clear()
    _total_tracks_meta_id.clear()

# =========================
# HTTP Spotify: PATCH 429 + PERF
# =========================
import time
import requests
from typing import Optional
from time import perf_counter

# Stats globales (resettable côté app.py si besoin)
_SPOTIFY_STATS = {
    "count": 0,
    "time": 0.0,
}

class SpotifyRateLimitError(Exception):
    pass


def spotify_get(
    url: str,
    token: str,
    params: Optional[dict] = None,
    retries: int = 8,
    max_wait_seconds: int = 10,   # 👈 CAP anti-sieste
) -> requests.Response:
    """
    GET Spotify avec gestion 429/401 + instrumentation perf.

    - 429 :
        * sleep Retry-After (cap à max_wait_seconds)
        * si Retry-After > cap => SpotifyRateLimitError
    - 401 :
        * token expiré => raise
    - Stats :
        * _SPOTIFY_STATS["count"] += 1
        * _SPOTIFY_STATS["time"]  += durée réelle de l'appel
    """

    start = perf_counter()

    try:
        for attempt in range(retries + 1):
            r = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                params=params,
                timeout=20,
            )

            if r.status_code == 429:
                retry_after = int(r.headers.get("Retry-After", "1"))
                print(
                    f"[SPOTIFY 429] retry_after={retry_after}s "
                    f"| attempt={attempt+1}/{retries+1} | url={url}"
                )

                if retry_after > max_wait_seconds:
                    raise SpotifyRateLimitError(
                        f"Retry-After too high ({retry_after}s) for url={url}"
                    )

                time.sleep(retry_after + 0.2)
                continue

            if r.status_code == 401:
                print(f"[SPOTIFY 401] token expired | url={url}")
                r.raise_for_status()

            r.raise_for_status()
            return r

        raise requests.HTTPError(
            f"Spotify request failed after {retries+1} tries | url={url}"
        )

    finally:
        elapsed = perf_counter() - start
        _SPOTIFY_STATS["count"] += 1
        _SPOTIFY_STATS["time"] += elapsed



# ============================================================
# DISCOGRAPHIE (EXACT NOTEBOOK)
# ============================================================
def _get_artist_id(name: str, token: str) -> Optional[str]:
    if name in _cache_artist_id:
        return _cache_artist_id[name]

    r = spotify_get(
        f"{SPOTIFY_API_BASE}/search",
        token=token,
        params={"q": name, "type": "artist", "limit": 1},
    )

    items = r.json()["artists"]["items"]
    if not items:
        return None

    artist_id = items[0]["id"]
    _cache_artist_id[name] = artist_id
    return artist_id

# ✅ NEW: trivial helper (artist_id already known)
def _get_artist_id_from_id(artist_id: str, token: str) -> Optional[str]:
    aid = _norm_id(artist_id)
    return aid if aid else None


def _get_albums_and_appears_on(artist_id: str, token: str) -> list[dict]:
    """
    EXACT notebook:
    include_groups = album,single,appears_on
    pagination offset
    """
    key = (artist_id, "full")
    if key in _cache_albums:
        return _cache_albums[key]

    albums: list[dict] = []
    params = {"include_groups": "album,single,appears_on", "limit": 50, "offset": 0}

    while True:
        r = spotify_get(
            f"{SPOTIFY_API_BASE}/artists/{artist_id}/albums",
            token=token,
            params=params,
        )
        data = r.json()
        albums.extend(data.get("items", []))

        if data.get("next"):
            params["offset"] += 50
        else:
            break

    _cache_albums[key] = albums
    return albums


def _get_tracks(album_id: str, token: str) -> list[dict]:
    """
    EXACT notebook:
    pagination offset
    """
    tracks: list[dict] = []
    params = {"limit": 50, "offset": 0}

    while True:
        r = spotify_get(
            f"{SPOTIFY_API_BASE}/albums/{album_id}/tracks",
            token=token,
            params=params,
        )
        data = r.json()
        tracks.extend(data.get("items", []))

        if data.get("next"):
            params["offset"] += 50
        else:
            break

    return tracks


def get_total_tracks(artist_name: str, token: Optional[str] = None) -> int:
    """
    EXACT notebook behavior + patch 429:
      - mêmes endpoints
      - mêmes params
      - mêmes threads (max_workers=10)
      - même normalisation track_name = strip().lower()
      - cache par artist_name (comme notebook)
    """
    if artist_name in _cache_tracks:
        return _cache_tracks[artist_name]

    tok = token or get_spotify_token()
    if not tok:
        return 0

    artist_id = _get_artist_id(artist_name, tok)
    if not artist_id:
        return 0

    albums = _get_albums_and_appears_on(artist_id, tok)
    album_ids = [a["id"] for a in albums if a.get("id")]

    unique_names: set[str] = set()

    with ThreadPoolExecutor(max_workers=10) as exe:
        results = exe.map(lambda aid: _get_tracks(aid, tok), album_ids)

        for track_list in results:
            for t in track_list:
                if artist_id in [art["id"] for art in t.get("artists", [])]:
                    track_name = (t.get("name") or "").strip().lower()
                    if track_name:
                        unique_names.add(track_name)

    total_tracks = len(unique_names)
    _cache_tracks[artist_name] = total_tracks
    return total_tracks

# ✅ NEW: same logic but input is artist_id (no name search, no ambiguity)
def get_total_tracks_by_artist_id(artist_id: str, token: Optional[str] = None) -> int:
    """
    Même logique que get_total_tracks(), mais en entrée: artist_id Spotify.
    Zéro ambiguïté.
    """
    tok = token or get_spotify_token()
    if not tok:
        return 0

    aid = _norm_id(artist_id)
    if not aid:
        return 0

    # cache séparé (artist_id)
    cache_key = f"id:{aid}"
    if cache_key in _cache_tracks:
        return _cache_tracks[cache_key]

    albums = _get_albums_and_appears_on(aid, tok)
    album_ids = [a["id"] for a in albums if a.get("id")]

    unique_names: set[str] = set()

    with ThreadPoolExecutor(max_workers=10) as exe:
        results = exe.map(lambda alb_id: _get_tracks(alb_id, tok), album_ids)

        for track_list in results:
            for t in track_list:
                if aid in [art["id"] for art in t.get("artists", [])]:
                    track_name = (t.get("name") or "").strip().lower()
                    if track_name:
                        unique_names.add(track_name)

    total_tracks = len(unique_names)
    _cache_tracks[cache_key] = total_tracks
    return total_tracks

# ============================================================
# KPI ARTISTE (site)
# ============================================================
def get_artist_rank(df_artists: pd.DataFrame, artist_name: str) -> Optional[int]:
    if df_artists is None or df_artists.empty:
        return None
    if not {"artiste", "temps_écoute"}.issubset(df_artists.columns):
        return None

    df = df_artists.copy()
    df["artiste"] = df["artiste"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)

    grp = (
        df.groupby("artiste", as_index=False)["temps_écoute"]
        .sum()
        .sort_values("temps_écoute", ascending=False)
        .reset_index(drop=True)
    )
    if grp.empty:
        return None

    target = artist_name.strip()
    hit = grp.index[grp["artiste"] == target].tolist()
    return int(hit[0] + 1) if hit else None


def get_artist_genres(artist_name: str, token: Optional[str] = None, market: str = "FR") -> list[str]:
    tok = token or get_spotify_token()
    if not tok:
        return []
    a = search_artist(artist_name, token=tok, market=market)
    if not a:
        return []
    raw = a.get("raw") or {}
    return list(raw.get("genres") or [])


def get_artist_followers(artist_name: str, token: Optional[str] = None, market: str = "FR") -> int:
    tok = token or get_spotify_token()
    if not tok:
        return 0
    a = search_artist(artist_name, token=tok, market=market)
    if not a:
        return 0
    raw = a.get("raw") or {}
    return int((raw.get("followers") or {}).get("total") or 0)


def get_first_listen_date(df_tracks: pd.DataFrame, artist_name: str) -> Optional[pd.Timestamp]:
    if df_tracks is None or df_tracks.empty:
        return None
    if not {"artiste", "date_écoute"}.issubset(df_tracks.columns):
        return None

    df = df_tracks.copy()
    df["artiste"] = df["artiste"].astype(str).str.strip()
    df["date_écoute"] = pd.to_datetime(df["date_écoute"], errors="coerce")

    sub = df[df["artiste"] == artist_name.strip()]
    if sub.empty:
        return None

    d = sub["date_écoute"].min()
    return d if pd.notna(d) else None


def get_total_listen_minutes(df_tracks: pd.DataFrame, artist_name: str) -> int:
    if df_tracks is None or df_tracks.empty:
        return 0
    if not {"artiste", "temps_écoute"}.issubset(df_tracks.columns):
        return 0

    df = df_tracks.copy()
    df["artiste"] = df["artiste"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)

    sub = df[df["artiste"] == artist_name.strip()]
    if sub.empty:
        return 0

    total_seconds = float(sub["temps_écoute"].sum())
    return int(round(total_seconds / 60.0))


def get_most_listened_month(df_tracks: pd.DataFrame, artist_name: str) -> Optional[str]:
    if df_tracks is None or df_tracks.empty:
        return None
    if not {"artiste", "temps_écoute", "date_écoute"}.issubset(df_tracks.columns):
        return None

    df = df_tracks.copy()
    df["artiste"] = df["artiste"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)
    df["date_écoute"] = pd.to_datetime(df["date_écoute"], errors="coerce")

    sub = df[(df["artiste"] == artist_name.strip()) & df["date_écoute"].notna()]
    if sub.empty:
        return None

    sub = sub.copy()
    sub["ym"] = sub["date_écoute"].dt.to_period("M")
    grp = sub.groupby("ym")["temps_écoute"].sum().sort_values(ascending=False)
    if grp.empty:
        return None

    best = grp.index[0]
    year = int(best.year)
    month = int(best.month)
    mon = calendar.month_abbr[month]
    return f"{mon} {year}"


def get_discography_coverage(df_artists: pd.DataFrame, artist_name: str, token: Optional[str] = None) -> float:
    """
    EXACT logique que tu as donnée:
      titres_uniques_écoutés / titres_publiés_spotify
    df_artists doit contenir (artiste, titre)
    """
    if df_artists is None or df_artists.empty:
        return 0.0
    if not {"artiste", "titre"}.issubset(df_artists.columns):
        return 0.0

    artist_name = str(artist_name).strip()

    listened_titles = (
        df_artists[df_artists["artiste"].astype(str).str.strip() == artist_name]["titre"]
        .astype(str)
        .str.lower()
        .unique()
    )
    listened_count = len(listened_titles)

    tok = token or get_spotify_token()
    published_count = get_total_tracks(artist_name, token=tok)

    if published_count == 0:
        return 0.0

    return listened_count / published_count


def _format_followers_fr(n: int) -> str:
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}".replace(".", ",") + "m"
    if n >= 1_000:
        return f"{n/1_000:.1f}".replace(".", ",") + "k"
    return str(n)

def _format_coverage_pill(ratio: float | None) -> str:
    """
    Formate un ratio [0..1] en pourcentage affichable.
    - None -> "—"
    - clamp dans [0..1]
    - arrondi entier comme ton comportement actuel
    """
    if ratio is None:
        return "—"
    try:
        if ratio < 0:
            ratio = 0.0
        elif ratio > 1:
            ratio = 1.0
        pct = int(round(ratio * 100))
        return f"{pct}%"
    except Exception:
        return "—"

def get_artist_kpis(
    df_tracks: pd.DataFrame,
    df_artists: pd.DataFrame,
    artist_name: str,
    market: str = "FR",
) -> dict:
    """
    Bundle prêt pour Flask: types simples uniquement.
    Token récupéré UNE fois puis passé aux fonctions (pas de token global).

    Modif perf:
      - NE BLOQUE PAS sur get_total_tracks (lancé en background)
      - nb_sons_pill et coverage_pill peuvent être "…" / "—" à la première visite
    """
    import re  # local pour ne pas toucher au reste de tes imports

    artist_name = str(artist_name).strip()
    tok = get_spotify_token()

    rank = get_artist_rank(df_artists, artist_name)

    first_dt = get_first_listen_date(df_tracks, artist_name)
    discover_date = first_dt.strftime("%d/%m/%y") if first_dt is not None else "—"

    total_min = get_total_listen_minutes(df_tracks, artist_name)
    listen_minutes_pill = f"{total_min} min"

    most_month = get_most_listened_month(df_tracks, artist_name) or "—"

    genres = get_artist_genres(artist_name, token=tok, market=market) if tok else []
    genres_pill = ", ".join(genres[:2]) if genres else "—"

    followers = get_artist_followers(artist_name, token=tok, market=market) if tok else 0
    followers_pill = f"{_format_followers_fr(followers)} followers"

    # --- PERF FIX: total tracks en async (ne bloque pas) ---
    total_tracks_spotify: int | None = None
    if tok:
        # lance le calcul en arrière-plan (ne bloque jamais)
        try:
            ensure_total_tracks_job(artist_name, token=tok)
        except Exception:
            pass

        # récupère si déjà prêt
        try:
            total_tracks_spotify = get_total_tracks_cached_value(artist_name)
        except Exception:
            total_tracks_spotify = None

    # Affichage du nombre de sons (si pas prêt -> "—")
    if total_tracks_spotify is None:
        nb_sons_pill = "—"
    else:
        nb_sons_pill = f"{total_tracks_spotify} sons"

    # Coverage dépend de published_count -> si pas prêt, on n'essaie pas
    if total_tracks_spotify is None:
        coverage_pill = "—"
    else:
        try:
            if df_tracks is None or df_tracks.empty or not {"artiste", "titre"}.issubset(df_tracks.columns):
                coverage_ratio = 0.0
            else:
                pattern = rf"\b{re.escape(artist_name)}\b"
                mask = (
                    df_tracks["artiste"]
                    .astype(str)
                    .str.strip()
                    .str.contains(pattern, case=False, na=False, regex=True)
                )

                listened_titles = (
                    df_tracks.loc[mask, "titre"]
                    .astype(str)
                    .str.strip()
                    .str.lower()
                    .unique()
                )
                listened_count = len(listened_titles)
                published_count = total_tracks_spotify

                coverage_ratio = (listened_count / published_count) if published_count else 0.0

            coverage_pill = _format_coverage_pill(coverage_ratio)

        except SpotifyRateLimitError:
            coverage_pill = "—"
        except Exception:
            coverage_pill = "—"

    return {
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
# ✅ NEW: KPI ARTISTE BY ID (pour la migration "IDs only")
# ============================================================

def get_artist_genres_by_id(artist_id: str, token: Optional[str] = None, market: str = "FR") -> list[str]:
    tok = token or get_spotify_token()
    if not tok:
        return []
    a = get_artist_by_id(artist_id, token=tok)
    if not a:
        return []
    raw = a.get("raw") or {}
    return list(raw.get("genres") or [])


def get_artist_followers_by_id(artist_id: str, token: Optional[str] = None, market: str = "FR") -> int:
    tok = token or get_spotify_token()
    if not tok:
        return 0
    a = get_artist_by_id(artist_id, token=tok)
    if not a:
        return 0
    raw = a.get("raw") or {}
    return int((raw.get("followers") or {}).get("total") or 0)


def get_discography_coverage_by_id(df_tracks: pd.DataFrame, artist_id: str, artist_name: str, token: Optional[str] = None) -> float | None:
    """
    Coverage ID-first:
      listened_unique_titles (local) / published_total_tracks (Spotify) via artist_id.
    On utilise artist_name pour matcher l'historique (ton Excel n'a pas artist_id).
    """
    if not artist_id:
        return None

    tok = token or get_spotify_token()
    if not tok:
        return None

    published_count = get_total_tracks_by_artist_id(artist_id, token=tok)
    if not isinstance(published_count, int) or published_count <= 0:
        return None

    if df_tracks is None or df_tracks.empty or not {"artiste", "titre"}.issubset(df_tracks.columns):
        return 0.0

    # matching robuste sur le nom Spotify (tolère feats)
    import re
    pattern = rf"\b{re.escape(str(artist_name).strip())}\b"
    mask = (
        df_tracks["artiste"].astype(str).str.strip()
        .str.contains(pattern, case=False, na=False, regex=True)
    )

    listened_count = (
        df_tracks.loc[mask, "titre"].astype(str).str.strip().str.lower().nunique()
    )

    return (listened_count / published_count) if published_count else 0.0


def get_artist_kpis_by_id(
    df_tracks: pd.DataFrame,
    df_artists: pd.DataFrame,
    artist_id: str,
    market: str = "FR",
) -> dict:
    """
    Version IDs-only (pour la future route /artist/<artist_id>).
    - Spotify: genres/followers/name via artist_id
    - Historique: rank/discover/month/time via artist_name (car ton Excel n’a pas artist_id)
    - Total tracks: job async par artist_id (ne bloque pas)
    """
    tok = get_spotify_token()
    a = get_artist_by_id(artist_id, token=tok) if tok else None
    artist_name = (a.get("name") if a else "") or "—"

    rank = get_artist_rank(df_artists, artist_name)

    first_dt = get_first_listen_date(df_tracks, artist_name)
    discover_date = first_dt.strftime("%d/%m/%y") if first_dt is not None else "—"

    total_min = get_total_listen_minutes(df_tracks, artist_name)
    listen_minutes_pill = f"{total_min} min"

    most_month = get_most_listened_month(df_tracks, artist_name) or "—"

    genres = get_artist_genres_by_id(artist_id, token=tok, market=market) if tok else []
    genres_pill = ", ".join(genres[:2]) if genres else "—"

    followers = get_artist_followers_by_id(artist_id, token=tok, market=market) if tok else 0
    followers_pill = f"{_format_followers_fr(followers)} followers" if followers else "—"

    # total tracks en async par ID
    total_tracks_spotify: int | None = None
    if tok:
        try:
            ensure_total_tracks_job_id(artist_id, token=tok)
        except Exception:
            pass
        try:
            total_tracks_spotify = get_total_tracks_cached_value_id(artist_id)
        except Exception:
            total_tracks_spotify = None

    nb_sons_pill = f"{total_tracks_spotify} sons" if isinstance(total_tracks_spotify, int) else "—"

    coverage_pill = "—"
    if isinstance(total_tracks_spotify, int) and total_tracks_spotify > 0:
        try:
            ratio = get_discography_coverage_by_id(df_tracks, artist_id, artist_name, token=tok)
            coverage_pill = _format_coverage_pill(ratio)
        except Exception:
            coverage_pill = "—"

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


import pandas as pd

from dashboard.analytics.spotify import hours_to_hm, get_spotify_token

def get_top_10_titles_by_listen_time(
    df_tracks: pd.DataFrame,
    artist_name: str,
    top_n: int = 10,
    market: str = "FR",
    token: str | None = None,
) -> pd.DataFrame:
    if df_tracks is None or df_tracks.empty:
        return pd.DataFrame(columns=["classement", "cover", "titre", "isrc", "temps_écoute"])

    required = {"artiste", "titre", "temps_écoute"}
    if not required.issubset(df_tracks.columns):
        return pd.DataFrame(columns=["classement", "cover", "titre", "isrc", "temps_écoute"])

    artist_name = str(artist_name).strip()
    cache_key = (artist_name.lower(), int(top_n), str(market).upper())
    if cache_key in _cache_top_titles:
        return _cache_top_titles[cache_key].copy()

    tok = token or get_spotify_token()
    if not tok:
        return pd.DataFrame(columns=["classement", "cover", "titre", "isrc", "temps_écoute"])

    import re
    pattern = r'(?i)(^|,\s*)' + re.escape(artist_name.strip()) + r'(\s*,|$)'
    df_artist = df_tracks[
        df_tracks["artiste"].astype(str).str.contains(pattern, regex=True, na=False)
        & (pd.to_numeric(df_tracks["temps_écoute"], errors="coerce").fillna(0) > 0)
    ].copy()

    if df_artist.empty:
        return pd.DataFrame(columns=["classement", "cover", "titre", "isrc", "temps_écoute"])

    top = (
        df_artist.groupby("titre", as_index=False)["temps_écoute"]
        .sum()
        .sort_values("temps_écoute", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
    
    top["classement"] = top.index + 1

    # ✅ ISRC dominant par titre (évite collisions)
    if "ISRC" in df_artist.columns:
        df_artist["ISRC"] = df_artist["ISRC"].fillna("").astype(str).str.strip()

        isrc_score = (
            df_artist.groupby(["titre", "ISRC"], as_index=False)["temps_écoute"]
            .sum()
        )
        idx = isrc_score.groupby("titre")["temps_écoute"].idxmax()
        best_isrc = isrc_score.loc[idx, ["titre", "ISRC"]].rename(columns={"ISRC": "isrc"})

        top = top.merge(best_isrc, on="titre", how="left")
    else:
        top["isrc"] = ""

    # seconds -> hours -> "XhYY"
    top["temps_écoute"] = (top["temps_écoute"] / 3600).apply(hours_to_hm)

    titles = top["titre"].astype(str).tolist()

    def _cover_for_title(title: str) -> str | None:
        t = search_track(title.strip(), artist_name, token=tok, market=market)
        return (t or {}).get("image_url")

    with ThreadPoolExecutor(max_workers=5) as ex:
        covers = list(ex.map(_cover_for_title, titles))

    top["cover"] = covers
    # Ajouter l'album dominant par titre
    if "album" in df_artist.columns:
        best_album = (
            df_artist.groupby(["titre", "album"], as_index=False)["temps_écoute"]
            .sum()
        )
        idx = best_album.groupby("titre")["temps_écoute"].idxmax()
        best_album = best_album.loc[idx, ["titre", "album"]]
        top = top.merge(best_album, on="titre", how="left")
    else:
        top["album"] = ""

    out = top[["classement", "cover", "titre", "album", "isrc", "temps_écoute"]]

    _cache_top_titles[cache_key] = out.copy()
    return out


def get_top_10_albums_by_listen_time(
    df_tracks: pd.DataFrame,
    artist_name: str,
    top_n: int = 10,
    market: str = "FR",
    token: str | None = None,
) -> pd.DataFrame:
    # ✅ maintenant on renvoie aussi album_id
    cols = ["classement", "cover", "album", "album_id", "temps_écoute"]

    if df_tracks is None or df_tracks.empty:
        return pd.DataFrame(columns=cols)

    required = {"artiste", "album", "temps_écoute"}
    if not required.issubset(df_tracks.columns):
        return pd.DataFrame(columns=cols)

    artist_name = str(artist_name).strip()
    cache_key = (artist_name.lower(), int(top_n), str(market).upper())
    if cache_key in _cache_top_albums:
        return _cache_top_albums[cache_key].copy()

    tok = token or get_spotify_token()
    if not tok:
        return pd.DataFrame(columns=cols)

    import re
    pattern = r'(?i)(^|,\s*)' + re.escape(artist_name.strip()) + r'(\s*,|$)'
    df_artist = df_tracks[
        df_tracks["artiste"].astype(str).str.contains(pattern, regex=True, na=False)
        & (pd.to_numeric(df_tracks["temps_écoute"], errors="coerce").fillna(0) > 0)
    ].copy()

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

    albums = top["album"].astype(str).tolist()

    # ✅ récup cover + album_id via search_album
    def _meta_for_album(album_name: str) -> tuple[str | None, str | None]:
        a = search_album(album_name.strip(), artist_name, token=tok, market=market)
        if not a:
            return None, None
        return a.get("id"), a.get("image_url")

    with ThreadPoolExecutor(max_workers=5) as ex:
        metas = list(ex.map(_meta_for_album, albums))

    top["album_id"] = [m[0] for m in metas]
    top["cover"] = [m[1] for m in metas]

    out = top[cols]
    _cache_top_albums[cache_key] = out.copy()
    return out
