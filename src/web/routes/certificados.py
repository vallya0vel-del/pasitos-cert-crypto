"""
routes/certificados.py — Listado y emisión de certificados
"""

import io
import json
import threading
import zipfile
import csv as csv_module
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, send_file, abort, Response

from .auth import login_required

certificados_bp = Blueprint("certificados", __name__)

_BASE    = Path(__file__).parent.parent.parent.parent
_OUTPUT  = _BASE / "output"
_JSON    = _OUTPUT / "certificados.json"
_DATA    = _BASE / "data"
_KEYS    = _BASE / "keys"

# Estado de emisión en curso (simple, suficiente para demo single-user)
_emit_status: dict = {"running": False, "log": [], "done": False, "error": None}
_emit_lock = threading.Lock()


@certificados_bp.route("/certificados")
@login_required()
def index():
    registros = _load_registro()
    return render_template(
        "certificados.html",
        registros=registros,
        username=session["username"],
        role=session["role"],
    )


@certificados_bp.route("/emitir", methods=["GET", "POST"])
@login_required(roles=["admin", "operator"])
def emitir():
    csv_registros = _DATA / "registros_cursos.csv"
    csv_catalogo  = _DATA / "catalogo_cursos.csv"
    priv_exists   = (_KEYS / "pasitos_private.pem").exists()
    pub_exists    = (_KEYS / "pasitos_public.pem").exists()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "generar_llaves":
            if session["role"] != "admin":
                flash("Solo el ADMIN puede generar llaves.", "error")
                return redirect(url_for("certificados.emitir"))
            try:
                import sys
                sys.path.insert(0, str(_BASE / "src"))
                from crypto.keys_manager import generate_key_pair, save_private_key, save_public_key
                priv, pub = generate_key_pair()
                _KEYS.mkdir(parents=True, exist_ok=True)
                save_private_key(priv, _KEYS / "pasitos_private.pem", password=None)
                save_public_key(pub, _KEYS / "pasitos_public.pem")
                flash("Par de llaves ECDSA generado exitosamente.", "success")
            except Exception as e:
                flash(f"Error al generar llaves: {e}", "error")
            return redirect(url_for("certificados.emitir"))

        if action == "emitir":
            if not priv_exists or not pub_exists:
                flash("No existen llaves. Genera el par de llaves primero.", "error")
                return redirect(url_for("certificados.emitir"))
            with _emit_lock:
                if _emit_status["running"]:
                    flash("Ya hay una emisión en curso.", "warning")
                    return redirect(url_for("certificados.emitir"))
                _emit_status.update({"running": True, "log": [], "done": False, "error": None})
            t = threading.Thread(target=_run_emit, daemon=True)
            t.start()
            return redirect(url_for("certificados.emitir_status"))

    return render_template(
        "emitir.html",
        priv_exists=priv_exists,
        pub_exists=pub_exists,
        csv_ok=csv_registros.exists() and csv_catalogo.exists(),
        username=session["username"],
        role=session["role"],
    )


@certificados_bp.route("/emitir/status")
@login_required(roles=["admin", "operator"])
def emitir_status():
    return render_template(
        "emitir_status.html",
        username=session["username"],
        role=session["role"],
    )


@certificados_bp.route("/emitir/poll")
@login_required(roles=["admin", "operator"])
def emitir_poll():
    """Endpoint AJAX para que el frontend consulte el estado de la emisión."""
    with _emit_lock:
        data = dict(_emit_status)
    return jsonify(data)


