"""
módulo: data_generator.py
Propósito: Simulación de datos de equipos biomédicos hospitalarios.
Genera registros realistas con estados de batería, calibración y alertas críticas.
"""

import random
import pandas as pd
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Constantes de umbrales críticos
# ---------------------------------------------------------------------------
UMBRAL_BATERIA_CRITICA = 30      # % → estado CRÍTICO
UMBRAL_BATERIA_BAJA = 60         # % → estado BAJO
UMBRAL_CALIBRACION_CRITICA = 90  # días → requiere calibración urgente
UMBRAL_CALIBRACION_ALERTA = 60   # días → calibración próxima


EQUIPOS_HOSPITALARIOS = [
    "Monitor Multiparámetro UMEC12",
    "Ventilador Mecánico PB840",
    "Bomba de Infusión IV",
    "Electrocardiógrafo ECG-12",
    "Desfibrilador LIFEPAK 20",
    "Oxímetro de Pulso Nellcor",
    "Monitor de Presión Arterial",
    "Ecógrafo Portátil SonoSite",
]


def calcular_estado_bateria(porcentaje: int) -> str:
    """
    Clasifica el nivel de batería en tres estados según umbrales clínicos.

    Args:
        porcentaje: Nivel de batería entre 0 y 100.

    Returns:
        Estado como string: 'CRÍTICO', 'BAJO' o 'NORMAL'.
    """
    if porcentaje <= UMBRAL_BATERIA_CRITICA:
        return "CRÍTICO"
    elif porcentaje <= UMBRAL_BATERIA_BAJA:
        return "BAJO"
    return "NORMAL"


def calcular_estado_calibracion(dias: int) -> str:
    """
    Evalúa si la calibración del equipo está vigente, próxima a vencer o vencida.

    Args:
        dias: Número de días desde la última calibración.

    Returns:
        Estado como string: 'VENCIDA', 'PRÓXIMA' o 'VIGENTE'.
    """
    if dias >= UMBRAL_CALIBRACION_CRITICA:
        return "VENCIDA"
    elif dias >= UMBRAL_CALIBRACION_ALERTA:
        return "PRÓXIMA"
    return "VIGENTE"


def es_critico(bateria: int, dias_calibracion: int) -> bool:
    """
    Determina si un equipo requiere atención inmediata.

    Un equipo es crítico si tiene batería CRÍTICA O calibración VENCIDA.

    Args:
        bateria: Porcentaje de batería.
        dias_calibracion: Días desde la última calibración.

    Returns:
        True si el equipo es crítico, False en caso contrario.
    """
    return (
        bateria <= UMBRAL_BATERIA_CRITICA
        or dias_calibracion >= UMBRAL_CALIBRACION_CRITICA
    )


def generar_datos(seed: int = None) -> pd.DataFrame:
    """
    Genera un DataFrame con datos simulados de equipos biomédicos.

    Simula condiciones reales de un inventario hospitalario, incluyendo
    equipos con batería baja, calibraciones vencidas y alertas críticas.

    Args:
        seed: Semilla para reproducibilidad (opcional).

    Returns:
        DataFrame con columnas de equipo, batería, calibración, estados y alertas.
    """
    if seed is not None:
        random.seed(seed)

    registros = []

    for equipo in EQUIPOS_HOSPITALARIOS:
        bateria = random.randint(15, 100)
        dias_calibracion = random.randint(5, 150)
        fecha_calibracion = datetime.now() - timedelta(days=dias_calibracion)
        ubicacion = random.choice(["UCI", "Urgencias", "Cirugía", "Pediatría", "Cardiología"])

        registros.append({
            "Equipo": equipo,
            "Ubicación": ubicacion,
            "Batería (%)": bateria,
            "Estado Batería": calcular_estado_bateria(bateria),
            "Última Calibración": fecha_calibracion.strftime("%Y-%m-%d"),
            "Días desde Calibración": dias_calibracion,
            "Estado Calibración": calcular_estado_calibracion(dias_calibracion),
            "Alerta Crítica": es_critico(bateria, dias_calibracion),
        })

    df = pd.DataFrame(registros)

    # Ordenar: críticos primero
    df = df.sort_values("Alerta Crítica", ascending=False).reset_index(drop=True)

    return df
