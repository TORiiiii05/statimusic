# analytics/track.py
from __future__ import annotations

import calendar
from typing import Optional, Tuple

import numpy as np
import plotly.graph_objects as go
import pandas as pd
import math
from pandas.tseries.offsets import DateOffset


from dashboard.analytics.spotify import get_spotify_token, search_track, seconds_to_mmss

from dashboard.analytics.spotify import get_spotify_token, search_track

def get_track_artists_spotify(track_name: str, artist_hint: str | None = None, market: str = "FR") -> list[str]:
    """
    Retourne la liste d'artistes du track depuis Spotify (inclut feats).
    artist_hint aide la recherche (ex: main_artist).
    """
    tok = get_spotify_token()
    if not tok:
        return []

    t = None
    if artist_hint:
        t = search_track(track_name, artist_hint, token=tok, market=market)

    if not t:
        # fallback sans hint
        t = search_track(track_name, "", token=tok, market=market)

    raw = (t or {}).get("raw") or {}
    artists = raw.get("artists") or []
    names = []
    seen = set()
    for a in artists:
        name = (a.get("name") or "").strip()
        key = name.lower()
        if name and key not in seen:
            seen.add(key)
            names.append(name)
    return names


def _split_artists(raw: str) -> list[str]:
    """
    Transforme "Vald, Damso" -> ["Vald", "Damso"]
    Robuste: trim, supprime vides, dédoublonne en gardant l'ordre.
    """
    if raw is None:
        return []
    parts = [p.strip() for p in str(raw).split(",")]
    parts = [p for p in parts if p]

    seen = set()
    out = []
    for p in parts:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def get_track_artists(
    df_tracks: pd.DataFrame,
    track_name: str,
    *,
    isrc: str | None = None,
    artist_hint: str | None = None,
) -> list[str]:
    """
    Retourne les artistes du track en évitant les collisions de noms.
    Priorité:
      1) filtre ISRC si dispo
      2) sinon filtre (titre + artist_hint)
      3) sinon titre seul (fallback)
    """
    if df_tracks is None or df_tracks.empty:
        return []
    if "titre" not in df_tracks.columns or "artiste" not in df_tracks.columns:
        return []

    df = df_tracks.copy()
    df["titre"] = df["titre"].astype(str).str.strip()
    df["artiste"] = df["artiste"].astype(str).str.strip()

    # 1) ISRC (meilleur)
    if isrc and "ISRC" in df.columns:
        df["ISRC"] = df["ISRC"].astype(str).str.strip()
        sub = df[df["ISRC"] == str(isrc).strip()]
    else:
        # 2) Titre + artiste hint (réduit énormément les collisions)
        t = str(track_name).strip().lower()
        sub = df[df["titre"].str.lower() == t]

        if artist_hint:
            ah = str(artist_hint).strip().lower()
            # contient() car parfois "Vald, Damso"
            sub = sub[sub["artiste"].str.lower().str.contains(ah, na=False)]

    if sub.empty:
        return []

    # split "A, B" -> ["A","B"] + dédoublonnage
    def _split(raw: str) -> list[str]:
        parts = [p.strip() for p in str(raw).split(",")]
        parts = [p for p in parts if p]
        seen, out = set(), []
        for p in parts:
            k = p.lower()
            if k not in seen:
                seen.add(k)
                out.append(p)
        return out

    counts = {}
    display = {}
    for raw in sub["artiste"].tolist():
        for a in _split(raw):
            k = a.lower()
            display[k] = display.get(k, a)
            counts[k] = counts.get(k, 0) + 1

    ordered = sorted(counts.keys(), key=lambda k: (-counts[k], k))
    return [display[k] for k in ordered]

def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


def _pick_main_artist_for_track(df_tracks: pd.DataFrame, track_name: str) -> Optional[str]:
    """
    Si plusieurs artistes existent pour un même titre (feat, remixes, etc.),
    on prend l'artiste le plus fréquent dans l'historique (proxy simple et robuste).
    """
    if df_tracks is None or df_tracks.empty or not {"titre", "artiste"}.issubset(df_tracks.columns):
        return None

    tkey = _norm(track_name)
    sub = df_tracks.copy()
    sub["titre"] = sub["titre"].astype(str)
    sub["artiste"] = sub["artiste"].astype(str)

    mask = sub["titre"].map(_norm) == tkey
    sub = sub.loc[mask]
    if sub.empty:
        return None

    # artiste le plus fréquent
    counts = sub["artiste"].fillna("").astype(str).str.strip()
    counts = counts[counts != ""].value_counts()
    return str(counts.index[0]) if len(counts) else None


