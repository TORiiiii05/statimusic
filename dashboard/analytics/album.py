# analytics/album.py
from __future__ import annotations

import calendar
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Tuple

import pandas as pd
import requests
import plotly.graph_objects as go

from dashboard.analytics.spotify import (
    get_spotify_token,
    search_album,
    search_track,
    get_album_by_id,
    hours_to_hm,
)
from dashboard.analytics.track import plot_listening_time_by_month_interactive

SPOTIFY_API_BASE = "https://api.spotify.com/v1"


def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _spotify_get(url: str, token: str, params: dict | None = None) -> dict | None:
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params, timeout=20)
    return r.json() if r.status_code == 200 else None


def _ms_to_hhmm(ms: int) -> str:
    sec = int(round(ms / 1000))
    h, m = sec // 3600, (sec % 3600) // 60
    return f"{h}h{m:02d}" if h > 0 else f"{m} min"


def _pick_main_artist_for_album(df_tracks: pd.DataFrame, album_name: str) -> Optional[str]:
    if df_tracks is None or df_tracks.empty or not {"album", "artiste"}.issubset(df_tracks.columns):
        return None
    akey = _norm(album_name)
    mask = df_tracks["album"].astype(str).map(_norm) == akey
    sub = df_tracks.loc[mask, "artiste"]
    if sub.empty:
        return None
    counts = sub.fillna("").astype(str).str.strip()
    counts = counts[counts != ""].value_counts()
    return str(counts.index[0]) if len(counts) else None


def get_album_rank(df_tracks: pd.DataFrame, album_name: str, artist_name: Optional[str] = None) -> Optional[int]:
    if df_tracks is None or df_tracks.empty or "album" not in df_tracks.columns:
        return None
    temps = pd.to_numeric(df_tracks["temps_écoute"], errors="coerce").fillna(0)
    album_col = df_tracks["album"].astype(str).str.strip()
    if artist_name and "artiste" in df_tracks.columns:
        grp = (
            pd.DataFrame({"album": album_col, "artiste": df_tracks["artiste"].astype(str).str.strip(), "t": temps})
            .groupby(["album", "artiste"], as_index=False)["t"].sum()
            .sort_values("t", ascending=False).reset_index(drop=True)
        )
        target = (grp["album"].str.lower() == album_name.strip().lower()) & (grp["artiste"] == artist_name.strip())
    else:
        grp = (
            pd.DataFrame({"album": album_col, "t": temps})
            .groupby("album", as_index=False)["t"].sum()
            .sort_values("t", ascending=False).reset_index(drop=True)
        )
        target = grp["album"].str.lower() == album_name.strip().lower()
    hit = grp.index[target].tolist()
    return int(hit[0] + 1) if hit else None


def get_album_listen_minutes(df_tracks: pd.DataFrame, album_name: str, artist_name: Optional[str] = None) -> int:
    if df_tracks is None or df_tracks.empty or "album" not in df_tracks.columns:
        return 0
    mask = df_tracks["album"].astype(str).str.strip().str.lower() == album_name.strip().lower()
    if artist_name and "artiste" in df_tracks.columns:
        mask = mask & (df_tracks["artiste"].astype(str).str.strip() == artist_name.strip())
    total = pd.to_numeric(df_tracks.loc[mask, "temps_écoute"], errors="coerce").fillna(0).sum()
    return int(round(float(total) / 60.0))


def get_album_listen_count(df_tracks: pd.DataFrame, album_name: str, artist_name: Optional[str] = None) -> int:
    if df_tracks is None or df_tracks.empty or "album" not in df_tracks.columns:
        return 0
    mask = df_tracks["album"].astype(str).str.strip().str.lower() == album_name.strip().lower()
    if artist_name and "artiste" in df_tracks.columns:
        mask = mask & (df_tracks["artiste"].astype(str).str.strip() == artist_name.strip())
    return int(mask.sum())


def get_album_first_listen_date(df_tracks: pd.DataFrame, album_name: str, artist_name: Optional[str] = None) -> Optional[pd.Timestamp]:
    if df_tracks is None or df_tracks.empty or not {"album", "date_écoute"}.issubset(df_tracks.columns):
        return None
    mask = df_tracks["album"].astype(str).str.strip().str.lower() == album_name.strip().lower()
    if artist_name and "artiste" in df_tracks.columns:
        mask = mask & (df_tracks["artiste"].astype(str).str.strip() == artist_name.strip())
    dates = pd.to_datetime(df_tracks.loc[mask, "date_écoute"], errors="coerce")
    d = dates.min()
    return d if pd.notna(d) else None


