"""
app.py — Servidor Web del Sistema de Gestión Biomédica
=======================================================
Levanta un servidor Flask que conecta el dashboard HTML
con todos los módulos Python del proyecto.

Uso:
    py app.py

Luego abre en el navegador:
    http://localhost:5000
"""

import os
import io
import json
import tempfile

import pandas as pd
from flask import (
    Flask,
    jsonify,
    request,
    send_file,
    render_template_string,
)

# Importar módulos del proyecto
from modules.data_generator import generar_datos
from modules.chart_generator import generar_grafica_bateria, generar_grafica_resumen
from modules.pdf_generator import generar_pdf
from modules.excel_exporter import exportar_excel


# ---------------------------------------------------------------------------
# Inicialización de la app
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder=".", static_url_path="")

# Estado en memoria: guarda el DataFrame activo de la sesión
_estado = {"df": None}


def _obtener_df() -> pd.DataFrame:
    """
    Retorna el DataFrame activo. Si no hay datos cargados,
    genera el demo por defecto.
    """
    if _estado["df"] is None:
        _estado["df"] = generar_datos(seed=42)
    return _estado["df"]


def _df_a_dict(df: pd.DataFrame) -> list:
    """Convierte el DataFrame a lista de dicts serializable en JSON."""
    df_json = df.copy()
    df_json["Alerta Crítica"] = df_json["Alerta Crítica"].apply(
        lambda x: "CRÍTICO" if x else "OK"
    )
    return df_json.to_dict(orient="records")


# ---------------------------------------------------------------------------
# Ruta principal — sirve el dashboard HTML
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Sirve el dashboard como página principal."""
    ruta_html = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(ruta_html, "r", encoding="utf-8") as f:
        contenido = f.read()
    return contenido


# ---------------------------------------------------------------------------
# API — Datos
# ---------------------------------------------------------------------------
@app.route("/api/datos", methods=["GET"])
def api_datos():
    """
    Retorna el inventario completo como JSON.

    Response:
        200: Lista de equipos con todos sus campos
    """
    df = _obtener_df()
    return jsonify({
        "total": len(df),
        "criticos": int(df["Alerta Crítica"].sum()),
        "equipos": _df_a_dict(df)
    })


@app.route("/api/resumen", methods=["GET"])
def api_resumen():
    """
    Retorna métricas ejecutivas del inventario.

    Response:
        200: KPIs principales del inventario
    """
    df = _obtener_df()
    return jsonify({
        "total_equipos": len(df),
        "alertas_criticas": int(df["Alerta Crítica"].sum()),
        "bateria_critica": int((df["Estado Batería"] == "CRÍTICO").sum()),
        "bateria_baja": int((df["Estado Batería"] == "BAJO").sum()),
        "bateria_normal": int((df["Estado Batería"] == "NORMAL").sum()),
        "calibracion_vencida": int((df["Estado Calibración"] == "VENCIDA").sum()),
        "calibracion_proxima": int((df["Estado Calibración"] == "PRÓXIMA").sum()),
        "calibracion_vigente": int((df["Estado Calibración"] == "VIGENTE").sum()),
        "bateria_promedio": round(df["Batería (%)"].mean(), 1),
        "dias_promedio_calibracion": round(df["Días desde Calibración"].mean(), 1),
    })


# ---------------------------------------------------------------------------
# API — Carga de archivos
# ---------------------------------------------------------------------------
@app.route("/api/subir", methods=["POST"])
def api_subir():
    """
    Recibe un archivo CSV o Excel, lo procesa y actualiza el estado.

    Body (multipart/form-data):
        archivo: Archivo .csv o .xlsx

    Response:
        200: Datos procesados correctamente
        400: Archivo inválido o columnas faltantes
    """
    if "archivo" not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400

    archivo = request.files["archivo"]
    nombre = archivo.filename.lower()

    try:
        if nombre.endswith(".csv"):
            df_raw = pd.read_csv(archivo)
        elif nombre.endswith((".xlsx", ".xls")):
            df_raw = pd.read_excel(archivo)
        else:
            return jsonify({"error": "Formato no soportado. Usa CSV o Excel."}), 400

        # Verificar columna mínima requerida
        if "Equipo" not in df_raw.columns and "equipo" not in df_raw.columns:
            return jsonify({"error": "El archivo debe tener una columna 'Equipo'"}), 400

        # Normalizar y calcular estados
        df_raw.columns = [c.strip() for c in df_raw.columns]
        df = _procesar_dataframe(df_raw)
        _estado["df"] = df

        return jsonify({
            "mensaje": f"✓ {len(df)} equipos cargados correctamente",
            "total": len(df),
            "criticos": int(df["Alerta Crítica"].sum()),
            "equipos": _df_a_dict(df)
        })

    except Exception as e:
        return jsonify({"error": f"Error al procesar el archivo: {str(e)}"}), 400


def _procesar_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Toma un DataFrame crudo del usuario y calcula todos los campos necesarios.

    Args:
        df_raw: DataFrame con columnas básicas del usuario.

    Returns:
        DataFrame completo con estados y alertas calculados.
    """
    from modules.data_generator import (
        calcular_estado_bateria,
        calcular_estado_calibracion,
        es_critico,
    )
    from datetime import datetime

    registros = []
    for _, row in df_raw.iterrows():
        equipo = row.get("Equipo") or row.get("equipo") or "Sin nombre"
        ubicacion = row.get("Ubicación") or row.get("Ubicacion") or row.get("ubicacion") or "N/A"
        bateria = int(row.get("Batería (%)") or row.get("Bateria") or row.get("bateria") or 50)

        ult_cal_raw = row.get("Última Calibración") or row.get("Ultima Calibracion") or "2025-01-01"
        try:
            fecha_cal = pd.to_datetime(str(ult_cal_raw))
            dias = (datetime.now() - fecha_cal.to_pydatetime().replace(tzinfo=None)).days
        except Exception:
            dias = 90

        registros.append({
            "Equipo": str(equipo),
            "Ubicación": str(ubicacion),
            "Batería (%)": bateria,
            "Estado Batería": calcular_estado_bateria(bateria),
            "Última Calibración": str(ult_cal_raw)[:10],
            "Días desde Calibración": dias,
            "Estado Calibración": calcular_estado_calibracion(dias),
            "Alerta Crítica": es_critico(bateria, dias),
        })

    df = pd.DataFrame(registros)
    return df.sort_values("Alerta Crítica", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# API — Generación de PDF
# ---------------------------------------------------------------------------
@app.route("/api/pdf", methods=["GET"])
def api_pdf():
    """
    Genera el reporte PDF completo y lo retorna para descarga.

    Response:
        200: Archivo PDF listo para descargar
        500: Error durante la generación
    """
    try:
        df = _obtener_df()

        # Usar directorio temporal para los archivos intermedios
        with tempfile.TemporaryDirectory() as tmp:
            ruta_barras = os.path.join(tmp, "grafica_bateria.png")
            ruta_dona   = os.path.join(tmp, "grafica_resumen.png")
            ruta_pdf    = os.path.join(tmp, "reporte_biomedico.pdf")

            generar_grafica_bateria(df, ruta_barras)
            generar_grafica_resumen(df, ruta_dona)
            generar_pdf(df, ruta_barras, ruta_dona, ruta_pdf)

            # Leer el PDF en memoria antes de que se borre el directorio temporal
            with open(ruta_pdf, "rb") as f:
                pdf_bytes = f.read()

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="reporte_biomedico.pdf",
        )

    except Exception as e:
        return jsonify({"error": f"Error al generar el PDF: {str(e)}"}), 500


