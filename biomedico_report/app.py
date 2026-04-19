# -*- coding: utf-8 -*-
import os, io, tempfile
from functools import wraps
import pandas as pd
from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from modules.data_generator import generar_datos
from modules.chart_generator import generar_grafica_bateria, generar_grafica_resumen
from modules.pdf_generator import generar_pdf
from modules.excel_exporter import exportar_excel
from modules.database import inicializar_db, obtener_equipos, guardar_equipos, hay_datos
from modules.mantenimiento import inicializar_tablas_mantenimiento, crear_orden, obtener_ordenes, completar_orden, actualizar_orden, eliminar_orden, obtener_proximos, obtener_vencidos, obtener_historial_mantenimiento, registrar_snapshot, obtener_tendencias, resumen_mantenimiento
from modules.clinicas import inicializar_tablas_clinicas, sembrar_datos_iniciales, verificar_login, obtener_clinicas, obtener_clinica, crear_clinica, actualizar_clinica, cambiar_password_clinica, desactivar_clinica, resumen_global

app = Flask(__name__, static_folder=".", static_url_path="", template_folder="templates")
app.secret_key = os.environ.get("SECRET_KEY", "biomedico-2025")

with app.app_context():
    inicializar_db()
    inicializar_tablas_mantenimiento()
    inicializar_tablas_clinicas()
    sembrar_datos_iniciales()
    if not hay_datos():
        df = generar_datos(seed=42)
        guardar_equipos(df)

# ---------------------------------------------------------------------------
# Decoradores
# ---------------------------------------------------------------------------
def login_requerido(f):
    @wraps(f)
    def d(*a, **k):
        if "usuario" not in session:
            return redirect(url_for("login"))
        return f(*a, **k)
    return d

def solo_admin(f):
    @wraps(f)
    def d(*a, **k):
        if "usuario" not in session:
            return redirect(url_for("login"))
        if session.get("rol") != "admin":
            return jsonify({"error": "Solo el admin puede hacer esto"}), 403
        return f(*a, **k)
    return d

def permiso_requerido(permiso):
    def dec(f):
        @wraps(f)
        def d(*a, **k):
            if "usuario" not in session:
                return redirect(url_for("login"))
            if permiso not in session.get("permisos", []):
                return jsonify({"error": "Sin permiso"}), 403
            return f(*a, **k)
        return d
    return dec

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clinica_id():
    """Retorna el clinica_id activo en la sesion (soporta 'entrar como')."""
    return session.get("clinica_id_activo") or session.get("clinica_id")

def _df_a_dict(df):
    df2 = df.copy()
    df2["Alerta Cr\u00edtica"] = df2["Alerta Cr\u00edtica"].apply(lambda x: "CRITICO" if x else "OK")
    return df2.to_dict(orient="records")

def _obtener_df_clinica():
    """Obtiene equipos filtrados por la clinica activa en sesion."""
    from modules.database import obtener_equipos_clinica
    clinica_id = _clinica_id()
    if session.get("rol") == "admin" and not session.get("clinica_id_activo"):
        return obtener_equipos()
    return obtener_equipos_clinica(clinica_id)

def _procesar_df(df_raw):
    from modules.data_generator import calcular_estado_bateria, calcular_estado_calibracion, es_critico
    from datetime import datetime
    rows = []
    for _, row in df_raw.iterrows():
        equipo = str(row.get("Equipo") or row.get("equipo") or "Sin nombre")
        ubicacion = str(row.get("Ubicaci\u00f3n") or row.get("Ubicacion") or "N/A")
        bateria = int(row.get("Bater\u00eda (%)") or row.get("Bateria") or 50)
        ult_cal = str(row.get("\u00daltima Calibraci\u00f3n") or row.get("Ultima Calibracion") or "2025-01-01")
        try:
            dias = (datetime.now() - pd.to_datetime(ult_cal).to_pydatetime().replace(tzinfo=None)).days
        except:
            dias = 90
        rows.append({"Equipo": equipo, "Ubicaci\u00f3n": ubicacion, "Bater\u00eda (%)": bateria,
            "Estado Bater\u00eda": calcular_estado_bateria(bateria),
            "\u00daltima Calibraci\u00f3n": ult_cal[:10], "D\u00edas desde Calibraci\u00f3n": dias,
            "Estado Calibraci\u00f3n": calcular_estado_calibracion(dias),
            "Alerta Cr\u00edtica": es_critico(bateria, dias)})
    df = pd.DataFrame(rows)
    return df.sort_values("Alerta Cr\u00edtica", ascending=False).reset_index(drop=True)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET","POST"])
