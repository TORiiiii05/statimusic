from __future__ import annotations
import base64
import gzip
import os
from io import BytesIO, StringIO
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


COLS_TO_STORE = ["artiste", "titre", "album", "ISRC", "temps_écoute", "date_écoute"]

def upload_df_to_storage(df_tracks: pd.DataFrame, user_id: str, supabase_client) -> str:
    """Compresse et uploade df_tracks dans Supabase Storage. Retourne le path."""
    # Garde uniquement les colonnes nécessaires pour réduire la mémoire
    cols = [c for c in COLS_TO_STORE if c in df_tracks.columns]
    df_slim = df_tracks[cols].copy()
    
    json_str = df_slim.to_json(orient="records", date_format="iso", force_ascii=False)
    compressed = gzip.compress(json_str.encode("utf-8"))
    path = f"{user_id}/df_tracks.json.gz"
    supabase_client.storage.from_("user-data").upload(
        path=path,
        file=compressed,
        file_options={"content-type": "application/gzip", "upsert": "true"},
    )
    return path

def download_df_from_storage(path: str, supabase_client) -> pd.DataFrame:
    """Télécharge et désérialise df_tracks depuis Supabase Storage."""
    raw = supabase_client.storage.from_("user-data").download(path)
    json_str = gzip.decompress(raw).decode("utf-8")
    df = pd.read_json(StringIO(json_str), orient="records")
    if "date_écoute" in df.columns:
        df["date_écoute"] = pd.to_datetime(df["date_écoute"], errors="coerce")
    return df


def build_search_index(df_tracks: pd.DataFrame) -> dict:
    """
    Construit un index de recherche léger depuis df_tracks.
    Retourne un dict JSON-serializable stockable en Supabase.
    """
    index = {"artists": [], "albums": [], "tracks": []}

    if df_tracks is None or df_tracks.empty:
        return index

    # Artistes — explosion sur virgule pour gérer les feats
    if "artiste" in df_tracks.columns and "temps_écoute" in df_tracks.columns:
        df_exp = df_tracks.copy()
        df_exp["artiste"] = df_exp["artiste"].astype(str).str.split(",")
        df_exp = df_exp.explode("artiste")
        df_exp["artiste"] = df_exp["artiste"].str.strip()
        df_exp = df_exp[df_exp["artiste"] != ""]
        df_exp["temps_écoute"] = pd.to_numeric(df_exp["temps_écoute"], errors="coerce").fillna(0)
        artists = (
            df_exp.groupby("artiste", as_index=False)["temps_écoute"]
            .sum()
            .sort_values("temps_écoute", ascending=False)
            .reset_index(drop=True)
        )
        index["artists"] = [
            {"name": row["artiste"], "search_key": row["artiste"].lower()}
            for _, row in artists.iterrows()
        ]

    # Albums
    if {"album", "artiste", "temps_écoute"}.issubset(df_tracks.columns):
        df_al = df_tracks.copy()
        df_al["temps_écoute"] = pd.to_numeric(df_al["temps_écoute"], errors="coerce").fillna(0)
        albums = (
            df_al.groupby(["album", "artiste"], as_index=False)["temps_écoute"]
            .sum()
            .sort_values("temps_écoute", ascending=False)
            .reset_index(drop=True)
        )
        index["albums"] = [
            {
                "album": row["album"],
                "artist": row["artiste"],
                "search_key": row["album"].lower(),
            }
            for _, row in albums.iterrows()
            if row["album"].strip()
        ]

    # Tracks
    if {"titre", "artiste", "ISRC", "temps_écoute"}.issubset(df_tracks.columns):
        df_tr = df_tracks.copy()
        df_tr["temps_écoute"] = pd.to_numeric(df_tr["temps_écoute"], errors="coerce").fillna(0)
        df_tr["ISRC"] = df_tr["ISRC"].astype(str).str.strip()
        tracks = (
            df_tr[df_tr["ISRC"] != ""]
            .groupby(["titre", "artiste", "ISRC"], as_index=False)["temps_écoute"]
            .sum()
            .sort_values("temps_écoute", ascending=False)
            .reset_index(drop=True)
        )
        index["tracks"] = [
            {
                "titre": row["titre"],
                "artist": row["artiste"],
                "isrc": row["ISRC"],
                "search_key": row["titre"].lower(),
            }
            for _, row in tracks.iterrows()
        ]

    return index