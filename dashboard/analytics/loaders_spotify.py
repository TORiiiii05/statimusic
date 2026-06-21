# analytics/loaders_spotify.py
from __future__ import annotations

import json
import zipfile
from io import BytesIO
from typing import List, Tuple

import pandas as pd


def load_spotify_history(files: List[Tuple[str, bytes]]) -> pd.DataFrame:
    """
    Charge un historique d'écoute Spotify depuis une liste de (nom_fichier, contenu_bytes).
    Accepte des fichiers .json individuels ou des .zip contenant plusieurs JSON Spotify.
    Retourne un DataFrame avec les mêmes colonnes que Deezer + source="spotify" + spotify_uri.
    """
    records = []

    for fname, content in files:
        fname_lower = fname.lower()

        if fname_lower.endswith(".zip"):
            _extract_zip(content, records)
        elif fname_lower.endswith(".json"):
            _parse_json_bytes(content, records)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # date_écoute : ts UTC → datetime pandas tz-naive (même format que Deezer)
    df["date_écoute"] = pd.to_datetime(df["date_écoute"], utc=True, errors="coerce").dt.tz_convert(None)

    # temps_écoute : ms → secondes (float)
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce")

    for col in ["titre", "artiste", "album"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    df["ISRC"] = None
    df["source"] = "spotify"

    return df[["titre", "artiste", "album", "ISRC", "temps_écoute", "date_écoute", "source", "spotify_uri"]]


def _extract_zip(content: bytes, records: list) -> None:
    try:
        with zipfile.ZipFile(BytesIO(content)) as zf:
            for name in zf.namelist():
                if name.lower().endswith(".json") and "Audio" in name:
                    json_bytes = zf.read(name)
                    _parse_json_bytes(json_bytes, records)
    except Exception as e:
        print(f"SPOTIFY LOADER ZIP ERROR: {e}")


def _parse_json_bytes(content: bytes, records: list) -> None:
    try:
        data = json.loads(content.decode("utf-8", errors="replace"))
    except Exception as e:
        print(f"SPOTIFY LOADER JSON ERROR: {e}")
        return

    if not isinstance(data, list):
        return

    for entry in data:
        if not isinstance(entry, dict):
            continue

        # Filtre podcasts et audiobooks
        if entry.get("episode_name") is not None:
            continue
        if entry.get("audiobook_title") is not None:
            continue

        ms = entry.get("ms_played")
        if ms is None:
            continue

        uri = entry.get("spotify_track_uri") or ""

        records.append({
            "titre": entry.get("master_metadata_track_name") or "",
            "artiste": entry.get("master_metadata_album_artist_name") or "",
            "album": entry.get("master_metadata_album_album_name") or "",
            "temps_écoute": float(ms) / 1000.0,
            "date_écoute": entry.get("ts") or "",
            "spotify_uri": uri if uri.startswith("spotify:track:") else None,
        })
