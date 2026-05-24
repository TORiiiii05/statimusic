# analytics/track.py
from __future__ import annotations

import calendar
import math
import uuid
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from pandas.tseries.offsets import DateOffset

from dashboard.analytics.spotify import get_spotify_token, search_track, seconds_to_mmss


# ============================================================
# HELPERS
# ============================================================

def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _pick_main_artist_for_track(df_tracks: pd.DataFrame, track_name: str) -> Optional[str]:
    if df_tracks is None or df_tracks.empty or not {"titre", "artiste"}.issubset(df_tracks.columns):
        return None
    tkey = _norm(track_name)
    mask = df_tracks["titre"].astype(str).map(_norm) == tkey
    sub = df_tracks.loc[mask, "artiste"]
    if sub.empty:
        return None
    counts = sub.fillna("").astype(str).str.strip()
    counts = counts[counts != ""].value_counts()
    return str(counts.index[0]) if len(counts) else None


def _sec_to_hhmm(sec: float) -> str:
    sec = int(round(sec))
    h, m = sec // 3600, (sec % 3600) // 60
    return f"{h}h{m:02d}"


def _ensure_month_start(df: pd.DataFrame, date_col: str) -> pd.Series:
    s = pd.to_datetime(df[date_col], errors="coerce").dropna()
    return s.dt.to_period("M").dt.to_timestamp()


def _duration_to_seconds(df: pd.DataFrame, duration_col: str, unit: str) -> pd.Series:
    x = pd.to_numeric(df[duration_col], errors="coerce")
    unit = unit.lower()
    if unit in ["minutes", "minute", "min", "m"]:
        return x * 60
    return x


# ============================================================
# KPI HELPERS (sans .copy())
# ============================================================

def get_track_rank(df_tracks: pd.DataFrame, track_name: str, artist_name: Optional[str] = None) -> Optional[int]:
    if df_tracks is None or df_tracks.empty or not {"titre", "temps_écoute"}.issubset(df_tracks.columns):
        return None
    temps = pd.to_numeric(df_tracks["temps_écoute"], errors="coerce").fillna(0)
    titre_col = df_tracks["titre"].astype(str).str.strip()
    if artist_name and "artiste" in df_tracks.columns:
        grp = (
            pd.DataFrame({"titre": titre_col, "artiste": df_tracks["artiste"].astype(str).str.strip(), "t": temps})
            .groupby(["titre", "artiste"], as_index=False)["t"].sum()
            .sort_values("t", ascending=False).reset_index(drop=True)
        )
        target = (grp["titre"].str.lower() == track_name.strip().lower()) & (grp["artiste"] == artist_name.strip())
    else:
        grp = (
            pd.DataFrame({"titre": titre_col, "t": temps})
            .groupby("titre", as_index=False)["t"].sum()
            .sort_values("t", ascending=False).reset_index(drop=True)
        )
        target = grp["titre"].str.lower() == track_name.strip().lower()
    hit = grp.index[target].tolist()
    return int(hit[0] + 1) if hit else None


def get_track_listen_minutes(df_tracks: pd.DataFrame, track_name: str, artist_name: Optional[str] = None) -> int:
    if df_tracks is None or df_tracks.empty or not {"titre", "temps_écoute"}.issubset(df_tracks.columns):
        return 0
    mask = df_tracks["titre"].astype(str).str.strip().str.lower() == track_name.strip().lower()
    if artist_name and "artiste" in df_tracks.columns:
        mask = mask & (df_tracks["artiste"].astype(str).str.strip() == artist_name.strip())
    total = pd.to_numeric(df_tracks.loc[mask, "temps_écoute"], errors="coerce").fillna(0).sum()
    return int(round(float(total) / 60.0))


def get_track_listen_count(df_tracks: pd.DataFrame, track_name: str, artist_name: Optional[str] = None) -> int:
    if df_tracks is None or df_tracks.empty or "titre" not in df_tracks.columns:
        return 0
    mask = df_tracks["titre"].astype(str).str.strip().str.lower() == track_name.strip().lower()
    if artist_name and "artiste" in df_tracks.columns:
        mask = mask & (df_tracks["artiste"].astype(str).str.strip() == artist_name.strip())
    return int(mask.sum())


def get_track_first_listen_date(df_tracks: pd.DataFrame, track_name: str, artist_name: Optional[str] = None) -> Optional[pd.Timestamp]:
    if df_tracks is None or df_tracks.empty or not {"titre", "date_écoute"}.issubset(df_tracks.columns):
        return None
    mask = df_tracks["titre"].astype(str).str.strip().str.lower() == track_name.strip().lower()
    if artist_name and "artiste" in df_tracks.columns:
        mask = mask & (df_tracks["artiste"].astype(str).str.strip() == artist_name.strip())
    dates = pd.to_datetime(df_tracks.loc[mask, "date_écoute"], errors="coerce")
    d = dates.min()
    return d if pd.notna(d) else None


