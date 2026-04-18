"""
módulo: pdf_generator.py
Propósito: Generación del reporte PDF profesional de equipos biomédicos.
Produce un documento de portafolio con diseño institucional, colores por estado,
sección de resumen ejecutivo y gráficas incrustadas.
"""

import os
from datetime import datetime

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ---------------------------------------------------------------------------
# Paleta de colores institucional (HEX → reportlab Color)
# ---------------------------------------------------------------------------
AZUL_OSCURO = colors.HexColor("#1A237E")
AZUL_MEDIO = colors.HexColor("#1565C0")
AZUL_CLARO = colors.HexColor("#E3F2FD")
GRIS_CLARO = colors.HexColor("#F5F7FA")
GRIS_CABECERA = colors.HexColor("#37474F")
ROJO = colors.HexColor("#E53935")
NARANJA = colors.HexColor("#FB8C00")
VERDE = colors.HexColor("#2E7D32")
AMARILLO_SUAVE = colors.HexColor("#FFF8E1")
ROJO_SUAVE = colors.HexColor("#FFEBEE")


def _construir_estilos() -> dict:
    """
    Define y retorna todos los estilos tipográficos del reporte.

    Returns:
        Diccionario de estilos ParagraphStyle indexados por nombre.
    """
    base = getSampleStyleSheet()

    estilos = {
        "titulo_principal": ParagraphStyle(
            "titulo_principal",
            fontSize=22,
            fontName="Helvetica-Bold",
            textColor=colors.white,
            alignment=TA_CENTER,
            spaceAfter=4,
        ),
        "subtitulo": ParagraphStyle(
            "subtitulo",
            fontSize=11,
            fontName="Helvetica",
            textColor=colors.HexColor("#BBDEFB"),
            alignment=TA_CENTER,
        ),
        "seccion": ParagraphStyle(
            "seccion",
            fontSize=13,
            fontName="Helvetica-Bold",
            textColor=AZUL_OSCURO,
            spaceBefore=14,
            spaceAfter=6,
        ),
        "normal": ParagraphStyle(
            "normal",
            fontSize=9,
            fontName="Helvetica",
            textColor=colors.HexColor("#37474F"),
            spaceAfter=4,
        ),
        "celda": ParagraphStyle(
            "celda",
            fontSize=8,
            fontName="Helvetica",
            textColor=colors.HexColor("#212121"),
            alignment=TA_CENTER,
        ),
        "celda_critica": ParagraphStyle(
            "celda_critica",
            fontSize=8,
            fontName="Helvetica-Bold",
            textColor=ROJO,
            alignment=TA_CENTER,
        ),
        "pie": ParagraphStyle(
            "pie",
            fontSize=7.5,
            fontName="Helvetica",
            textColor=colors.HexColor("#90A4AE"),
            alignment=TA_CENTER,
        ),
        "kpi_valor": ParagraphStyle(
            "kpi_valor",
            fontSize=22,
            fontName="Helvetica-Bold",
            textColor=AZUL_OSCURO,
            alignment=TA_CENTER,
        ),
        "kpi_label": ParagraphStyle(
            "kpi_label",
            fontSize=8,
            fontName="Helvetica",
            textColor=colors.HexColor("#607D8B"),
            alignment=TA_CENTER,
        ),
    }
    return estilos


def _encabezado(estilos: dict, fecha: str) -> list:
    """
    Construye el bloque de encabezado con banner institucional.

    Args:
        estilos: Diccionario de estilos.
        fecha: Fecha de generación del reporte.

    Returns:
        Lista de Flowables del encabezado.
    """
    # Banner de título como tabla de una celda con fondo azul
    datos_banner = [[
        Paragraph("SISTEMA DE GESTIÓN DE EQUIPOS BIOMÉDICOS", estilos["titulo_principal"]),
    ]]
    banner = Table(datos_banner, colWidths=[6.5 * inch])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL_OSCURO),
        ("TOPPADDING", (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("ROUNDEDCORNERS", [6, 6, 0, 0]),
    ]))

    datos_sub = [[
        Paragraph(
            f"Reporte de Estado y Alertas Críticas  ·  Generado: {fecha}",
            estilos["subtitulo"]
        ),
    ]]
    sub_banner = Table(datos_sub, colWidths=[6.5 * inch])
    sub_banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), AZUL_MEDIO),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("ROUNDEDCORNERS", [0, 0, 6, 6]),
    ]))

    return [banner, sub_banner, Spacer(1, 14)]