def get_album_most_listened_month(df_tracks: pd.DataFrame, album_name: str, artist_name: Optional[str] = None) -> Optional[str]:
    if df_tracks is None or df_tracks.empty or not {"album", "temps_écoute", "date_écoute"}.issubset(df_tracks.columns):
        return None
    mask = df_tracks["album"].astype(str).str.strip().str.lower() == album_name.strip().lower()
    if artist_name and "artiste" in df_tracks.columns:
        mask = mask & (df_tracks["artiste"].astype(str).str.strip() == artist_name.strip())
    sub = df_tracks.loc[mask].copy()
    sub["date_écoute"] = pd.to_datetime(sub["date_écoute"], errors="coerce")
    sub["temps_écoute"] = pd.to_numeric(sub["temps_écoute"], errors="coerce").fillna(0)
    sub = sub[sub["date_écoute"].notna() & (sub["temps_écoute"] > 0)]
    if sub.empty:
        return None
    sub["ym"] = sub["date_écoute"].dt.to_period("M")
    grp = sub.groupby("ym")["temps_écoute"].sum().sort_values(ascending=False)
    if grp.empty:
        return None
    best = grp.index[0]
    return f"{calendar.month_abbr[int(best.month)]} {int(best.year)}"


def get_album_spotify_meta(album_name: str, artist_name: Optional[str], market: str = "FR") -> dict:
    empty = {"release_date": "—", "nb_tracks_pill": "—", "album_duration_pill": "—"}
    tok = get_spotify_token()
    if not tok or not album_name or not artist_name:
        return empty
    al = search_album(album_name, artist_name, token=tok, market=market)
    if not al:
        return empty
    raw = al.get("raw") or {}
    release_date = raw.get("release_date") or "—"
    nb_tracks = int(raw.get("total_tracks") or 0)
    nb_tracks_pill = f"{nb_tracks} titres" if nb_tracks else "—"
    album_id = raw.get("id")
    total_ms = 0
    if album_id:
        params = {"limit": 50, "offset": 0, "market": market}
        while True:
            data = _spotify_get(f"{SPOTIFY_API_BASE}/albums/{album_id}/tracks", tok, params=params)
            if not data:
                break
            for t in data.get("items", []) or []:
                ms = t.get("duration_ms")
                if isinstance(ms, int):
                    total_ms += ms
            if not data.get("next"):
                break
            params["offset"] += 50
    album_duration_pill = _ms_to_hhmm(total_ms) if total_ms > 0 else "—"
    return {"release_date": release_date, "nb_tracks_pill": nb_tracks_pill, "album_duration_pill": album_duration_pill}


def get_album_kpis(df_tracks: pd.DataFrame, album_name: str, market: str = "FR") -> Tuple[dict, Optional[str]]:
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


def get_album_kpis_by_id(df_tracks: pd.DataFrame, album_id: str, market: str = "FR") -> Tuple[dict, dict]:
    tok = get_spotify_token()
    al = get_album_by_id(album_id, token=tok, market=market) if tok else None
    raw = (al or {}).get("raw") or {}
    album_name = (raw.get("name") or "—").strip()
    artists = raw.get("artists") or []
    artist_name = (artists[0].get("name") if artists else "—") or "—"
    kpis, _ = get_album_kpis(df_tracks, album_name, market=market)
    kpis["album_id"] = album_id
    kpis["album_name"] = album_name
    kpis["artist_name"] = artist_name
    return kpis, {"album_id": album_id, "album_name": album_name, "artist_name": artist_name}


