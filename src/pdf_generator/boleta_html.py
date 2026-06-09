"""
boleta_html.py
--------------
Genera la Boleta de Evaluación como PDF usando un template HTML/CSS
renderizado con Playwright (Chromium headless).

Ventajas sobre el enfoque PIL:
    · CSS flexbox/grid controla el layout — sin coordenadas píxel a píxel.
    · Ajustes de diseño se hacen en boleta.html (CSS estándar).
    · Previsualización inmediata en cualquier navegador.
    · Texto que desborda se maneja automáticamente (overflow, text-overflow).
"""

import base64
import io
from pathlib import Path

import qrcode
import qrcode.constants
from jinja2 import Environment, FileSystemLoader
from PIL import Image
from playwright.sync_api import sync_playwright

# ── Rutas ─────────────────────────────────────────────────────────────────────
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "docs" / "templates"
_TEMPLATE_HTML = _TEMPLATES_DIR / "boleta.html"

# ── Formateo de fechas ────────────────────────────────────────────────────────
_MES_LARGO = {
    1:"enero", 2:"febrero", 3:"marzo", 4:"abril",
    5:"mayo", 6:"junio", 7:"julio", 8:"agosto",
    9:"septiembre", 10:"octubre", 11:"noviembre", 12:"diciembre",
}
_MES_CORTO = {
    1:"ene", 2:"feb", 3:"mar", 4:"abr",
    5:"may", 6:"jun", 7:"jul", 8:"ago",
    9:"sep", 10:"oct", 11:"nov", 12:"dic",
}

def _fmt_largo(fecha: str) -> str:
    try:
        d, m, y = fecha.strip().split("/")
        return f"{int(d)} de {_MES_LARGO[int(m)]} de {y}"
    except Exception:
        return fecha

def _fmt_corto(fecha: str) -> str:
    try:
        d, m, y = fecha.strip().split("/")
        return f"{int(d):02d} {_MES_CORTO[int(m)]} {y}"
    except Exception:
        return fecha


# ── QR como data URL base64 ───────────────────────────────────────────────────

def _qr_data_url(folio: str) -> str:
    """
    Genera el QR apuntando al verificador web y lo retorna como data URL base64 (PNG).
    Al escanear abre el verificador con el folio pre-cargado.
    """
    payload = f"http://localhost:5000/verificar?folio={folio}"
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=6,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _template_data_url(template_path: Path) -> str:
    """Convierte un PNG a data URL base64."""
    with open(template_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    suffix = template_path.suffix.lower().lstrip(".")
    mime = "png" if suffix == "png" else "jpeg"
    return f"data:image/{mime};base64,{b64}"


def _img_data_url(path: Path) -> str:
    """Alias legible de _template_data_url."""
    return _template_data_url(path)


# ── Contexto Jinja2 ───────────────────────────────────────────────────────────

def _build_context(record: dict, signature_hex: str, templates_dir: Path) -> dict:
    """Construye el diccionario de variables para el template Jinja2."""
    folio     = record.get("Folio Verificación", "")
    modulo    = record.get("Módulo", "Único").strip()
    if modulo in ("", "Único"):
        modulo = record.get("Curso", "")

    resultado = record.get("Resultado", "—").strip()
    cal       = str(record.get("Calificación (0-10)", "—"))

    inicio  = _fmt_corto(record.get("Fecha de Inicio",  ""))
    termino = _fmt_corto(record.get("Fecha de Término", ""))

    return {
        "logo_url":      _img_data_url(templates_dir / "pasitos_logo.png"),
        "text_url":      _img_data_url(templates_dir / "pasitos_text.png"),
        "no_cert":       record.get("No. de Certificado", ""),
        "fecha_emision": _fmt_largo(record.get("Fecha de Emisión", "")),
        "nombre":        record.get("Nombre Completo", ""),
        "curp":          record.get("CURP", ""),
        "programa":      record.get("Curso", ""),
        "periodo":       f"{inicio} al {termino}",
        "duracion":      record.get("Duración (horas)", "—"),
        "modalidad":     record.get("Modalidad", "—"),
        "folio":         folio,
        "qr_data_url":   _qr_data_url(folio),
        "calificacion":  cal,
        "modulos": [
            {
                "modulo":       modulo,
                "calificacion": cal,
                "resultado":    resultado,
            }
        ],
    }


# ── Renderizado HTML → PDF ────────────────────────────────────────────────────

def render_boleta_html(record: dict, signature_hex: str,
                       templates_dir: Path) -> str:
    """
    Renderiza el template Jinja2 con los datos del participante.

    Returns:
        String HTML listo para pasar a Playwright.
    """
    env      = Environment(loader=FileSystemLoader(str(_TEMPLATE_HTML.parent)))
    template = env.get_template(_TEMPLATE_HTML.name)
    ctx      = _build_context(record, signature_hex, templates_dir)
    return template.render(**ctx)


def build_boleta_html(
    record: dict,
    signature_hex: str,
    output_dir: str | Path,
    templates_dir: str | Path = "docs/templates",
) -> Path:
    """
    Genera el PDF de la Boleta de Evaluación usando HTML/CSS + Playwright.
    """
    folio    = record.get("Folio Verificación", "boleta").replace("/", "-")
    out_path = Path(output_dir) / f"boleta_{folio}.pdf"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    html_content = render_boleta_html(record, signature_hex, Path(templates_dir))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        page.pdf(
            path=str(out_path),
            width="1280px",
            height="853px",
            print_background=True,
        )
        browser.close()

    return out_path


def build_boleta_preview(
    record: dict,
    signature_hex: str,
    output_path: str | Path,
    templates_dir: str | Path = "docs/templates",
) -> Path:
    """
    Genera un PNG de preview de la boleta (útil para revisión rápida).
    """
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    html_content = render_boleta_html(record, signature_hex, Path(templates_dir))

    with sync_playwright() as p:
        browser  = p.chromium.launch()
        page     = browser.new_page(viewport={"width": 1280, "height": 853})
        page.set_content(html_content, wait_until="networkidle")
        page.screenshot(path=str(out_path), full_page=False)
        browser.close()

    return out_path
