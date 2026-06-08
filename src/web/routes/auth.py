"""
routes/auth.py — Login y logout
"""

import sys
import functools
from pathlib import Path
from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash,
)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auth.auth_manager import verify_login, Role

auth_bp = Blueprint("auth", __name__)


# ─── Decorador de sesión ──────────────────────────────────────────────────────

def login_required(roles: list[str] | None = None):
    """Decorador que exige sesión activa y, opcionalmente, un rol específico."""
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            if "username" not in session:
                flash("Inicia sesión para continuar.", "warning")
                return redirect(url_for("auth.login"))
            if roles and session.get("role") not in roles:
                flash("No tienes permisos para acceder a esta sección.", "error")
                return redirect(url_for("dashboard.index"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


# ─── Rutas ────────────────────────────────────────────────────────────────────

@auth_bp.route("/", methods=["GET"])
def root():
    if "username" in session:
        return redirect(url_for("dashboard.index"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "username" in session:
        return redirect(url_for("dashboard.index"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            error = "Completa todos los campos."
        else:
            ok, role = verify_login(username, password)
            if ok:
                session["username"] = username
                session["role"] = role.value
                return redirect(url_for("dashboard.index"))
            else:
                error = "Usuario o contraseña incorrectos."

    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
