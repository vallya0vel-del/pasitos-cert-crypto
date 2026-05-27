"""
csv_reader.py
-------------
Procesamiento del registro de participantes en cursos de Pasitos.

Estrategia de detección dinámica de encabezados:
    El CSV exportado desde Excel incluye filas de título y sección vacías
    antes de los encabezados reales. Se localiza la fila que contiene el
    anchor esperado para posicionarse correctamente sin depender de índices
    de fila fijos.

Seguridad:
    No se persiste ni transmite información personal; solo se retornan los
    registros filtrados en memoria para su posterior firma y emisión.
"""

import csv
import hashlib
from pathlib import Path

# ─── Constantes de detección ──────────────────────────────────────────────────
_REGISTROS_ANCHOR = "Nombre Completo"   # Columna que marca los encabezados reales
_CATALOGO_ANCHOR  = "ID Curso"          # Columna que marca los encabezados del catálogo
_RESULT_FIELD     = "Resultado"
_RESULT_VALUE     = "Acreditado"


# ─── Helpers internos ─────────────────────────────────────────────────────────

def _find_header_row(rows: list[list[str]], anchor: str) -> int:
    """
    Localiza el índice de la fila de encabezados reales buscando `anchor`.

    Raises:
        ValueError: Si no se encuentra ninguna fila con el anchor indicado.
    """
    for i, row in enumerate(rows):
        if any(anchor in cell for cell in row):
            return i
    raise ValueError(
        f"Encabezados no encontrados. Se esperaba una columna con '{anchor}'."
    )


def _rows_to_dicts(rows: list[list[str]], header_idx: int) -> list[dict]:
    """Convierte filas crudas a lista de diccionarios usando la fila de headers."""
    headers = [h.strip() for h in rows[header_idx]]
    records = []
    for row in rows[header_idx + 1:]:
        if not any(cell.strip() for cell in row):
            continue
        record = {
            headers[i]: (row[i].strip() if i < len(row) else "")
            for i in range(len(headers))
        }
        records.append(record)
    return records


# ─── API pública ──────────────────────────────────────────────────────────────

def read_acreditados(csv_path: str | Path) -> list[dict]:
    """
    Lee el CSV de registros y retorna solo los participantes Acreditados.

    La función detecta dinámicamente dónde comienzan los encabezados reales
    (buscando la columna 'Nombre Completo'), ignorando las filas de título y
    sección que anteceden al área de datos.

    Args:
        csv_path: Ruta al archivo CSV exportado desde el registro de cursos.

    Returns:
        Lista de diccionarios; cada uno representa un participante acreditado.
        Las claves corresponden a los encabezados del CSV.

    Raises:
        FileNotFoundError: Si el archivo no existe en la ruta indicada.
        ValueError: Si no se encuentran los encabezados esperados.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {path}")

    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    header_idx = _find_header_row(rows, _REGISTROS_ANCHOR)
    all_records = _rows_to_dicts(rows, header_idx)

    return [
        r for r in all_records
        if r.get(_RESULT_FIELD, "").strip() == _RESULT_VALUE
    ]


def read_catalogo(csv_path: str | Path) -> dict[str, dict]:
    """
    Lee el catálogo de cursos activos.

    Returns:
        Diccionario indexado por 'Nombre del Curso'; cada valor es un dict
        con los campos del catálogo (Duración, Modalidad, etc.).
        Retorna dict vacío si el archivo no existe.
    """
    path = Path(csv_path)
    if not path.exists():
        return {}

    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    try:
        header_idx = _find_header_row(rows, _CATALOGO_ANCHOR)
    except ValueError:
        return {}

    records = _rows_to_dicts(rows, header_idx)
    return {r.get("Nombre del Curso", ""): r for r in records if r.get("Nombre del Curso")}


def enrich_with_catalog(records: list[dict], catalogo: dict[str, dict]) -> None:
    """
    Enriquece cada registro de participante con datos del catálogo de cursos.

    Agrega los campos 'Duración (horas)' y 'Modalidad' al registro si no
    están presentes, tomándolos del catálogo según el nombre del curso.
    La modificación es en sitio (in-place).

    Args:
        records:  Lista de registros obtenida con read_acreditados().
        catalogo: Diccionario obtenido con read_catalogo().
    """
    for record in records:
        curso = record.get("Curso", "")
        curso_data = catalogo.get(curso, {})
        record.setdefault("Duración (horas)", curso_data.get("Duración (horas)", "—"))
        record.setdefault("Modalidad", curso_data.get("Modalidad", "—"))


def generate_certificate_hash(record: dict) -> str:
    """
    Genera un hash SHA-256 que identifica unívocamente un certificado.

    Concatena CURP + Curso + Folio Verificación separados por '|'.
    Esta cadena canónica es la que se firma digitalmente con ECDSA, garantizando
    que cualquier alteración de los datos invalide la firma (no-repudio).

    Args:
        record: Diccionario de un participante obtenido con read_acreditados().

    Returns:
        Hash SHA-256 en hexadecimal (64 caracteres).

    Raises:
        ValueError: Si alguno de los tres campos está vacío.
    """
    curp  = record.get("CURP", "").strip()
    curso = record.get("Curso", "").strip()
    folio = record.get("Folio Verificación", "").strip()

    if not all([curp, curso, folio]):
        raise ValueError(
            f"Registro incompleto para hash — "
            f"CURP='{curp}', Curso='{curso}', Folio='{folio}'"
        )

    raw = f"{curp}|{curso}|{folio}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
