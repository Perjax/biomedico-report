# -*- coding: utf-8 -*-
"""
modulo: clinicas.py
Proposito: Gestion de clinicas, usuarios y acceso multi-tenant.
Cada clinica tiene sus propios equipos y usuarios.
El admin ve todo desde un panel unificado.
"""

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "biomedico.db")


@contextmanager
def _conexion():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def inicializar_tablas_clinicas():
    """Crea las tablas de clinicas y usuarios si no existen."""
    with _conexion() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS clinicas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo      TEXT NOT NULL UNIQUE,
                nombre      TEXT NOT NULL,
                nit         TEXT,
                ciudad      TEXT,
                telefono    TEXT,
                color       TEXT NOT NULL DEFAULT '#3b82f6',
                activa      INTEGER NOT NULL DEFAULT 1,
                creada_en   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS usuarios (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario         TEXT NOT NULL UNIQUE,
                password_hash   TEXT NOT NULL,
                nombre          TEXT NOT NULL,
                rol             TEXT NOT NULL DEFAULT 'clinica',
                clinica_id      INTEGER,
                activo          INTEGER NOT NULL DEFAULT 1,
                creado_en       TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (clinica_id) REFERENCES clinicas(id)
            );

            CREATE INDEX IF NOT EXISTS idx_usuarios_clinica
                ON usuarios(clinica_id);
        """)

        # Agregar columna clinica_id a equipos si no existe
        try:
            conn.execute("ALTER TABLE equipos ADD COLUMN clinica_id INTEGER DEFAULT 1")
        except Exception:
            pass


def sembrar_datos_iniciales():
    """Crea el admin y clinicas de demo si no existen."""
    with _conexion() as conn:
        # Admin global
        existe = conn.execute("SELECT id FROM usuarios WHERE usuario='admin'").fetchone()
        if not existe:
            conn.execute("""
                INSERT INTO usuarios (usuario, password_hash, nombre, rol, clinica_id)
                VALUES (?, ?, ?, 'admin', NULL)
            """, ('admin', generate_password_hash('biomedico123'), 'Administrador'))

        # Clinicas demo
        clinicas_demo = [
            ('CLINICA001', 'Clinica San Rafael', '900123456-1', 'Bogota', '6011234567', '#3b82f6'),
            ('CLINICA002', 'Hospital El Rosario', '800987654-2', 'Medellin', '6044567890', '#10b981'),
            ('CLINICA003', 'Centro Medico Norte', '700456789-3', 'Cali', '6023456789', '#f59e0b'),
        ]
        for c in clinicas_demo:
            existe = conn.execute("SELECT id FROM clinicas WHERE codigo=?", (c[0],)).fetchone()
            if not existe:
                conn.execute("""
                    INSERT INTO clinicas (codigo, nombre, nit, ciudad, telefono, color)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, c)
                clinica_id = conn.execute("SELECT id FROM clinicas WHERE codigo=?", (c[0],)).fetchone()['id']
                usuario = c[0].lower().replace('clinica', 'clinica')
                password = 'clave' + c[0][-3:]
                conn.execute("""
                    INSERT OR IGNORE INTO usuarios
                        (usuario, password_hash, nombre, rol, clinica_id)
                    VALUES (?, ?, ?, 'clinica', ?)
                """, (usuario, generate_password_hash(password), c[1], clinica_id))


# ---------------------------------------------------------------------------
# Autenticacion
# ---------------------------------------------------------------------------
def verificar_login(usuario, contrasena):
    """
    Verifica credenciales y retorna info del usuario si son correctas.
    Retorna None si son incorrectas.
    """
    with _conexion() as conn:
        row = conn.execute("""
            SELECT u.*, c.nombre as clinica_nombre, c.color as clinica_color,
                   c.codigo as clinica_codigo, c.ciudad as clinica_ciudad
            FROM usuarios u
            LEFT JOIN clinicas c ON u.clinica_id = c.id
            WHERE u.usuario = ? AND u.activo = 1
        """, (usuario,)).fetchone()

    if not row:
        return None
    if not check_password_hash(row['password_hash'], contrasena):
        return None

    return {
        'usuario': row['usuario'],
        'nombre': row['nombre'],
        'rol': row['rol'],
        'clinica_id': row['clinica_id'],
        'clinica_nombre': row['clinica_nombre'] or 'Administrador',
        'clinica_color': row['clinica_color'] or '#3b82f6',
        'clinica_codigo': row['clinica_codigo'],
        'permisos': ['ver', 'exportar', 'subir'] if row['rol'] == 'admin' else ['ver', 'exportar'],
    }


