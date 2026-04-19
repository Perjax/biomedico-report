"""
app.py — Servidor Web del Sistema de Gestion Biomedica
=======================================================
Version con base de datos SQLite persistente + login.

Los equipos se guardan en data/biomedico.db y persisten
aunque cierres el servidor.

Uso:
    py app.py

Credenciales:
    admin   / biomedico123  (acceso completo)
    tecnico / tecnico456    (solo ver y exportar)
"""

import os
import io
import tempfile
from functools import wraps

import pandas as pd
from flask import (
    Flask, jsonify, redirect, render_template,
    request, send_file, session, url_for,
)

from modules.data_generator import generar_datos
from modules.chart_generator import generar_grafica_bateria, generar_grafica_resumen
from modules.pdf_generator import generar_pdf
from modules.excel_exporter import exportar_excel
from modules.auth import verificar_credenciales, tiene_permiso
from modules.database import (
    inicializar_db, obtener_equipos, guardar_equipos,
    agregar_equipo, actualizar_equipo, eliminar_equipo,
    obtener_historial, hay_datos,
)


# ---------------------------------------------------------------------------
# Inicializacion
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder=".", static_url_path="", template_folder="templates")
app.secret_key = "biomedico-secret-key-2025-cambiar-en-produccion"

# Crear tablas y cargar demo si la BD esta vacia
with app.app_context():
    inicializar_db()
    if not hay_datos():
        print("  Base de datos vacia — cargando datos demo...")
        guardar_equipos(generar_datos(seed=42))
        print("  ✓ Datos demo cargados en la BD")


