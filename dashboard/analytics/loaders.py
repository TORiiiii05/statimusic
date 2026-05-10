# analytics/loaders.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd


# =========================
# Config simple / utilitaires
# =========================

DEFAULT_EXCEL_NAME = "deezer-data_2503587702.xlsx"
DEFAULT_SHEET_NAME = "10_listeningHistory"


def project_root() -> Path:
    """
    analytics/ est un package. Ce fichier est: <root>/analytics/loaders.py
    Donc root = parent de analytics.
    """
    return Path(__file__).resolve().parents[1]


def default_excel_path() -> Path:
    return project_root() / "data" / DEFAULT_EXCEL_NAME


def _safe_rename(df: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    """Renomme uniquement les colonnes qui existent."""
    existing = {k: v for k, v in mapping.items() if k in df.columns}
    return df.rename(columns=existing)


# =========================
# Load principal
# =========================

@dataclass(frozen=True)
class LoadedData:
    df_tracks: pd.DataFrame
    df_artists: pd.DataFrame


def load_listening_history(
    excel_path: Optional[str | Path] = None,
    sheet_name: str = DEFAULT_SHEET_NAME,
) -> LoadedData:
    """
    Charge le fichier Excel Deezer, nettoie, renvoie:
      - df_tracks : 1 ligne = 1 écoute (structure "track")
      - df_artists : 1 ligne = 1 écoute × 1 artiste (explosion)
    """
    path = Path(excel_path) if excel_path else default_excel_path()
    if not path.exists():
        # On renvoie des DF vides plutôt que de crash toute l'app
        empty = pd.DataFrame()
        return LoadedData(df_tracks=empty, df_artists=empty)

    # --- Import brut ---
    df = pd.read_excel(path, sheet_name=sheet_name)

    # Nettoyage noms de colonnes
    df.columns = df.columns.astype(str).str.strip()

    # Renommage en français (ce qu'on voit dans ton notebook)
    df = _safe_rename(df, {
        "Song Title": "titre",
        "Artist": "artiste",
        "Album Title": "album",
        "Listening Time": "temps_écoute",
        "Date": "date_écoute",
        "Platform Name": "plateforme",
    })

    # Optionnel: si tes colonnes existent déjà mais avec espaces bizarres
    df = _safe_rename(df, {
        "Platform Model": "Platform Model",
        "IP Address": "IP Address",
        "ISRC": "ISRC",
    })

    # Convertir les dates (robuste)
    if "date_écoute" in df.columns:
        df["date_écoute"] = pd.to_datetime(df["date_écoute"], errors="coerce")

    # Listening time en numérique (au cas où)
    if "temps_écoute" in df.columns:
        df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce")

    # Nettoyage basique string
    for col in ["titre", "artiste", "album", "plateforme"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()

    # df_tracks = base (1 ligne = 1 écoute)
    df_tracks = df.copy()

    # =========================
    # df_artists: explosion artistes (virgules)
    # =========================
    if "artiste" in df.columns:
        df_artists = df.copy()

        # On garde l'index d'origine (clé de jointure) = ce que tu faisais
        df_artists = df_artists.reset_index().rename(columns={"index": "track_row_id"})

        # garde uniquement lignes avec artiste non vide
        df_artists["artiste"] = df_artists["artiste"].fillna("").astype(str)
        df_artists = df_artists[df_artists["artiste"].str.strip() != ""]

        # split multi-artistes: "A, B, C"
        df_artists["artiste"] = df_artists["artiste"].str.split(",").apply(
            lambda lst: [a.strip() for a in lst if a and a.strip()]
        )

        # Explosion : une ligne = une écoute × un artiste
        df_artists = df_artists.explode("artiste").reset_index(drop=True)

        # (optionnel) supprime doublons exacts si tu en as
        df_artists = df_artists.drop_duplicates()

    else:
        df_artists = pd.DataFrame()

    return LoadedData(df_tracks=df_tracks, df_artists=df_artists)


# Petit alias pratique si tu veux unpack directement
def load_tracks_and_artists(
    excel_path: Optional[str | Path] = None,
    sheet_name: str = DEFAULT_SHEET_NAME,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    data = load_listening_history(excel_path=excel_path, sheet_name=sheet_name)
    return data.df_tracks, data.df_artists