def _run_emit():
    """Hilo de fondo que corre el proceso de emisión."""
    import sys
    sys.path.insert(0, str(_BASE / "src"))

    log = _emit_status["log"]

    try:
        from crypto.keys_manager import load_private_key, load_public_key, sign_data
        from data_manager.csv_reader import read_acreditados, read_catalogo, enrich_with_catalog, generate_certificate_hash
        from pdf_generator.certificate_html import build_certificate_html
        from pdf_generator.certificate_builder import merge_pdfs
        from pdf_generator.boleta_html import build_boleta_html

        _OUTPUT.mkdir(parents=True, exist_ok=True)
        templates_dir = _BASE / "docs" / "templates"

        log.append("Cargando llaves ECDSA...")
        priv = load_private_key(_KEYS / "pasitos_private.pem", password=None)
        pub  = load_public_key(_KEYS / "pasitos_public.pem")
        log.append("Llaves cargadas.")

        log.append("Leyendo registros CSV...")
        records  = read_acreditados(_DATA / "registros_cursos.csv")
        catalogo = read_catalogo(_DATA / "catalogo_cursos.csv")
        enrich_with_catalog(records, catalogo)
        log.append(f"{len(records)} participante(s) acreditado(s) encontrado(s).")

        # Cargar registro previo
        if _JSON.exists():
            existing = json.loads(_JSON.read_text("utf-8"))
        else:
            existing = {}

        emitidos = dict(existing)

        for i, record in enumerate(records, 1):
            nombre = record.get("Nombre Completo", "—")
            folio  = record.get("Folio Verificación", "—")
            log.append(f"[{i}/{len(records)}] Procesando: {nombre} ({folio})...")

            if folio in emitidos:
                log.append(f"  → Ya emitido anteriormente. Omitido.")
                continue

            cert_hash  = generate_certificate_hash(record)
            firma      = sign_data(priv, cert_hash.encode("utf-8"))
            firma_hex  = firma.hex()

            folio_safe  = folio.replace("/", "-")
            cert_path   = build_certificate_html(record, firma_hex, _OUTPUT, templates_dir)
            boleta_path = build_boleta_html(record, firma_hex, _OUTPUT, templates_dir)

            # Fusionar certificado + boleta en un único PDF descargable
            merged_path = _OUTPUT / f"documento_{folio_safe}.pdf"
            merge_pdfs([cert_path, boleta_path], merged_path)

            emitidos[folio] = {
                "nombre":       record.get("Nombre Completo", ""),
                "curp":         record.get("CURP", ""),
                "curso":        record.get("Curso", ""),
                "no_cert":      record.get("No. de Certificado", ""),
                "fecha_emision":record.get("Fecha de Emisión", ""),
                "calificacion": record.get("Calificación (0-10)", ""),
                "hash":         cert_hash,
                "firma_hex":    firma_hex,
            }
            log.append(f"  ✓ Certificado HTML, boleta y PDF combinado generados.")

        _JSON.write_text(json.dumps(emitidos, ensure_ascii=False, indent=2), encoding="utf-8")
        log.append(f"Registro guardado en {_JSON.name}.")
        log.append("¡Emisión completada exitosamente!")
        _emit_status["done"] = True

    except Exception as e:
        _emit_status["error"] = str(e)
        log.append(f"ERROR: {e}")
    finally:
        _emit_status["running"] = False


def _load_registro() -> list[dict]:
    if not _JSON.exists():
        return []
    try:
        data = json.loads(_JSON.read_text("utf-8"))
        result = []
        for folio, entry in data.items():
            entry["folio"] = folio
            result.append(entry)
        return sorted(result, key=lambda x: x.get("fecha_emision", ""), reverse=True)
    except Exception:
        return []


@certificados_bp.route("/descargar/<folio>")
@login_required()
def descargar(folio: str):
    """Sirve el PDF combinado (certificado + boleta) de un folio dado.
    Si el merged no existe aún, lo genera sobre la marcha."""
    import sys
    sys.path.insert(0, str(_BASE / "src"))

    folio_safe  = folio.strip().upper().replace("/", "-")
    merged      = _OUTPUT / f"documento_{folio_safe}.pdf"
    cert_path   = _OUTPUT / f"certificado_{folio_safe}.pdf"
    boleta_path = _OUTPUT / f"boleta_{folio_safe}.pdf"

    if not merged.exists():
        # Intentar construir el merged si ambas piezas existen
        if cert_path.exists() and boleta_path.exists():
            from pdf_generator.certificate_builder import merge_pdfs
            merge_pdfs([cert_path, boleta_path], merged)
        elif cert_path.exists():
            # Solo certificado disponible
            return send_file(cert_path, as_attachment=True,
                             download_name=f"certificado_{folio_safe}.pdf",
                             mimetype="application/pdf")
        else:
            abort(404)

    return send_file(merged, as_attachment=True,
                     download_name=f"Pasitos_{folio_safe}.pdf",
                     mimetype="application/pdf")