def login():
    if "usuario" in session:
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        res = verificar_login(request.form.get("usuario","").strip(), request.form.get("contrasena",""))
        if res:
            session.update(res)
            session.pop("clinica_id_activo", None)
            if res["rol"] == "admin":
                return redirect(url_for("admin_panel"))
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
    with open(os.path.join(os.path.dirname(__file__), "dashboard.html"), "r", encoding="utf-8") as f:
        html = f.read()
    rol = session.get("rol","")
    nombre = session.get("nombre","")
    clinica_nombre = session.get("clinica_nombre","")
    color = session.get("clinica_color","#3b82f6")
    modo_clinica = session.get("clinica_id_activo")

    extra_links = ""
    if rol == "admin":
        extra_links = '<a href="/admin" style="color:#8892a4;text-decoration:none;padding:5px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.1);">Panel Admin</a>'
        if modo_clinica:
            extra_links += '<a href="/admin/salir-clinica" style="color:#f97316;text-decoration:none;padding:5px 12px;border-radius:8px;border:1px solid rgba(249,115,22,0.3);">Salir de clinica</a>'

    barra = f'<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 24px;font-size:12px;background:#0a0e1a;border-bottom:1px solid rgba(255,255,255,0.07);font-family:sans-serif;color:#8892a4;"><span>{"Vista: " if modo_clinica else ""}<strong style="color:#e8eaf0">{clinica_nombre or nombre}</strong><span style="margin-left:8px;padding:2px 8px;border-radius:20px;font-size:10px;background:rgba(59,130,246,0.15);color:{color};font-family:monospace;">{rol.upper()}</span></span><div style="display:flex;gap:8px">{extra_links}<a href="/logout" style="color:#8892a4;text-decoration:none;padding:5px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.1);">Cerrar sesion</a></div></div>'
    return html.replace("<body>", "<body>" + barra, 1)

# ---------------------------------------------------------------------------
# Panel Admin
# ---------------------------------------------------------------------------
@app.route("/admin")
@solo_admin
def admin_panel():
    session.pop("clinica_id_activo", None)
    return render_template("admin.html")

@app.route("/admin/salir-clinica")
@solo_admin
def salir_clinica():
    session.pop("clinica_id_activo", None)
    return redirect(url_for("admin_panel"))

@app.route("/api/admin/resumen")
@solo_admin
def api_admin_resumen():
    return jsonify(resumen_global())

@app.route("/api/admin/clinicas", methods=["GET"])
@solo_admin
def api_admin_clinicas():
    return jsonify({"clinicas": obtener_clinicas()})

