from __future__ import annotations

import re

import pandas as pd
from PIL import Image

# Spotify helpers
from dashboard.analytics.spotify import (
    hours_to_hm,
    cover_getter,
    covers_getter,
)

# ============================================================
# HOME - KPI
# ============================================================

def get_home_kpis(df_tracks: pd.DataFrame) -> dict:
    if df_tracks is None or df_tracks.empty:
        return {
            "total_hours": 0,
            "nb_tracks": 0,
            "avg_minutes_per_day": 0.0,
            "nb_artists": 0,
        }

    df = df_tracks.copy()

    df["temps_écoute"] = pd.to_numeric(df.get("temps_écoute", 0), errors="coerce").fillna(0)
    df["date_écoute"] = pd.to_datetime(df.get("date_écoute"), errors="coerce")
    df["artiste"] = df.get("artiste", "").astype(str).str.strip()

    df_pos = df[df["temps_écoute"] > 0]

    total_seconds = float(df_pos["temps_écoute"].sum())
    total_hours = int(round(total_seconds / 3600))

    nb_tracks = int(len(df))

    if df_pos["date_écoute"].notna().any():
        per_day = df_pos.groupby(df_pos["date_écoute"].dt.date)["temps_écoute"].sum()
        avg_minutes_per_day = float(per_day.mean() / 60.0) if len(per_day) else 0.0
    else:
        avg_minutes_per_day = 0.0

    all_artists = (
        df["artiste"]
        .apply(lambda x: re.split(r",\s*", x) if x else [])
        .explode()
        .str.strip()
    )
    nb_artists = int(all_artists[all_artists != ""].nunique())

    return {
        "total_hours": total_hours,
        "nb_tracks": nb_tracks,
        "avg_minutes_per_day": avg_minutes_per_day,
        "nb_artists": nb_artists,
    }


# ============================================================
# HOME - TOP ARTISTS (ID READY)
# ============================================================

def get_top_artists_by_listen_time_circle(
    df_tracks: pd.DataFrame,
    top_n: int = 10,
    img_size: int = 400,
    market: str = "FR",
) -> pd.DataFrame:
    """
    Retourne:
    classement | artist_name | artist_id | cover | temps_écoute
    """

    cols = ["classement", "artist_name", "artist_id", "cover", "temps_écoute"]

    if df_tracks is None or df_tracks.empty:
        return pd.DataFrame(columns=cols)

    if not {"artiste", "temps_écoute"}.issubset(df_tracks.columns):
        return pd.DataFrame(columns=cols)

    df = df_tracks.copy()
    df["artiste"] = df["artiste"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)
    df = df[df["temps_écoute"] > 0]

    if df.empty:
        return pd.DataFrame(columns=cols)

    top = (
        df.groupby("artiste", as_index=False)["temps_écoute"]
        .sum()
        .sort_values("temps_écoute", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )

    top["classement"] = top.index + 1
    top["temps_écoute"] = (top["temps_écoute"] / 3600).apply(hours_to_hm)

    from dashboard.analytics.spotify import get_spotify_token, search_artist
    tok = get_spotify_token()
    def _resolve_artist_id(name):
        if not tok:
            return ""
        a = search_artist(name, token=tok, market=market)
        return (a or {}).get("id", "")
    top["artist_id"] = top["artiste"].apply(_resolve_artist_id)

    covers: list[Image.Image | None] = []
    for artist in top["artiste"].tolist():
        pil = cover_getter(
            artist_name=artist,
            market=market,
            shape="square",
        )
        if pil:
            try:
                pil = pil.resize((img_size, img_size), Image.LANCZOS)
            except Exception:
                pass
        covers.append(pil)

    top["cover"] = covers
    top = top.rename(columns={"artiste": "artist_name"})

    return top[cols]


# ============================================================
# HOME - TOP TRACKS (ISRC FIRST)
# ============================================================

def get_top_tracks_by_listen_time(
    df_tracks: pd.DataFrame,
    top_n: int = 3,
    img_size: int = 400,
    market: str = "FR",
) -> pd.DataFrame:
    """
    Retourne:
    classement | titre | artiste | isrc | cover | temps_écoute
    """

    cols = ["classement", "titre", "artiste", "isrc", "cover", "temps_écoute"]

    if df_tracks is None or df_tracks.empty:
        return pd.DataFrame(columns=cols)

    required = {"titre", "artiste", "temps_écoute", "ISRC"}
    if not required.issubset(df_tracks.columns):
        return pd.DataFrame(columns=cols)

    df = df_tracks.copy()
    df["titre"] = df["titre"].astype(str).str.strip()
    df["artiste"] = df["artiste"].astype(str).str.strip()
    df["ISRC"] = df["ISRC"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)
    df = df[(df["temps_écoute"] > 0) & (df["ISRC"] != "")]

    if df.empty:
        return pd.DataFrame(columns=cols)

    top = (
        df.groupby(["titre", "artiste", "ISRC"], as_index=False)["temps_écoute"]
        .sum()
        .sort_values("temps_écoute", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )

    top["classement"] = top.index + 1
    top["temps_écoute"] = (top["temps_écoute"] / 3600).apply(hours_to_hm)
    top = top.rename(columns={"ISRC": "isrc"})

    top = covers_getter(
        top,
        mode="track",
        market=market,
        shape="rounded",
        img_size=img_size,
        col_track="titre",
        col_artist="artiste",
        out_col="cover",
    )

    return top[cols]


# ============================================================
# HOME - TOP ALBUMS (ID READY)
# ============================================================

def get_top_albums_by_listen_time(
    df_tracks: pd.DataFrame,
    top_n: int = 3,
    img_size: int = 400,
    market: str = "FR",
) -> pd.DataFrame:
    """
    Retourne:
    classement | album | artiste | album_id | cover | temps_écoute
    """

    cols = ["classement", "album", "artiste", "album_id", "cover", "temps_écoute"]

    if df_tracks is None or df_tracks.empty:
        return pd.DataFrame(columns=cols)

    required = {"album", "artiste", "temps_écoute"}
    if not required.issubset(df_tracks.columns):
        return pd.DataFrame(columns=cols)

    df = df_tracks.copy()
    df["album"] = df["album"].astype(str).str.strip()
    df["artiste"] = df["artiste"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)
    df = df[(df["temps_écoute"] > 0) & (df["album"] != "")]

    if df.empty:
        return pd.DataFrame(columns=cols)

    top = (
        df.groupby(["album", "artiste"], as_index=False)["temps_écoute"]
        .sum()
        .sort_values("temps_écoute", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )

    top["classement"] = top.index + 1
    top["temps_écoute"] = (top["temps_écoute"] / 3600).apply(hours_to_hm)

    from dashboard.analytics.spotify import get_spotify_token, search_album
    tok = get_spotify_token()
    def _resolve_album_id(row):
        if not tok:
            return ""
        al = search_album(row["album"], row["artiste"], token=tok, market=market)
        return (al or {}).get("id", "")
    top["album_id"] = top.apply(_resolve_album_id, axis=1)

    top = covers_getter(
        top,
        mode="album",
        market=market,
        shape="rounded",
        img_size=img_size,
        col_album="album",
        col_artist="artiste",
        out_col="cover",
    )

    return top[cols]
