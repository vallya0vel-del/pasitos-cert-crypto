"""
main.py
-------
Orquestador CLI del sistema de emisión de certificados digitales de
Pasitos Education & Health A.C.

Flujo de ejecución:
    1. Solicitar credenciales de acceso (login).
    2. Validar rol — solo ADMIN u OPERATOR pueden emitir certificados.
    3. Generar o cargar el par de llaves ECDSA SECP256R1.
    4. Leer el CSV de registros desde /data.
    5. Enriquecer registros con datos del catálogo de cursos.
    6. Por cada participante Acreditado:
           a. Generar hash SHA-256 del certificado (CURP + Curso + Folio).
           b. Firmar el hash con la llave privada (ECDSA, RFC 6979).
           c. Generar el PDF del Certificado de Competencia Laboral.
           d. Generar el PDF de la Boleta de Evaluación.
    7. Mostrar resumen en consola con folios de verificación emitidos.
"""

import getpass
import sys
from pathlib import Path

# Agregar /src al path para que los imports funcionen al ejecutar directamente
sys.path.insert(0, str(Path(__file__).parent))

from auth.auth_manager import Role, require_role, verify_login
from crypto.keys_manager import (
    generate_key_pair,
    load_private_key,
    load_public_key,
    save_private_key,
    save_public_key,
    sign_data,
)
from data_manager.csv_reader import (
    enrich_with_catalog,
    generate_certificate_hash,
    read_acreditados,
    read_catalogo,
)
from pdf_generator.certificate_builder import build_boleta, build_certificate

# ─── Rutas del proyecto ───────────────────────────────────────────────────────
_BASE_DIR      = Path(__file__).parent.parent
_DATA_DIR      = _BASE_DIR / "data"
_KEYS_DIR      = _BASE_DIR / "keys"
_OUTPUT_DIR    = _BASE_DIR / "output"
_TEMPLATES_DIR = _BASE_DIR / "docs" / "templates"

_CSV_REGISTROS = _DATA_DIR / "registros_cursos.csv"
_CSV_CATALOGO  = _DATA_DIR / "catalogo_cursos.csv"
_PRIV_KEY_PATH = _KEYS_DIR / "pasitos_private.pem"
_PUB_KEY_PATH  = _KEYS_DIR / "pasitos_public.pem"

_BANNER = """
╔══════════════════════════════════════════════════════╗
║      Pasitos Education & Health A.C.                 ║
║      Sistema de Certificados Digitales               ║
║      Zapopan, Jalisco — ODS 9                        ║
╚══════════════════════════════════════════════════════╝
"""


# ─── Pasos del flujo ──────────────────────────────────────────────────────────

def _step_login() -> Role:
    """Solicita credenciales y retorna el rol del usuario autenticado."""
    print(_BANNER)
    for attempt in range(3):
        username = input("  Usuario    : ").strip()
        password = getpass.getpass("  Contraseña : ")

        ok, role = verify_login(username, password)
        if ok:
            print(f"\n  ✓ Sesión iniciada — Rol: {role.value.upper()}\n")
            return role

        remaining = 2 - attempt
        print(f"  ✗ Credenciales incorrectas.", end="")
        if remaining > 0:
            print(f" Intentos restantes: {remaining}")
        else:
            print()

    print("\n  Acceso denegado. Demasiados intentos fallidos.\n")
    sys.exit(1)


def _step_validate_role(role: Role) -> None:
    """Verifica que el rol tiene permisos para emitir certificados."""
    if not require_role(role, [Role.ADMIN, Role.OPERATOR]):
        print(f"  ✗ El rol '{role.value}' no tiene permisos de emisión.")
        print("    Se requiere: ADMIN u OPERATOR.\n")
        sys.exit(1)