# ---------------------------------------------------------------------------
# CRUD Clinicas
# ---------------------------------------------------------------------------
def obtener_clinicas():
    """Retorna todas las clinicas activas."""
    with _conexion() as conn:
        rows = conn.execute("""
            SELECT c.*,
                   COUNT(e.id) as total_equipos,
                   SUM(CASE WHEN e.alerta_critica=1 THEN 1 ELSE 0 END) as criticos
            FROM clinicas c
            LEFT JOIN equipos e ON e.clinica_id = c.id
            WHERE c.activa = 1
            GROUP BY c.id
            ORDER BY c.nombre
        """).fetchall()
        return [dict(r) for r in rows]


def obtener_clinica(clinica_id):
    """Retorna una clinica por ID."""
    with _conexion() as conn:
        row = conn.execute("SELECT * FROM clinicas WHERE id=?", (clinica_id,)).fetchone()
        return dict(row) if row else None


def crear_clinica(datos):
    """Crea una clinica nueva con su usuario."""
    with _conexion() as conn:
        # Crear clinica
        cursor = conn.execute("""
            INSERT INTO clinicas (codigo, nombre, nit, ciudad, telefono, color)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datos.get('codigo', '').upper(),
            datos.get('nombre', ''),
            datos.get('nit', ''),
            datos.get('ciudad', ''),
            datos.get('telefono', ''),
            datos.get('color', '#3b82f6'),
        ))
        clinica_id = cursor.lastrowid

        # Crear usuario para la clinica
        conn.execute("""
            INSERT INTO usuarios (usuario, password_hash, nombre, rol, clinica_id)
            VALUES (?, ?, ?, 'clinica', ?)
        """, (
            datos.get('usuario', ''),
            generate_password_hash(datos.get('password', 'clinica123')),
            datos.get('nombre', ''),
            clinica_id,
        ))

        return clinica_id


def actualizar_clinica(clinica_id, datos):
    """Actualiza los datos de una clinica."""
    with _conexion() as conn:
        conn.execute("""
            UPDATE clinicas SET
                nombre=?, nit=?, ciudad=?, telefono=?, color=?
            WHERE id=?
        """, (
            datos.get('nombre'),
            datos.get('nit', ''),
            datos.get('ciudad', ''),
            datos.get('telefono', ''),
            datos.get('color', '#3b82f6'),
            clinica_id,
        ))
        return True


def cambiar_password_clinica(clinica_id, nueva_password):
    """Cambia la contrasena del usuario de una clinica."""
    with _conexion() as conn:
        conn.execute("""
            UPDATE usuarios SET password_hash=?
            WHERE clinica_id=? AND rol='clinica'
        """, (generate_password_hash(nueva_password), clinica_id))
        return True


def desactivar_clinica(clinica_id):
    """Desactiva una clinica sin eliminarla."""
    with _conexion() as conn:
        conn.execute("UPDATE clinicas SET activa=0 WHERE id=?", (clinica_id,))
        conn.execute("UPDATE usuarios SET activo=0 WHERE clinica_id=?", (clinica_id,))
        return True


def obtener_usuarios_clinica(clinica_id):
    """Retorna los usuarios de una clinica."""
    with _conexion() as conn:
        rows = conn.execute("""
            SELECT id, usuario, nombre, rol, activo, creado_en
            FROM usuarios WHERE clinica_id=?
        """, (clinica_id,)).fetchall()
        return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Resumen admin
# ---------------------------------------------------------------------------
def resumen_global():
    """Retorna metricas globales de todas las clinicas para el admin."""
    with _conexion() as conn:
        total_clinicas = conn.execute("SELECT COUNT(*) FROM clinicas WHERE activa=1").fetchone()[0]
        total_equipos = conn.execute("SELECT COUNT(*) FROM equipos").fetchone()[0]
        total_criticos = conn.execute("SELECT COUNT(*) FROM equipos WHERE alerta_critica=1").fetchone()[0]
        por_clinica = conn.execute("""
            SELECT c.nombre, c.color, c.ciudad,
                   COUNT(e.id) as equipos,
                   SUM(CASE WHEN e.alerta_critica=1 THEN 1 ELSE 0 END) as criticos
            FROM clinicas c
            LEFT JOIN equipos e ON e.clinica_id = c.id
            WHERE c.activa = 1
            GROUP BY c.id ORDER BY c.nombre
        """).fetchall()

        return {
            'total_clinicas': total_clinicas,
            'total_equipos': total_equipos,
            'total_criticos': total_criticos,
            'por_clinica': [dict(r) for r in por_clinica],
        }
