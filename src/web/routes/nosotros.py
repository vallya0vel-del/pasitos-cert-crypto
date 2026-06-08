"""
routes/nosotros.py — Página "Acerca de" con info de Pasitos A.C.
"""

from flask import Blueprint, render_template, session
from .auth import login_required

nosotros_bp = Blueprint("nosotros", __name__)


@nosotros_bp.route("/nosotros")
@login_required()
def index():
    return render_template(
        "nosotros.html",
        username=session["username"],
        role=session["role"],
    )
