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
import json
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

# ─── Coordenadas de la BOLETA (plantilla 1280×853 px) ─────────────────────────
# La sección inferior (y ≥ 604) se reconstruye en _draw_boleta_bottom().
_BOLETA = {
    # Panel superior derecho
    "no_cert":         (1180,  42),  # (cx, y) — texto grande top-right
    "fecha_emision":   (1090, 120),  # (x,  y) — "28 de marzo de 2025"

    # Fila 1: participante
    "nombre":          ( 268, 178),  # (x, y)
    "curp":            ( 574, 178),
    "programa":        ( 858, 178),

    # Fila 2: curso
    "periodo":         ( 268, 244),  # (x, y) — "01 mar 2025 al 28 mar 2025"
    "duracion":        ( 586, 244),
    "modalidad":       ( 858, 244),

    # Sección inferior (ver _draw_boleta_bottom para estructura estática)
    "calificacion":    ( 185, 643),  # (cx ref, y_top) — número grande 58 pt
    "observaciones":   ( 360, 648),  # (x, y)
    "obs_max_width":   435,

    "folio_value":     ( 975, 733),  # (x,  y) — izq. de "FOLIO DE VERIFICACIÓN:"
    "qr_topleft":      (1082, 614),  # (x,  y) — dentro de caja verificación
    "qr_size":         138,
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
    payload = json.dumps(
        {
            "curp":   curp,
            "folio":  folio,
            "sig":    signature_hex,
            "iss":    "Pasitos Education & Health A.C.",
            "verify": "https://www.pasitosac.org/certificados",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=1,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


# ─── Reconstrucción de sección inferior de la boleta ─────────────────────────

def _draw_boleta_bottom(img: Image.Image, draw: ImageDraw.ImageDraw) -> None:
    """
    Reconstruye la sección inferior de la boleta que fue eliminada del template
    de Canva al desagrupar los elementos.  Dibuja:
      · 3 cajas redondeadas: Calificación / Observaciones / Verificación
      · Cabecera de cada caja: ícono circular + etiqueta + línea separadora
      · Texto estático de la caja de Verificación
      · Pie de página institucional con cuatro ítems
    Los valores dinámicos (calificación, observaciones, QR, folio) se superponen
    encima desde _compose_boleta().
    """
    BOX_BG  = (248, 245, 255)   # lavanda muy suave
    BORDER  = (196, 175, 228)   # morado claro
    SEP_CLR = (216, 200, 236)   # separador interior
    GRAY    = (140, 140, 140)   # texto del pie de página

    BOX_Y   = 604
    BOX_H   = 151
    BOX_BOT = BOX_Y + BOX_H    # 755
    SEP_Y   = BOX_Y + 36       # línea divisoria interna (640)
    RADIUS  = 10

    # Límites x de las 3 cajas (medidos del ejemplo)
    BOXES = [(55, 355), (355, 805), (808, 1262)]

    for bx1, bx2 in BOXES:
        draw.rounded_rectangle(
            [(bx1, BOX_Y), (bx2, BOX_BOT)],
            radius=RADIUS, fill=BOX_BG, outline=BORDER, width=2,
        )
        draw.line([(bx1 + 10, SEP_Y), (bx2 - 10, SEP_Y)],
                  fill=SEP_CLR, width=1)

    # Helper: ícono circular con símbolo centrado
    def _icon(cx: int, cy: int, r: int, sym: str, sym_sz: int) -> None:
        draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=_PURPLE)
        f  = _font(bold=True, size=sym_sz)
        bb = draw.textbbox((0, 0), sym, font=f)
        sw, sh = bb[2] - bb[0], bb[3] - bb[1]
        draw.text((cx - sw // 2, cy - sh // 2 - 1), sym,
                  font=f, fill=(255, 255, 255))

    LBL_FONT = _font(bold=True, size=9)
    ICY      = BOX_Y + 18      # cy del ícono (622)

    # Box 1 ── CALIFICACIÓN FINAL
    _icon(80, ICY, 14, "★", 11)
    draw.text((102, BOX_Y + 11), "CALIFICACIÓN FINAL",
              font=LBL_FONT, fill=_PURPLE)

    # Box 2 ── OBSERVACIONES DEL INSTRUCTOR
    _icon(380, ICY, 14, "≡", 14)
    draw.text((402, BOX_Y + 11), "OBSERVACIONES DEL INSTRUCTOR",
              font=LBL_FONT, fill=_PURPLE)

    # Box 3 ── VERIFICACIÓN DE AUTENTICIDAD
    _icon(832, ICY, 14, "✓", 12)
    draw.text((854, BOX_Y + 11), "VERIFICACIÓN DE AUTENTICIDAD",
              font=LBL_FONT, fill=_PURPLE)
    _draw_wrapped(
        draw,
        "Escanea el código QR o ingresa el folio de verificación en nuestra "
        "página para comprobar la autenticidad de este documento.",
        815, SEP_Y + 10,
        max_width=255, font=_font(size=10), fill=_DARK, line_height=14,
    )
    draw.text((815, BOX_BOT - 24), "FOLIO DE VERIFICACIÓN:",
              font=LBL_FONT, fill=_PURPLE)

    # Pie de página
    FOOT_Y  = BOX_BOT + 8      # 763
    FOOT_CY = (FOOT_Y + 842) // 2  # ≈ 802
    FOOT_TY = FOOT_Y + 6           # 769

    draw.line([(55, FOOT_Y), (1262, FOOT_Y)], fill=SEP_CLR, width=1)
    foot = _font(size=9)

    def _dot(cx: int, cy: int) -> None:
        draw.ellipse([(cx - 10, cy - 10), (cx + 10, cy + 10)], fill=BORDER)

    _dot(75, FOOT_CY)
    _draw_wrapped(draw,
        "Este documento forma parte integral del certificado DC-3 emitido "
        "por Pasitos Education & Health A.C., con validez oficial ante la STPS.",
        93, FOOT_TY, max_width=340, font=foot, fill=GRAY, line_height=13)

    _dot(473, FOOT_CY)
    draw.text((491, FOOT_CY - 6), "Zapopan, Jalisco, México",
              font=foot, fill=GRAY)

    _dot(755, FOOT_CY)
    _draw_wrapped(draw,
        "Documento emitido con firma digital. Protegido contra alteraciones.",
        773, FOOT_TY, max_width=270, font=foot, fill=GRAY, line_height=13)

    _dot(1087, FOOT_CY)
    draw.text((1105, FOOT_CY - 6), "www.pasitosac.org",
              font=_font(bold=True, size=9), fill=_PURPLE)


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


def _compose_boleta(
    record: dict, signature_hex: str, template_path: Path
) -> Image.Image:
    """Superpone los datos del participante sobre la plantilla de boleta."""
    img  = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Reconstruir sección inferior (eliminada del template en Canva)
    _draw_boleta_bottom(img, draw)

    b = _BOLETA

    # Número de certificado
    _draw_centered(draw, record["No. de Certificado"], *b["no_cert"],
                   font=_font(bold=True, size=18), fill=_DARK_PURPLE)

    # Fecha en formato largo
    draw.text(b["fecha_emision"],
              _fmt_largo(record.get("Fecha de Emisión", "")),
              font=_font(bold=True, size=13), fill=_DARK)

    # Fila 1: datos del participante
    draw.text(b["nombre"],   record["Nombre Completo"],
              font=_font(bold=True, size=14), fill=_DARK)
    draw.text(b["curp"],     record["CURP"],
              font=_font(bold=True, size=13), fill=_DARK)
    draw.text(b["programa"], record["Curso"],
              font=_font(bold=True, size=14), fill=_DARK)

    # Fila 2: datos del curso
    inicio  = _fmt_corto(record.get("Fecha de Inicio",  ""))
    termino = _fmt_corto(record.get("Fecha de Término", ""))
    draw.text(b["periodo"],
              f"{inicio} al {termino}",
              font=_font(size=13), fill=_DARK)
    draw.text(b["duracion"],
              f"{record.get('Duración (horas)', '—')} HRS",
              font=_font(size=13), fill=_DARK)
    draw.text(b["modalidad"],
              record.get("Modalidad", "—"),
              font=_font(size=13), fill=_DARK)

    # Calificación: número grande + "/10" dinámico + "✓ ACREDITADO"
    CAL_CX = b["calificacion"][0]
    score  = str(record.get("Calificación (0-10)", "—"))
    s_font = _font(bold=True, size=58)
    s_bb   = draw.textbbox((0, 0), score, font=s_font)
    s_w    = s_bb[2] - s_bb[0]
    s_x    = CAL_CX - s_w // 2
    s_y    = b["calificacion"][1]
    draw.text((s_x, s_y), score, font=s_font, fill=_DARK)
    draw.text((s_x + s_w + 4, s_y + 38), "/10",
              font=_font(size=16), fill=_DARK)
    a_font = _font(bold=True, size=13)
    a_text = "✓  ACREDITADO"
    a_bb   = draw.textbbox((0, 0), a_text, font=a_font)
    draw.text((CAL_CX - (a_bb[2] - a_bb[0]) // 2, s_y + 82),
              a_text, font=a_font, fill=_GREEN)

    # Observaciones del instructor
    obs = record.get("Observaciones", "").strip() or "—"
    _draw_wrapped(draw, obs, *b["observaciones"],
                  max_width=b["obs_max_width"],
                  font=_font(size=12), fill=_DARK, line_height=16)

    # Folio (left-aligned)
    draw.text(b["folio_value"], record["Folio Verificación"],
              font=_font(bold=True, size=15), fill=_DARK_PURPLE)

    # Código QR de autenticidad
    qr_img = generate_qr(record["CURP"], record["Folio Verificación"], signature_hex)
    qr_img = qr_img.resize((b["qr_size"], b["qr_size"]), Image.LANCZOS)
    img.paste(qr_img, b["qr_topleft"])

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


def build_boleta(
    record: dict,
    signature_hex: str,
    output_dir: str | Path,
    templates_dir: str | Path = "docs/templates",
) -> Path:
    """
    Genera el PDF de la Boleta de Evaluación por Competencias.

    Args:
        record:        Diccionario del participante (de csv_reader).
        signature_hex: Firma ECDSA en hexadecimal del hash del certificado.
        output_dir:    Directorio de salida para los PDFs generados.
        templates_dir: Directorio que contiene las plantillas JPG.

    Returns:
        Path absoluto al archivo PDF generado.
    """
    template = Path(templates_dir) / "boleta_template.png"
    folio    = record["Folio Verificación"].replace("/", "-")
    out_path = Path(output_dir) / f"boleta_{folio}.pdf"

    img = _compose_boleta(record, signature_hex, template)
    _image_to_pdf(img, out_path)
    return out_path