def get_album_top_titles_by_listen_time(df_tracks: pd.DataFrame, album_name: str, artist_name: Optional[str] = None, top_n: int = 10, market: str = "FR", token: str | None = None) -> pd.DataFrame:
    cols = ["classement", "cover", "titre", "isrc", "temps_écoute"]
    if df_tracks is None or df_tracks.empty or not {"album", "titre", "temps_écoute"}.issubset(df_tracks.columns):
        return pd.DataFrame(columns=cols)
    tok = token or get_spotify_token()
    if not tok:
        return pd.DataFrame(columns=cols)

    mask = (df_tracks["album"].astype(str).str.strip().str.lower() == str(album_name).strip().lower()) & (pd.to_numeric(df_tracks["temps_écoute"], errors="coerce").fillna(0) > 0)
    if artist_name and "artiste" in df_tracks.columns:
        mask = mask & df_tracks["artiste"].astype(str).str.strip().str.contains(str(artist_name).strip(), na=False)

    cols_needed = [c for c in ["titre", "artiste", "temps_écoute", "ISRC"] if c in df_tracks.columns]
    df_album = df_tracks.loc[mask, cols_needed]
    if df_album.empty:
        return pd.DataFrame(columns=cols)

    top = (
        df_album.groupby("titre", as_index=False)["temps_écoute"].sum()
        .sort_values("temps_écoute", ascending=False).head(top_n).reset_index(drop=True)
    )
    top["classement"] = top.index + 1
    top["temps_écoute"] = (top["temps_écoute"] / 3600).apply(hours_to_hm)

    if "ISRC" in df_album.columns:
        isrc_score = df_album.groupby(["titre", "ISRC"], as_index=False)["temps_écoute"].sum()
        idx = isrc_score.groupby("titre")["temps_écoute"].idxmax()
        best_isrc = isrc_score.loc[idx, ["titre", "ISRC"]].rename(columns={"ISRC": "isrc"})
        top = top.merge(best_isrc, on="titre", how="left")
    else:
        top["isrc"] = ""

    artist_for_cover = str(artist_name).strip() if artist_name else ""

    def _cover_for_title(title: str) -> str | None:
        t = search_track(title.strip(), artist_for_cover, token=tok, market=market) if artist_for_cover else None
        if not t:
            t = search_track(title.strip(), "", token=tok, market=market)
        return (t or {}).get("image_url")

    with ThreadPoolExecutor(max_workers=5) as ex:
        top["cover"] = list(ex.map(_cover_for_title, top["titre"].astype(str).tolist()))

    return top[cols]


def get_album_top_titles_by_listen_time_by_id(df_tracks: pd.DataFrame, album_id: str, top_n: int = 10, market: str = "FR", token: str | None = None) -> pd.DataFrame:
    tok = token or get_spotify_token()
    al = get_album_by_id(album_id, token=tok, market=market) if tok else None
    raw = (al or {}).get("raw") or {}
    album_name = (raw.get("name") or "").strip()
    artists = raw.get("artists") or []
    artist_name = (artists[0].get("name") if artists else "") or ""
    return get_album_top_titles_by_listen_time(df_tracks, album_name=album_name, artist_name=artist_name, top_n=top_n, market=market, token=tok)


def album_monthly_listening_chart_html(df_tracks: pd.DataFrame, album_name: str, artist_name: str | None = None, date_col: str = "date_écoute", duration_col: str = "temps_écoute", duration_unit: str = "seconds", height: int = 400, market: str = "FR") -> str:
    def _empty_fig(msg: str = "") -> str:
        fig = go.Figure()
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=height)
        return fig.to_html(full_html=False, include_plotlyjs=False, div_id=f"chart_{uuid.uuid4().hex}")

    if df_tracks is None or df_tracks.empty or "album" not in df_tracks.columns:
        return _empty_fig()

    mask = df_tracks["album"].astype(str).str.strip().str.lower() == str(album_name).strip().lower()
    if artist_name and "artiste" in df_tracks.columns:
        mask = mask & df_tracks["artiste"].astype(str).str.strip().str.contains(str(artist_name).strip(), na=False)

    df_album = df_tracks.loc[mask].copy()
    if df_album.empty:
        return _empty_fig()

    fig, _, _ = plot_listening_time_by_month_interactive(df_album, date_col=date_col, duration_col=duration_col, duration_unit=duration_unit, title="", height=height)
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#888888"),
        margin=dict(l=40, r=20, t=10, b=40),
        xaxis=dict(gridcolor="#2a2a2a", linecolor="#2a2a2a"),
        yaxis=dict(gridcolor="#2a2a2a", linecolor="#2a2a2a"),
    )
    fig.update_traces(marker_color="#F2CC0D")
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False, "responsive": True}, div_id=f"chart_{uuid.uuid4().hex}")


def album_monthly_listening_chart_html_by_id(df_tracks: pd.DataFrame, album_id: str, date_col: str = "date_écoute", duration_col: str = "temps_écoute", duration_unit: str = "seconds", height: int = 400, market: str = "FR") -> str:
    tok = get_spotify_token()
    al = get_album_by_id(album_id, token=tok, market=market) if tok else None
    raw = (al or {}).get("raw") or {}
    album_name = (raw.get("name") or "").strip()
    artists = raw.get("artists") or []
    artist_name = (artists[0].get("name") if artists else "") or ""
    return album_monthly_listening_chart_html(df_tracks, album_name=album_name, artist_name=artist_name, date_col=date_col, duration_col=duration_col, duration_unit=duration_unit, height=height, market=market)