def get_track_rank(df_tracks: pd.DataFrame, track_name: str, artist_name: Optional[str] = None) -> Optional[int]:
    """
    Rang du titre (par temps d'écoute total).
    - Si artist_name est fourni, on classe sur le couple (titre, artiste)
    - Sinon on classe sur le titre (tous artistes confondus)
    """
    if df_tracks is None or df_tracks.empty:
        return None
    if not {"titre", "temps_écoute"}.issubset(df_tracks.columns):
        return None

    df = df_tracks.copy()
    df["titre"] = df["titre"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)

    if artist_name and "artiste" in df.columns:
        df["artiste"] = df["artiste"].astype(str).str.strip()
        grp = (
            df.groupby(["titre", "artiste"], as_index=False)["temps_écoute"]
            .sum()
            .sort_values("temps_écoute", ascending=False)
            .reset_index(drop=True)
        )
        target_mask = (grp["titre"].str.lower() == track_name.strip().lower()) & (grp["artiste"] == artist_name.strip())
    else:
        grp = (
            df.groupby("titre", as_index=False)["temps_écoute"]
            .sum()
            .sort_values("temps_écoute", ascending=False)
            .reset_index(drop=True)
        )
        target_mask = grp["titre"].str.lower() == track_name.strip().lower()

    hit = grp.index[target_mask].tolist()
    return int(hit[0] + 1) if hit else None


def get_track_listen_minutes(df_tracks: pd.DataFrame, track_name: str, artist_name: Optional[str] = None) -> int:
    if df_tracks is None or df_tracks.empty:
        return 0
    if not {"titre", "temps_écoute"}.issubset(df_tracks.columns):
        return 0

    df = df_tracks.copy()
    df["titre"] = df["titre"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)

    mask = df["titre"].str.lower() == track_name.strip().lower()
    if artist_name and "artiste" in df.columns:
        df["artiste"] = df["artiste"].astype(str).str.strip()
        mask = mask & (df["artiste"] == artist_name.strip())

    sub = df.loc[mask]
    if sub.empty:
        return 0

    total_seconds = float(sub["temps_écoute"].sum())
    return int(round(total_seconds / 60.0))


def get_track_listen_count(df_tracks: pd.DataFrame, track_name: str, artist_name: Optional[str] = None) -> int:
    if df_tracks is None or df_tracks.empty or "titre" not in df_tracks.columns:
        return 0

    df = df_tracks.copy()
    df["titre"] = df["titre"].astype(str).str.strip()

    mask = df["titre"].str.lower() == track_name.strip().lower()
    if artist_name and "artiste" in df.columns:
        df["artiste"] = df["artiste"].astype(str).str.strip()
        mask = mask & (df["artiste"] == artist_name.strip())

    return int(mask.sum())


def get_track_first_listen_date(df_tracks: pd.DataFrame, track_name: str, artist_name: Optional[str] = None) -> Optional[pd.Timestamp]:
    if df_tracks is None or df_tracks.empty:
        return None
    if not {"titre", "date_écoute"}.issubset(df_tracks.columns):
        return None

    df = df_tracks.copy()
    df["titre"] = df["titre"].astype(str).str.strip()
    df["date_écoute"] = pd.to_datetime(df["date_écoute"], errors="coerce")

    mask = df["titre"].str.lower() == track_name.strip().lower()
    if artist_name and "artiste" in df.columns:
        df["artiste"] = df["artiste"].astype(str).str.strip()
        mask = mask & (df["artiste"] == artist_name.strip())

    sub = df.loc[mask & df["date_écoute"].notna()]
    if sub.empty:
        return None

    d = sub["date_écoute"].min()
    return d if pd.notna(d) else None


def get_track_most_listened_month(df_tracks: pd.DataFrame, track_name: str, artist_name: Optional[str] = None) -> Optional[str]:
    if df_tracks is None or df_tracks.empty:
        return None
    if not {"titre", "temps_écoute", "date_écoute"}.issubset(df_tracks.columns):
        return None

    df = df_tracks.copy()
    df["titre"] = df["titre"].astype(str).str.strip()
    df["temps_écoute"] = pd.to_numeric(df["temps_écoute"], errors="coerce").fillna(0)
    df["date_écoute"] = pd.to_datetime(df["date_écoute"], errors="coerce")

    mask = df["titre"].str.lower() == track_name.strip().lower()
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


