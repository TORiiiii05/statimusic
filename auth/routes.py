import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from models import User
from db import supabase
from auth.email import send_reset_email

auth_bp = Blueprint("auth", __name__)
bcrypt = Bcrypt()

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        
        # Vérifie si l'email existe déjà
        existing = supabase.table("users").select("id").eq("email", email).execute()
        if existing.data:
            flash("Cet email est déjà utilisé.", "error")
            return redirect(url_for("auth.register"))
        
        # Hash du mot de passe
        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        
        # Insertion en base
        supabase.table("users").insert({
            "email": email,
            "password_hash": password_hash
        }).execute()
        
        flash("Compte créé ! Tu peux te connecter.", "success")
        return redirect(url_for("auth.login"))
    
    return render_template("auth/register.html")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        
        # Cherche l'utilisateur
        res = supabase.table("users").select("*").eq("email", email).execute()
        if not res.data:
            flash("Email ou mot de passe incorrect.", "error")
            return redirect(url_for("auth.login"))
        
        u = res.data[0]
        if not bcrypt.check_password_hash(u["password_hash"], password):
            flash("Email ou mot de passe incorrect.", "error")
            return redirect(url_for("auth.login"))
        
        user = User(u["id"], u["email"])
        login_user(user)
        return redirect(url_for("dashboard.home"))
    
    return render_template("auth/login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login")) 


@auth_bp.route("/landing")
def landing():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    return render_template("landing.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        from datetime import datetime, timezone, timedelta
        email = request.form["email"].strip().lower()
        res = supabase.table("users").select("id").eq("email", email).execute()
        if res.data:
            user_id = res.data[0]["id"]
            token = str(uuid.uuid4())
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            supabase.table("password_reset_tokens").insert({
                "user_id": user_id,
                "token": token,
                "expires_at": expires_at,
                "used": False,
            }).execute()
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            try:
                send_reset_email(email, reset_url)
            except Exception:
                pass
        flash("Si un compte existe avec cet email, tu recevras un lien dans quelques minutes.", "success")
        return redirect(url_for("auth.forgot_password"))
    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    res = supabase.table("password_reset_tokens").select("*").eq("token", token).eq("used", False).execute()
    if not res.data:
        flash("Lien invalide ou expiré.", "error")
        return redirect(url_for("auth.forgot_password"))

    row = res.data[0]
    from datetime import datetime, timezone
    expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires_at:
        flash("Lien invalide ou expiré.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form["password"]
        confirm = request.form["confirm_password"]
        if password != confirm:
            flash("Les mots de passe ne correspondent pas.", "error")
            return render_template("auth/reset_password.html", token=token)
        if len(password) < 8:
            flash("Le mot de passe doit faire au moins 8 caractères.", "error")
            return render_template("auth/reset_password.html", token=token)
        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        supabase.table("users").update({"password_hash": password_hash}).eq("id", row["user_id"]).execute()
        supabase.table("password_reset_tokens").update({"used": True}).eq("token", token).execute()
        flash("Mot de passe mis à jour. Tu peux te connecter.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)