def get_track_most_listened_month(df_tracks: pd.DataFrame, track_name: str, artist_name: Optional[str] = None) -> Optional[str]:
    if df_tracks is None or df_tracks.empty or not {"titre", "temps_écoute", "date_écoute"}.issubset(df_tracks.columns):
        return None
    mask = df_tracks["titre"].astype(str).str.strip().str.lower() == track_name.strip().lower()
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


def get_track_spotify_meta(track_name: str, artist_name: Optional[str], market: str = "FR") -> dict:
    empty = {"duration_pill": "—", "release_date": "—", "album_name": "—"}
    tok = get_spotify_token()
    if not tok or not track_name:
        return empty
    t = search_track(track_name, artist_name or "", token=tok, market=market) if artist_name else None
    if not t:
        t = search_track(track_name, "", token=tok, market=market)
    if not t:
        return empty
    raw = t.get("raw") or {}
    duration_ms = raw.get("duration_ms")
    duration_pill = seconds_to_mmss(duration_ms / 1000) if isinstance(duration_ms, int) and duration_ms > 0 else "—"
    album = raw.get("album") or {}
    return {"duration_pill": duration_pill or "—", "release_date": album.get("release_date") or "—", "album_name": album.get("name") or "—"}


def get_track_kpis(df_tracks: pd.DataFrame, track_name: str, market: str = "FR") -> Tuple[dict, Optional[str]]:
    track_name = str(track_name).strip()
    main_artist = _pick_main_artist_for_track(df_tracks, track_name)
    rank = get_track_rank(df_tracks, track_name, artist_name=main_artist)
    listen_minutes = get_track_listen_minutes(df_tracks, track_name, artist_name=main_artist)
    nb_listens = get_track_listen_count(df_tracks, track_name, artist_name=main_artist)
    first_dt = get_track_first_listen_date(df_tracks, track_name, artist_name=main_artist)
    discover_date = first_dt.strftime("%d/%m/%y") if first_dt is not None else "—"
    most_month = get_track_most_listened_month(df_tracks, track_name, artist_name=main_artist) or "—"
    sp = get_track_spotify_meta(track_name, main_artist, market=market)
    return (
        {
            "track_name": track_name,
            "artist_name": main_artist or "—",
            "rank": rank,
            "duration_pill": sp.get("duration_pill", "—"),
            "release_date": sp.get("release_date", "—"),
            "discover_date": discover_date,
            "listen_minutes_pill": f"{listen_minutes} min",
            "most_listened_month": most_month,
            "nb_listens_pill": str(nb_listens),
            "album_name": sp.get("album_name", "—"),
        },
        main_artist,
    )


# ============================================================
# CHART
# ============================================================

BASE_COLOR = "#F2CC0D"
PAPER_BG   = "rgba(0,0,0,0)"
PLOT_BG    = "rgba(0,0,0,0)"
TEXT_COLOR = "#888888"
FIG_HEIGHT = 400


