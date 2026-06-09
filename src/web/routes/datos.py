"""
routes/datos.py — Carga de CSV de registros y vista previa
"""

import csv as csv_module
import shutil
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash,
)

from .auth import login_required

datos_bp = Blueprint("datos", __name__, url_prefix="/datos")

_BASE      = Path(__file__).parent.parent.parent.parent
_DATA      = _BASE / "data"
_REGISTROS = _DATA / "registros_cursos.csv"

_ANCHOR    = "Nombre Completo"


def _read_all_rows() -> tuple[list[str], list[dict]]:
    """Returns (headers, all_rows_as_dicts) regardless of Acreditado status."""
    if not _REGISTROS.exists():
        return [], []
    with _REGISTROS.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv_module.reader(f))
    header_idx = None
    for i, row in enumerate(rows):
        if any(_ANCHOR in c for c in row):
            header_idx = i
            break
    if header_idx is None:
        return [], []
    headers = [h.strip() for h in rows[header_idx]]
    data = []
    for row in rows[header_idx + 1:]:
        if not any(c.strip() for c in row):
            continue
        data.append({headers[i]: (row[i].strip() if i < len(row) else "") for i in range(len(headers))})
    return headers, data


# ─── Rutas ────────────────────────────────────────────────────────────────────

@datos_bp.route("/")
@login_required()
def index():
    headers, registros = _read_all_rows()
    csv_exists = _REGISTROS.exists()
    return render_template(
        "datos.html",
        headers=headers,
        registros=registros,
        csv_exists=csv_exists,
        csv_name=_REGISTROS.name if csv_exists else None,
        username=session["username"],
        role=session["role"],
    )


@datos_bp.route("/subir", methods=["POST"])
@login_required(roles=["admin", "operator"])
def subir():
    f = request.files.get("archivo")
    if not f or not f.filename:
        flash("Selecciona un archivo CSV para subir.", "error")
        return redirect(url_for("datos.index"))

    if not f.filename.lower().endswith(".csv"):
        flash("Solo se aceptan archivos .csv", "error")
        return redirect(url_for("datos.index"))

    content = f.read().decode("utf-8-sig", errors="replace")

    # Validate that the file has the expected anchor column
    if _ANCHOR not in content:
        flash(
            f"El archivo no parece ser un registro válido de Pasitos "
            f"(no se encontró la columna '{_ANCHOR}').",
            "error",
        )
        return redirect(url_for("datos.index"))

    # Backup existing file
    if _REGISTROS.exists():
        ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup  = _DATA / f"registros_cursos_backup_{ts}.csv"
        shutil.copy2(_REGISTROS, backup)

    _DATA.mkdir(parents=True, exist_ok=True)
    _REGISTROS.write_text(content, encoding="utf-8-sig")

    # Count rows
    headers, registros = _read_all_rows()
    acreditados = sum(1 for r in registros if r.get("Resultado", "").strip() == "Acreditado")

    flash(
        f"CSV cargado exitosamente. {len(registros)} registro(s) encontrado(s), "
        f"{acreditados} acreditado(s).",
        "success",
    )
    return redirect(url_for("datos.index"))
