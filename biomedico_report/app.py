"""
app.py — Servidor Web del Sistema de Gestión Biomédica
=======================================================
Versión con autenticación por usuario y contraseña.

Uso:
    py app.py

Luego abre en el navegador:
    http://localhost:5000

Credenciales de demo:
    admin    / biomedico123   (acceso completo)
    tecnico  / tecnico456     (solo lectura y exportar)
"""

import os
import io
import tempfile
from functools import wraps

import pandas as pd
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from modules.data_generator import generar_datos
from modules.chart_generator import generar_grafica_bateria, generar_grafica_resumen
from modules.pdf_generator import generar_pdf
from modules.excel_exporter import exportar_excel
from modules.auth import verificar_credenciales, tiene_permiso


# ---------------------------------------------------------------------------
# Inicialización
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder=".", static_url_path="", template_folder="templates")

# Clave secreta para firmar las sesiones — cámbiala en producción
app.secret_key = "biomedico-secret-key-2025-cambiar-en-produccion"

# Estado en memoria
_estado = {"df": None}


# ---------------------------------------------------------------------------
# Decoradores de protección
# ---------------------------------------------------------------------------
def login_requerido(f):
    """Redirige al login si el usuario no tiene sesión activa."""
    @wraps(f)
    def decorado(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorado


def permiso_requerido(permiso):
    """Bloquea la ruta si el usuario no tiene el permiso indicado."""
    def decorador(f):
        @wraps(f)
        def decorado(*args, **kwargs):
            if "usuario" not in session:
                return redirect(url_for("login"))
            if not tiene_permiso(session, permiso):
                return jsonify({"error": "No tienes permiso para esta acción"}), 403
            return f(*args, **kwargs)
        return decorado
    return decorador


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _obtener_df() -> pd.DataFrame:
    if _estado["df"] is None:
        _estado["df"] = generar_datos(seed=42)
    return _estado["df"]


def _df_a_dict(df: pd.DataFrame) -> list:
    df_json = df.copy()
    df_json["Alerta Crítica"] = df_json["Alerta Crítica"].apply(
        lambda x: "CRÍTICO" if x else "OK"
    )
    return df_json.to_dict(orient="records")


def _procesar_dataframe(df_raw: pd.DataFrame) -> pd.DataFrame:
    from modules.data_generator import (
        calcular_estado_bateria,
        calcular_estado_calibracion,
        es_critico,
    )
    from datetime import datetime

    registros = []
    for _, row in df_raw.iterrows():
        equipo    = row.get("Equipo") or row.get("equipo") or "Sin nombre"
        ubicacion = row.get("Ubicación") or row.get("Ubicacion") or "N/A"
        bateria   = int(row.get("Batería (%)") or row.get("Bateria") or 50)

        ult_cal = row.get("Última Calibración") or row.get("Ultima Calibracion") or "2025-01-01"
        try:
            fecha = pd.to_datetime(str(ult_cal))
            dias  = (datetime.now() - fecha.to_pydatetime().replace(tzinfo=None)).days
        except Exception:
            dias = 90

        registros.append({
            "Equipo": str(equipo),
            "Ubicación": str(ubicacion),
            "Batería (%)": bateria,
            "Estado Batería": calcular_estado_bateria(bateria),
            "Última Calibración": str(ult_cal)[:10],
            "Días desde Calibración": dias,
            "Estado Calibración": calcular_estado_calibracion(dias),
            "Alerta Crítica": es_critico(bateria, dias),
        })

    df = pd.DataFrame(registros)
    return df.sort_values("Alerta Crítica", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Rutas de autenticación
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    """Muestra el formulario de login y procesa las credenciales."""
    if "usuario" in session:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        usuario    = request.form.get("usuario", "").strip()
        contrasena = request.form.get("contrasena", "")

        resultado = verificar_credenciales(usuario, contrasena)
        if resultado:
            session["usuario"]  = resultado["usuario"]
            session["nombre"]   = resultado["nombre"]
            session["rol"]      = resultado["rol"]
            session["permisos"] = resultado["permisos"]
            return redirect(url_for("index"))
        else:
            error = "Usuario o contraseña incorrectos"

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    """Cierra la sesión y redirige al login."""
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Dashboard principal
# ---------------------------------------------------------------------------
@app.route("/")
@login_requerido
def index():
    """Sirve el dashboard con barra de sesión inyectada."""
    ruta_html = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(ruta_html, "r", encoding="utf-8") as f:
        contenido = f.read()

    es_admin = session.get("rol") == "admin"
    color_rol   = "rgba(59,130,246,0.15)" if es_admin else "rgba(34,197,94,0.12)"
    texto_rol   = "#3b82f6"               if es_admin else "#22c55e"

    barra = f"""
    <div style="
        display:flex;align-items:center;justify-content:space-between;
        padding:8px 24px;font-size:12px;
        background:#0a0e1a;border-bottom:1px solid rgba(255,255,255,0.07);
        font-family:'DM Sans',sans-serif;color:#8892a4;
    ">
      <span>
        Sesión activa:
        <strong style="color:#e8eaf0">{session['nombre']}</strong>
        <span style="
            margin-left:8px;padding:2px 8px;border-radius:20px;font-size:10px;
            background:{color_rol};color:{texto_rol};font-family:monospace;
        ">{session['rol'].upper()}</span>
      </span>
      <a href="/logout" style="
          color:#8892a4;text-decoration:none;padding:5px 12px;
          border-radius:8px;border:1px solid rgba(255,255,255,0.1);
      " onmouseover="this.style.background='rgba(255,255,255,0.05)'"
         onmouseout="this.style.background='transparent'">
        Cerrar sesión
      </a>
    </div>
    """
    contenido = contenido.replace("<body>", "<body>" + barra, 1)
    return contenido


# ---------------------------------------------------------------------------
# API — Datos
# ---------------------------------------------------------------------------
@app.route("/api/datos")
@login_requerido
def api_datos():
    df = _obtener_df()
    return jsonify({
        "total": len(df),
        "criticos": int(df["Alerta Crítica"].sum()),
        "usuario": session.get("nombre"),
        "rol": session.get("rol"),
        "equipos": _df_a_dict(df)
    })


@app.route("/api/resumen")
@login_requerido
def api_resumen():
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
# API — Subir archivo (solo admin)
# ---------------------------------------------------------------------------
@app.route("/api/subir", methods=["POST"])
@permiso_requerido("subir")
def api_subir():
    if "archivo" not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400

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
        _estado["df"] = df

        return jsonify({
            "mensaje": f"✓ {len(df)} equipos cargados correctamente",
            "total": len(df),
            "criticos": int(df["Alerta Crítica"].sum()),
            "equipos": _df_a_dict(df)
        })

    except Exception as e:
        return jsonify({"error": f"Error al procesar: {str(e)}"}), 400


# ---------------------------------------------------------------------------
# API — PDF
# ---------------------------------------------------------------------------
@app.route("/api/pdf")
@permiso_requerido("exportar")
def api_pdf():
    try:
        df = _obtener_df()
        with tempfile.TemporaryDirectory() as tmp:
            ruta_barras = os.path.join(tmp, "grafica_bateria.png")
            ruta_dona   = os.path.join(tmp, "grafica_resumen.png")
            ruta_pdf    = os.path.join(tmp, "reporte_biomedico.pdf")

            generar_grafica_bateria(df, ruta_barras)
            generar_grafica_resumen(df, ruta_dona)
            generar_pdf(df, ruta_barras, ruta_dona, ruta_pdf)

            with open(ruta_pdf, "rb") as f:
                pdf_bytes = f.read()

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="reporte_biomedico.pdf",
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API — Excel
# ---------------------------------------------------------------------------
@app.route("/api/excel")
@permiso_requerido("exportar")
def api_excel():
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
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API — Demo y estado
# ---------------------------------------------------------------------------
@app.route("/api/demo", methods=["POST"])
@login_requerido
def api_demo():
    _estado["df"] = generar_datos(seed=42)
    df = _estado["df"]
    return jsonify({
        "mensaje": f"✓ Datos demo cargados: {len(df)} equipos",
        "total": len(df),
        "criticos": int(df["Alerta Crítica"].sum()),
        "equipos": _df_a_dict(df)
    })


@app.route("/api/estado")
@login_requerido
def api_estado():
    df = _obtener_df()
    return jsonify({
        "estado": "activo",
        "equipos_cargados": len(df),
        "usuario": session.get("nombre"),
        "rol": session.get("rol"),
        "version": "2.0.0"
    })


# ---------------------------------------------------------------------------
# Punto de entrada
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 52)
    print("  SISTEMA DE GESTIÓN BIOMÉDICA v2.0 — con Login")
    print("=" * 52)
    print("\n  Abre esto en tu navegador:")
    print("  → http://localhost:5000")
    print("\n  Usuarios disponibles:")
    print("  admin   / biomedico123  (acceso completo)")
    print("  tecnico / tecnico456    (solo ver y exportar)")
    print("\n  Presiona Ctrl+C para detener")
    print("=" * 52 + "\n")

    app.run(debug=True, port=5000)