def _tarjetas_kpi(df: pd.DataFrame, estilos: dict) -> list:
    """
    Genera tarjetas de KPI con métricas clave del inventario.

    Args:
        df: DataFrame con datos de equipos.
        estilos: Diccionario de estilos.

    Returns:
        Lista de Flowables con las tarjetas KPI.
    """
    total = len(df)
    criticos = int(df["Alerta Crítica"].sum())
    bateria_baja = int((df["Estado Batería"] != "NORMAL").sum())
    calib_vencida = int((df["Estado Calibración"] == "VENCIDA").sum())
    bateria_prom = int(df["Batería (%)"].mean())

    kpis = [
        (str(total), "Total Equipos", AZUL_CLARO),
        (str(criticos), "Alertas Críticas", ROJO_SUAVE if criticos > 0 else AZUL_CLARO),
        (str(bateria_baja), "Batería Baja/Crítica", AMARILLO_SUAVE if bateria_baja > 0 else AZUL_CLARO),
        (str(calib_vencida), "Calibraciones Vencidas", ROJO_SUAVE if calib_vencida > 0 else AZUL_CLARO),
        (f"{bateria_prom}%", "Batería Promedio", AZUL_CLARO),
    ]

    celdas = [[
        Table(
            [[Paragraph(v, estilos["kpi_valor"])], [Paragraph(l, estilos["kpi_label"])]],
            colWidths=[1.15 * inch]
        )
        for v, l, _ in kpis
    ]]

    tabla_kpi = Table(celdas, colWidths=[1.3 * inch] * 5)
    estilo_kpi = [
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CFD8DC")),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]
    for i, (_, _, bg) in enumerate(kpis):
        estilo_kpi.append(("BACKGROUND", (i, 0), (i, 0), bg))

    tabla_kpi.setStyle(TableStyle(estilo_kpi))

    return [
        Paragraph("RESUMEN EJECUTIVO", estilos["seccion"]),
        HRFlowable(width="100%", thickness=1, color=AZUL_MEDIO, spaceAfter=8),
        tabla_kpi,
        Spacer(1, 16),
    ]


def _color_bateria(estado: str) -> colors.Color:
    """Retorna el color de celda según el estado de batería."""
    mapa = {
        "CRÍTICO": colors.HexColor("#FFCDD2"),
        "BAJO": colors.HexColor("#FFE0B2"),
        "NORMAL": colors.HexColor("#C8E6C9"),
    }
    return mapa.get(estado, colors.white)


def _color_calibracion(estado: str) -> colors.Color:
    """Retorna el color de celda según el estado de calibración."""
    mapa = {
        "VENCIDA": colors.HexColor("#FFCDD2"),
        "PRÓXIMA": colors.HexColor("#FFE0B2"),
        "VIGENTE": colors.HexColor("#C8E6C9"),
    }
    return mapa.get(estado, colors.white)


def _tabla_equipos(df: pd.DataFrame, estilos: dict) -> list:
    """
    Construye la tabla detallada de equipos con colores por estado.

    Args:
        df: DataFrame con todos los campos de equipos.
        estilos: Diccionario de estilos.

    Returns:
        Lista de Flowables con el título y la tabla.
    """
    columnas = [
        "Equipo", "Ubicación", "Batería (%)",
        "Estado Batería", "Última Calibración",
        "Estado Calibración", "Alerta"
    ]

    cabecera = [Paragraph(f"<b>{c}</b>", estilos["celda"]) for c in columnas]
    filas = [cabecera]

    for _, row in df.iterrows():
        critico = row["Alerta Crítica"]
        estilo_fila = estilos["celda_critica"] if critico else estilos["celda"]
        alerta_txt = "⚠ CRÍTICO" if critico else "✓ OK"

        filas.append([
            Paragraph(row["Equipo"], estilo_fila),
            Paragraph(row["Ubicación"], estilos["celda"]),
            Paragraph(str(row["Batería (%)"]) + "%", estilo_fila),
            Paragraph(row["Estado Batería"], estilos["celda"]),
            Paragraph(row["Última Calibración"], estilos["celda"]),
            Paragraph(row["Estado Calibración"], estilos["celda"]),
            Paragraph(alerta_txt, estilo_fila),
        ])

    anchos = [2.1*inch, 0.85*inch, 0.7*inch, 0.8*inch, 0.9*inch, 0.85*inch, 0.7*inch]
    tabla = Table(filas, colWidths=anchos, repeatRows=1)

    estilo_tabla = [
        # Cabecera
        ("BACKGROUND", (0, 0), (-1, 0), GRIS_CABECERA),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B0BEC5")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS_CLARO]),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]

    # Colores individuales por estado
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        col_bat = _color_bateria(row["Estado Batería"])
        col_cal = _color_calibracion(row["Estado Calibración"])
        estilo_tabla.append(("BACKGROUND", (2, i), (3, i), col_bat))
        estilo_tabla.append(("BACKGROUND", (4, i), (5, i), col_cal))
        if row["Alerta Crítica"]:
            estilo_tabla.append(("BACKGROUND", (6, i), (6, i), colors.HexColor("#FFCDD2")))

    tabla.setStyle(TableStyle(estilo_tabla))

    return [
        Paragraph("INVENTARIO DETALLADO DE EQUIPOS", estilos["seccion"]),
        HRFlowable(width="100%", thickness=1, color=AZUL_MEDIO, spaceAfter=8),
        tabla,
        Spacer(1, 16),
    ]


def _seccion_criticos(df: pd.DataFrame, estilos: dict) -> list:
    """
    Genera la sección de equipos críticos con descripción de cada alerta.

    Args:
        df: DataFrame completo.
        estilos: Diccionario de estilos.

    Returns:
        Lista de Flowables con alertas críticas o mensaje de estado óptimo.
    """
    criticos = df[df["Alerta Crítica"] == True]
    elementos = [
        Paragraph("ALERTAS Y EQUIPOS CRÍTICOS", estilos["seccion"]),
        HRFlowable(width="100%", thickness=1, color=ROJO, spaceAfter=8),
    ]

    if criticos.empty:
        elementos.append(
            Paragraph(
                "✓  Todos los equipos se encuentran en estado operativo normal.",
                ParagraphStyle("ok", fontSize=10, textColor=VERDE, fontName="Helvetica-Bold")
            )
        )
        return elementos

    for _, row in criticos.iterrows():
        razones = []
        if row["Estado Batería"] in ("CRÍTICO", "BAJO"):
            razones.append(f"Batería al {row['Batería (%)']}% (Estado: {row['Estado Batería']})")
        if row["Estado Calibración"] == "VENCIDA":
            razones.append(f"Calibración vencida hace {row['Días desde Calibración']} días")

        texto = (
            f"<b>⚠  {row['Equipo']}</b>  —  {row['Ubicación']}  |  "
            + "  ·  ".join(razones)
        )
        bloque = [[Paragraph(texto, estilos["normal"])]]
        t = Table(bloque, colWidths=[6.3 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), ROJO_SUAVE),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("BOX", (0, 0), (-1, -1), 1, ROJO),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]))
        elementos.append(t)
        elementos.append(Spacer(1, 4))

    return elementos


