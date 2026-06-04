"""
verificar.py
------------
Herramienta CLI de verificación local de certificados digitales emitidos
por Pasitos Education & Health A.C.

Uso:
    python src/verificar.py <folio>
    python src/verificar.py VER-0001

Flujo de verificación:
    1. Lee output/certificados.json (registro de certificados emitidos).
    2. Busca el folio ingresado.
    3. Recalcula el hash SHA-256 canónico (CURP + Curso + Folio).
    4. Carga la llave pública ECDSA desde keys/pasitos_public.pem.
    5. Verifica la firma ECDSA almacenada contra el hash recalculado.
    6. Muestra resultado: VÁLIDO / INVÁLIDO / NO ENCONTRADO.
"""

import json
import sys
from pathlib import Path

# Agregar /src al path
sys.path.insert(0, str(Path(__file__).parent))

from crypto.keys_manager import load_public_key, verify_signature

_BASE_DIR      = Path(__file__).parent.parent
_REGISTRO_JSON = _BASE_DIR / "output" / "certificados.json"
_PUB_KEY_PATH  = _BASE_DIR / "keys" / "pasitos_public.pem"

_BANNER = """
╔══════════════════════════════════════════════════════╗
║      Pasitos Education & Health A.C.                 ║
║      Verificación de Certificado Digital             ║
╚══════════════════════════════════════════════════════╝
"""


def verificar(folio: str) -> None:
    print(_BANNER)
    folio = folio.strip().upper()

    # 1. Cargar registro
    if not _REGISTRO_JSON.exists():
        print("  ✗ No se encontró el registro de certificados.")
        print(f"    Ruta esperada: {_REGISTRO_JSON}\n")
        sys.exit(1)

    try:
        registro = json.loads(_REGISTRO_JSON.read_text("utf-8"))
    except Exception as e:
        print(f"  ✗ Error al leer el registro: {e}\n")
        sys.exit(1)

    # 2. Buscar folio
    entry = registro.get(folio)
    if entry is None:
        print(f"  ✗ Folio '{folio}' NO ENCONTRADO en el registro.\n")
        print("  El documento puede ser falso o el folio fue ingresado incorrectamente.")
        print()
        sys.exit(1)

    print(f"  Folio encontrado: {folio}")
    print(f"  Nombre          : {entry.get('nombre', '—')}")
    print(f"  CURP            : {entry.get('curp', '—')}")
    print(f"  Curso           : {entry.get('curso', '—')}")
    print(f"  Fecha de emisión: {entry.get('fecha_emision', '—')}")
    print()

    # 3. Recalcular hash canónico
    import hashlib
    curp  = entry.get("curp",  "").strip()
    curso = entry.get("curso", "").strip()
    hash_recalculado = hashlib.sha256(f"{curp}|{curso}|{folio}".encode("utf-8")).hexdigest()
    hash_almacenado  = entry.get("hash", "")

    if hash_recalculado != hash_almacenado:
        print("  ✗ INVÁLIDO — el hash del registro no coincide.")
        print("    El registro pudo haber sido alterado.\n")
        sys.exit(1)

    # 4. Cargar llave pública
    if not _PUB_KEY_PATH.exists():
        print(f"  ✗ No se encontró la llave pública en: {_PUB_KEY_PATH}\n")
        sys.exit(1)

    try:
        pub_key = load_public_key(_PUB_KEY_PATH)
    except Exception as e:
        print(f"  ✗ Error al cargar la llave pública: {e}\n")
        sys.exit(1)

    # 5. Verificar firma ECDSA
    try:
        firma_bytes = bytes.fromhex(entry.get("firma_hex", ""))
        valida = verify_signature(pub_key, hash_recalculado.encode("utf-8"), firma_bytes)
    except Exception as e:
        print(f"  ✗ Error al verificar la firma: {e}\n")
        sys.exit(1)

    # 6. Resultado
    if valida:
        print("  ╔══════════════════════════════════╗")
        print("  ║  ✓  CERTIFICADO VÁLIDO           ║")
        print("  ║     Firma ECDSA verificada       ║")
        print("  ╚══════════════════════════════════╝")
    else:
        print("  ╔══════════════════════════════════╗")
        print("  ║  ✗  CERTIFICADO INVÁLIDO         ║")
        print("  ║     La firma no corresponde      ║")
        print("  ╚══════════════════════════════════╝")
    print()


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python src/verificar.py <folio>")
        print("Ejemplo: python src/verificar.py VER-0001")
        sys.exit(1)
    verificar(sys.argv[1])


if __name__ == "__main__":
    main()
