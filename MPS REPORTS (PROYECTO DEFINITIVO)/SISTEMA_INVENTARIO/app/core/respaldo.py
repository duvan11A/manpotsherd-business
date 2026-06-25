# -*- coding: utf-8 -*-
"""
MPS REPORTS - Respaldo automatico
Copia de seguridad de la base propia cada 3 dias en la carpeta
COPIA DE SEGURIDAD, conservando las ultimas 10 copias (RN-11).
"""

import os
import shutil
from datetime import datetime

import base_propia
import auditoria

# Carpeta de respaldos (en la raiz del proyecto)
DIR_RESPALDO = os.path.join(base_propia.DIR_RAIZ, "COPIA DE SEGURIDAD")


def respaldar_si_corresponde(forzar=False):
    """
    Hace un respaldo si nunca se ha hecho, si han pasado los dias
    configurados (3 por defecto), o si forzar=True.
    Devuelve la ruta del respaldo creado, o None si no correspondia.
    """
    ultima = base_propia.obtener_config("ultima_copia_seguridad")
    dias_entre = int(base_propia.obtener_config("dias_entre_respaldos") or "3")

    if not forzar and ultima:
        try:
            fecha_ultima = datetime.strptime(ultima, "%Y-%m-%d %H:%M:%S")
            dias_pasados = (datetime.now() - fecha_ultima).days
            if dias_pasados < dias_entre:
                return None  # aun no toca respaldar
        except ValueError:
            pass  # fecha invalida: respaldar de todos modos

    return _hacer_respaldo()


def _hacer_respaldo():
    """Copia la base, actualiza la fecha, registra y aplica retencion."""
    os.makedirs(DIR_RESPALDO, exist_ok=True)

    if not os.path.exists(base_propia.RUTA_DB):
        # No hay base que respaldar todavia
        return None

    ahora = datetime.now()
    nombre = "sistema_" + ahora.strftime("%Y-%m-%d_%H%M%S") + ".db"
    destino = os.path.join(DIR_RESPALDO, nombre)

    shutil.copy2(base_propia.RUTA_DB, destino)

    # Actualizar la fecha del ultimo respaldo
    base_propia.guardar_config(
        "ultima_copia_seguridad", ahora.strftime("%Y-%m-%d %H:%M:%S"))

    # Registrar en historial
    auditoria.registrar("SISTEMA", "RESPALDO",
                        "Copia de seguridad creada: " + nombre)

    # Aplicar retencion
    _aplicar_retencion()

    return destino


def _aplicar_retencion():
    """Conserva solo las ultimas N copias (10 por defecto)."""
    a_conservar = int(base_propia.obtener_config("copias_a_conservar") or "10")

    if not os.path.exists(DIR_RESPALDO):
        return

    copias = [f for f in os.listdir(DIR_RESPALDO)
              if f.startswith("sistema_") and f.endswith(".db")]
    # Ordenar por nombre (que incluye la fecha): mas antiguas primero
    copias.sort()

    while len(copias) > a_conservar:
        mas_antigua = copias.pop(0)
        try:
            os.remove(os.path.join(DIR_RESPALDO, mas_antigua))
        except OSError:
            pass


if __name__ == "__main__":
    base_propia.inicializar_base()
    ruta = respaldar_si_corresponde(forzar=True)
    if ruta:
        print("Respaldo creado:")
        print("  " + ruta)
    else:
        print("No correspondia respaldar en este momento.")
