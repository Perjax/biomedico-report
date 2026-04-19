"""
módulo: auth.py
Propósito: Gestión de autenticación y usuarios del sistema biomédico.
Maneja login, logout, sesiones y control de acceso por rol.
"""

from werkzeug.security import generate_password_hash, check_password_hash


# ---------------------------------------------------------------------------
# Base de usuarios del sistema
# En un proyecto real esto vendría de una base de datos.
# Cada usuario tiene: nombre, hash de contraseña y rol.
# ---------------------------------------------------------------------------
USUARIOS = {
    "admin": {
        "nombre": "Administrador",
        "password_hash": generate_password_hash("biomedico123"),
        "rol": "admin",
    },
    "tecnico": {
        "nombre": "Técnico Biomédico",
        "password_hash": generate_password_hash("tecnico456"),
        "rol": "tecnico",
    },
}

# Permisos por rol
PERMISOS = {
    "admin":   ["ver", "exportar", "subir", "gestionar_usuarios"],
    "tecnico": ["ver", "exportar"],
}


def verificar_credenciales(usuario: str, contrasena: str) -> dict | None:
    """
    Verifica si las credenciales son válidas.

    Args:
        usuario: Nombre de usuario.
        contrasena: Contraseña en texto plano.

    Returns:
        Diccionario con info del usuario si es válido, None si no.
    """
    user = USUARIOS.get(usuario)
    if not user:
        return None
    if not check_password_hash(user["password_hash"], contrasena):
        return None
    return {
        "usuario": usuario,
        "nombre": user["nombre"],
        "rol": user["rol"],
        "permisos": PERMISOS.get(user["rol"], []),
    }


def tiene_permiso(sesion: dict, permiso: str) -> bool:
    """
    Verifica si el usuario en sesión tiene un permiso específico.

    Args:
        sesion: Diccionario de sesión de Flask.
        permiso: Nombre del permiso a verificar.

    Returns:
        True si tiene el permiso, False si no.
    """
    permisos = sesion.get("permisos", [])
    return permiso in permisos
