from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from flask_bcrypt import Bcrypt
from models import User
from db import supabase

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
