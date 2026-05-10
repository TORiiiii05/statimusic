from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
import os
import json
import tempfile
import gzip
import base64 as b64
from io import StringIO

import pandas as pd

from db import supabase
from dashboard.analytics.loaders import load_listening_history
from dashboard.analytics.spotify import get_spotify_token, search_track_by_isrc, image_getter
from dashboard.analytics.track import get_track_kpis, track_monthly_listening_chart_html
from dashboard.processor import (
    process_excel_and_build_stats,
    serialize_df_tracks,
    _pil_to_b64,
)

from dashboard.analytics.album import get_album_kpis_by_id, get_album_top_titles_by_listen_time_by_id, album_monthly_listening_chart_html_by_id
from dashboard.analytics.artist import get_artist_kpis_by_id, get_top_10_titles_by_listen_time, get_top_10_albums_by_listen_time
from dashboard.analytics.spotify import get_album_by_id, get_artist_by_id
dashboard_bp = Blueprint("dashboard", __name__)

MARKET = os.getenv("SPOTIFY_MARKET", "FR")


def _load_df_from_supabase(df_json_b64: str) -> pd.DataFrame:
    """Décompresse et désérialise le df_tracks stocké en Supabase."""
    raw = b64.b64decode(df_json_b64.encode("utf-8"))
    json_str = gzip.decompress(raw).decode("utf-8")
    df = pd.read_json(StringIO(json_str), orient="records")
    if "date_écoute" in df.columns:
        df["date_écoute"] = pd.to_datetime(df["date_écoute"], errors="coerce")
    return df


# ============================================================
# HOME
# ============================================================

@dashboard_bp.route("/home")
@login_required
def home():
    res = supabase.table("users").select("stats_json").eq("id", current_user.id).execute()
    stats = None
    if res.data and res.data[0].get("stats_json"):
        stats = json.loads(res.data[0]["stats_json"])

    if not stats:
        return redirect(url_for("dashboard.upload"))

    return render_template("dashboard/home.html", user=current_user, stats=stats)


# ============================================================
# UPLOAD
# ============================================================

@dashboard_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        f = request.files.get("excel_file")
        if not f or not f.filename.endswith(".xlsx"):
            return render_template("dashboard/upload.html", error="Merci d'uploader un fichier .xlsx")

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        tmp.close()
        f.save(tmp.name)

        try:
            # Chargement unique du fichier
            loaded = load_listening_history(excel_path=tmp.name)

            # Calcul des stats home (appelle Spotify pour les covers)
            stats = process_excel_and_build_stats(tmp.name, market=MARKET)
            stats_json = json.dumps(stats, ensure_ascii=False)

            # Sérialisation du df_tracks brut
            df_json = serialize_df_tracks(loaded.df_tracks)

            supabase.table("users").update({
                "stats_json": stats_json,
                "df_json": df_json,
            }).eq("id", current_user.id).execute()

            flash("Ton historique a bien été importé !", "success")
            return redirect(url_for("dashboard.home"))

        except Exception as e:
            return render_template("dashboard/upload.html", error=f"Erreur lors du traitement : {e}")
        finally:
            os.unlink(tmp.name)

    return render_template("dashboard/upload.html")


# ============================================================
# TRACK
# ============================================================

