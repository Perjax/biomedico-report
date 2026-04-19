"""
módulo: database.py
Propósito: Gestión de la base de datos SQLite del sistema biomédico.
Maneja la creación, lectura, escritura y consulta del inventario
de equipos de forma persistente entre sesiones.
"""

import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

import pandas as pd


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "biomedico.db")


@contextmanager
def _conexion():
    """
    Context manager que abre y cierra la conexión a SQLite de forma segura.
    Hace commit automático al salir sin errores, rollback si hay excepción.
    """
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Permite acceder a columnas por nombre
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Inicialización
# ---------------------------------------------------------------------------
def inicializar_db() -> None:
    """
    Crea las tablas necesarias si no existen.
    Se llama una vez al iniciar el servidor.

    Tablas:
        equipos     — inventario principal de equipos biomédicos
        historial   — registro de cambios de estado por fecha
    """
    with _conexion() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS equipos (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                equipo              TEXT NOT NULL,
                ubicacion           TEXT NOT NULL DEFAULT 'N/A',
                bateria             INTEGER NOT NULL DEFAULT 100,
                estado_bateria      TEXT NOT NULL DEFAULT 'NORMAL',
                ultima_calibracion  TEXT NOT NULL,
                dias_calibracion    INTEGER NOT NULL DEFAULT 0,
                estado_calibracion  TEXT NOT NULL DEFAULT 'VIGENTE',
                alerta_critica      INTEGER NOT NULL DEFAULT 0,
                creado_en           TEXT NOT NULL DEFAULT (datetime('now')),
                actualizado_en      TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS historial (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                equipo_id       INTEGER NOT NULL,
                equipo          TEXT NOT NULL,
                bateria         INTEGER,
                estado_bateria  TEXT,
                estado_cal      TEXT,
                alerta_critica  INTEGER,
                registrado_en   TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (equipo_id) REFERENCES equipos(id)
            );

            CREATE INDEX IF NOT EXISTS idx_equipos_alerta
                ON equipos(alerta_critica);
            CREATE INDEX IF NOT EXISTS idx_historial_equipo
                ON historial(equipo_id);
        """)


# ---------------------------------------------------------------------------
# CRUD de equipos
# ---------------------------------------------------------------------------
def obtener_equipos() -> pd.DataFrame:
    """
    Retorna todos los equipos del inventario como DataFrame.

    Returns:
        DataFrame con todos los campos de equipos, críticos primero.
    """
    with _conexion() as conn:
        cursor = conn.execute("""
            SELECT equipo        AS "Equipo",
                   ubicacion     AS "Ubicación",
                   bateria       AS "Batería (%)",
                   estado_bateria AS "Estado Batería",
                   ultima_calibracion AS "Última Calibración",
                   dias_calibracion   AS "Días desde Calibración",
                   estado_calibracion AS "Estado Calibración",
                   alerta_critica     AS "Alerta Crítica"
            FROM equipos
            ORDER BY alerta_critica DESC, bateria ASC
        """)
        filas = cursor.fetchall()

    if not filas:
        return pd.DataFrame()

    df = pd.DataFrame([dict(f) for f in filas])
    df["Alerta Crítica"] = df["Alerta Crítica"].astype(bool)
    return df


def guardar_equipos(df: pd.DataFrame) -> int:
    """
    Reemplaza todo el inventario con los datos del DataFrame.
    Guarda también una instantánea en el historial.

    Args:
        df: DataFrame con el inventario completo.

    Returns:
        Número de equipos guardados.
    """
    with _conexion() as conn:
        # Guardar historial antes de reemplazar
        existentes = conn.execute("SELECT id, equipo FROM equipos").fetchall()
        for row in existentes:
            conn.execute("""
                INSERT INTO historial
                    (equipo_id, equipo, bateria, estado_bateria,
                     estado_cal, alerta_critica)
                SELECT id, equipo, bateria, estado_bateria,
                       estado_calibracion, alerta_critica
                FROM equipos WHERE id = ?
            """, (row["id"],))

        # Reemplazar inventario
        conn.execute("DELETE FROM equipos")

        for _, row in df.iterrows():
            conn.execute("""
                INSERT INTO equipos
                    (equipo, ubicacion, bateria, estado_bateria,
                     ultima_calibracion, dias_calibracion,
                     estado_calibracion, alerta_critica, actualizado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(row["Equipo"]),
                str(row["Ubicación"]),
                int(row["Batería (%)"]),
                str(row["Estado Batería"]),
                str(row["Última Calibración"]),
                int(row["Días desde Calibración"]),
                str(row["Estado Calibración"]),
                int(bool(row["Alerta Crítica"])),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ))

    return len(df)