def get_track_spotify_meta(track_name: str, artist_name: Optional[str], market: str = "FR") -> dict:
    """
    Récupère via Spotify:
    - durée (mm:ss)
    - date de sortie (album.release_date)
    - album (nom)
    """
    tok = get_spotify_token()
    if not tok or not track_name:
        return {"duration_pill": "—", "release_date": "—", "album_name": "—"}

    # Spotify search marche mieux avec artiste si on l'a
    t = search_track(track_name, artist_name or "", token=tok, market=market) if artist_name else None
    if not t:
        # fallback: tente une recherche sans artiste (moins précis mais mieux que rien)
        t = search_track(track_name, "", token=tok, market=market)

    if not t:
        return {"duration_pill": "—", "release_date": "—", "album_name": "—"}

    raw = t.get("raw") or {}
    duration_ms = raw.get("duration_ms")
    duration_pill = "—"
    if isinstance(duration_ms, int) and duration_ms > 0:
        duration_pill = seconds_to_mmss(duration_ms / 1000) or "—"

    album = raw.get("album") or {}
    release_date = album.get("release_date") or "—"
    album_name = album.get("name") or "—"

    return {"duration_pill": duration_pill, "release_date": release_date, "album_name": album_name}


def get_track_kpis(df_tracks: pd.DataFrame, track_name: str, market: str = "FR") -> Tuple[dict, Optional[str]]:
    """
    Bundle KPI prêt pour template.
    Retourne (kpis, main_artist_name)
    """
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

# ============================
# CHART: Temps d'écoute par mois (Plotly)
# ============================

# Fallbacks si tu n'as pas déjà ces constantes dans ton projet
BASE_COLOR = globals().get("BASE_COLOR", "#F2CC0D")
PAPER_BG   = globals().get("PAPER_BG", "#191919")
PLOT_BG    = globals().get("PLOT_BG", "#191919")
TEXT_COLOR = globals().get("TEXT_COLOR", "#F0F0F0")
FIG_HEIGHT = globals().get("FIG_HEIGHT", 380)
YEAR_LIGHT_LOW  = globals().get("YEAR_LIGHT_LOW", 0.85)
YEAR_LIGHT_HIGH = globals().get("YEAR_LIGHT_HIGH", 1.25)


def _ensure_month_start(df: pd.DataFrame, date_col: str) -> pd.Series:
    s = pd.to_datetime(df[date_col], errors="coerce")
    if s.isna().any():
        s = s.dropna()
    return s.dt.to_period("M").dt.to_timestamp()  # début de mois


def _duration_to_seconds(df: pd.DataFrame, duration_col: str, unit: str) -> pd.Series:
    x = pd.to_numeric(df[duration_col], errors="coerce")
    if x.isna().any():
        raise ValueError(f"{x.isna().sum()} durées invalides dans {duration_col}")
    unit = unit.lower()
    if unit in ["seconds", "second", "sec", "s", "seconde", "secondes"]:
        return x
    if unit in ["minutes", "minute", "min", "m"]:
        return x * 60
    raise ValueError("duration_unit doit être 'seconds' ou 'minutes' (ou équivalent).")


def _sec_to_hhmm(sec: float) -> str:
    sec = int(round(sec))
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h}h{m:02d}"


