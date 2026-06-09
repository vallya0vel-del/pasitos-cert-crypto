"""
certificate_html.py
-------------------
Genera el Certificado de Competencia Laboral como PDF usando HTML/CSS
renderizado con Playwright (Chromium headless), igual que la boleta.

Esto reemplaza el enfoque anterior basado en PIL + coordenadas píxel.
"""

import base64
import io
from pathlib import Path

import qrcode
import qrcode.constants
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

_TEMPLATE_NAME = "certificado.html"

_MES_LARGO = {
    1:"enero", 2:"febrero", 3:"marzo", 4:"abril",
    5:"mayo", 6:"junio", 7:"julio", 8:"agosto",
    9:"septiembre", 10:"octubre", 11:"noviembre", 12:"diciembre",
}


def _fmt_largo(fecha: str) -> str:
    try:
        d, m, y = fecha.strip().split("/")
        return f"{int(d)} de {_MES_LARGO[int(m)]} de {y}"
    except Exception:
        return fecha


def _qr_data_url(folio: str) -> str:
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


def _img_data_url(path: Path) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    suffix = path.suffix.lower().lstrip(".")
    mime = "png" if suffix == "png" else "jpeg"
    return f"data:image/{mime};base64,{b64}"


def _build_context(record: dict, templates_dir: Path) -> dict:
    folio = record.get("Folio Verificación", "")
    return {
        "logo_url":      _img_data_url(templates_dir / "pasitos_logo.png"),
        "text_url":      _img_data_url(templates_dir / "pasitos_text.png"),
        "no_cert":       record.get("No. de Certificado", ""),
        "fecha_emision": _fmt_largo(record.get("Fecha de Emisión", "")),
        "nombre":        record.get("Nombre Completo", ""),
        "curp":          record.get("CURP", ""),
        "programa":      record.get("Curso", ""),
        "folio":         folio,
        "qr_data_url":   _qr_data_url(folio),
    }


def render_certificado_html(record: dict, templates_dir: Path) -> str:
    env      = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template(_TEMPLATE_NAME)
    ctx      = _build_context(record, templates_dir)
    return template.render(**ctx)


def build_certificate_html(
    record: dict,
    signature_hex: str,
    output_dir: str | Path,
    templates_dir: str | Path = "docs/templates",
) -> Path:
    """
    Genera el PDF del Certificado de Competencia Laboral mediante HTML/CSS + Playwright.

    Args:
        record:        Diccionario del participante.
        signature_hex: Firma ECDSA (solo para compatibilidad de API; no se imprime en el cert).
        output_dir:    Directorio de salida.
        templates_dir: Directorio con certificado.html y assets.

    Returns:
        Path absoluto al PDF generado.
    """
    folio    = record.get("Folio Verificación", "cert").replace("/", "-")
    out_path = Path(output_dir) / f"certificado_{folio}.pdf"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    html = render_certificado_html(record, Path(templates_dir))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page    = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        page.pdf(
            path=str(out_path),
            width="1280px",
            height="853px",
            print_background=True,
        )
        browser.close()

    return out_path
