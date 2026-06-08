"""
routes/verificar.py — Verificación pública de certificados
"""

import json
import hashlib
from pathlib import Path
from flask import Blueprint, render_template, request

verificar_bp = Blueprint("verificar", __name__)

_BASE   = Path(__file__).parent.parent.parent.parent
_JSON   = _BASE / "output" / "certificados.json"
_PUB    = _BASE / "keys" / "pasitos_public.pem"


@verificar_bp.route("/verificar", methods=["GET", "POST"])
def verificar():
    result = None
    folio_query = ""

    if request.method == "POST":
        folio_query = request.form.get("folio", "").strip().upper()
        result = _verificar_folio(folio_query)
    elif request.method == "GET" and request.args.get("folio"):
        folio_query = request.args.get("folio", "").strip().upper()
        result = _verificar_folio(folio_query)

    return render_template("verificar.html", result=result, folio=folio_query)


def _verificar_folio(folio: str) -> dict:
    """Verifica un folio y retorna un dict con el resultado."""
    import sys
    sys.path.insert(0, str(_BASE / "src"))

    if not _JSON.exists():
        return {"estado": "error", "mensaje": "No existe un registro de certificados en el sistema."}

    try:
        registro = json.loads(_JSON.read_text("utf-8"))
    except Exception as e:
        return {"estado": "error", "mensaje": f"Error al leer el registro: {e}"}

    entry = registro.get(folio)
    if entry is None:
        return {
            "estado": "no_encontrado",
            "mensaje": f"El folio '{folio}' no se encuentra en el registro.",
        }

    # Recalcular hash canónico
    curp  = entry.get("curp",  "").strip()
    curso = entry.get("curso", "").strip()
    hash_recalculado = hashlib.sha256(f"{curp}|{curso}|{folio}".encode("utf-8")).hexdigest()
    hash_almacenado  = entry.get("hash", "")

    if hash_recalculado != hash_almacenado:
        return {
            "estado": "invalido",
            "mensaje": "El hash del registro no coincide. El documento puede haber sido alterado.",
            "entry": entry,
        }

    if not _PUB.exists():
        return {
            "estado": "error",
            "mensaje": "No se encontró la llave pública en el sistema.",
            "entry": entry,
        }

    try:
        from crypto.keys_manager import load_public_key, verify_signature
        pub_key    = load_public_key(_PUB)
        firma_bytes = bytes.fromhex(entry.get("firma_hex", ""))
        valida      = verify_signature(pub_key, hash_recalculado.encode("utf-8"), firma_bytes)
    except Exception as e:
        return {"estado": "error", "mensaje": f"Error al verificar la firma ECDSA: {e}", "entry": entry}

    if valida:
        return {"estado": "valido", "entry": entry, "folio": folio}
    else:
        return {
            "estado": "invalido",
            "mensaje": "La firma ECDSA no es válida. El certificado no fue emitido por Pasitos.",
            "entry": entry,
        }