def plot_listening_time_by_month_interactive(
    df_tracks: pd.DataFrame,
    date_col: str = "date_écoute",
    duration_col: str = "temps_écoute",
    duration_unit: str = "seconds",
    fill_missing_months: bool = True,
    base_color: str = BASE_COLOR,
    title: str = "",
    height: int = FIG_HEIGHT,
    min_bars: int = 20,
    max_bars: int = 36,
):
    def _empty_fig():
        fig = go.Figure()
        fig.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, font=dict(color=TEXT_COLOR), height=height, autosize=True)
        return fig, pd.DataFrame(), {"k": 1, "n_bars": 0, "n_months": 0}

    if df_tracks is None or df_tracks.empty:
        return _empty_fig()

    df = df_tracks[[date_col, duration_col]].copy()
    df["_month"] = _ensure_month_start(df, date_col)
    df["_sec"] = pd.to_numeric(_duration_to_seconds(df, duration_col, duration_unit), errors="coerce")
    df = df.dropna(subset=["_month", "_sec"])

    monthly = df.groupby("_month", as_index=False)["_sec"].sum().sort_values("_month").reset_index(drop=True)
    if monthly.empty:
        return _empty_fig()

    if fill_missing_months:
        full = pd.date_range(monthly["_month"].min(), monthly["_month"].max(), freq="MS")
        monthly = monthly.set_index("_month").reindex(full, fill_value=0.0).rename_axis("_month").reset_index()

    monthly["_month"] = pd.to_datetime(monthly["_month"], errors="coerce")
    monthly["_sec"] = pd.to_numeric(monthly["_sec"], errors="coerce").fillna(0.0)
    monthly = monthly.dropna(subset=["_month"]).sort_values("_month").reset_index(drop=True)
    n_months = len(monthly)

    if n_months <= max_bars:
        k = 1
    else:
        candidates = [k_try for k_try in range(1, n_months + 1) if min_bars <= math.ceil(n_months / k_try) <= max_bars]
        k = min(candidates) if candidates else max(1, math.ceil(n_months / max_bars))

    if k > 1:
        base = monthly["_month"].min()
        base_lin = int(base.year * 12 + (base.month - 1))
        month_lin = (monthly["_month"].dt.year * 12 + (monthly["_month"].dt.month - 1)).astype(int)
        monthly["_bin"] = ((month_lin - base_lin) // k).astype(int)
        agg = monthly.groupby("_bin", as_index=False)["_sec"].sum().sort_values("_bin").reset_index(drop=True)
        start_lin = (base_lin + agg["_bin"] * k).astype(int)
        end_lin = (start_lin + (k - 1)).astype(int)
        def _idx_to_ts(i): return pd.Timestamp(year=i//12, month=(i%12)+1, day=1)
        out = agg.copy()
        out["start_month"] = start_lin.apply(_idx_to_ts)
        out["end_month"] = end_lin.apply(_idx_to_ts)
    else:
        out = monthly.copy()
        out["start_month"] = out["_month"]
        out["end_month"] = out["_month"]

    out["_sec"] = pd.to_numeric(out["_sec"], errors="coerce").fillna(0.0)
    out["minutes"] = (out["_sec"] / 60.0)
    out["hhmm"] = out["_sec"].apply(_sec_to_hhmm)
    out["year"] = out["start_month"].dt.year.astype(int)
    s0 = out["start_month"].dt.strftime("%b %y")
    s1 = out["end_month"].dt.strftime("%b %y")
    out["label_hover"] = np.where(s0 == s1, s0, s0 + " - " + s1)
    out = out.sort_values("start_month").reset_index(drop=True)
    out["x_key"] = out["start_month"].dt.strftime("%Y-%m")

    year_change = out["year"].ne(out["year"].shift(1))
    tickvals = out.loc[year_change, "x_key"].tolist()
    ticktext = out.loc[year_change, "year"].astype(str).tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=out["x_key"].astype(str).tolist(),
        y=out["minutes"].astype(float).tolist(),
        marker=dict(color=base_color, line=dict(width=0)),
        customdata=np.stack([out["label_hover"].astype(str), out["minutes"].round(0).astype(int).astype(str)], axis=1),
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} min<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(color=TEXT_COLOR), margin=dict(l=55, r=20, t=10, b=70),
        height=height, autosize=True, hovermode="closest", bargap=0.18,
    )
    fig.update_xaxes(type="category", showgrid=False, tickmode="array", tickvals=tickvals, ticktext=ticktext, ticks="outside", ticklen=6)
    fig.update_yaxes(title_text="Minutes", showgrid=False, zeroline=False)

    return fig, out, {"k": k, "n_months": n_months, "n_bars": len(out)}


def track_monthly_listening_chart_html(df_tracks: pd.DataFrame, track_name: str, date_col: str = "date_écoute", duration_col: str = "temps_écoute", duration_unit: str = "seconds", height: int = 400) -> str:
    mask = df_tracks["titre"] == track_name
    df_track = df_tracks.loc[mask].copy()
    df_track = df_track.dropna(subset=["date_écoute", "temps_écoute"])
    df_track["date_écoute"] = pd.to_datetime(df_track["date_écoute"], errors="coerce")
    df_track = df_track.dropna(subset=["date_écoute"])

    def _empty():
        fig = go.Figure()
        fig.update_layout(paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG, font=dict(family="Inter, sans-serif", color=TEXT_COLOR), height=height)
        return fig.to_html(full_html=False, include_plotlyjs=False, div_id=f"chart_{uuid.uuid4().hex}")

    if df_track.empty:
        return _empty()

    fig, _, _ = plot_listening_time_by_month_interactive(df_track, date_col=date_col, duration_col=duration_col, duration_unit=duration_unit, title="", height=height)
    fig.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        font=dict(family="Inter, sans-serif", color=TEXT_COLOR),
        margin=dict(l=40, r=20, t=10, b=40),
        xaxis=dict(gridcolor="#2a2a2a", linecolor="#2a2a2a"),
        yaxis=dict(gridcolor="#2a2a2a", linecolor="#2a2a2a"),
    )
    fig.update_traces(marker_color="#F2CC0D")
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": False, "responsive": True}, div_id=f"chart_{uuid.uuid4().hex}")