# ---------------------------------------------------------------------------
# API — Generación de Excel
# ---------------------------------------------------------------------------
@app.route("/api/excel", methods=["GET"])
def api_excel():
    """
    Genera el reporte Excel y lo retorna para descarga.

    Response:
        200: Archivo Excel listo para descargar
        500: Error durante la generación
    """
    try:
        df = _obtener_df()

        with tempfile.TemporaryDirectory() as tmp:
            ruta_excel = os.path.join(tmp, "reporte_biomedico.xlsx")
            exportar_excel(df, ruta_excel)

            with open(ruta_excel, "rb") as f:
                excel_bytes = f.read()

        return send_file(
            io.BytesIO(excel_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="reporte_biomedico.xlsx",
        )

    except Exception as e:
        return jsonify({"error": f"Error al generar el Excel: {str(e)}"}), 500


# ---------------------------------------------------------------------------
# API — Demo
# ---------------------------------------------------------------------------
@app.route("/api/demo", methods=["POST"])
def api_demo():
    """
    Carga los datos de demostración y resetea el estado.

    Response:
        200: Datos demo cargados
    """
    _estado["df"] = generar_datos(seed=42)
    df = _estado["df"]
    return jsonify({
        "mensaje": f"✓ Datos demo cargados: {len(df)} equipos",
        "total": len(df),
        "criticos": int(df["Alerta Crítica"].sum()),
        "equipos": _df_a_dict(df)
    })


# ---------------------------------------------------------------------------
# API — Estado del servidor
# ---------------------------------------------------------------------------
@app.route("/api/estado", methods=["GET"])
def api_estado():
    """Endpoint de health-check para verificar que el servidor está activo."""
    df = _obtener_df()
    return jsonify({
        "estado": "activo",
        "equipos_cargados": len(df),
        "version": "2.0.0"
    })


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 52)
    print("  SISTEMA DE GESTIÓN BIOMÉDICA — Servidor Web")
    print("=" * 52)
    print("\n  Abre esto en tu navegador:")
    print("  → http://localhost:5000\n")
    print("  Endpoints disponibles:")
    print("  GET  /api/datos     → inventario JSON")
    print("  GET  /api/resumen   → KPIs ejecutivos")
    print("  GET  /api/pdf       → descarga PDF")
    print("  GET  /api/excel     → descarga Excel")
    print("  POST /api/subir     → carga CSV/Excel")
    print("  POST /api/demo      → datos de demo")
    print("\n  Presiona Ctrl+C para detener el servidor")
    print("=" * 52 + "\n")

    app.run(debug=True, port=5000)