def _seccion_graficas(ruta_barras: str, ruta_dona: str, estilos: dict) -> list:
    """
    Inserta las gráficas generadas en el flujo del PDF.

    Args:
        ruta_barras: Ruta al PNG de barras horizontales.
        ruta_dona: Ruta al PNG de la gráfica de dona.
        estilos: Diccionario de estilos.

    Returns:
        Lista de Flowables con las imágenes embebidas.
    """
    elementos = [
        Spacer(1, 10),
        Paragraph("ANÁLISIS VISUAL", estilos["seccion"]),
        HRFlowable(width="100%", thickness=1, color=AZUL_MEDIO, spaceAfter=10),
    ]

    img_barras = Image(ruta_barras, width=4.8 * inch, height=2.5 * inch)
    img_dona = Image(ruta_dona, width=2.0 * inch, height=2.0 * inch)

    fila_graficas = [[img_barras, img_dona]]
    tabla_graficas = Table(fila_graficas, colWidths=[5.0 * inch, 2.1 * inch])
    tabla_graficas.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))

    elementos.append(tabla_graficas)
    return elementos


def _pie_pagina(estilos: dict) -> list:
    """Genera el pie de página del reporte."""
    return [
        Spacer(1, 20),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CFD8DC")),
        Spacer(1, 4),
        Paragraph(
            "Documento generado automáticamente · Sistema de Gestión Biomédica v2.0 "
            "· Confidencial — solo para uso interno hospitalario",
            estilos["pie"]
        ),
    ]


def generar_pdf(
    df: pd.DataFrame,
    ruta_barras: str,
    ruta_dona: str,
    ruta_salida: str = "reports/reporte_biomedico.pdf",
) -> str:
    """
    Genera el reporte PDF completo con diseño profesional e institucional.

    El reporte incluye:
    - Encabezado con banner institucional
    - Tarjetas de KPI (resumen ejecutivo)
    - Tabla detallada con colores por estado
    - Sección de alertas críticas
    - Gráficas incrustadas
    - Pie de página

    Args:
        df: DataFrame con datos de equipos biomédicos.
        ruta_barras: Ruta al PNG del gráfico de barras.
        ruta_dona: Ruta al PNG del gráfico de dona.
        ruta_salida: Ruta y nombre del archivo PDF de salida.

    Returns:
        Ruta del archivo PDF generado.
    """
    os.makedirs(os.path.dirname(ruta_salida), exist_ok=True)

    doc = SimpleDocTemplate(
        ruta_salida,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    estilos = _construir_estilos()
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    elementos = []

    elementos += _encabezado(estilos, fecha)
    elementos += _tarjetas_kpi(df, estilos)
    elementos += _tabla_equipos(df, estilos)
    elementos += _seccion_criticos(df, estilos)
    elementos += _seccion_graficas(ruta_barras, ruta_dona, estilos)
    elementos += _pie_pagina(estilos)

    doc.build(elementos)
    return ruta_salida
