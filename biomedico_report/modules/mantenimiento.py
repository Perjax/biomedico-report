"""
módulo: mantenimiento.py
Propósito: Gestión completa de mantenimientos preventivos y calibraciones.
Maneja agendamiento, seguimiento, completado e historial de intervenciones
sobre equipos biomédicos.
"""

import sqlite3
import os
from datetime import datetime, date, timedelta
from contextlib import contextmanager

# Ruta a la misma BD del proyecto
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "biomedico.db")

TIPOS_MANTENIMIENTO = ["Preventivo", "Calibración", "Correctivo", "Inspección"]
ESTADOS_ORDEN = ["Pendiente", "En proceso", "Completado", "Cancelado"]
PRIORIDADES = ["Alta", "Media", "Baja"]


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


# ---------------------------------------------------------------------------
# Inicialización de tablas de mantenimiento
# ---------------------------------------------------------------------------
def inicializar_tablas_mantenimiento() -> None:
    """
    Crea las tablas de mantenimiento si no existen.

    Tablas:
        ordenes_mantenimiento — agenda de intervenciones programadas
        historial_mantenimiento — registro de trabajos completados
        snapshots_inventario — foto semanal del estado del inventario
    """
    with _conexion() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS ordenes_mantenimiento (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                equipo          TEXT NOT NULL,
                ubicacion       TEXT NOT NULL DEFAULT 'N/A',
                tipo            TEXT NOT NULL DEFAULT 'Preventivo',
                prioridad       TEXT NOT NULL DEFAULT 'Media',
                descripcion     TEXT,
                responsable     TEXT,
                fecha_programada TEXT NOT NULL,
                fecha_completado TEXT,
                estado          TEXT NOT NULL DEFAULT 'Pendiente',
                observaciones   TEXT,
                creado_en       TEXT NOT NULL DEFAULT (datetime('now')),
                actualizado_en  TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS historial_mantenimiento (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                orden_id        INTEGER,
                equipo          TEXT NOT NULL,
                tipo            TEXT NOT NULL,
                responsable     TEXT,
                fecha_realizado TEXT NOT NULL,
                duracion_horas  REAL,
                resultado       TEXT,
                observaciones   TEXT,
                registrado_en   TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS snapshots_inventario (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha           TEXT NOT NULL,
                total_equipos   INTEGER NOT NULL DEFAULT 0,
                criticos        INTEGER NOT NULL DEFAULT 0,
                bat_critica     INTEGER NOT NULL DEFAULT 0,
                bat_baja        INTEGER NOT NULL DEFAULT 0,
                bat_normal      INTEGER NOT NULL DEFAULT 0,
                cal_vencida     INTEGER NOT NULL DEFAULT 0,
                cal_proxima     INTEGER NOT NULL DEFAULT 0,
                cal_vigente     INTEGER NOT NULL DEFAULT 0,
                bateria_promedio REAL NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_ordenes_estado
                ON ordenes_mantenimiento(estado);
            CREATE INDEX IF NOT EXISTS idx_ordenes_fecha
                ON ordenes_mantenimiento(fecha_programada);
            CREATE INDEX IF NOT EXISTS idx_snapshots_fecha
                ON snapshots_inventario(fecha);
        """)


# ---------------------------------------------------------------------------
# Órdenes de mantenimiento
# ---------------------------------------------------------------------------
def crear_orden(datos: dict) -> int:
    """
    Crea una nueva orden de mantenimiento.

    Args:
        datos: Dict con equipo, tipo, prioridad, responsable, fecha_programada, descripcion.

    Returns:
        ID de la orden creada.
    """
    with _conexion() as conn:
        cursor = conn.execute("""
            INSERT INTO ordenes_mantenimiento
                (equipo, ubicacion, tipo, prioridad, descripcion,
                 responsable, fecha_programada, estado)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente')
        """, (
            datos.get("equipo", ""),
            datos.get("ubicacion", "N/A"),
            datos.get("tipo", "Preventivo"),
            datos.get("prioridad", "Media"),
            datos.get("descripcion", ""),
            datos.get("responsable", ""),
            datos.get("fecha_programada", date.today().isoformat()),
        ))
        return cursor.lastrowid


def obtener_ordenes(estado: str = None, limite: int = 100) -> list:
    """
    Retorna órdenes de mantenimiento, opcionalmente filtradas por estado.

    Args:
        estado: 'Pendiente', 'En proceso', 'Completado', 'Cancelado' o None para todas.
        limite: Máximo de registros.

    Returns:
        Lista de dicts con las órdenes.
    """
    with _conexion() as conn:
        if estado:
            cursor = conn.execute("""
                SELECT * FROM ordenes_mantenimiento
                WHERE estado = ?
                ORDER BY
                    CASE prioridad WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END,
                    fecha_programada ASC
                LIMIT ?
            """, (estado, limite))
        else:
            cursor = conn.execute("""
                SELECT * FROM ordenes_mantenimiento
                ORDER BY
                    CASE estado WHEN 'Pendiente' THEN 1 WHEN 'En proceso' THEN 2
                                WHEN 'Completado' THEN 3 ELSE 4 END,
                    CASE prioridad WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END,
                    fecha_programada ASC
                LIMIT ?
            """, (limite,))
        return [dict(row) for row in cursor.fetchall()]


def completar_orden(orden_id: int, datos: dict) -> bool:
    """
    Marca una orden como completada y registra en el historial.

    Args:
        orden_id: ID de la orden a completar.
        datos: Dict con responsable, duracion_horas, resultado, observaciones.

    Returns:
        True si se completó, False si no existía.
    """
    hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with _conexion() as conn:
        orden = conn.execute(
            "SELECT * FROM ordenes_mantenimiento WHERE id = ?", (orden_id,)
        ).fetchone()

        if not orden:
            return False

        # Actualizar orden
        conn.execute("""
            UPDATE ordenes_mantenimiento
            SET estado = 'Completado',
                fecha_completado = ?,
                responsable = ?,
                observaciones = ?,
                actualizado_en = ?
            WHERE id = ?
        """, (
            hoy,
            datos.get("responsable", orden["responsable"]),
            datos.get("observaciones", ""),
            hoy,
            orden_id,
        ))

        # Registrar en historial
        conn.execute("""
            INSERT INTO historial_mantenimiento
                (orden_id, equipo, tipo, responsable, fecha_realizado,
                 duracion_horas, resultado, observaciones)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            orden_id,
            orden["equipo"],
            orden["tipo"],
            datos.get("responsable", orden["responsable"] or "N/A"),
            hoy,
            datos.get("duracion_horas", 0),
            datos.get("resultado", "Completado satisfactoriamente"),
            datos.get("observaciones", ""),
        ))

    return True


def actualizar_orden(orden_id: int, datos: dict) -> bool:
    """Actualiza los campos de una orden existente."""
    with _conexion() as conn:
        cursor = conn.execute("""
            UPDATE ordenes_mantenimiento
            SET equipo = ?, tipo = ?, prioridad = ?, descripcion = ?,
                responsable = ?, fecha_programada = ?, estado = ?,
                actualizado_en = ?
            WHERE id = ?
        """, (
            datos.get("equipo"),
            datos.get("tipo", "Preventivo"),
            datos.get("prioridad", "Media"),
            datos.get("descripcion", ""),
            datos.get("responsable", ""),
            datos.get("fecha_programada"),
            datos.get("estado", "Pendiente"),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            orden_id,
        ))
        return cursor.rowcount > 0


def eliminar_orden(orden_id: int) -> bool:
    """Elimina una orden de mantenimiento."""
    with _conexion() as conn:
        cursor = conn.execute(
            "DELETE FROM ordenes_mantenimiento WHERE id = ?", (orden_id,)
        )
        return cursor.rowcount > 0


def obtener_proximos(dias: int = 30) -> list:
    """
    Retorna órdenes pendientes programadas en los próximos N días.

    Args:
        dias: Ventana de días a mirar hacia adelante.

    Returns:
        Lista de órdenes próximas, ordenadas por fecha.
    """
    hoy = date.today().isoformat()
    limite = (date.today() + timedelta(days=dias)).isoformat()

    with _conexion() as conn:
        cursor = conn.execute("""
            SELECT * FROM ordenes_mantenimiento
            WHERE estado IN ('Pendiente', 'En proceso')
              AND fecha_programada BETWEEN ? AND ?
            ORDER BY fecha_programada ASC
        """, (hoy, limite))
        return [dict(row) for row in cursor.fetchall()]


def obtener_vencidos() -> list:
    """Retorna órdenes pendientes cuya fecha ya pasó."""
    hoy = date.today().isoformat()
    with _conexion() as conn:
        cursor = conn.execute("""
            SELECT * FROM ordenes_mantenimiento
            WHERE estado IN ('Pendiente', 'En proceso')
              AND fecha_programada < ?
            ORDER BY fecha_programada ASC
        """, (hoy,))
        return [dict(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Historial de mantenimientos realizados
# ---------------------------------------------------------------------------
def obtener_historial_mantenimiento(limite: int = 50) -> list:
    """Retorna los mantenimientos completados más recientes."""
    with _conexion() as conn:
        cursor = conn.execute("""
            SELECT * FROM historial_mantenimiento
            ORDER BY fecha_realizado DESC
            LIMIT ?
        """, (limite,))
        return [dict(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Snapshots para tendencias
# ---------------------------------------------------------------------------
def registrar_snapshot(df_equipos) -> None:
    """
    Guarda una foto del estado actual del inventario para tendencias.
    Solo guarda un snapshot por día.

    Args:
        df_equipos: DataFrame actual del inventario.
    """
    hoy = date.today().isoformat()

    with _conexion() as conn:
        # Evitar duplicados del mismo día
        existente = conn.execute(
            "SELECT id FROM snapshots_inventario WHERE fecha = ?", (hoy,)
        ).fetchone()

        if existente:
            return

        conn.execute("""
            INSERT INTO snapshots_inventario
                (fecha, total_equipos, criticos, bat_critica, bat_baja, bat_normal,
                 cal_vencida, cal_proxima, cal_vigente, bateria_promedio)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            hoy,
            len(df_equipos),
            int(df_equipos["Alerta Crítica"].sum()),
            int((df_equipos["Estado Batería"] == "CRÍTICO").sum()),
            int((df_equipos["Estado Batería"] == "BAJO").sum()),
            int((df_equipos["Estado Batería"] == "NORMAL").sum()),
            int((df_equipos["Estado Calibración"] == "VENCIDA").sum()),
            int((df_equipos["Estado Calibración"] == "PRÓXIMA").sum()),
            int((df_equipos["Estado Calibración"] == "VIGENTE").sum()),
            round(float(df_equipos["Batería (%)"].mean()), 1),
        ))


def obtener_tendencias(dias: int = 30) -> list:
    """
    Retorna los snapshots de los últimos N días para graficar tendencias.

    Args:
        dias: Número de días hacia atrás.

    Returns:
        Lista de snapshots ordenados por fecha ascendente.
    """
    desde = (date.today() - timedelta(days=dias)).isoformat()
    with _conexion() as conn:
        cursor = conn.execute("""
            SELECT * FROM snapshots_inventario
            WHERE fecha >= ?
            ORDER BY fecha ASC
        """, (desde,))
        return [dict(row) for row in cursor.fetchall()]


def resumen_mantenimiento() -> dict:
    """Retorna métricas clave del módulo de mantenimiento."""
    with _conexion() as conn:
        pendientes  = conn.execute("SELECT COUNT(*) FROM ordenes_mantenimiento WHERE estado='Pendiente'").fetchone()[0]
        en_proceso  = conn.execute("SELECT COUNT(*) FROM ordenes_mantenimiento WHERE estado='En proceso'").fetchone()[0]
        completados = conn.execute("SELECT COUNT(*) FROM ordenes_mantenimiento WHERE estado='Completado'").fetchone()[0]
        vencidos    = len(obtener_vencidos())
        proximos_7  = len(obtener_proximos(7))

        return {
            "pendientes": pendientes,
            "en_proceso": en_proceso,
            "completados": completados,
            "vencidos": vencidos,
            "proximos_7_dias": proximos_7,
        }
