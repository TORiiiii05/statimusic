from flask import Flask
from flask_login import LoginManager
from config import Config
from db import supabase

app = Flask(__name__)
app.config.from_object(Config)

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "auth.login"

from models import User

@login_manager.user_loader
def load_user(user_id):
    res = supabase.table("users").select("*").eq("id", user_id).execute()
    if res.data:
        u = res.data[0]
        return User(u["id"], u["email"])
    return None

# Blueprints
from auth.routes import auth_bp
from dashboard.routes import dashboard_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)

from flask import redirect, url_for
from flask_login import current_user

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    return redirect(url_for("auth.landing"))

if __name__ == "__main__":
    app.run(debug=True)