# ---------------------------------------------------------------------------
# Decoradores
# ---------------------------------------------------------------------------
def login_requerido(f):
    @wraps(f)
    def decorado(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorado


def permiso_requerido(permiso):
    def decorador(f):
        @wraps(f)
        def decorado(*args, **kwargs):
            if "usuario" not in session:
                return redirect(url_for("login"))
            if not tiene_permiso(session, permiso):
                return jsonify({"error": "No tienes permiso para esta accion"}), 403
            return f(*args, **kwargs)
        return decorado
    return decorador


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _df_a_dict(df: pd.DataFrame) -> list:
    df_json = df.copy()
    df_json["Alerta Critica"] = df_json["Alerta Critica"].apply(
        lambda x: "CRITICO" if x else "OK"
    )
    return df_json.to_dict(orient="records")


def _procesar_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    from modules.data_generator import (
        calcular_estado_bateria, calcular_estado_calibracion, es_critico,
    )
    from datetime import datetime

    registros = []
    for _, row in df_raw.iterrows():
        equipo    = str(row.get("Equipo") or row.get("equipo") or "Sin nombre")
        ubicacion = str(row.get("Ubicacion") or row.get("Ubicacion") or "N/A")
        bateria   = int(row.get("Bateria (%)") or row.get("Bateria") or 50)
        ult_cal   = str(row.get("Ultima Calibracion") or row.get("Ultima Calibracion") or "2025-01-01")

        try:
            fecha = pd.to_datetime(ult_cal)
            dias  = (datetime.now() - fecha.to_pydatetime().replace(tzinfo=None)).days
        except Exception:
            dias = 90

        registros.append({
            "Equipo": equipo, "Ubicacion": ubicacion,
            "Bateria (%)": bateria,
            "Estado Bateria": calcular_estado_bateria(bateria),
            "Ultima Calibracion": ult_cal[:10],
            "Dias desde Calibracion": dias,
            "Estado Calibracion": calcular_estado_calibracion(dias),
            "Alerta Critica": es_critico(bateria, dias),
        })

    df = pd.DataFrame(registros)
    return df.sort_values("Alerta Critica", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Autenticacion
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if "usuario" in session:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        resultado = verificar_credenciales(
            request.form.get("usuario", "").strip(),
            request.form.get("contrasena", ""),
        )
        if resultado:
            session.update(resultado)
            return redirect(url_for("index"))
        error = "Usuario o contrasena incorrectos"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route("/")
@login_requerido
def index():
    ruta_html = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(ruta_html, "r", encoding="utf-8") as f:
        contenido = f.read()

    es_admin  = session.get("rol") == "admin"
    color_rol = "rgba(59,130,246,0.15)" if es_admin else "rgba(34,197,94,0.12)"
    texto_rol = "#3b82f6" if es_admin else "#22c55e"

    barra = f"""
    <div style="display:flex;align-items:center;justify-content:space-between;
        padding:8px 24px;font-size:12px;background:#0a0e1a;
        border-bottom:1px solid rgba(255,255,255,0.07);
        font-family:'DM Sans',sans-serif;color:#8892a4;">
      <span>
        Sesion activa:
        <strong style="color:#e8eaf0">{session['nombre']}</strong>
        <span style="margin-left:8px;padding:2px 8px;border-radius:20px;font-size:10px;
            background:{color_rol};color:{texto_rol};font-family:monospace;">
          {session['rol'].upper()}
        </span>
      </span>
      <a href="/logout" style="color:#8892a4;text-decoration:none;padding:5px 12px;
          border-radius:8px;border:1px solid rgba(255,255,255,0.1);"
         onmouseover="this.style.background='rgba(255,255,255,0.05)'"
         onmouseout="this.style.background='transparent'">
        Cerrar sesion
      </a>
    </div>"""

    contenido = contenido.replace("<body>", "<body>" + barra, 1)
    return contenido


# ---------------------------------------------------------------------------
# API — Datos (lee desde BD)
# ---------------------------------------------------------------------------
@app.route("/api/datos")
@login_requerido
def api_datos():
    df = obtener_equipos()
    if df.empty:
        return jsonify({"total": 0, "criticos": 0, "equipos": []})
    return jsonify({
        "total": len(df),
        "criticos": int(df["Alerta Critica"].sum()),
        "usuario": session.get("nombre"),
        "rol": session.get("rol"),
        "equipos": _df_a_dict(df),
    })


@app.route("/api/resumen")
@login_requerido
def api_resumen():
    df = obtener_equipos()
    if df.empty:
        return jsonify({"total_equipos": 0})
    return jsonify({
        "total_equipos": len(df),
        "alertas_criticas": int(df["Alerta Critica"].sum()),
        "bateria_critica": int((df["Estado Bateria"] == "CRITICO").sum()),
        "bateria_baja": int((df["Estado Bateria"] == "BAJO").sum()),
        "bateria_normal": int((df["Estado Bateria"] == "NORMAL").sum()),
        "calibracion_vencida": int((df["Estado Calibracion"] == "VENCIDA").sum()),
        "calibracion_proxima": int((df["Estado Calibracion"] == "PROXIMA").sum()),
        "calibracion_vigente": int((df["Estado Calibracion"] == "VIGENTE").sum()),
        "bateria_promedio": round(df["Bateria (%)"].mean(), 1),
        "dias_promedio_calibracion": round(df["Dias desde Calibracion"].mean(), 1),
    })


# ---------------------------------------------------------------------------
# API — CRUD de equipos (solo admin)
# ---------------------------------------------------------------------------
@app.route("/api/equipos", methods=["POST"])
@permiso_requerido("subir")
def api_agregar_equipo():
    """Agrega un equipo nuevo a la base de datos."""
    datos = request.get_json()
    if not datos or not datos.get("equipo"):
        return jsonify({"error": "El campo 'equipo' es requerido"}), 400
    nuevo_id = agregar_equipo(datos)
    return jsonify({"mensaje": "Equipo agregado correctamente", "id": nuevo_id}), 201


@app.route("/api/equipos/<int:equipo_id>", methods=["PUT"])
@permiso_requerido("subir")
def api_actualizar_equipo(equipo_id):
    """Actualiza los datos de un equipo existente."""
    datos = request.get_json()
    if not datos:
        return jsonify({"error": "No se enviaron datos"}), 400
    ok = actualizar_equipo(equipo_id, datos)
    if not ok:
        return jsonify({"error": "Equipo no encontrado"}), 404
    return jsonify({"mensaje": "Equipo actualizado correctamente"})


@app.route("/api/equipos/<int:equipo_id>", methods=["DELETE"])
@permiso_requerido("subir")
def api_eliminar_equipo(equipo_id):
    """Elimina un equipo de la base de datos."""
    ok = eliminar_equipo(equipo_id)
    if not ok:
        return jsonify({"error": "Equipo no encontrado"}), 404
    return jsonify({"mensaje": "Equipo eliminado correctamente"})


# ---------------------------------------------------------------------------
# API — Historial
# ---------------------------------------------------------------------------
@app.route("/api/historial")
@login_requerido
def api_historial():
    """Retorna el historial de cambios de estado."""
    historial = obtener_historial(limite=100)
    return jsonify({"historial": historial, "total": len(historial)})


# ---------------------------------------------------------------------------
# API — Subir archivo CSV/Excel (guarda en BD)
# ---------------------------------------------------------------------------
@app.route("/api/subir", methods=["POST"])
@permiso_requerido("subir")
def api_subir():
    if "archivo" not in request.files:
        return jsonify({"error": "No se envio ningun archivo"}), 400

    archivo = request.files["archivo"]
    nombre  = archivo.filename.lower()

    try:
        if nombre.endswith(".csv"):
            df_raw = pd.read_csv(archivo)
        elif nombre.endswith((".xlsx", ".xls")):
            df_raw = pd.read_excel(archivo)
        else:
            return jsonify({"error": "Formato no soportado. Usa CSV o Excel."}), 400

        df_raw.columns = [c.strip() for c in df_raw.columns]
        if "Equipo" not in df_raw.columns and "equipo" not in df_raw.columns:
            return jsonify({"error": "El archivo debe tener una columna 'Equipo'"}), 400

        df = _procesar_dataframe(df_raw)
        guardar_equipos(df)  # ← Guarda en BD

        return jsonify({
            "mensaje": f"✓ {len(df)} equipos guardados en la base de datos",
            "total": len(df),
            "criticos": int(df["Alerta Critica"].sum()),
            "equipos": _df_a_dict(df),
        })

    except Exception as e:
        return jsonify({"error": f"Error al procesar: {str(e)}"}), 400


# ---------------------------------------------------------------------------
# API — PDF y Excel
# ---------------------------------------------------------------------------
@app.route("/api/pdf")
@permiso_requerido("exportar")
def api_pdf():
    try:
        df = obtener_equipos()
        with tempfile.TemporaryDirectory() as tmp:
            ruta_barras = os.path.join(tmp, "grafica_bateria.png")
            ruta_dona   = os.path.join(tmp, "grafica_resumen.png")
            ruta_pdf    = os.path.join(tmp, "reporte_biomedico.pdf")
            generar_grafica_bateria(df, ruta_barras)
            generar_grafica_resumen(df, ruta_dona)
            generar_pdf(df, ruta_barras, ruta_dona, ruta_pdf)
            with open(ruta_pdf, "rb") as f:
                pdf_bytes = f.read()
        return send_file(io.BytesIO(pdf_bytes), mimetype="application/pdf",
                         as_attachment=True, download_name="reporte_biomedico.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/excel")
@permiso_requerido("exportar")
def api_excel():
    try:
        df = obtener_equipos()
        with tempfile.TemporaryDirectory() as tmp:
            ruta_excel = os.path.join(tmp, "reporte_biomedico.xlsx")
            exportar_excel(df, ruta_excel)
            with open(ruta_excel, "rb") as f:
                excel_bytes = f.read()
        return send_file(io.BytesIO(excel_bytes),
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name="reporte_biomedico.xlsx")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API — Demo (recarga datos demo en BD)
# ---------------------------------------------------------------------------
@app.route("/api/demo", methods=["POST"])
@permiso_requerido("subir")
def api_demo():
    df = generar_datos(seed=42)
    guardar_equipos(df)
    return jsonify({
        "mensaje": f"✓ Datos demo guardados: {len(df)} equipos",
        "total": len(df),
        "criticos": int(df["Alerta Critica"].sum()),
        "equipos": _df_a_dict(df),
    })


# ---------------------------------------------------------------------------
# API — Estado
# ---------------------------------------------------------------------------
@app.route("/api/estado")
@login_requerido
def api_estado():
    df = obtener_equipos()
    return jsonify({
        "estado": "activo",
        "equipos_en_bd": len(df),
        "usuario": session.get("nombre"),
        "rol": session.get("rol"),
        "version": "3.0.0",
        "base_de_datos": "SQLite (persistente)",
    })


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 52)
    print("  SISTEMA DE GESTION BIOMEDICA v3.0")
    print("  Con base de datos SQLite persistente")
    print("=" * 52)
    print("\n  Abre esto en tu navegador:")
    print("  → http://localhost:5000")
    print("\n  Usuarios:")
    print("  admin   / biomedico123  (acceso completo)")
    print("  tecnico / tecnico456    (solo ver y exportar)")
    print("\n  Base de datos: data/biomedico.db")
    print("  Presiona Ctrl+C para detener")
    print("=" * 52 + "\n")

    app.run(debug=True, port=5000)


# ---------------------------------------------------------------------------
# Modulo de Mantenimiento — rutas
# ---------------------------------------------------------------------------
from modules.mantenimiento import (
    inicializar_tablas_mantenimiento, crear_orden, obtener_ordenes,
    completar_orden, actualizar_orden, eliminar_orden,
    obtener_proximos, obtener_vencidos,
    obtener_historial_mantenimiento, registrar_snapshot,
    obtener_tendencias, resumen_mantenimiento,
)

# Inicializar tablas de mantenimiento al arrancar
with app.app_context():
    inicializar_tablas_mantenimiento()


@app.route("/mantenimiento")
@login_requerido
def mantenimiento():
    """Sirve la pagina del modulo de mantenimiento."""
    return render_template("mantenimiento.html")


@app.route("/api/mantenimiento/resumen")
@login_requerido
def api_mant_resumen():
    return jsonify(resumen_mantenimiento())


@app.route("/api/mantenimiento/ordenes", methods=["GET"])
@login_requerido
def api_mant_ordenes():
    estado = request.args.get("estado")
    ordenes = obtener_ordenes(estado=estado)
    return jsonify({"ordenes": ordenes, "total": len(ordenes)})


@app.route("/api/mantenimiento/ordenes", methods=["POST"])
@permiso_requerido("subir")
def api_mant_crear():
    datos = request.get_json()
    if not datos or not datos.get("equipo"):
        return jsonify({"error": "El campo equipo es requerido"}), 400
    nuevo_id = crear_orden(datos)
    return jsonify({"mensaje": "Orden creada", "id": nuevo_id}), 201


@app.route("/api/mantenimiento/ordenes/<int:orden_id>", methods=["PUT"])
@permiso_requerido("subir")
def api_mant_actualizar(orden_id):
    datos = request.get_json()
    ok = actualizar_orden(orden_id, datos)
    if not ok:
        return jsonify({"error": "Orden no encontrada"}), 404
    return jsonify({"mensaje": "Orden actualizada"})


@app.route("/api/mantenimiento/ordenes/<int:orden_id>", methods=["DELETE"])
@permiso_requerido("subir")
def api_mant_eliminar(orden_id):
    ok = eliminar_orden(orden_id)
    if not ok:
        return jsonify({"error": "Orden no encontrada"}), 404
    return jsonify({"mensaje": "Orden eliminada"})


@app.route("/api/mantenimiento/ordenes/<int:orden_id>/completar", methods=["POST"])
@permiso_requerido("exportar")
def api_mant_completar(orden_id):
    datos = request.get_json() or {}
    ok = completar_orden(orden_id, datos)
    if not ok:
        return jsonify({"error": "Orden no encontrada"}), 404
    return jsonify({"mensaje": "Orden completada y registrada en historial"})


@app.route("/api/mantenimiento/proximos")
@login_requerido
def api_mant_proximos():
    dias = int(request.args.get("dias", 30))
    proximos = obtener_proximos(dias)
    return jsonify({"proximos": proximos, "total": len(proximos)})


@app.route("/api/mantenimiento/vencidos")
@login_requerido
def api_mant_vencidos():
    vencidos = obtener_vencidos()
    return jsonify({"vencidos": vencidos, "total": len(vencidos)})


@app.route("/api/mantenimiento/historial")
@login_requerido
def api_mant_historial():
    historial = obtener_historial_mantenimiento()
    return jsonify({"historial": historial, "total": len(historial)})


@app.route("/api/mantenimiento/tendencias")
@login_requerido
def api_mant_tendencias():
    dias = int(request.args.get("dias", 60))
    snapshots = obtener_tendencias(dias)
    return jsonify({"snapshots": snapshots, "total": len(snapshots)})


@app.route("/api/mantenimiento/snapshot", methods=["POST"])
@permiso_requerido("subir")
def api_mant_snapshot():
    """Genera manualmente un snapshot del inventario actual."""
    df = obtener_equipos()
    if not df.empty:
        registrar_snapshot(df)
        return jsonify({"mensaje": "Snapshot registrado"})
    return jsonify({"error": "No hay equipos cargados"}), 400
