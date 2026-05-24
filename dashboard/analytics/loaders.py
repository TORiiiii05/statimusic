# analytics/loaders.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd


DEFAULT_EXCEL_NAME = "deezer-data_2503587702.xlsx"
DEFAULT_SHEET_NAME = "10_listeningHistory"

# Colonnes lues depuis l'Excel — on ignore tout le reste
USECOLS = ["Song Title", "Artist", "Album Title", "Listening Time", "Date", "ISRC"]

def project_root() -> Path:
    return Path(__file__).resolve().parents[1]

def default_excel_path() -> Path:
    return project_root() / "data" / DEFAULT_EXCEL_NAME

def _safe_rename(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    existing = {k: v for k, v in mapping.items() if k in df.columns}
    return df.rename(columns=existing)


@dataclass(frozen=True)
class LoadedData:
    df_tracks: pd.DataFrame
    df_artists: pd.DataFrame  # gardé pour compatibilité, toujours vide


def load_listening_history(
    excel_path: Optional[str | Path] = None,
    sheet_name: str = DEFAULT_SHEET_NAME,
) -> LoadedData:
    path = Path(excel_path) if excel_path else default_excel_path()
    if not path.exists():
        empty = pd.DataFrame()
        return LoadedData(df_tracks=empty, df_artists=empty)

    # Lecture avec seulement les colonnes nécessaires
    df = pd.read_excel(
        path,
        sheet_name=sheet_name,
        usecols=lambda c: c.strip() in USECOLS,
    )

    df.columns = df.columns.astype(str).str.strip()

    df = _safe_rename(df, {
        "Song Title": "titre",
        "Artist": "artiste",
        "Album Title": "album",
        "Listening Time": "temps_écoute",
        "Date": "date_écoute",
        "ISRC": "ISRC",
    })

    if "date_écoute" in df.columns:
        df["date_écoute"] = pd.to_datetime(df["date_écoute"], errors="coerce")

    if "temps_écoute" in df.columns:
        df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce")

    for col in ["titre", "artiste", "album"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    return LoadedData(df_tracks=df, df_artists=pd.DataFrame())