"""
routes/admin.py — Gestión de usuarios (solo ADMIN)
"""

import sys
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from .auth import login_required

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from auth.auth_manager import _USER_DB, Role, hash_password

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/usuarios")
@login_required(roles=["admin"])
def usuarios():
    users = [
        {"username": u, "role": data["role"].value}
        for u, data in _USER_DB.items()
    ]
    return render_template(
        "admin_usuarios.html",
        users=users,
        username=session["username"],
        role=session["role"],
    )


@admin_bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@login_required(roles=["admin"])
def nuevo_usuario():
    error = None
    if request.method == "POST":
        uname    = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role_str = request.form.get("role", "viewer")

        if not uname or not password:
            error = "Todos los campos son obligatorios."
        elif uname in _USER_DB:
            error = f"El usuario '{uname}' ya existe."
        elif len(password) < 8:
            error = "La contraseña debe tener al menos 8 caracteres."
        else:
            try:
                role = Role(role_str)
            except ValueError:
                error = "Rol no válido."
            else:
                _USER_DB[uname] = {
                    "password_hash": hash_password(password),
                    "role": role,
                }
                flash(f"Usuario '{uname}' creado con rol {role.value.upper()}.", "success")
                return redirect(url_for("admin.usuarios"))

    return render_template(
        "admin_nuevo_usuario.html",
        error=error,
        username=session["username"],
        role=session["role"],
    )


@admin_bp.route("/usuarios/eliminar/<uname>", methods=["POST"])
@login_required(roles=["admin"])
def eliminar_usuario(uname):
    if uname == session["username"]:
        flash("No puedes eliminar tu propio usuario.", "error")
    elif uname not in _USER_DB:
        flash(f"El usuario '{uname}' no existe.", "error")
    else:
        del _USER_DB[uname]
        flash(f"Usuario '{uname}' eliminado.", "success")
    return redirect(url_for("admin.usuarios"))
