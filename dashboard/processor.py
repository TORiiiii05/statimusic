from __future__ import annotations
import base64
import os
from io import BytesIO
from PIL import Image
import pandas as pd
from dashboard.analytics.loaders import load_listening_history
from dashboard.analytics.spotify import get_spotify_token
from dashboard.analytics.home import (
    get_home_kpis,
    get_top_artists_by_listen_time_circle,
    get_top_tracks_by_listen_time,
    get_top_albums_by_listen_time,
)


def _pil_to_b64(img: Image.Image | None) -> str | None:
    if img is None:
        return None
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _serialize_artists(df: pd.DataFrame) -> list[dict]:
    out = []
    for _, row in df.iterrows():
        out.append({
            "classement": int(row["classement"]),
            "artist_name": str(row["artist_name"]),
            "artist_id": str(row.get("artist_id") or ""),
            "cover": _pil_to_b64(row.get("cover")),
            "temps_ecoute": str(row["temps_écoute"]),
        })
    return out


def _serialize_tracks(df: pd.DataFrame) -> list[dict]:
    out = []
    for _, row in df.iterrows():
        out.append({
            "classement": int(row["classement"]),
            "titre": str(row["titre"]),
            "artiste": str(row["artiste"]),
            "isrc": str(row.get("isrc") or ""),
            "cover": _pil_to_b64(row.get("cover")),
            "temps_ecoute": str(row["temps_écoute"]),
        })
    return out


def _serialize_albums(df: pd.DataFrame) -> list[dict]:
    out = []
    for _, row in df.iterrows():
        out.append({
            "classement": int(row["classement"]),
            "album": str(row["album"]),
            "artiste": str(row["artiste"]),
            "album_id": str(row.get("album_id") or ""),
            "cover": _pil_to_b64(row.get("cover")),
            "temps_ecoute": str(row["temps_écoute"]),
        })
    return out


def process_excel_and_build_stats(excel_path: str, market: str = "FR") -> dict:
    """
    Charge l'Excel, calcule toutes les stats home, retourne un dict JSON-serializable.
    """
    loaded = load_listening_history(excel_path=excel_path)
    df_tracks = loaded.df_tracks
    df_artists = loaded.df_artists

    if df_tracks is None or df_tracks.empty:
        raise ValueError("Fichier Excel vide ou colonnes non reconnues.")

    kpis = get_home_kpis(df_tracks)
    top_artists = get_top_artists_by_listen_time_circle(df_tracks, top_n=10, market=market)
    top_tracks = get_top_tracks_by_listen_time(df_tracks, top_n=3, market=market)
    top_albums = get_top_albums_by_listen_time(df_tracks, top_n=3, market=market)

    return {
        "kpis": kpis,
        "top_artists": _serialize_artists(top_artists),
        "top_tracks": _serialize_tracks(top_tracks),
        "top_albums": _serialize_albums(top_albums),
    }

def serialize_df_tracks(df_tracks: pd.DataFrame) -> str:
    import gzip
    import base64
    json_str = df_tracks.to_json(orient="records", date_format="iso", force_ascii=False)
    compressed = gzip.compress(json_str.encode("utf-8"))
    return base64.b64encode(compressed).decode("utf-8")

def load_df_from_supabase(df_json_b64: str) -> pd.DataFrame:
    import gzip, base64 as b64
    from io import StringIO
    raw = b64.b64decode(df_json_b64.encode("utf-8"))
    json_str = gzip.decompress(raw).decode("utf-8")
    df = pd.read_json(StringIO(json_str), orient="records")
    if "date_écoute" in df.columns:
        df["date_écoute"] = pd.to_datetime(df["date_écoute"], errors="coerce")
    return dfv