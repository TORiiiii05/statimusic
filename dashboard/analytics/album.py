# analytics/album.py
from __future__ import annotations

import calendar
from typing import Optional, Tuple

import pandas as pd
import requests

from dashboard.analytics.spotify import get_spotify_token, search_album
from concurrent.futures import ThreadPoolExecutor
from dashboard.analytics.spotify import search_track
from dashboard.analytics.spotify import hours_to_hm
from dashboard.analytics.track import plot_listening_time_by_month_interactive
import plotly.graph_objects as go

# ✅ NEW (ID-first)
from dashboard.analytics.spotify import get_album_by_id


SPOTIFY_API_BASE = "https://api.spotify.com/v1"


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _spotify_get(url: str, token: str, params: Optional[dict] = None) -> Optional[dict]:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=20)
    if r.status_code != 200:
        return None
    return r.json()


def _ms_to_hhmm(ms: int) -> str:
    sec = int(round(ms / 1000))
    h = sec // 3600
    m = (sec % 3600) // 60
    if h > 0:
        return f"{h}h{m:02d}"
    return f"{m} min"


def _pick_main_artist_for_album(df_tracks: pd.DataFrame, album_name: str) -> Optional[str]:
    """
    Si un album apparaît avec plusieurs artistes (compils, remaster, etc.),
    on prend l'artiste le plus fréquent dans l'historique.
    """
    if df_tracks is None or df_tracks.empty or not {"album", "artiste"}.issubset(df_tracks.columns):
        return None

    akey = _norm(album_name)
    sub = df_tracks.copy()
    sub["album"] = sub["album"].astype(str)
    sub["artiste"] = sub["artiste"].astype(str)

    mask = sub["album"].map(_norm) == akey
    sub = sub.loc[mask]
    if sub.empty:
        return None

    counts = sub["artiste"].fillna("").astype(str).str.strip()
    counts = counts[counts != ""].value_counts()
    return str(counts.index[0]) if len(counts) else None


def get_album_rank(df_tracks: pd.DataFrame, album_name: str, artist_name: Optional[str] = None) -> Optional[int]:
    """
    Rang de l'album par temps d'écoute total.
    - Si artist_name fourni => classement sur (album, artiste)
    - Sinon => classement sur album (tous artistes confondus)
    """
    if df_tracks is None or df_tracks.empty:
        return None
    if not {"album", "temps_écoute"}.issubset(df_tracks.columns):
        return None

    df = df_tracks.copy()
    df["album"] = df["album"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)

    if artist_name and "artiste" in df.columns:
        df["artiste"] = df["artiste"].astype(str).str.strip()
        grp = (
            df.groupby(["album", "artiste"], as_index=False)["temps_écoute"]
              .sum()
              .sort_values("temps_écoute", ascending=False)
              .reset_index(drop=True)
        )
        target = (grp["album"].str.lower() == album_name.strip().lower()) & (grp["artiste"] == artist_name.strip())
    else:
        grp = (
            df.groupby("album", as_index=False)["temps_écoute"]
              .sum()
              .sort_values("temps_écoute", ascending=False)
              .reset_index(drop=True)
        )
        target = grp["album"].str.lower() == album_name.strip().lower()

    hit = grp.index[target].tolist()
    return int(hit[0] + 1) if hit else None


def get_album_listen_minutes(df_tracks: pd.DataFrame, album_name: str, artist_name: Optional[str] = None) -> int:
    if df_tracks is None or df_tracks.empty:
        return 0
    if not {"album", "temps_écoute"}.issubset(df_tracks.columns):
        return 0

    df = df_tracks.copy()
    df["album"] = df["album"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)

    mask = df["album"].str.lower() == album_name.strip().lower()
    if artist_name and "artiste" in df.columns:
        df["artiste"] = df["artiste"].astype(str).str.strip()
        mask = mask & (df["artiste"] == artist_name.strip())

    sub = df.loc[mask]
    if sub.empty:
        return 0

    total_seconds = float(sub["temps_écoute"].sum())
    return int(round(total_seconds / 60.0))


