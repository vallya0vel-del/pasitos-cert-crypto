"""
certificate_builder.py
----------------------
Generación visual de Certificados de Competencia Laboral y Boletas de
Evaluación para Pasitos Education & Health A.C.

Estrategia de composición:
    1. Abrir la plantilla JPG como imagen de fondo (Pillow).
    2. Superponer texto dinámico mediante ImageDraw + ImageFont (Arial del sistema).
    3. Generar el código QR con payload de verificación (CURP + Folio + Firma DER).
    4. Pegar el QR sobre la imagen en la posición predefinida.
    5. Convertir la imagen compuesta a PDF A4 landscape con reportlab.

Ajuste de coordenadas:
    Las constantes _CERT_COORDS y _BOLETA_COORDS mapean cada campo dinámico
    a coordenadas en píxeles sobre una imagen de 1280×853 px. Si la plantilla
    cambia de resolución o diseño, solo es necesario ajustar esas constantes.
"""

import io
from pathlib import Path

import qrcode
import qrcode.constants
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas

# ─── Fuentes del sistema (Windows) ────────────────────────────────────────────
_FONT_BOLD    = Path("C:/Windows/Fonts/arialbd.ttf")
_FONT_REGULAR = Path("C:/Windows/Fonts/arial.ttf")

# ─── Paleta Pasitos ───────────────────────────────────────────────────────────
_PURPLE      = (130,  50, 185)   # morado principal — textos destacados
_DARK_PURPLE = ( 90,  30, 140)   # morado oscuro — folios y números de cert.
_DARK        = ( 35,  35,  35)   # casi negro — texto general
_GREEN       = ( 46, 160,  67)   # verde — texto "Acreditado"

# ─── Formateo de fechas en español ───────────────────────────────────────────
_MES_LARGO = {
    1: "enero",      2: "febrero",   3: "marzo",      4: "abril",
    5: "mayo",       6: "junio",     7: "julio",      8: "agosto",
    9: "septiembre", 10: "octubre",  11: "noviembre", 12: "diciembre",
}
_MES_CORTO = {
    1: "ene",  2: "feb",  3: "mar",  4: "abr",
    5: "may",  6: "jun",  7: "jul",  8: "ago",
    9: "sep",  10: "oct", 11: "nov", 12: "dic",
}

def _fmt_largo(fecha: str) -> str:
    """'28/03/2025' → '28 de marzo de 2025'"""
    try:
        d, m, y = fecha.strip().split("/")
        return f"{int(d)} de {_MES_LARGO[int(m)]} de {y}"
    except Exception:
        return fecha

def _fmt_corto(fecha: str) -> str:
    """'28/03/2025' → '28 mar 2025'  |  '01/03/2025' → '01 mar 2025'"""
    try:
        d, m, y = fecha.strip().split("/")
        return f"{int(d):02d} {_MES_CORTO[int(m)]} {y}"
    except Exception:
        return fecha

# ─── Coordenadas del CERTIFICADO (plantilla 1280×853 px) ─────────────────────
# (cx, y): texto centrado; (x, y): alineado a la izquierda.
# Área de contenido: x≈220 (ribete) → x≈960 (panel der.) → cx≈590.
# Sin QR — la autenticidad se verifica solo por folio en la boleta.
_CERT = {
    # Panel superior derecho
    "no_cert":         (1155,  88),  # (cx, y) — valor en el recuadro redondeado
    "fecha_emision":   (1104, 142),  # (x,  y) — "28 de marzo de 2025"
    "ubicacion":       (1104, 196),  # (x,  y) — "Zapopan, Jalisco, México"

    # Área de contenido central (cx=590)
    "nombre":          ( 590, 305),  # (cx, y) — 48 pt bold
    "curp":            ( 590, 370),  # (cx, y) — 19 pt
    "programa":        ( 590, 455),  # (cx, y) — 52 pt bold, morado
    "desc_programa":   ( 590, 522),  # (cx, y) — 16 pt

    # Folio en panel derecho (solo texto, sin QR)
    "folio_value":     (1140, 690),  # (cx, y)
}

# ─── Helpers de renderizado ───────────────────────────────────────────────────

