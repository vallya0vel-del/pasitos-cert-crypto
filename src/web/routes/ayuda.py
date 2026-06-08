"""
routes/ayuda.py — Página de ayuda y referencia del sistema
"""

from flask import Blueprint, render_template, session
from .auth import login_required

ayuda_bp = Blueprint("ayuda", __name__)


@ayuda_bp.route("/ayuda")
@login_required()
def index():
    return render_template(
        "ayuda.html",
        username=session["username"],
        role=session["role"],
    )