def get_album_listen_count(df_tracks: pd.DataFrame, album_name: str, artist_name: Optional[str] = None) -> int:
    if df_tracks is None or df_tracks.empty or "album" not in df_tracks.columns:
        return 0

    df = df_tracks.copy()
    df["album"] = df["album"].astype(str).str.strip()

    mask = df["album"].str.lower() == album_name.strip().lower()
    if artist_name and "artiste" in df.columns:
        df["artiste"] = df["artiste"].astype(str).str.strip()
        mask = mask & (df["artiste"] == artist_name.strip())

    return int(mask.sum())


def get_album_first_listen_date(df_tracks: pd.DataFrame, album_name: str, artist_name: Optional[str] = None) -> Optional[pd.Timestamp]:
    if df_tracks is None or df_tracks.empty:
        return None
    if not {"album", "date_écoute"}.issubset(df_tracks.columns):
        return None

    df = df_tracks.copy()
    df["album"] = df["album"].astype(str).str.strip()
    df["date_écoute"] = pd.to_datetime(df["date_écoute"], errors="coerce")

    mask = df["album"].str.lower() == album_name.strip().lower()
    if artist_name and "artiste" in df.columns:
        df["artiste"] = df["artiste"].astype(str).str.strip()
        mask = mask & (df["artiste"] == artist_name.strip())

    sub = df.loc[mask & df["date_écoute"].notna()]
    if sub.empty:
        return None

    d = sub["date_écoute"].min()
    return d if pd.notna(d) else None


def get_album_most_listened_month(df_tracks: pd.DataFrame, album_name: str, artist_name: Optional[str] = None) -> Optional[str]:
    if df_tracks is None or df_tracks.empty:
        return None
    if not {"album", "temps_écoute", "date_écoute"}.issubset(df_tracks.columns):
        return None

    df = df_tracks.copy()
    df["album"] = df["album"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)
    df["date_écoute"] = pd.to_datetime(df["date_écoute"], errors="coerce")

    mask = df["album"].str.lower() == album_name.strip().lower()
    if artist_name and "artiste" in df.columns:
        df["artiste"] = df["artiste"].astype(str).str.strip()
        mask = mask & (df["artiste"] == artist_name.strip())

    sub = df.loc[mask & df["date_écoute"].notna() & (df["temps_écoute"] > 0)].copy()
    if sub.empty:
        return None

    sub["ym"] = sub["date_écoute"].dt.to_period("M")
    grp = sub.groupby("ym")["temps_écoute"].sum().sort_values(ascending=False)
    if grp.empty:
        return None

    best = grp.index[0]
    year = int(best.year)
    month = int(best.month)
    mon = calendar.month_abbr[month]
    return f"{mon} {year}"


def get_album_spotify_meta(album_name: str, artist_name: Optional[str], market: str = "FR") -> dict:
    """
    Spotify meta:
      - release_date
      - nb_tracks
      - album_duration_pill (durée totale de l'album, pas ton temps d'écoute)
    """
    tok = get_spotify_token()
    if not tok or not album_name or not artist_name:
        return {"release_date": "—", "nb_tracks_pill": "—", "album_duration_pill": "—"}

    al = search_album(album_name, artist_name, token=tok, market=market)
    if not al:
        return {"release_date": "—", "nb_tracks_pill": "—", "album_duration_pill": "—"}

    raw = al.get("raw") or {}
    release_date = raw.get("release_date") or "—"
    nb_tracks = int(raw.get("total_tracks") or 0)
    nb_tracks_pill = f"{nb_tracks} titres" if nb_tracks else "—"

    album_id = raw.get("id")
    total_ms = 0
    if album_id:
        url = f"{SPOTIFY_API_BASE}/albums/{album_id}/tracks"
        params = {"limit": 50, "offset": 0, "market": market}
        while True:
            data = _spotify_get(url, tok, params=params)
            if not data:
                break
            items = data.get("items", []) or []
            for t in items:
                ms = t.get("duration_ms")
                if isinstance(ms, int):
                    total_ms += ms
            if data.get("next"):
                params["offset"] += 50
            else:
                break

    album_duration_pill = _ms_to_hhmm(total_ms) if total_ms > 0 else "—"
    return {"release_date": release_date, "nb_tracks_pill": nb_tracks_pill, "album_duration_pill": album_duration_pill}