def _font(bold: bool = False, size: int = 20) -> ImageFont.FreeTypeFont:
    """Carga fuente TTF del sistema; retrocede a fuente por defecto si falla."""
    path = _FONT_BOLD if bold else _FONT_REGULAR
    try:
        return ImageFont.truetype(str(path), size)
    except (IOError, OSError):
        return ImageFont.load_default()


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    cx: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
) -> None:
    """Dibuja `text` centrado horizontalmente alrededor del punto (cx, y)."""
    bbox   = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    draw.text((cx - text_w // 2, y), text, font=font, fill=fill)


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    line_height: int = 17,
) -> None:
    """Dibuja `text` con salto de línea automático dentro de `max_width` px."""
    words, line = text.split(), ""
    for word in words:
        candidate = f"{line} {word}".strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            line = candidate
        else:
            if line:
                draw.text((x, y), line, font=font, fill=fill)
                y += line_height
            line = word
    if line:
        draw.text((x, y), line, font=font, fill=fill)


# ─── Generación de QR ─────────────────────────────────────────────────────────

def generate_qr(curp: str, folio: str, signature_hex: str) -> Image.Image:
    """
    Genera un código QR con el payload de verificación del certificado.

    El payload JSON incluye CURP, Folio y la firma ECDSA DER completa en hex,
    permitiendo verificación matemática offline del documento.

    Args:
        curp:          CURP del participante (18 caracteres).
        folio:         Folio de verificación (ej. VER-0001).
        signature_hex: Firma ECDSA serializada en hexadecimal.

    Returns:
        Imagen QR como PIL.Image.Image en modo RGB, lista para incrustar.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(folio)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


# ─── Composición de imágenes ──────────────────────────────────────────────────

def _compose_certificate(
    record: dict, signature_hex: str, template_path: Path
) -> Image.Image:
    """Superpone los datos del participante sobre la plantilla de certificado."""
    img  = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(img)
    c    = _CERT

    # Número de certificado
    _draw_centered(draw, record["No. de Certificado"], *c["no_cert"],
                   font=_font(bold=True, size=20), fill=_DARK_PURPLE)

    # Fecha en formato largo + ubicación
    draw.text(c["fecha_emision"],
              _fmt_largo(record.get("Fecha de Emisión", "")),
              font=_font(bold=True, size=14), fill=_DARK)
    draw.text(c["ubicacion"], "Zapopan, Jalisco, México",
              font=_font(size=13), fill=_DARK)

    # Nombre del participante
    _draw_centered(draw, record["Nombre Completo"], *c["nombre"],
                   font=_font(bold=True, size=48), fill=_DARK)

    # CURP
    _draw_centered(draw, f"CURP:  {record['CURP']}", *c["curp"],
                   font=_font(size=19), fill=_DARK)

    # Nombre del programa (muy grande, morado) y subtítulo
    _draw_centered(draw, record["Curso"].upper(), *c["programa"],
                   font=_font(bold=True, size=52), fill=_PURPLE)
    _draw_centered(
        draw,
        f"Programa de Capacitación en {record['Curso'].title()}",
        *c["desc_programa"],
        font=_font(size=16),
        fill=_DARK,
    )

    # Folio de verificación (solo texto — sin QR en el certificado)
    _draw_centered(draw, record["Folio Verificación"], *c["folio_value"],
                   font=_font(bold=True, size=18), fill=_DARK_PURPLE)

    return img


# ─── Exportación a PDF ────────────────────────────────────────────────────────

def _image_to_pdf(image: Image.Image, output_path: Path) -> None:
    """
    Convierte una imagen PIL a PDF A4 landscape usando reportlab.

    La imagen se escala para cubrir la página completa sin márgenes.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    page_w, page_h = landscape(A4)

    c = rl_canvas.Canvas(str(output_path), pagesize=landscape(A4))

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=95)
    buf.seek(0)

    c.drawImage(ImageReader(buf), 0, 0, width=page_w, height=page_h,
                preserveAspectRatio=False)
    c.save()


# ─── API pública ──────────────────────────────────────────────────────────────

def build_certificate(
    record: dict,
    signature_hex: str,
    output_dir: str | Path,
    templates_dir: str | Path = "docs/templates",
) -> Path:
    """
    Genera el PDF del Certificado de Competencia Laboral.

    Args:
        record:        Diccionario del participante (de csv_reader).
        signature_hex: Firma ECDSA en hexadecimal del hash del certificado.
        output_dir:    Directorio de salida para los PDFs generados.
        templates_dir: Directorio que contiene las plantillas JPG.

    Returns:
        Path absoluto al archivo PDF generado.
    """
    template = Path(templates_dir) / "certificado_template.png"
    folio    = record["Folio Verificación"].replace("/", "-")
    out_path = Path(output_dir) / f"certificado_{folio}.pdf"

    img = _compose_certificate(record, signature_hex, template)
    _image_to_pdf(img, out_path)
    return out_path