@app.route("/api/admin/clinicas", methods=["POST"])
@solo_admin
def api_admin_crear_clinica():
    datos = request.get_json()
    if not datos or not datos.get("nombre"):
        return jsonify({"error": "Nombre requerido"}), 400
    if not datos.get("usuario") or not datos.get("password"):
        return jsonify({"error": "Usuario y contrasena requeridos"}), 400
    try:
        clinica_id = crear_clinica(datos)
        return jsonify({"mensaje": "Clinica creada", "id": clinica_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/admin/clinicas/<int:clinica_id>", methods=["PUT"])
@solo_admin
def api_admin_actualizar_clinica(clinica_id):
    actualizar_clinica(clinica_id, request.get_json())
    return jsonify({"mensaje": "Clinica actualizada"})

@app.route("/api/admin/clinicas/<int:clinica_id>/password", methods=["POST"])
@solo_admin
def api_admin_cambiar_password(clinica_id):
    datos = request.get_json()
    if not datos.get("password"):
        return jsonify({"error": "Contrasena requerida"}), 400
    cambiar_password_clinica(clinica_id, datos["password"])
    return jsonify({"mensaje": "Contrasena actualizada"})

@app.route("/api/admin/entrar-como/<int:clinica_id>", methods=["POST"])
@solo_admin
def api_entrar_como(clinica_id):
    clinica = obtener_clinica(clinica_id)
    if not clinica:
        return jsonify({"error": "Clinica no encontrada"}), 404
    session["clinica_id_activo"] = clinica_id
    session["clinica_nombre"] = clinica["nombre"]
    session["clinica_color"] = clinica["color"]
    return jsonify({"ok": True})

# ---------------------------------------------------------------------------
# API Datos (filtrado por clinica)
# ---------------------------------------------------------------------------
@app.route("/api/datos")
@login_requerido
def api_datos():
    from modules.database import obtener_equipos_clinica
    clinica_id = _clinica_id()
    if session.get("rol") == "admin" and not session.get("clinica_id_activo"):
        df = obtener_equipos()
    else:
        df = obtener_equipos_clinica(clinica_id)
    if df.empty:
        return jsonify({"total":0,"criticos":0,"equipos":[]})
    return jsonify({"total":len(df),"criticos":int(df["Alerta Cr\u00edtica"].sum()),"equipos":_df_a_dict(df)})

@app.route("/api/resumen")
@login_requerido
def api_resumen():
    from modules.database import obtener_equipos_clinica
    clinica_id = _clinica_id()
    if session.get("rol") == "admin" and not session.get("clinica_id_activo"):
        df = obtener_equipos()
    else:
        df = obtener_equipos_clinica(clinica_id)
    if df.empty:
        return jsonify({"total_equipos":0})
    return jsonify({"total_equipos":len(df),"alertas_criticas":int(df["Alerta Cr\u00edtica"].sum()),
        "bateria_critica":int((df["Estado Bater\u00eda"]=="CR\u00cdTICO").sum()),
        "bateria_baja":int((df["Estado Bater\u00eda"]=="BAJO").sum()),
        "bateria_normal":int((df["Estado Bater\u00eda"]=="NORMAL").sum()),
        "calibracion_vencida":int((df["Estado Calibraci\u00f3n"]=="VENCIDA").sum()),
        "calibracion_proxima":int((df["Estado Calibraci\u00f3n"]=="PR\u00d3XIMA").sum()),
        "calibracion_vigente":int((df["Estado Calibraci\u00f3n"]=="VIGENTE").sum()),
        "bateria_promedio":round(df["Bater\u00eda (%)"].mean(),1),
        "dias_promedio_calibracion":round(df["D\u00edas desde Calibraci\u00f3n"].mean(),1)})

@app.route("/api/subir", methods=["POST"])
@permiso_requerido("subir")
def api_subir():
    from modules.database import guardar_equipos_clinica
    if "archivo" not in request.files:
        return jsonify({"error":"No se envio archivo"}),400
    archivo = request.files["archivo"]
    nombre = archivo.filename.lower()
    try:
        df_raw = pd.read_csv(archivo) if nombre.endswith(".csv") else pd.read_excel(archivo)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        df = _procesar_df(df_raw)
        clinica_id = _clinica_id() or 1
        guardar_equipos_clinica(df, clinica_id)
        return jsonify({"mensaje":f"{len(df)} equipos guardados","total":len(df),"criticos":int(df["Alerta Cr\u00edtica"].sum()),"equipos":_df_a_dict(df)})
    except Exception as e:
        return jsonify({"error":str(e)}),400

@app.route("/api/pdf")
@permiso_requerido("exportar")
def api_pdf():
    try:
        from modules.database import obtener_equipos_clinica
        clinica_id = _clinica_id()
        df = obtener_equipos() if (session.get("rol")=="admin" and not session.get("clinica_id_activo")) else obtener_equipos_clinica(clinica_id)
        with tempfile.TemporaryDirectory() as tmp:
            rb=os.path.join(tmp,"b.png");rd=os.path.join(tmp,"d.png");rp=os.path.join(tmp,"r.pdf")
            generar_grafica_bateria(df,rb);generar_grafica_resumen(df,rd);generar_pdf(df,rb,rd,rp)
            with open(rp,"rb") as f: b=f.read()
        return send_file(io.BytesIO(b),mimetype="application/pdf",as_attachment=True,download_name="reporte_biomedico.pdf")
    except Exception as e:
        return jsonify({"error":str(e)}),500

@app.route("/api/excel")
@permiso_requerido("exportar")
def api_excel():
    try:
        from modules.database import obtener_equipos_clinica
        clinica_id = _clinica_id()
        df = obtener_equipos() if (session.get("rol")=="admin" and not session.get("clinica_id_activo")) else obtener_equipos_clinica(clinica_id)
        with tempfile.TemporaryDirectory() as tmp:
            re_=os.path.join(tmp,"r.xlsx");exportar_excel(df,re_)
            with open(re_,"rb") as f: b=f.read()
        return send_file(io.BytesIO(b),mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",as_attachment=True,download_name="reporte_biomedico.xlsx")
    except Exception as e:
        return jsonify({"error":str(e)}),500

@app.route("/api/demo", methods=["POST"])
@permiso_requerido("subir")
def api_demo():
    from modules.database import guardar_equipos_clinica
    df = generar_datos(seed=42)
    clinica_id = _clinica_id() or 1
    guardar_equipos_clinica(df, clinica_id)
    return jsonify({"mensaje":f"{len(df)} equipos cargados","total":len(df),"criticos":int(df["Alerta Cr\u00edtica"].sum()),"equipos":_df_a_dict(df)})

@app.route("/api/estado")
@login_requerido
def api_estado():
    return jsonify({"estado":"activo","usuario":session.get("nombre"),"rol":session.get("rol"),"version":"4.0.0"})

# ---------------------------------------------------------------------------
# Mantenimiento
# ---------------------------------------------------------------------------
@app.route("/mantenimiento")
@login_requerido
def mantenimiento():
    return render_template("mantenimiento.html")

@app.route("/api/mantenimiento/resumen")
@login_requerido
def api_mant_resumen():
    return jsonify(resumen_mantenimiento())

@app.route("/api/mantenimiento/ordenes", methods=["GET"])
@login_requerido
def api_mant_ordenes():
    estado = request.args.get("estado")
    return jsonify({"ordenes":obtener_ordenes(estado=estado)})

@app.route("/api/mantenimiento/ordenes", methods=["POST"])
@permiso_requerido("subir")
def api_mant_crear():
    datos = request.get_json()
    if not datos or not datos.get("equipo"):
        return jsonify({"error":"Equipo requerido"}),400
    return jsonify({"mensaje":"Orden creada","id":crear_orden(datos)}),201

@app.route("/api/mantenimiento/ordenes/<int:orden_id>", methods=["PUT"])
@permiso_requerido("subir")
def api_mant_actualizar(orden_id):
    ok = actualizar_orden(orden_id, request.get_json())
    return jsonify({"mensaje":"Actualizada"}) if ok else (jsonify({"error":"No encontrada"}),404)

@app.route("/api/mantenimiento/ordenes/<int:orden_id>", methods=["DELETE"])
@permiso_requerido("subir")
def api_mant_eliminar(orden_id):
    ok = eliminar_orden(orden_id)
    return jsonify({"mensaje":"Eliminada"}) if ok else (jsonify({"error":"No encontrada"}),404)

@app.route("/api/mantenimiento/ordenes/<int:orden_id>/completar", methods=["POST"])
@permiso_requerido("exportar")
def api_mant_completar(orden_id):
    ok = completar_orden(orden_id, request.get_json() or {})
    return jsonify({"mensaje":"Completada"}) if ok else (jsonify({"error":"No encontrada"}),404)

@app.route("/api/mantenimiento/proximos")
@login_requerido
def api_mant_proximos():
    proximos = obtener_proximos(int(request.args.get("dias",30)))
    return jsonify({"proximos":proximos,"total":len(proximos)})

@app.route("/api/mantenimiento/vencidos")
@login_requerido
def api_mant_vencidos():
    vencidos = obtener_vencidos()
    return jsonify({"vencidos":vencidos,"total":len(vencidos)})

@app.route("/api/mantenimiento/historial")
@login_requerido
def api_mant_historial():
    historial = obtener_historial_mantenimiento()
    return jsonify({"historial":historial,"total":len(historial)})

@app.route("/api/mantenimiento/tendencias")
@login_requerido
def api_mant_tendencias():
    snapshots = obtener_tendencias(int(request.args.get("dias",60)))
    return jsonify({"snapshots":snapshots,"total":len(snapshots)})

@app.route("/api/mantenimiento/snapshot", methods=["POST"])
@permiso_requerido("subir")
def api_mant_snapshot():
    df = obtener_equipos()
    if not df.empty:
        registrar_snapshot(df)
        return jsonify({"mensaje":"Snapshot registrado"})
    return jsonify({"error":"Sin equipos"}),400

if __name__ == "__main__":
    print("Sistema Biomedico v4.0 - http://localhost:5000")
    app.run(debug=False, port=5000)
