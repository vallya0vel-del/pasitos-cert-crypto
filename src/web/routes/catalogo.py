"""
routes/catalogo.py — Gestión del catálogo de cursos
"""

import csv as csv_module
import io
from pathlib import Path

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, Response,
)

from .auth import login_required

catalogo_bp = Blueprint("catalogo", __name__, url_prefix="/catalogo")

_BASE        = Path(__file__).parent.parent.parent.parent
_CATALOGO    = _BASE / "data" / "catalogo_cursos.csv"

_FIELDS      = ["ID Curso", "Nombre del Curso", "Tipo / Formato",
                "Duración (horas)", "Modalidad", "Descripción", "Estado"]

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _read_cursos() -> list[dict]:
    if not _CATALOGO.exists():
        return []
    with _CATALOGO.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv_module.reader(f))
    # Detect header row
    header_idx = None
    for i, row in enumerate(rows):
        if any("ID Curso" in c for c in row):
            header_idx = i
            break
    if header_idx is None:
        return []
    headers = [h.strip() for h in rows[header_idx]]
    cursos = []
    for row in rows[header_idx + 1:]:
        if not any(c.strip() for c in row):
            continue
        cursos.append({headers[i]: (row[i].strip() if i < len(row) else "") for i in range(len(headers))})
    return cursos


def _write_cursos(cursos: list[dict]) -> None:
    _CATALOGO.parent.mkdir(parents=True, exist_ok=True)
    with _CATALOGO.open("w", encoding="utf-8-sig", newline="") as f:
        f.write("PASITOS EDUCATION & HEALTH A.C. — Catálogo de Cursos Activos,,,,,, \n")
        f.write(",,,,,, \n")
        writer = csv_module.DictWriter(f, fieldnames=_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(cursos)


def _next_id(cursos: list[dict]) -> str:
    nums = []
    for c in cursos:
        try:
            nums.append(int(c.get("ID Curso", "C-000").replace("C-", "")))
        except ValueError:
            pass
    return f"C-{(max(nums, default=0) + 1):03d}"


# ─── Rutas ────────────────────────────────────────────────────────────────────

@catalogo_bp.route("/")
@login_required()
def index():
    cursos = _read_cursos()
    return render_template(
        "catalogo.html",
        cursos=cursos,
        username=session["username"],
        role=session["role"],
    )


@catalogo_bp.route("/nuevo", methods=["GET", "POST"])
@login_required(roles=["admin", "operator"])
def nuevo():
    error = None
    cursos = _read_cursos()

    if request.method == "POST":
        nombre    = request.form.get("nombre", "").strip()
        tipo      = request.form.get("tipo", "").strip()
        duracion  = request.form.get("duracion", "").strip()
        modalidad = request.form.get("modalidad", "").strip()
        desc      = request.form.get("descripcion", "").strip()
        estado    = request.form.get("estado", "Activo").strip()

        if not nombre:
            error = "El nombre del curso es obligatorio."
        else:
            new_id = _next_id(cursos)
            cursos.append({
                "ID Curso":          new_id,
                "Nombre del Curso":  nombre,
                "Tipo / Formato":    tipo,
                "Duración (horas)":  duracion,
                "Modalidad":         modalidad,
                "Descripción":       desc,
                "Estado":            estado,
            })
            _write_cursos(cursos)
            flash(f"Curso '{nombre}' ({new_id}) creado exitosamente.", "success")
            return redirect(url_for("catalogo.index"))

    return render_template(
        "catalogo_form.html",
        mode="nuevo",
        curso=None,
        error=error,
        username=session["username"],
        role=session["role"],
    )


@catalogo_bp.route("/editar/<curso_id>", methods=["GET", "POST"])
@login_required(roles=["admin", "operator"])
def editar(curso_id: str):
    cursos = _read_cursos()
    idx    = next((i for i, c in enumerate(cursos) if c.get("ID Curso") == curso_id), None)

    if idx is None:
        flash(f"Curso '{curso_id}' no encontrado.", "error")
        return redirect(url_for("catalogo.index"))

    error = None

    if request.method == "POST":
        cursos[idx]["Nombre del Curso"] = request.form.get("nombre", "").strip()
        cursos[idx]["Tipo / Formato"]   = request.form.get("tipo", "").strip()
        cursos[idx]["Duración (horas)"] = request.form.get("duracion", "").strip()
        cursos[idx]["Modalidad"]        = request.form.get("modalidad", "").strip()
        cursos[idx]["Descripción"]      = request.form.get("descripcion", "").strip()
        cursos[idx]["Estado"]           = request.form.get("estado", "Activo").strip()

        if not cursos[idx]["Nombre del Curso"]:
            error = "El nombre del curso es obligatorio."
        else:
            _write_cursos(cursos)
            flash(f"Curso '{cursos[idx]['Nombre del Curso']}' actualizado.", "success")
            return redirect(url_for("catalogo.index"))

    return render_template(
        "catalogo_form.html",
        mode="editar",
        curso=cursos[idx],
        error=error,
        username=session["username"],
        role=session["role"],
    )


@catalogo_bp.route("/eliminar/<curso_id>", methods=["POST"])
@login_required(roles=["admin"])
def eliminar(curso_id: str):
    cursos = _read_cursos()
    before = len(cursos)
    cursos = [c for c in cursos if c.get("ID Curso") != curso_id]
    if len(cursos) < before:
        _write_cursos(cursos)
        flash(f"Curso {curso_id} eliminado.", "success")
    else:
        flash(f"Curso '{curso_id}' no encontrado.", "error")
    return redirect(url_for("catalogo.index"))


@catalogo_bp.route("/exportar")
@login_required()
def exportar():
    cursos = _read_cursos()
    buf = io.StringIO()
    writer = csv_module.DictWriter(buf, fieldnames=_FIELDS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(cursos)
    return Response(
        buf.getvalue().encode("utf-8-sig"),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=catalogo_cursos_pasitos.csv"},
    )