@certificados_bp.route("/eliminar/<folio>", methods=["POST"])
@login_required(roles=["admin"])
def eliminar(folio: str):
    """Elimina un certificado del registro JSON y borra sus PDFs."""
    folio      = folio.strip().upper()
    folio_safe = folio.replace("/", "-")

    if not _JSON.exists():
        flash("No existe registro de certificados.", "error")
        return redirect(url_for("certificados.index"))

    try:
        registro = json.loads(_JSON.read_text("utf-8"))
    except Exception as e:
        flash(f"Error al leer el registro: {e}", "error")
        return redirect(url_for("certificados.index"))

    if folio not in registro:
        flash(f"Folio '{folio}' no encontrado.", "error")
        return redirect(url_for("certificados.index"))

    del registro[folio]
    _JSON.write_text(json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")

    # Borrar PDFs asociados
    for pattern in [f"certificado_{folio_safe}.pdf",
                    f"boleta_{folio_safe}.pdf",
                    f"documento_{folio_safe}.pdf"]:
        p = _OUTPUT / pattern
        if p.exists():
            p.unlink()

    flash(f"Certificado {folio} eliminado correctamente.", "success")
    return redirect(url_for("certificados.index"))


# ─── Inline preview (serves PDF with Content-Disposition: inline) ─────────────

@certificados_bp.route("/ver/<folio>")
@login_required()
def ver(folio: str):
    """Sirve el PDF combinado para visualización en línea (sin descarga forzada)."""
    import sys
    sys.path.insert(0, str(_BASE / "src"))

    folio_safe  = folio.strip().upper().replace("/", "-")
    merged      = _OUTPUT / f"documento_{folio_safe}.pdf"
    cert_path   = _OUTPUT / f"certificado_{folio_safe}.pdf"
    boleta_path = _OUTPUT / f"boleta_{folio_safe}.pdf"

    if not merged.exists():
        if cert_path.exists() and boleta_path.exists():
            from pdf_generator.certificate_builder import merge_pdfs
            merge_pdfs([cert_path, boleta_path], merged)
        elif cert_path.exists():
            return send_file(cert_path, as_attachment=False, mimetype="application/pdf")
        else:
            abort(404)

    return send_file(merged, as_attachment=False, mimetype="application/pdf")


# ─── Re-emit single certificate ───────────────────────────────────────────────

@certificados_bp.route("/reemitir/<folio>", methods=["POST"])
@login_required(roles=["admin", "operator"])
def reemitir(folio: str):
    """Regenera los PDFs de un folio ya firmado (no vuelve a firmar)."""
    import sys
    sys.path.insert(0, str(_BASE / "src"))

    folio = folio.strip().upper()

    if not _JSON.exists():
        flash("No existe registro de certificados.", "error")
        return redirect(url_for("certificados.index"))

    try:
        registro = json.loads(_JSON.read_text("utf-8"))
    except Exception as e:
        flash(f"Error al leer el registro: {e}", "error")
        return redirect(url_for("certificados.index"))

    entry = registro.get(folio)
    if not entry:
        flash(f"Folio '{folio}' no encontrado en el registro.", "error")
        return redirect(url_for("certificados.index"))

    # Reconstruir un pseudo-record desde la entrada del JSON
    record = {
        "Nombre Completo":      entry.get("nombre", ""),
        "CURP":                 entry.get("curp", ""),
        "Curso":                entry.get("curso", ""),
        "No. de Certificado":   entry.get("no_cert", ""),
        "Fecha de Emisión":     entry.get("fecha_emision", ""),
        "Calificación (0-10)":  entry.get("calificacion", ""),
        "Folio Verificación":   folio,
        "Resultado":            "Acreditado",
        "Módulo":               "Único",
        "Fecha de Inicio":      "",
        "Fecha de Término":     entry.get("fecha_emision", ""),
        "Duración (horas)":     "—",
        "Modalidad":            "—",
    }

    templates_dir = _BASE / "docs" / "templates"
    firma_hex     = entry.get("firma_hex", "")
    folio_safe    = folio.replace("/", "-")

    try:
        from pdf_generator.certificate_html import build_certificate_html
        from pdf_generator.boleta_html import build_boleta_html
        from pdf_generator.certificate_builder import merge_pdfs

        cert_path   = build_certificate_html(record, firma_hex, _OUTPUT, templates_dir)
        boleta_path = build_boleta_html(record, firma_hex, _OUTPUT, templates_dir)
        merged_path = _OUTPUT / f"documento_{folio_safe}.pdf"
        merge_pdfs([cert_path, boleta_path], merged_path)

        flash(f"PDFs de {folio} regenerados correctamente.", "success")
    except Exception as e:
        flash(f"Error al regenerar PDFs: {e}", "error")

    return redirect(url_for("certificados.index"))


# ─── Export as CSV ────────────────────────────────────────────────────────────

@certificados_bp.route("/exportar/csv")
@login_required()
def exportar_csv():
    """Exporta el registro de certificados como archivo CSV."""
    registros = _load_registro()
    fields = ["folio", "no_cert", "nombre", "curp", "curso", "calificacion", "fecha_emision"]
    headers = ["Folio", "No. Certificado", "Nombre", "CURP", "Curso", "Calificación", "Fecha Emisión"]

    buf = io.StringIO()
    writer = csv_module.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    writer.writerow(dict(zip(fields, headers)))
    writer.writerows(registros)

    output = buf.getvalue().encode("utf-8-sig")
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=certificados_pasitos.csv"},
    )


# ─── Export all PDFs as ZIP ───────────────────────────────────────────────────

@certificados_bp.route("/exportar/zip")
@login_required()
def exportar_zip():
    """Descarga todos los PDFs combinados en un único archivo ZIP."""
    registros = _load_registro()
    if not registros:
        flash("No hay certificados para exportar.", "warning")
        return redirect(url_for("certificados.index"))

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in registros:
            folio_safe = r["folio"].replace("/", "-")
            merged = _OUTPUT / f"documento_{folio_safe}.pdf"
            cert   = _OUTPUT / f"certificado_{folio_safe}.pdf"

            if merged.exists():
                zf.write(merged, f"Pasitos_{folio_safe}.pdf")
            elif cert.exists():
                zf.write(cert, f"certificado_{folio_safe}.pdf")

    buf.seek(0)
    return send_file(
        buf,
        as_attachment=True,
        download_name="certificados_pasitos.zip",
        mimetype="application/zip",
    )