def plot_listening_time_by_month_interactive(
    df_tracks: pd.DataFrame,
    date_col: str = "date_écoute",
    duration_col: str = "temps_écoute",
    duration_unit: str = "seconds",
    fill_missing_months: bool = True,
    base_color: str = BASE_COLOR,
    title: str = "Temps d'écoute total par mois",
    height: int = FIG_HEIGHT,
    min_bars: int = 20,
    max_bars: int = 36,
):
    """
    Graph barres verticales:
      - X: catégories (clé YYYY-MM), ticks = années uniquement
      - Y: minutes écoutées sur la période
    Features:
      - inclut TOUS les mois entre première et dernière écoute (0 inclus)
      - bins automatiques (k mois par barre) pour garder un nb de barres lisible
      - hover:
          k=1 -> "Sep 19"
          k>1 -> "Sep 19 - Oct 19" / "Sep 19 - Dec 19"
      - valeurs numériques forcées -> évite le bug Plotly "index 1..n"
    Retourne: (fig, out_df, meta)
    """

    import math

    # -------------------------
    # 0) Cas vide
    # -------------------------
    if df_tracks is None or df_tracks.empty:
        fig = go.Figure()
        fig.update_layout(
            title=title,
            paper_bgcolor=PAPER_BG,
            plot_bgcolor=PLOT_BG,
            font=dict(color=TEXT_COLOR),
            height=height,
            autosize=True,
        )
        return fig, pd.DataFrame(), {"k": 1, "n_bars": 0, "n_months": 0}

    # -------------------------
    # 1) Série mensuelle complète (0 inclus)
    # -------------------------
    df = df_tracks.copy()
    df["_month"] = _ensure_month_start(df, date_col)
    df["_sec"] = _duration_to_seconds(df, duration_col, duration_unit)

    # force float (anti-bug "catégories")
    df["_sec"] = pd.to_numeric(df["_sec"], errors="coerce").astype(float)
    df = df.dropna(subset=["_month", "_sec"]).copy()

    monthly = (
        df.groupby("_month", as_index=False)["_sec"]
          .sum()
          .sort_values("_month")
          .reset_index(drop=True)
    )

    if monthly.empty:
        fig = go.Figure()
        fig.update_layout(
            title=title,
            paper_bgcolor=PAPER_BG,
            plot_bgcolor=PLOT_BG,
            font=dict(color=TEXT_COLOR),
            height=height,
            autosize=True,
        )
        return fig, monthly, {"k": 1, "n_bars": 0, "n_months": 0}

    # ✅ force tous les mois entre min et max
    if fill_missing_months:
        full = pd.date_range(monthly["_month"].min(), monthly["_month"].max(), freq="MS")
        monthly = (
            monthly.set_index("_month")
                   .reindex(full, fill_value=0.0)
                   .rename_axis("_month")
                   .reset_index()
        )

    monthly["_month"] = pd.to_datetime(monthly["_month"], errors="coerce")
    monthly["_sec"] = pd.to_numeric(monthly["_sec"], errors="coerce").fillna(0.0).astype(float)
    monthly = monthly.dropna(subset=["_month"]).sort_values("_month").reset_index(drop=True)

    n_months = int(len(monthly))

    # -------------------------
    # 2) Choix automatique de k (mois par barre)
    # -------------------------
    if n_months <= max_bars:
        k = 1
    else:
        candidates = []
        for k_try in range(1, n_months + 1):
            bars = int(math.ceil(n_months / k_try))
            if min_bars <= bars <= max_bars:
                candidates.append(k_try)

        if candidates:
            k = min(candidates)  # le plus détaillé possible
        else:
            k = max(1, int(math.ceil(n_months / max_bars)))

    # -------------------------
    # 3) Binning (si k>1)
    # -------------------------
    if k > 1:
        base = monthly["_month"].min()
        base_lin = int(base.year * 12 + (base.month - 1))

        month_lin = (monthly["_month"].dt.year * 12 + (monthly["_month"].dt.month - 1)).astype(int)
        monthly["_bin"] = ((month_lin - base_lin) // k).astype(int)

        agg = (
            monthly.groupby("_bin", as_index=False)["_sec"]
                  .sum()
                  .sort_values("_bin")
                  .reset_index(drop=True)
        )

        start_lin = (base_lin + agg["_bin"] * k).astype(int)
        end_lin = (start_lin + (k - 1)).astype(int)

        def _idx_to_ts(i: int) -> pd.Timestamp:
            y = i // 12
            m = (i % 12) + 1
            return pd.Timestamp(year=int(y), month=int(m), day=1)

        out = agg.copy()
        out["start_month"] = start_lin.apply(_idx_to_ts)
        out["end_month"] = end_lin.apply(_idx_to_ts)

    else:
        out = monthly.copy()
        out["start_month"] = out["_month"]
        out["end_month"] = out["_month"]

    # -------------------------
    # 4) Minutes + labels hover
    # -------------------------
    out["_sec"] = pd.to_numeric(out["_sec"], errors="coerce").fillna(0.0).astype(float)
    out["minutes"] = (out["_sec"] / 60.0).astype(float)
    out["hhmm"] = out["_sec"].apply(_sec_to_hhmm)
    out["year"] = out["start_month"].dt.year.astype(int)

    # Hover label:
    # 1 mois -> "Sep 19"
    # >=2 mois -> "Sep 19 - Oct 19"
    s0 = out["start_month"].dt.strftime("%b %y")
    s1 = out["end_month"].dt.strftime("%b %y")
    out["label_hover"] = np.where(s0 == s1, s0, s0 + " - " + s1)

    out = out.sort_values("start_month").reset_index(drop=True)

    # -------------------------
    # 5) Couleurs (simple)
    # -------------------------
    out["color"] = base_color

    # -------------------------
    # 6) Axe X: clé stable + ticks années
    # -------------------------
    # x_key doit être unique et triable
    out["x_key"] = out["start_month"].dt.strftime("%Y-%m")

    # tick aux changements d'année (premier bin de chaque année)
    year_change = out["year"].ne(out["year"].shift(1))
    tickvals = out.loc[year_change, "x_key"].tolist()
    ticktext = out.loc[year_change, "year"].astype(str).tolist()

    # -------------------------
    # 7) Plot (listes Python, barres verticales)
    # -------------------------
    x = out["x_key"].astype(str).tolist()
    y = out["minutes"].astype(float).tolist()
    colors = out["color"].astype(str).tolist()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=x,
        y=y,
        orientation="v",
        marker=dict(color=colors, line=dict(width=0)),
        customdata=np.stack(
            [out["label_hover"].astype(str), out["minutes"].round(0).astype(int).astype(str)],
            axis=1
        ),
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]} min<extra></extra>",
    ))

    fig.update_layout(
        title=None,
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(color=TEXT_COLOR),
        margin=dict(l=55, r=20, t=55, b=70),
        height=height,
        autosize=True,
        hovermode="closest",
        bargap=0.18,
    )

    # Axe X: n'affiche que les années
    fig.update_xaxes(
        type="category",
        showgrid=False,
        tickmode="array",
        tickvals=tickvals,
        ticktext=ticktext,
        ticks="outside",
        ticklen=6,
    )

    fig.update_yaxes(
        title_text="Minutes",
        showgrid=False,
        zeroline=False,
    )

    return fig, out, {"k": k, "n_months": n_months, "n_bars": int(len(out))}