def _step_keys(role: Role):
    """Genera o carga el par de llaves ECDSA. Retorna (priv_key, pub_key)."""
    if _PRIV_KEY_PATH.exists() and _PUB_KEY_PATH.exists():
        print("  → Llaves existentes encontradas. Cargando...")
        pwd_input = getpass.getpass("  Contraseña de la llave privada (Enter si no tiene): ")
        password  = pwd_input.encode("utf-8") if pwd_input else None

        priv = load_private_key(_PRIV_KEY_PATH, password=password)
        pub  = load_public_key(_PUB_KEY_PATH)
        print("  ✓ Llaves cargadas.\n")
        return priv, pub

    # No existen llaves — solo ADMIN puede generarlas
    if role != Role.ADMIN:
        print("  ✗ No existen llaves y solo ADMIN puede generarlas.")
        print("    Contacta al administrador del sistema.\n")
        sys.exit(1)

    print("  → Generando nuevo par de llaves ECDSA SECP256R1...")
    priv, pub = generate_key_pair()

    pwd_input = getpass.getpass(
        "  Contraseña para proteger la llave privada (Enter para omitir): "
    )
    password = pwd_input.encode("utf-8") if pwd_input else None

    _KEYS_DIR.mkdir(parents=True, exist_ok=True)
    save_private_key(priv, _PRIV_KEY_PATH, password=password)
    save_public_key(pub, _PUB_KEY_PATH)
    print(f"  ✓ Llaves guardadas en: {_KEYS_DIR}\n")
    return priv, pub


def _step_process(priv_key, pub_key) -> None:
    """Lee el CSV, firma y genera los documentos PDF por cada acreditado."""
    print(f"  → Leyendo registros: {_CSV_REGISTROS.name}")

    records  = read_acreditados(_CSV_REGISTROS)
    catalogo = read_catalogo(_CSV_CATALOGO)
    enrich_with_catalog(records, catalogo)

    if not records:
        print("  ✗ No se encontraron participantes 'Acreditado' en el CSV.\n")
        return

    print(f"  ✓ {len(records)} participante(s) acreditado(s).\n")
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"  {'#':<4} {'Nombre':<32} {'Folio':<12} Estado")
    print("  " + "─" * 62)

    emitidos = []

    for i, record in enumerate(records, 1):
        nombre = record.get("Nombre Completo", "—")
        folio  = record.get("Folio Verificación", "—")

        try:
            # a. Hash canónico del certificado
            cert_hash = generate_certificate_hash(record)

            # b. Firma digital ECDSA-SHA256 (nonce determinista RFC 6979)
            signature     = sign_data(priv_key, cert_hash.encode("utf-8"))
            signature_hex = signature.hex()

            # c. PDF — Certificado de Competencia Laboral
            cert_path = build_certificate(
                record, signature_hex, _OUTPUT_DIR, _TEMPLATES_DIR
            )

            # d. PDF — Boleta de Evaluación por Competencias
            boleta_path = build_boleta(
                record, signature_hex, _OUTPUT_DIR, _TEMPLATES_DIR
            )

            print(f"  {i:<4} {nombre:<32} {folio:<12} ✓")
            print(f"       ├─ {cert_path.name}")
            print(f"       └─ {boleta_path.name}")
            print()
            emitidos.append(folio)

        except Exception as exc:
            print(f"  {i:<4} {nombre:<32} {folio:<12} ✗ {exc}\n")

    print("  " + "─" * 62)
    print(f"\n  ✓ {len(emitidos)} certificado(s) emitido(s) correctamente.")
    print(f"  Documentos guardados en: {_OUTPUT_DIR}\n")

    if emitidos:
        print("  Folios de verificación emitidos:")
        for f in emitidos:
            print(f"    · {f}")
    print()


# ─── Punto de entrada ─────────────────────────────────────────────────────────

def main() -> None:
    role = _step_login()
    _step_validate_role(role)
    priv_key, pub_key = _step_keys(role)
    _step_process(priv_key, pub_key)


if __name__ == "__main__":
    main()