def get_album_kpis(df_tracks: pd.DataFrame, album_name: str, market: str = "FR") -> Tuple[dict, Optional[str]]:
    """
    Bundle KPI prêt pour template.
    Retourne (kpis, main_artist_name)
    """
    album_name = str(album_name).strip()
    main_artist = _pick_main_artist_for_album(df_tracks, album_name)

    rank = get_album_rank(df_tracks, album_name, artist_name=main_artist)
    listen_minutes = get_album_listen_minutes(df_tracks, album_name, artist_name=main_artist)
    nb_listens = get_album_listen_count(df_tracks, album_name, artist_name=main_artist)

    first_dt = get_album_first_listen_date(df_tracks, album_name, artist_name=main_artist)
    discover_date = first_dt.strftime("%d/%m/%y") if first_dt is not None else "—"

    most_month = get_album_most_listened_month(df_tracks, album_name, artist_name=main_artist) or "—"

    sp = get_album_spotify_meta(album_name, main_artist, market=market)

    return (
        {
            "album_name": album_name,
            "artist_name": main_artist or "—",
            "rank": rank,
            "album_duration_pill": sp.get("album_duration_pill", "—"),
            "release_date": sp.get("release_date", "—"),
            "nb_tracks_pill": sp.get("nb_tracks_pill", "—"),
            "discover_date": discover_date,
            "most_listened_month": most_month,
            "listen_minutes_pill": f"{listen_minutes} min",
            "nb_listens_pill": str(nb_listens),
        },
        main_artist,
    )

def get_album_top_titles_by_listen_time(
    df_tracks: pd.DataFrame,
    album_name: str,
    artist_name: Optional[str] = None,
    top_n: int = 10,
    market: str = "FR",
    token: str | None = None,
) -> pd.DataFrame:
    """
    Top titres (tracks) d'un ALBUM, classés par temps d'écoute.
    Retour: classement | cover | titre | isrc | temps_écoute (XhYY)
    """
    cols = ["classement", "cover", "titre", "isrc", "temps_écoute"]

    if df_tracks is None or df_tracks.empty:
        return pd.DataFrame(columns=cols)

    required = {"album", "titre", "temps_écoute"}
    if not required.issubset(df_tracks.columns):
        return pd.DataFrame(columns=cols)

    album_name = str(album_name).strip()

    tok = token or get_spotify_token()
    if not tok:
        return pd.DataFrame(columns=cols)

    df = df_tracks.copy()
    df["album"] = df["album"].astype(str).str.strip()
    df["titre"] = df["titre"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)

    mask = (df["album"].str.lower() == album_name.lower()) & (df["temps_écoute"] > 0)

    if artist_name and "artiste" in df.columns:
        df["artiste"] = df["artiste"].astype(str).str.strip()
        mask = mask & df["artiste"].str.contains(str(artist_name).strip(), na=False)

    df_album = df.loc[mask].copy()
    if df_album.empty:
        return pd.DataFrame(columns=cols)

    top = (
        df_album.groupby("titre", as_index=False)["temps_écoute"]
                .sum()
                .sort_values("temps_écoute", ascending=False)
                .head(top_n)
                .reset_index(drop=True)
    )

    top["classement"] = top.index + 1
    top["temps_écoute"] = (top["temps_écoute"] / 3600).apply(hours_to_hm)

    if "ISRC" in df_album.columns:
        df_album["ISRC"] = df_album["ISRC"].fillna("").astype(str).str.strip()

        isrc_score = (
            df_album.groupby(["titre", "ISRC"], as_index=False)["temps_écoute"]
                    .sum()
        )
        idx = isrc_score.groupby("titre")["temps_écoute"].idxmax()
        best_isrc = isrc_score.loc[idx, ["titre", "ISRC"]].rename(columns={"ISRC": "isrc"})

        top = top.merge(best_isrc, on="titre", how="left")
    else:
        top["isrc"] = ""

    titles = top["titre"].astype(str).tolist()
    artist_for_cover = str(artist_name).strip() if artist_name else ""

    def _cover_for_title(title: str) -> str | None:
        t = search_track(title.strip(), artist_for_cover, token=tok, market=market) if artist_for_cover else None
        if not t:
            t = search_track(title.strip(), "", token=tok, market=market)
        return (t or {}).get("image_url")

    with ThreadPoolExecutor(max_workers=5) as ex:
        covers = list(ex.map(_cover_for_title, titles))

    top["cover"] = covers
    return top[cols]


