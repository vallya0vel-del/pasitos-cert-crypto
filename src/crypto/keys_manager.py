"""
keys_manager.py
---------------
Motor criptográfico ECDSA basado en la curva elíptica SECP256R1 (P-256).

Por qué SECP256R1:
    - 128 bits de seguridad equivalentes con claves mucho más cortas que RSA-3072.
    - La librería `cryptography` implementa operaciones sobre la curva usando
      aritmética de tiempo constante, mitigando ataques de canal lateral (SCA).
    - Ampliamente adoptada en TLS 1.3, FIDO2 y estándares NIST FIPS 186-5.

Flujo de no-repudio:
    Emisor  → generate_key_pair() → sign_data(privkey, cert_bytes) → firma DER
    Receptor → verify_signature(pubkey, cert_bytes, firma)          → True/False
"""

import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ec import (
    ECDSA,
    SECP256R1,
    EllipticCurvePrivateKey,
    EllipticCurvePublicKey,
    generate_private_key,
)


# ─── Generación de llaves ─────────────────────────────────────────────────────

def generate_key_pair() -> tuple[EllipticCurvePrivateKey, EllipticCurvePublicKey]:
    """
    Genera un par de llaves asimétricas ECDSA usando la curva SECP256R1.

    La entropía proviene del CSPRNG del sistema operativo (os.urandom internamente).

    Returns:
        Tupla (llave_privada, llave_pública).
    """
    private_key = generate_private_key(SECP256R1())
    return private_key, private_key.public_key()


# ─── Serialización (guardar / cargar) ─────────────────────────────────────────

def save_private_key(
    private_key: EllipticCurvePrivateKey,
    path: str | Path,
    password: bytes | None = None,
) -> None:
    """
    Serializa y persiste la llave privada en formato PEM (PKCS8).

    Args:
        private_key: Llave privada ECDSA a guardar.
        path:        Ruta destino del archivo .pem.
        password:    Contraseña opcional para cifrar la llave en reposo
                     (usa AES-256-CBC vía BestAvailableEncryption).

    Nota de seguridad:
        Si se provee contraseña, la llave se cifra en reposo con el mejor
        algoritmo simétrico disponible en la versión instalada de `cryptography`.
        En sistemas Unix, se aplica chmod 0o600 para restringir lectura al dueño.
    """
    encryption = (
        serialization.BestAvailableEncryption(password)
        if password
        else serialization.NoEncryption()
    )
    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pem_bytes)

    # Restringir permisos del archivo en sistemas Unix
    try:
        os.chmod(path, 0o600)
    except (NotImplementedError, AttributeError):
        pass  # Windows no soporta chmod POSIX; gestionar permisos vía ACL si es necesario


def save_public_key(public_key: EllipticCurvePublicKey, path: str | Path) -> None:
    """
    Serializa y persiste la llave pública en formato PEM (SubjectPublicKeyInfo).

    La llave pública puede distribuirse libremente; no contiene información sensible.

    Args:
        public_key: Llave pública ECDSA.
        path:       Ruta destino del archivo .pem.
    """
    pem_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pem_bytes)


def load_private_key(
    path: str | Path,
    password: bytes | None = None,
) -> EllipticCurvePrivateKey:
    """
    Carga una llave privada desde un archivo PEM.

    Args:
        path:     Ruta al archivo .pem.
        password: Contraseña de desencriptación si la llave está cifrada en reposo.

    Returns:
        Objeto EllipticCurvePrivateKey listo para firmar.

    Raises:
        FileNotFoundError:  Si el archivo no existe.
        ValueError:         Si el PEM es inválido o la contraseña es incorrecta.
    """
    return serialization.load_pem_private_key(
        Path(path).read_bytes(),
        password=password,
    )


def load_public_key(path: str | Path) -> EllipticCurvePublicKey:
    """
    Carga una llave pública desde un archivo PEM.

    Args:
        path: Ruta al archivo .pem.

    Returns:
        Objeto EllipticCurvePublicKey listo para verificar firmas.

    Raises:
        FileNotFoundError: Si el archivo no existe.
        ValueError:        Si el PEM es inválido.
    """
    return serialization.load_pem_public_key(Path(path).read_bytes())


# ─── Firma y Verificación ─────────────────────────────────────────────────────

def sign_data(private_key: EllipticCurvePrivateKey, data: bytes) -> bytes:
    """
    Firma datos arbitrarios usando ECDSA con SHA-256.

    La librería `cryptography` aplica internamente RFC 6979 para la generación
    determinista del nonce 'k', eliminando el riesgo de reutilización de nonce
    que comprometería la llave privada (como ocurrió con PlayStation 3).

    Args:
        private_key: Llave privada ECDSA del emisor.
        data:        Bytes a firmar (p. ej., datos del certificado en UTF-8).

    Returns:
        Firma digital en formato DER (bytes). Almacenar o incrustar en el QR.
    """
    return private_key.sign(data, ECDSA(hashes.SHA256()))


def verify_signature(
    public_key: EllipticCurvePublicKey,
    data: bytes,
    signature: bytes,
) -> bool:
    """
    Verifica matemáticamente una firma ECDSA-SHA256.

    Garantiza no-repudio: si la verificación es exitosa, solo el poseedor
    de la llave privada correspondiente pudo haber producido esa firma.
    Cualquier alteración de `data` invalida la verificación.

    Args:
        public_key: Llave pública ECDSA del emisor del certificado.
        data:       Datos originales en bytes (mismos que se firmaron).
        signature:  Firma DER a verificar.

    Returns:
        True  → Firma válida; el documento es auténtico e íntegro.
        False → Firma inválida; el documento fue alterado o la firma es espuria.
    """
    try:
        public_key.verify(signature, data, ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False
