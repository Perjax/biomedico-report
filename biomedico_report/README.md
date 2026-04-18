# 🏥 Sistema de Gestión de Equipos Biomédicos

> Herramienta profesional de reporting automatizado para inventarios hospitalarios.  
> Genera reportes PDF y Excel con alertas críticas, gráficas y métricas ejecutivas.

---

## 📋 Descripción del Proyecto

Este sistema automatiza el monitoreo del estado operativo de equipos biomédicos en entornos hospitalarios. A partir de datos de inventario (reales o simulados), genera un reporte completo en **PDF** y **Excel** con diseño institucional, incluyendo:

- **Alertas críticas automáticas** por batería baja o calibración vencida
- **Colores por estado** (rojo/naranja/verde) para identificación visual rápida
- **Gráficas incrustadas** (nivel de batería por equipo + distribución de estados)
- **Resumen ejecutivo con KPIs** (equipos críticos, promedios, vencimientos)
- **Exportación a Excel** con dos hojas: inventario detallado y resumen gerencial

---

## 🎯 Caso de Uso — Sector Biomédico

Los hospitales y clínicas deben garantizar que sus equipos estén **cargados, calibrados y operativos** en todo momento. Fallar en esto puede representar riesgos para los pacientes.

Este sistema está diseñado para:

| Actor | Necesidad | Solución |
|---|---|---|
| Coordinador Biomédico | Conocer qué equipos requieren acción inmediata | Sección de alertas críticas en el PDF |
| Jefe de Área | Resumen ejecutivo para tomar decisiones | Tarjetas KPI + hoja de resumen Excel |
| Técnico de Mantenimiento | Lista de equipos con calibración vencida | Tabla coloreada con estado de calibración |
| Dirección Hospital | Indicadores de disponibilidad del parque tecnológico | Gráficas y métricas globales |

---

## 🗂️ Estructura del Proyecto

```
biomedico_report/
│
├── main.py                    # Punto de entrada — ejecutar este archivo
│
├── modules/
│   ├── data_generator.py      # Simulación de datos de equipos
│   ├── chart_generator.py     # Gráficas con matplotlib
│   ├── pdf_generator.py       # Reporte PDF con ReportLab
│   └── excel_exporter.py      # Exportación a Excel con openpyxl
│
├── reports/                   # Archivos generados (PDF + Excel)
│   ├── reporte_biomedico.pdf
│   └── reporte_biomedico.xlsx
│
├── charts/                    # Gráficas temporales incrustadas en PDF
│   ├── grafica_bateria.png
│   └── grafica_resumen.png
│
├── requirements.txt
└── README.md
```

---

## ⚙️ Instalación y Ejecución

### Requisitos

- Python 3.8 o superior
- pip

### Paso 1 — Clonar o descargar el proyecto

```bash
git clone https://github.com/tu-usuario/biomedico-report.git
cd biomedico-report
```

### Paso 2 — Instalar dependencias

```bash
pip install -r requirements.txt
```

### Paso 3 — Ejecutar

```bash
python main.py
```

Al finalizar, encontrarás los archivos generados en la carpeta `reports/`:

```
reports/
├── reporte_biomedico.pdf    ← Reporte completo con gráficas
└── reporte_biomedico.xlsx   ← Inventario + resumen en Excel
```

---

## 📦 Dependencias

```
pandas>=1.5.0
reportlab>=3.6.0
matplotlib>=3.6.0
openpyxl>=3.0.0
```

---

## 🚨 Lógica de Alertas Críticas

El sistema clasifica automáticamente cada equipo según los siguientes umbrales:

### Estado de Batería

| Nivel | Estado | Color |
|---|---|---|
| > 60% | NORMAL | 🟢 Verde |
| 31% – 60% | BAJO | 🟡 Naranja |
| ≤ 30% | CRÍTICO | 🔴 Rojo |

### Estado de Calibración

| Días sin calibrar | Estado | Color |
|---|---|---|
| ≤ 60 días | VIGENTE | 🟢 Verde |
| 61 – 90 días | PRÓXIMA | 🟡 Naranja |
| > 90 días | VENCIDA | 🔴 Rojo |

Un equipo se marca como **"⚠ CRÍTICO"** si cumple al menos una de estas condiciones:
- Batería ≤ 30%
- Calibración > 90 días sin renovar

---

## 🔧 Personalización

Para adaptar el sistema a datos reales, reemplaza la función `generar_datos()` en `modules/data_generator.py` con una lectura desde:

- Archivo CSV/Excel: `pd.read_csv("inventario.csv")`
- Base de datos: `pd.read_sql(query, connection)`
- API REST: `pd.DataFrame(requests.get(url).json())`

Los umbrales críticos se configuran en las constantes al inicio de `data_generator.py`:

```python
UMBRAL_BATERIA_CRITICA = 30      # Cambiar según política hospitalaria
UMBRAL_CALIBRACION_CRITICA = 90  # Según normativa vigente (ej: INVIMA)
```

---

## 📊 Tecnologías Utilizadas

| Librería | Uso |
|---|---|
| `pandas` | Manipulación y análisis de datos |
| `reportlab` | Generación de PDFs con layout profesional |
| `matplotlib` | Gráficas de barras y dona |
| `openpyxl` | Exportación a Excel con formato condicional |

---

## 👤 Autor

Desarrollado como proyecto de portafolio freelance en el área de **automatización de reportes para el sector salud**.  
Disponible para proyectos de consultoría en gestión de equipos biomédicos, hospitalarios e industriales.

---

## 📄 Licencia

MIT License — libre para uso, modificación y distribución con atribución.
