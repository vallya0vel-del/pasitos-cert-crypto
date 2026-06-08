"""
routes/dashboard.py — Panel principal
"""

import json
from pathlib import Path
from flask import Blueprint, render_template, session

from .auth import login_required

dashboard_bp = Blueprint("dashboard", __name__)

_BASE   = Path(__file__).parent.parent.parent.parent
_OUTPUT = _BASE / "output" / "certificados.json"
_DATA   = _BASE / "data"


@dashboard_bp.route("/dashboard")
@login_required()
def index():
    stats = _build_stats()
    return render_template(
        "dashboard.html",
        username=session["username"],
        role=session["role"],
        stats=stats,
    )


def _build_stats() -> dict:
    """Lee certificados.json y CSVs para construir métricas del dashboard."""
    stats = {
        "total_emitidos": 0,
        "recientes": [],
        "por_curso": {},
        "total_registros": 0,
        "total_acreditados": 0,
    }

    # Certificados emitidos (firmas reales)
    if _OUTPUT.exists():
        try:
            registro = json.loads(_OUTPUT.read_text("utf-8"))
            stats["total_emitidos"] = len(registro)
            recientes = sorted(
                [{"folio": k, **v} for k, v in registro.items()],
                key=lambda x: x.get("fecha_emision", ""),
                reverse=True,
            )[:5]
            stats["recientes"] = recientes
            for entry in registro.values():
                curso = entry.get("curso", "Desconocido")
                stats["por_curso"][curso] = stats["por_curso"].get(curso, 0) + 1
        except Exception:
            pass

    # Totales del CSV
    csv_path = _DATA / "registros_cursos.csv"
    if csv_path.exists():
        import sys
        sys.path.insert(0, str(_BASE / "src"))
        try:
            from data_manager.csv_reader import read_acreditados
            import csv
            with csv_path.open(encoding="utf-8-sig", newline="") as f:
                all_rows = list(csv.reader(f))
            # Encontrar encabezado
            header_idx = None
            for i, row in enumerate(all_rows):
                if any("Nombre Completo" in c for c in row):
                    header_idx = i
                    break
            if header_idx is not None:
                data_rows = [r for r in all_rows[header_idx + 1:] if any(c.strip() for c in r)]
                stats["total_registros"] = len(data_rows)
            acreditados = read_acreditados(csv_path)
            stats["total_acreditados"] = len(acreditados)
        except Exception:
            pass

    return stats