def album_monthly_listening_chart_html(
    df_tracks: pd.DataFrame,
    album_name: str,
    artist_name: str | None = None,
    date_col: str = "date_écoute",
    duration_col: str = "temps_écoute",
    duration_unit: str = "seconds",
    height: int = 460,
    market: str = "FR",
) -> str:
    """
    Graph 'temps d'écoute par mois' pour un ALBUM (name-based).
    """
    import uuid

    if df_tracks is None or df_tracks.empty:
        fig = go.Figure()
        fig.update_layout(title="Aucune donnée", height=height)
        return fig.to_html(full_html=False, include_plotlyjs=False, div_id=f"chart_{uuid.uuid4().hex}")

    df = df_tracks.copy()
    if "album" not in df.columns:
        fig = go.Figure()
        fig.update_layout(title="Colonne album manquante", height=height)
        return fig.to_html(full_html=False, include_plotlyjs=False, div_id=f"chart_{uuid.uuid4().hex}")

    df["album"] = df["album"].astype(str).str.strip()
    mask = df["album"].str.lower() == str(album_name).strip().lower()

    if artist_name and "artiste" in df.columns:
        df["artiste"] = df["artiste"].astype(str).str.strip()
        mask = mask & df["artiste"].str.contains(str(artist_name).strip(), na=False)

    df_album = df.loc[mask].copy()

    if df_album.empty:
        fig = go.Figure()
        fig.update_layout(title=f"Aucune écoute pour {album_name}", height=height)
        return fig.to_html(full_html=False, include_plotlyjs=False, div_id=f"chart_{uuid.uuid4().hex}")

    fig, _, _ = plot_listening_time_by_month_interactive(
        df_album,
        date_col=date_col,
        duration_col=duration_col,
        duration_unit=duration_unit,
        title=f"Répartition du temps d'écoute par mois – {album_name}",
        height=height,
    )

    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,
        config={"displayModeBar": False, "responsive": True},
        div_id=f"chart_{uuid.uuid4().hex}",
    )


