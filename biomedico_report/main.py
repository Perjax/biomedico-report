"""
main.py — Sistema de Gestión de Equipos Biomédicos
====================================================
Punto de entrada principal del sistema.

Flujo de ejecución:
  1. Genera datos simulados de equipos hospitalarios
  2. Crea gráficas de análisis (batería + distribución)
  3. Genera reporte PDF profesional con colores por estado
  4. Exporta inventario a Excel con formato institucional

Uso:
  python main.py

Autor: [Tu nombre]
Versión: 2.0.0
"""

import os
import sys

# Asegurar que los módulos locales sean encontrados
sys.path.insert(0, os.path.dirname(__file__))

from modules.data_generator import generar_datos
from modules.chart_generator import generar_grafica_bateria, generar_grafica_resumen
from modules.pdf_generator import generar_pdf
from modules.excel_exporter import exportar_excel


# ---------------------------------------------------------------------------
# Rutas de salida
# ---------------------------------------------------------------------------
RUTA_CHARTS = "charts"
RUTA_REPORTS = "reports"
ARCHIVO_BARRAS = os.path.join(RUTA_CHARTS, "grafica_bateria.png")
ARCHIVO_DONA = os.path.join(RUTA_CHARTS, "grafica_resumen.png")
ARCHIVO_PDF = os.path.join(RUTA_REPORTS, "reporte_biomedico.pdf")
ARCHIVO_EXCEL = os.path.join(RUTA_REPORTS, "reporte_biomedico.xlsx")


def main() -> None:
    """Orquesta la generación completa del reporte biomédico."""

    print("=" * 58)
    print("  SISTEMA DE GESTIÓN DE EQUIPOS BIOMÉDICOS v2.0")
    print("=" * 58)

    # Crear carpetas de salida
    os.makedirs(RUTA_CHARTS, exist_ok=True)
    os.makedirs(RUTA_REPORTS, exist_ok=True)

    # ── Paso 1: Datos ──────────────────────────────────────────
    print("\n[1/4] Generando datos de equipos...")
    df = generar_datos(seed=42)
    criticos = int(df["Alerta Crítica"].sum())
    print(f"      {len(df)} equipos cargados  |  {criticos} alertas críticas detectadas")
    print(df[["Equipo", "Batería (%)", "Estado Batería", "Estado Calibración", "Alerta Crítica"]].to_string(index=False))

    # ── Paso 2: Gráficas ───────────────────────────────────────
    print("\n[2/4] Generando gráficas...")
    generar_grafica_bateria(df, ARCHIVO_BARRAS)
    generar_grafica_resumen(df, ARCHIVO_DONA)
    print(f"      ✓ {ARCHIVO_BARRAS}")
    print(f"      ✓ {ARCHIVO_DONA}")

    # ── Paso 3: PDF ────────────────────────────────────────────
    print("\n[3/4] Generando reporte PDF...")
    generar_pdf(df, ARCHIVO_BARRAS, ARCHIVO_DONA, ARCHIVO_PDF)
    print(f"      ✓ {ARCHIVO_PDF}")

    # ── Paso 4: Excel ──────────────────────────────────────────
    print("\n[4/4] Exportando a Excel...")
    exportar_excel(df, ARCHIVO_EXCEL)
    print(f"      ✓ {ARCHIVO_EXCEL}")

    print("\n" + "=" * 58)
    print("  ✅  Reporte generado exitosamente")
    print("=" * 58 + "\n")


if __name__ == "__main__":
    main()