def track_monthly_listening_chart_html(
    df_tracks: pd.DataFrame,
    track_name: str,
    date_col: str = "date_écoute",
    duration_col: str = "temps_écoute",
    duration_unit: str = "seconds",
    height: int = 460,
) -> str:
    """
    Retourne le HTML Plotly (div) prêt à injecter dans Jinja
    pour le graphique 'temps d'écoute par mois' d'un titre.
    Version robuste (div_id unique, pas de cache).
    """
    import uuid

    # -------------------------
    # 1) Filtrage strict du titre
    # -------------------------
    df_track = df_tracks[df_tracks["titre"] == track_name].copy()
    df_track = df_track.dropna(subset=["date_écoute", "temps_écoute"])
    df_track["date_écoute"] = pd.to_datetime(df_track["date_écoute"], errors="coerce")
    df_track = df_track.dropna(subset=["date_écoute"])

    # Sécurité : si aucune donnée
    if df_track.empty:
        fig = go.Figure()
        fig.update_layout(
            title=f"Aucune donnée pour {track_name}",
            height=height,
        )
        return fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            div_id=f"chart_{uuid.uuid4().hex}",
        )

    # -------------------------
    # 2) Génération de la figure
    # -------------------------
    fig, _, _ = plot_listening_time_by_month_interactive(
        df_track,
        date_col=date_col,
        duration_col=duration_col,
        duration_unit=duration_unit,
        title=f"Répartition du temps d'écoute par mois – {track_name}",
        height=height,
    )

    # -------------------------
    # 3) HTML Plotly avec div_id unique (ANTI CACHE)
    # -------------------------
    return fig.to_html(
        full_html=False,
        include_plotlyjs=False,  # Plotly chargé une seule fois dans base.html
        config={
            "displayModeBar": False,
            "responsive": True,
        },
        div_id=f"chart_{uuid.uuid4().hex}",  # 🔑 empêche la réutilisation d'un ancien graphe
    )
