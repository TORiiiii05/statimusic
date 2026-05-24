from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import login_required, current_user
import os
import json
import tempfile

import pandas as pd

from db import supabase, supabase_admin
from dashboard.analytics.loaders import load_listening_history
from dashboard.analytics.spotify import get_spotify_token, search_track_by_isrc, image_getter
from dashboard.analytics.track import get_track_kpis, track_monthly_listening_chart_html
from dashboard.analytics.album import get_album_kpis_by_id, get_album_top_titles_by_listen_time_by_id, album_monthly_listening_chart_html_by_id
from dashboard.analytics.artist import get_artist_kpis_by_id, get_top_10_titles_by_listen_time, get_top_10_albums_by_listen_time
from dashboard.analytics.spotify import get_album_by_id, get_artist_by_id
from dashboard.processor import (
    process_excel_and_build_stats,
    upload_df_to_storage,
    download_df_from_storage,
    build_search_index,
    _pil_to_b64,
)

dashboard_bp = Blueprint("dashboard", __name__)

MARKET = os.getenv("SPOTIFY_MARKET", "FR")


def _load_df_from_supabase(user_id: str) -> pd.DataFrame:
    res = supabase.table("users").select("df_path").eq("id", user_id).execute()
    if not res.data or not res.data[0].get("df_path"):
        raise ValueError("Aucun historique trouvé. Merci d'uploader ton fichier Excel.")
    return download_df_from_storage(res.data[0]["df_path"], supabase_admin)


@dashboard_bp.route("/home")
@login_required
def home():
    res = supabase.table("users").select("stats_json, df_path, search_index_json").eq("id", current_user.id).execute()
    stats = None
    if res.data and res.data[0].get("stats_json"):
        stats = json.loads(res.data[0]["stats_json"])

    if not stats:
        return redirect(url_for("dashboard.upload"))

    if not res.data[0].get("search_index_json") and res.data[0].get("df_path"):
        try:
            df = _load_df_from_supabase(current_user.id)
            index = build_search_index(df)
            supabase.table("users").update({
                "search_index_json": json.dumps(index, ensure_ascii=False)
            }).eq("id", current_user.id).execute()
        except Exception:
            pass

    return render_template("dashboard/home.html", user=current_user, stats=stats)


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
            loaded = load_listening_history(excel_path=tmp.name)
            stats = process_excel_and_build_stats(tmp.name, market=MARKET)
            stats_json = json.dumps(stats, ensure_ascii=False)
            df_path = upload_df_to_storage(loaded.df_tracks, current_user.id, supabase_admin)

            supabase.table("users").update({
                "stats_json": stats_json,
                "df_path": df_path,
            }).eq("id", current_user.id).execute()

            try:
                index = build_search_index(loaded.df_tracks)
                supabase.table("users").update({
                    "search_index_json": json.dumps(index, ensure_ascii=False)
                }).eq("id", current_user.id).execute()
            except Exception:
                pass

            flash("Ton historique a bien été importé !", "success")
            return redirect(url_for("dashboard.home"))

        except Exception as e:
            return render_template("dashboard/upload.html", error=f"Erreur lors du traitement : {e}")
        finally:
            os.unlink(tmp.name)

    return render_template("dashboard/upload.html")


@dashboard_bp.route("/track/<isrc>")
@login_required
def track(isrc):
    try:
        df_tracks = _load_df_from_supabase(current_user.id)
    except Exception as e:
        return render_template("dashboard/upload.html", error=f"Erreur chargement données : {e}")

    tok = get_spotify_token()
    sp = search_track_by_isrc(isrc, token=tok) if tok else None

    track_name = None
    if "ISRC" in df_tracks.columns:
        match = df_tracks[df_tracks["ISRC"].astype(str).str.strip() == isrc]
        track_name = match["titre"].iloc[0] if not match.empty else None
    if not track_name:
        track_name = sp.get("name") if sp else isrc

    kpis, main_artist = get_track_kpis(df_tracks, track_name)

    cover_b64 = None
    if sp and sp.get("image_url"):
        img = image_getter(sp["image_url"])
        cover_b64 = _pil_to_b64(img)
    kpis["cover"] = cover_b64

    try:
        chart_html = track_monthly_listening_chart_html(df_tracks, track_name)
    except Exception:
        chart_html = ""

    return render_template("dashboard/track.html", kpis=kpis, chart_html=chart_html)