def recommend_albums_colisten_windows(
    df_tracks: pd.DataFrame,
    album_name: str,
    artist_name: str | None = None,
    date_col: str = "date_écoute",
    album_col: str = "album",
    artist_col: str = "artiste",
    duration_col: str = "temps_écoute",
    duration_unit: str = "seconds",
    freq: str = "D",
    score_mode: str = "windows",
    top_n: int = 12,
    min_shared_windows: int = 2,
) -> pd.DataFrame:
    """
    Reco d'albums proches de `album_name` via co-écoute (name-based).
    """
    if df_tracks is None or df_tracks.empty:
        return pd.DataFrame(columns=["album", "artist", "score", "shared_windows", "reason"])

    df = df_tracks.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col, album_col])

    df[album_col] = df[album_col].astype(str).str.strip()
    if artist_col in df.columns:
        df[artist_col] = df[artist_col].astype(str).str.strip()

    df = df[(pd.to_numeric(df[duration_col], errors="coerce").fillna(0) > 0) & (df[album_col] != "")]
    if df.empty:
        return pd.DataFrame(columns=["album", "artist", "score", "shared_windows", "reason"])

    if artist_name and artist_col in df.columns:
        df = df[df[artist_col].str.contains(str(artist_name).strip(), na=False) | (df[album_col] != album_name)]

    if album_name not in set(df[album_col].unique()):
        return pd.DataFrame(columns=["album", "artist", "score", "shared_windows", "reason"])

    f = freq.upper()
    if f == "M":
        df["_window"] = df[date_col].dt.to_period("M").dt.to_timestamp()
        window_label = "mois"
    elif f == "W":
        df["_window"] = df[date_col].dt.to_period("W").apply(lambda p: p.start_time)
        window_label = "semaines"
    elif f == "D":
        df["_window"] = df[date_col].dt.floor("D")
        window_label = "jours"
    else:
        raise ValueError("freq doit être 'D', 'W' ou 'M'.")

    windows_target = set(df.loc[df[album_col] == album_name, "_window"].unique())
    if not windows_target:
        return pd.DataFrame(columns=["album", "artist", "score", "shared_windows", "reason"])

    df_in = df[df["_window"].isin(windows_target)].copy()

    shared = (
        df_in.groupby(album_col)["_window"]
             .nunique()
             .rename("shared_windows")
             .reset_index()
    )
    shared = shared[shared[album_col] != album_name].copy()
    shared = shared[shared["shared_windows"] >= int(min_shared_windows)].copy()

    if shared.empty:
        return pd.DataFrame(columns=["album", "artist", "score", "shared_windows", "reason"])

    score_mode = score_mode.lower()
    if score_mode == "windows":
        shared["score"] = shared["shared_windows"].astype(float)

    elif score_mode == "time":
        dur = pd.to_numeric(df_in[duration_col], errors="coerce").fillna(0)
        u = duration_unit.lower()
        if u in ["minutes", "minute", "min", "m"]:
            dur = dur * 60
        elif u in ["seconds", "second", "sec", "s", "seconde", "secondes"]:
            pass
        else:
            raise ValueError("duration_unit doit être 'seconds' ou 'minutes'.")

        df_in["_sec"] = dur
        time_score = (
            df_in.groupby(album_col)["_sec"]
                 .sum()
                 .rename("score")
                 .reset_index()
        )
        shared = shared.merge(time_score, on=album_col, how="inner")
        shared["score"] = shared["score"] / 3600.0

    else:
        raise ValueError("score_mode doit être 'windows' ou 'time'.")

    def _main_artist_for_album(alb: str) -> str:
        dfa = df_in[df_in[album_col] == alb]
        if dfa.empty or artist_col not in dfa.columns:
            return ""
        g = dfa.groupby(artist_col)[duration_col].sum().sort_values(ascending=False)
        return str(g.index[0]) if len(g) else ""

    shared["artist"] = shared[album_col].apply(_main_artist_for_album)

    shared = shared.rename(columns={album_col: "album"})
    shared["reason"] = shared.apply(
        lambda r: f"Co-écouté les mêmes {window_label} ({int(r['shared_windows'])} {window_label} partagés).",
        axis=1
    )

    shared = shared.sort_values(["score", "shared_windows"], ascending=False)
    return shared[["album", "artist", "score", "shared_windows", "reason"]].head(int(top_n)).reset_index(drop=True)


def format_album_reco_for_web(
    reco_df: pd.DataFrame,
    market: str = "FR",
    top_n: int = 6,
) -> pd.DataFrame:
    cols = ["album", "artist", "score", "cover_url"]

    if reco_df is None or reco_df.empty:
        return pd.DataFrame(columns=cols)

    tok = get_spotify_token()
    if not tok:
        out = reco_df.head(top_n).copy()
        out["cover_url"] = None
        return out[["album", "artist", "score", "cover_url"]]

    df = reco_df.head(top_n).copy()
    df["album"] = df["album"].astype(str)
    df["artist"] = df["artist"].astype(str)

    def _cover(album: str, artist: str) -> str | None:
        a = search_album(album, artist, token=tok, market=market)
        return (a or {}).get("image_url")

    with ThreadPoolExecutor(max_workers=5) as ex:
        covers = list(ex.map(lambda r: _cover(r[0], r[1]), zip(df["album"], df["artist"])))

    df["cover_url"] = covers
    return df[["album", "artist", "score", "cover_url"]]


# ============================================================
# ✅ NEW: ALBUM BY ID (pour route /album/<album_id>)
# ============================================================

