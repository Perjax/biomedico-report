"""
módulo: chart_generator.py
Propósito: Generación de gráficas profesionales para el reporte biomédico.
Produce visualizaciones en PNG listas para incrustar en el PDF.
"""

import os
import matplotlib
matplotlib.use("Agg")  # Backend sin interfaz gráfica (compatible con servidores)
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import pandas as pd


# ---------------------------------------------------------------------------
# Paleta de colores institucional
# ---------------------------------------------------------------------------
COLOR_CRITICO = "#E53935"    # Rojo clínico
COLOR_BAJO = "#FB8C00"       # Naranja advertencia
COLOR_NORMAL = "#43A047"     # Verde operativo
COLOR_FONDO = "#F5F7FA"
COLOR_TITULO = "#1A237E"     # Azul institucional oscuro


def color_por_estado_bateria(estado: str) -> str:
    """Retorna el color HEX correspondiente al estado de batería."""
    mapa = {
        "CRÍTICO": COLOR_CRITICO,
        "BAJO": COLOR_BAJO,
        "NORMAL": COLOR_NORMAL,
    }
    return mapa.get(estado, COLOR_NORMAL)


def generar_grafica_bateria(df: pd.DataFrame, ruta_salida: str) -> str:
    """
    Genera un gráfico de barras horizontal con el nivel de batería por equipo.

    Las barras se colorean automáticamente según el estado clínico:
    rojo (crítico), naranja (bajo), verde (normal).

    Args:
        df: DataFrame con columnas 'Equipo', 'Batería (%)', 'Estado Batería'.
        ruta_salida: Ruta donde guardar el PNG.

    Returns:
        Ruta del archivo PNG generado.
    """
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(COLOR_FONDO)
    ax.set_facecolor(COLOR_FONDO)

    # Nombres cortos para el eje Y
    nombres = [e[:28] + "…" if len(e) > 28 else e for e in df["Equipo"]]
    baterias = df["Batería (%)"].tolist()
    colores = [color_por_estado_bateria(e) for e in df["Estado Batería"]]

    bars = ax.barh(nombres, baterias, color=colores, edgecolor="white", height=0.6)

    # Etiquetas de valor dentro de cada barra
    for bar, val in zip(bars, baterias):
        ax.text(
            bar.get_width() - 3, bar.get_y() + bar.get_height() / 2,
            f"{val}%", va="center", ha="right",
            color="white", fontsize=9, fontweight="bold"
        )

    # Línea de umbral crítico
    ax.axvline(x=30, color=COLOR_CRITICO, linestyle="--", linewidth=1.2, alpha=0.7)
    ax.axvline(x=60, color=COLOR_BAJO, linestyle="--", linewidth=1.2, alpha=0.7)

    # Leyenda
    leyenda = [
        mpatches.Patch(color=COLOR_NORMAL, label="Normal (>60%)"),
        mpatches.Patch(color=COLOR_BAJO, label="Bajo (31–60%)"),
        mpatches.Patch(color=COLOR_CRITICO, label="Crítico (≤30%)"),
    ]
    ax.legend(handles=leyenda, loc="lower right", fontsize=8, framealpha=0.8)

    ax.set_xlabel("Nivel de Batería (%)", fontsize=10, color=COLOR_TITULO)
    ax.set_title("Estado de Batería por Equipo Biomédico", fontsize=13,
                 fontweight="bold", color=COLOR_TITULO, pad=12)
    ax.set_xlim(0, 110)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="y", labelsize=8)

    plt.tight_layout()
    plt.savefig(ruta_salida, dpi=150, bbox_inches="tight", facecolor=COLOR_FONDO)
    plt.close()

    return ruta_salida


def generar_grafica_resumen(df: pd.DataFrame, ruta_salida: str) -> str:
    """
    Genera un gráfico de dona con la distribución de estados críticos vs operativos.

    Args:
        df: DataFrame con columna 'Alerta Crítica'.
        ruta_salida: Ruta donde guardar el PNG.

    Returns:
        Ruta del archivo PNG generado.
    """
    criticos = df["Alerta Crítica"].sum()
    operativos = len(df) - criticos

    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    fig.patch.set_facecolor(COLOR_FONDO)

    wedges, texts, autotexts = ax.pie(
        [criticos, operativos],
        labels=["Críticos", "Operativos"],
        colors=[COLOR_CRITICO, COLOR_NORMAL],
        autopct="%1.0f%%",
        startangle=90,
        wedgeprops={"width": 0.55, "edgecolor": "white", "linewidth": 2},
        textprops={"fontsize": 11},
    )

    for at in autotexts:
        at.set_fontsize(12)
        at.set_fontweight("bold")
        at.set_color("white")

    ax.set_title("Distribución de Estado\nde Equipos", fontsize=11,
                 fontweight="bold", color=COLOR_TITULO, pad=10)

    plt.tight_layout()
    plt.savefig(ruta_salida, dpi=150, bbox_inches="tight", facecolor=COLOR_FONDO)
    plt.close()

    return ruta_salida