def agregar_equipo(datos: dict) -> int:
    """
    Agrega un equipo nuevo al inventario.

    Args:
        datos: Diccionario con los campos del equipo.

    Returns:
        ID del equipo creado.
    """
    from modules.data_generator import (
        calcular_estado_bateria,
        calcular_estado_calibracion,
        es_critico,
    )

    bateria = int(datos.get("bateria", 100))
    dias    = int(datos.get("dias_calibracion", 0))

    with _conexion() as conn:
        cursor = conn.execute("""
            INSERT INTO equipos
                (equipo, ubicacion, bateria, estado_bateria,
                 ultima_calibracion, dias_calibracion,
                 estado_calibracion, alerta_critica)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datos.get("equipo", "Nuevo equipo"),
            datos.get("ubicacion", "N/A"),
            bateria,
            calcular_estado_bateria(bateria),
            datos.get("ultima_calibracion", datetime.now().strftime("%Y-%m-%d")),
            dias,
            calcular_estado_calibracion(dias),
            int(es_critico(bateria, dias)),
        ))
        return cursor.lastrowid


def actualizar_equipo(equipo_id: int, datos: dict) -> bool:
    """
    Actualiza los datos de un equipo existente.

    Args:
        equipo_id: ID del equipo a actualizar.
        datos: Campos a actualizar.

    Returns:
        True si se actualizó, False si no existía.
    """
    from modules.data_generator import (
        calcular_estado_bateria,
        calcular_estado_calibracion,
        es_critico,
    )

    bateria = int(datos.get("bateria", 100))
    dias    = int(datos.get("dias_calibracion", 0))

    with _conexion() as conn:
        cursor = conn.execute("""
            UPDATE equipos SET
                equipo             = ?,
                ubicacion          = ?,
                bateria            = ?,
                estado_bateria     = ?,
                ultima_calibracion = ?,
                dias_calibracion   = ?,
                estado_calibracion = ?,
                alerta_critica     = ?,
                actualizado_en     = ?
            WHERE id = ?
        """, (
            datos.get("equipo"),
            datos.get("ubicacion", "N/A"),
            bateria,
            calcular_estado_bateria(bateria),
            datos.get("ultima_calibracion"),
            dias,
            calcular_estado_calibracion(dias),
            int(es_critico(bateria, dias)),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            equipo_id,
        ))
        return cursor.rowcount > 0


def eliminar_equipo(equipo_id: int) -> bool:
    """
    Elimina un equipo del inventario.

    Args:
        equipo_id: ID del equipo a eliminar.

    Returns:
        True si se eliminó, False si no existía.
    """
    with _conexion() as conn:
        cursor = conn.execute("DELETE FROM equipos WHERE id = ?", (equipo_id,))
        return cursor.rowcount > 0


def obtener_historial(limite: int = 50) -> list:
    """
    Retorna el historial de cambios de estado más recientes.

    Args:
        limite: Número máximo de registros a retornar.

    Returns:
        Lista de dicts con el historial.
    """
    with _conexion() as conn:
        cursor = conn.execute("""
            SELECT equipo, bateria, estado_bateria,
                   estado_cal, alerta_critica, registrado_en
            FROM historial
            ORDER BY registrado_en DESC
            LIMIT ?
        """, (limite,))
        return [dict(row) for row in cursor.fetchall()]


def hay_datos() -> bool:
    """Retorna True si la base de datos tiene equipos cargados."""
    with _conexion() as conn:
        count = conn.execute("SELECT COUNT(*) FROM equipos").fetchone()[0]
        return count > 0


def obtener_equipos_clinica(clinica_id: int):
    """Retorna equipos filtrados por clinica."""
    import pandas as pd
    with _conexion() as conn:
        cursor = conn.execute("""
            SELECT equipo AS "Equipo", ubicacion AS "Ubicacion",
                   bateria AS "Bateria (%)", estado_bateria AS "Estado Bateria",
                   ultima_calibracion AS "Ultima Calibracion",
                   dias_calibracion AS "Dias desde Calibracion",
                   estado_calibracion AS "Estado Calibracion",
                   alerta_critica AS "Alerta Critica"
            FROM equipos WHERE clinica_id = ?
            ORDER BY alerta_critica DESC, bateria ASC
        """, (clinica_id,))
        filas = cursor.fetchall()
    if not filas:
        return pd.DataFrame()
    df = pd.DataFrame([dict(f) for f in filas])
    # Rename to Spanish with accents for compatibility
    df = df.rename(columns={
        "Ubicacion": "Ubicaci\u00f3n",
        "Bateria (%)": "Bater\u00eda (%)",
        "Estado Bateria": "Estado Bater\u00eda",
        "Ultima Calibracion": "\u00daltima Calibraci\u00f3n",
        "Dias desde Calibracion": "D\u00edas desde Calibraci\u00f3n",
        "Estado Calibracion": "Estado Calibraci\u00f3n",
        "Alerta Critica": "Alerta Cr\u00edtica",
    })
    df["Alerta Cr\u00edtica"] = df["Alerta Cr\u00edtica"].astype(bool)
    return df


def guardar_equipos_clinica(df, clinica_id: int):
    """Guarda equipos asociados a una clinica especifica."""
    from datetime import datetime
    with _conexion() as conn:
        conn.execute("DELETE FROM equipos WHERE clinica_id = ?", (clinica_id,))
        for _, row in df.iterrows():
            conn.execute("""
                INSERT INTO equipos
                    (equipo, ubicacion, bateria, estado_bateria,
                     ultima_calibracion, dias_calibracion,
                     estado_calibracion, alerta_critica, actualizado_en, clinica_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(row["Equipo"]),
                str(row.get("Ubicaci\u00f3n", "N/A")),
                int(row["Bater\u00eda (%)"]),
                str(row["Estado Bater\u00eda"]),
                str(row["\u00daltima Calibraci\u00f3n"]),
                int(row["D\u00edas desde Calibraci\u00f3n"]),
                str(row["Estado Calibraci\u00f3n"]),
                int(bool(row["Alerta Cr\u00edtica"])),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                clinica_id,
            ))
