# -*- coding: utf-8 -*-
"""
MPS REPORTS - Actualizador
Calcula la 'firma' de los archivos de Business (tamano + fecha de
modificacion de items.dbf y de todos los movite*.dbf). Si la firma
cambia, Business fue modificado y el sistema debe recargar (RN-10).
"""

import os
from pathlib import Path


def firma_business(datos):
    """
    Devuelve una cadena que representa el estado actual de los
    archivos de Business. Si dos firmas son distintas, hubo un cambio.
    Si no hay acceso, devuelve None.
    """
    if not datos or not os.path.exists(datos):
        return None

    partes = []
    try:
        objetivos = list(Path(datos).glob("movite*.dbf"))
        items = Path(datos) / "items.dbf"
        if items.exists():
            objetivos.append(items)

        for f in sorted(objetivos):
            try:
                st = f.stat()
                partes.append("{}:{}:{}".format(
                    f.name, st.st_size, int(st.st_mtime)))
            except OSError:
                pass
    except Exception:
        return None

    return "|".join(partes)


def hubo_cambios(firma_anterior, firma_actual):
    """True si la firma cambio (y ambas son validas)."""
    if firma_anterior is None or firma_actual is None:
        return False
    return firma_anterior != firma_actual


if __name__ == "__main__":
    import business_reader
    datos = business_reader.detectar_ruta()
    if not datos:
        print("Sin conexion a Business.")
    else:
        f1 = firma_business(datos)
        print("Firma (primeros 120 caracteres):")
        print(" ", (f1 or "")[:120], "...")
        print("Longitud total de la firma:", len(f1 or ""))