@dashboard_bp.route("/track/<isrc>")
@login_required
def track(isrc):
    res = supabase.table("users").select("df_json").eq("id", current_user.id).execute()
    if not res.data or not res.data[0].get("df_json"):
        return redirect(url_for("dashboard.upload"))

    try:
        df_tracks = _load_df_from_supabase(res.data[0]["df_json"])
    except Exception as e:
        return render_template("dashboard/upload.html", error=f"Erreur chargement données : {e}")

    # Résoudre le track depuis l'ISRC via Spotify
    tok = get_spotify_token()
    sp = search_track_by_isrc(isrc, token=tok) if tok else None

    # Priorité : nom depuis le df local (via ISRC) — plus fiable que Spotify
    track_name = None
    if "ISRC" in df_tracks.columns:
        match = df_tracks[df_tracks["ISRC"].astype(str).str.strip() == isrc]
        track_name = match["titre"].iloc[0] if not match.empty else None

    # Fallback : nom Spotify
    if not track_name:
        track_name = sp.get("name") if sp else isrc

    kpis, main_artist = get_track_kpis(df_tracks, track_name)

    # Cover depuis Spotify
    cover_b64 = None
    if sp and sp.get("image_url"):
        img = image_getter(sp["image_url"])
        cover_b64 = _pil_to_b64(img)
    kpis["cover"] = cover_b64

    # Graphique mensuel
    try:
        chart_html = track_monthly_listening_chart_html(df_tracks, track_name)
    except Exception:
        chart_html = ""

    return render_template("dashboard/track.html", kpis=kpis, chart_html=chart_html)

@dashboard_bp.route("/album/<album_id>")
@login_required
def album(album_id):
    res = supabase.table("users").select("df_json").eq("id", current_user.id).execute()
    if not res.data or not res.data[0].get("df_json"):
        return redirect(url_for("dashboard.upload"))

    try:
        df_tracks = _load_df_from_supabase(res.data[0]["df_json"])
    except Exception as e:
        return render_template("dashboard/upload.html", error=f"Erreur chargement données : {e}")

    kpis, _ = get_album_kpis_by_id(df_tracks, album_id, market=MARKET)

    # Cover
    tok = get_spotify_token()
    al = get_album_by_id(album_id, token=tok, market=MARKET) if tok else None
    cover_b64 = None
    if al and al.get("image_url"):
        img = image_getter(al["image_url"])
        cover_b64 = _pil_to_b64(img)
    kpis["cover"] = cover_b64

    # Top titres
    top_tracks = get_album_top_titles_by_listen_time_by_id(df_tracks, album_id, market=MARKET)
    top_tracks_list = top_tracks.to_dict(orient="records") if not top_tracks.empty else []

    # Graphique
    try:
        chart_html = album_monthly_listening_chart_html_by_id(df_tracks, album_id, market=MARKET)
    except Exception:
        chart_html = ""

    return render_template("dashboard/album.html", kpis=kpis, top_tracks=top_tracks_list, chart_html=chart_html)


@dashboard_bp.route("/artist/<artist_id>")
@login_required
def artist(artist_id):
    res = supabase.table("users").select("df_json").eq("id", current_user.id).execute()
    if not res.data or not res.data[0].get("df_json"):
        return redirect(url_for("dashboard.upload"))

    try:
        df_tracks = _load_df_from_supabase(res.data[0]["df_json"])
    except Exception as e:
        return render_template("dashboard/upload.html", error=f"Erreur chargement données : {e}")

    kpis = get_artist_kpis_by_id(df_tracks, pd.DataFrame(), artist_id, market=MARKET)

    # Cover
    tok = get_spotify_token()
    ar = get_artist_by_id(artist_id, token=tok) if tok else None
    cover_b64 = None
    if ar and ar.get("image_url"):
        img = image_getter(ar["image_url"])
        cover_b64 = _pil_to_b64(img)

    # Top titres et albums
    artist_name = kpis.get("artist_name", "")
    top_tracks = get_top_10_titles_by_listen_time(df_tracks, artist_name, market=MARKET)
    top_albums = get_top_10_albums_by_listen_time(df_tracks, artist_name, market=MARKET)

    top_tracks_list = top_tracks.to_dict(orient="records") if not top_tracks.empty else []
    top_albums_list = top_albums.to_dict(orient="records") if not top_albums.empty else []

    return render_template("dashboard/artist.html",
        kpis=kpis,
        cover=cover_b64,
        top_tracks=top_tracks_list,
        top_albums=top_albums_list,
    )