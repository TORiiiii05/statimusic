from __future__ import annotations

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

    total_seconds = float(df["temps_écoute"].sum())
    total_hours = int(round(total_seconds / 3600))

    nb_tracks = int(len(df))

    if df["date_écoute"].notna().any():
        per_day = df.groupby(df["date_écoute"].dt.date)["temps_écoute"].sum()
        avg_minutes_per_day = float(per_day.mean() / 60.0) if len(per_day) else 0.0
    else:
        avg_minutes_per_day = 0.0

    nb_artists = int(df["artiste"].nunique())

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
    img_size: int = 96,
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

    # ⚠️ artist_id pas encore résolu ici (sera fait plus tard via ISRC/Spotify)
    top["artist_id"] = ""

    covers: list[Image.Image | None] = []
    for artist in top["artiste"].tolist():
        pil = cover_getter(
            artist_name=artist,
            market=market,
            shape="circle",
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
    img_size: int = 220,
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
    img_size: int = 220,
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

    # album_id sera résolu plus tard (via Spotify / ISRC)
    top["album_id"] = ""

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
