"""
auth_manager.py
---------------
Control de Acceso Basado en Roles (RBAC) con protección de contraseñas
mediante bcrypt (salting automático, algoritmo Blowfish adaptativo).

Roles disponibles (jerarquía descendente):
    ADMIN    → Acceso total: generar llaves, firmar, emitir certificados.
    OPERATOR → Emitir certificados sin gestión de llaves.
    VIEWER   → Solo consulta; no avanza en el flujo de emisión.

Consideraciones de seguridad:
    - bcrypt aplica un salt único por contraseña (previene ataques de tabla arcoíris).
    - El check de tiempo constante previene la enumeración de usuarios vía timing attack.
    - En producción, reemplazar _USER_DB por una base de datos cifrada en reposo.
"""

from enum import Enum

import bcrypt


# ─── Roles del sistema ────────────────────────────────────────────────────────

class Role(Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


# ─── Hash de relleno para comparaciones de tiempo constante ───────────────────
# Se computa UNA vez al importar el módulo para no regenerar salt en cada intento.
_DUMMY_HASH: bytes = bcrypt.hashpw(b"__dummy_pasitos_sentinel__", bcrypt.gensalt())


# ─── Base de datos simulada de usuarios ──────────────────────────────────────
# Nota: bcrypt.gensalt() genera un salt aleatorio en cada ejecución; los hashes
# cambian entre inicios de la aplicación, lo cual es correcto para este demo.
# En producción, persistir los hashes en una DB y NO recomputarlos cada vez.
_USER_DB: dict[str, dict] = {
    "admin_pasitos": {
        "password_hash": bcrypt.hashpw(b"Admin@Pasitos2024!", bcrypt.gensalt()),
        "role": Role.ADMIN,
    },
    "operador01": {
        "password_hash": bcrypt.hashpw(b"Oper@2024#Zapopan", bcrypt.gensalt()),
        "role": Role.OPERATOR,
    },
    "visor01": {
        "password_hash": bcrypt.hashpw(b"View@2024$ODS9", bcrypt.gensalt()),
        "role": Role.VIEWER,
    },
}


# ─── Funciones públicas ───────────────────────────────────────────────────────

def hash_password(plain: str) -> bytes:
    """
    Genera un hash bcrypt de la contraseña con salting automático.

    Args:
        plain: Contraseña en texto plano (no vacía).

    Returns:
        Hash bcrypt como bytes, listo para almacenar.

    Raises:
        ValueError: Si la contraseña está vacía.
    """
    if not plain:
        raise ValueError("La contraseña no puede estar vacía.")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())


def verify_login(username: str, password: str) -> tuple[bool, Role | None]:
    """
    Verifica las credenciales de un usuario.

    Aplica comparación en tiempo constante tanto para usuarios inexistentes
    como para contraseñas incorrectas, previniendo timing attacks y enumeración
    de usuarios.

    Args:
        username: Identificador del usuario.
        password: Contraseña en texto plano.

    Returns:
        (True, Role)  → Credenciales válidas.
        (False, None) → Usuario no encontrado o contraseña incorrecta.
    """
    user = _USER_DB.get(username)

    if user is None:
        # Ejecutar un check bcrypt ficticio para mantener tiempo de respuesta constante
        # y evitar que un atacante distinga usuarios válidos de inválidos por latencia.
        bcrypt.checkpw(password.encode("utf-8"), _DUMMY_HASH)
        return False, None

    is_valid = bcrypt.checkpw(password.encode("utf-8"), user["password_hash"])
    return (True, user["role"]) if is_valid else (False, None)


def require_role(current_role: Role, required_roles: list[Role]) -> bool:
    """
    Comprueba si el rol actual tiene los permisos necesarios para una operación.

    Args:
        current_role:  Rol del usuario autenticado.
        required_roles: Lista de roles con acceso permitido a la operación.

    Returns:
        True si current_role está en required_roles, False en caso contrario.
    """
    return current_role in required_roles