@dashboard_bp.route("/album/<album_id>")
@login_required
def album(album_id):
    try:
        df_tracks = _load_df_from_supabase(current_user.id)
    except Exception as e:
        return render_template("dashboard/upload.html", error=f"Erreur chargement données : {e}")

    kpis, _ = get_album_kpis_by_id(df_tracks, album_id, market=MARKET)

    tok = get_spotify_token()
    al = get_album_by_id(album_id, token=tok, market=MARKET) if tok else None
    cover_b64 = None
    if al and al.get("image_url"):
        img = image_getter(al["image_url"])
        cover_b64 = _pil_to_b64(img)
    kpis["cover"] = cover_b64

    top_tracks = get_album_top_titles_by_listen_time_by_id(df_tracks, album_id, market=MARKET)
    top_tracks_list = top_tracks.to_dict(orient="records") if not top_tracks.empty else []

    try:
        chart_html = album_monthly_listening_chart_html_by_id(df_tracks, album_id, market=MARKET)
    except Exception:
        chart_html = ""

    return render_template("dashboard/album.html", kpis=kpis, top_tracks=top_tracks_list, chart_html=chart_html)


@dashboard_bp.route("/artist/<artist_id>")
@login_required
def artist(artist_id):
    try:
        df_tracks = _load_df_from_supabase(current_user.id)
    except Exception as e:
        return render_template("dashboard/upload.html", error=f"Erreur chargement données : {e}")

    kpis = get_artist_kpis_by_id(df_tracks, df_tracks, artist_id, market=MARKET)

    tok = get_spotify_token()
    ar = get_artist_by_id(artist_id, token=tok) if tok else None
    cover_b64 = None
    if ar and ar.get("image_url"):
        img = image_getter(ar["image_url"])
        cover_b64 = _pil_to_b64(img)

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


@dashboard_bp.route("/api/search")
@login_required
def search():
    q = request.args.get("q", "").strip().lower()
    if len(q) < 2:
        return jsonify([])

    res = supabase.table("users").select("search_index_json").eq("id", current_user.id).execute()
    if not res.data or not res.data[0].get("search_index_json"):
        return jsonify([])
    try:
        index = json.loads(res.data[0]["search_index_json"])
    except Exception:
        return jsonify([])

    results = []

    count = 0
    for item in index["artists"]:
        if count >= 4: break
        if q in item["search_key"]:
            results.append({"type": "artist", "label": item["name"], "name": item["name"],
                "url": url_for("dashboard.resolve_artist", name=item["name"])})
            count += 1

    count = 0
    for item in index["albums"]:
        if count >= 3: break
        if q in item["search_key"]:
            results.append({"type": "album", "label": f"{item['album']} — {item['artist']}",
                "album": item["album"], "artist": item["artist"],
                "url": url_for("dashboard.resolve_album", album=item["album"], artist=item["artist"])})
            count += 1

    count = 0
    for item in index["tracks"]:
        if count >= 3: break
        if q in item["search_key"]:
            results.append({"type": "track", "label": f"{item['titre']} — {item['artist']}",
                "url": url_for("dashboard.track", isrc=item["isrc"]), "isrc": item["isrc"]})
            count += 1

    return jsonify(results)


@dashboard_bp.route("/search/resolve/artist")
@login_required
def resolve_artist():
    from dashboard.analytics.spotify import search_artist
    name = request.args.get("name", "").strip()
    if not name:
        return redirect(url_for("dashboard.home"))
    tok = get_spotify_token()
    a = search_artist(name, token=tok, market=MARKET) if tok else None
    artist_id = (a or {}).get("id", "")
    if artist_id:
        return redirect(url_for("dashboard.artist", artist_id=artist_id))
    return redirect(url_for("dashboard.home"))


@dashboard_bp.route("/search/resolve/album")
@login_required
def resolve_album():
    from dashboard.analytics.spotify import search_album
    album = request.args.get("album", "").strip()
    artist = request.args.get("artist", "").strip()
    if not album:
        return redirect(url_for("dashboard.home"))
    tok = get_spotify_token()
    al = search_album(album, artist, token=tok, market=MARKET) if tok else None
    album_id = (al or {}).get("id", "")
    if album_id:
        return redirect(url_for("dashboard.album", album_id=album_id))
    return redirect(url_for("dashboard.home"))