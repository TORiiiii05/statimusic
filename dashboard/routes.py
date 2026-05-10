from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
import os
import json
import tempfile

from db import supabase
from dashboard.processor import process_excel_and_build_stats

dashboard_bp = Blueprint("dashboard", __name__)

MARKET = os.getenv("SPOTIFY_MARKET", "FR")


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


@dashboard_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        f = request.files.get("excel_file")
        if not f or not f.filename.endswith(".xlsx"):
            return render_template("dashboard/upload.html", error="Merci d'uploader un fichier .xlsx")

        # Sauvegarde temporaire
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        tmp.close()
        f.save(tmp.name)

        try:
            stats = process_excel_and_build_stats(tmp.name, market=MARKET)
            stats_json = json.dumps(stats, ensure_ascii=False)
            supabase.table("users").update({"stats_json": stats_json}).eq("id", current_user.id).execute()
            flash("Ton historique a bien été importé !", "success")
            return redirect(url_for("dashboard.home"))
        except Exception as e:
            return render_template("dashboard/upload.html", error=f"Erreur lors du traitement : {e}")
        finally:
            os.unlink(tmp.name)

    return render_template("dashboard/upload.html")