def get_album_kpis_by_id(df_tracks: pd.DataFrame, album_id: str, market: str = "FR") -> Tuple[dict, dict]:
    """
    Version ID-first:
    - album_id Spotify = clé
    - album_name / artist_name viennent de Spotify
    - historique local filtré sur album_name + (optionnel) artist_name
    Retour:
      (kpis, album_meta)
    album_meta: {album_id, album_name, artist_name}
    """
    tok = get_spotify_token()
    al = get_album_by_id(album_id, token=tok, market=market) if tok else None
    raw = (al or {}).get("raw") or {}

    album_name = (raw.get("name") or "—").strip()
    artists = raw.get("artists") or []
    artist_name = (artists[0].get("name") if artists else "—") or "—"

    # réutilise ta logique existante (name-based) pour les stats historique
    kpis, _main_artist = get_album_kpis(df_tracks, album_name, market=market)
    # écrase artist_name par Spotify (plus fiable)
    kpis["album_id"] = album_id
    kpis["album_name"] = album_name
    kpis["artist_name"] = artist_name

    return kpis, {"album_id": album_id, "album_name": album_name, "artist_name": artist_name}


def get_album_top_titles_by_listen_time_by_id(
    df_tracks: pd.DataFrame,
    album_id: str,
    top_n: int = 10,
    market: str = "FR",
    token: str | None = None,
) -> pd.DataFrame:
    """
    Top titres d'un album ID-first.
    On récupère album_name + artist_name depuis Spotify album_id,
    puis on réutilise ta fonction existante (name-based) qui renvoie déjà isrc.
    """
    tok = token or get_spotify_token()
    al = get_album_by_id(album_id, token=tok, market=market) if tok else None
    raw = (al or {}).get("raw") or {}

    album_name = (raw.get("name") or "").strip()
    artists = raw.get("artists") or []
    artist_name = (artists[0].get("name") if artists else "") or ""

    return get_album_top_titles_by_listen_time(
        df_tracks,
        album_name=album_name,
        artist_name=artist_name,
        top_n=top_n,
        market=market,
        token=tok,
    )


def album_monthly_listening_chart_html_by_id(
    df_tracks: pd.DataFrame,
    album_id: str,
    date_col: str = "date_écoute",
    duration_col: str = "temps_écoute",
    duration_unit: str = "seconds",
    height: int = 460,
    market: str = "FR",
) -> str:
    """
    Graph album ID-first:
    - resolve album_name+artist_name via Spotify album_id
    - utilise ta fonction name-based existante
    """
    tok = get_spotify_token()
    al = get_album_by_id(album_id, token=tok, market=market) if tok else None
    raw = (al or {}).get("raw") or {}

    album_name = (raw.get("name") or "").strip()
    artists = raw.get("artists") or []
    artist_name = (artists[0].get("name") if artists else "") or ""

    return album_monthly_listening_chart_html(
        df_tracks,
        album_name=album_name,
        artist_name=artist_name,
        date_col=date_col,
        duration_col=duration_col,
        duration_unit=duration_unit,
        height=height,
        market=market,
    )


def format_album_reco_for_web_by_id(
    reco_df: pd.DataFrame,
    market: str = "FR",
    top_n: int = 6,
) -> pd.DataFrame:
    """
    Même sortie que format_album_reco_for_web, mais ajoute album_id si possible.
    On garde tout ton comportement, on enrichit juste.
    """
    if reco_df is None or reco_df.empty:
        return pd.DataFrame(columns=["album", "artist", "album_id", "score", "cover_url"])

    df = format_album_reco_for_web(reco_df, market=market, top_n=top_n).copy()

    # essaie de récupérer album_id via search_album (name-based), sans casser si fail
    tok = get_spotify_token()
    if not tok or df.empty:
        df["album_id"] = ""
        return df[["album", "artist", "album_id", "score", "cover_url"]]

    def _album_id(album: str, artist: str) -> str | None:
        a = search_album(album, artist, token=tok, market=market)
        return (a or {}).get("id")

    with ThreadPoolExecutor(max_workers=5) as ex:
        ids = list(ex.map(lambda r: _album_id(r[0], r[1]), zip(df["album"], df["artist"])))

    df["album_id"] = [i or "" for i in ids]
    return df[["album", "artist", "album_id", "score", "cover_url"]]
