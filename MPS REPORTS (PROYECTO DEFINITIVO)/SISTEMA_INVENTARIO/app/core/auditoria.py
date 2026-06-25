# -*- coding: utf-8 -*-
"""
MPS REPORTS - Auditoria
Registra toda accion de escritura en la tabla historial (RN-07).
"""

from datetime import datetime
import base_propia

# Acciones tipificadas validas (segun la documentacion)
ACCIONES = [
    "INICIO_SESION",
    "INTENTO_FALLIDO",
    "REGISTRO_PRODUCCION",
    "EDICION_PRODUCCION",
    "CREACION_PRODUCTO",
    "CREACION_USUARIO",
    "DESACTIVACION_USUARIO",
    "CREACION_EQUIVALENCIA",
    "EXPORTACION",
    "RESPALDO",
]


def registrar(usuario, accion, detalle):
    """
    Inserta un registro en el historial con fecha y hora actual.
    usuario: nombre del usuario que realiza la accion.
    accion:  uno de los tipos de ACCIONES.
    detalle: descripcion legible de lo que paso.
    """
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = base_propia.conectar()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO historial (fecha_hora, usuario, accion, detalle)
        VALUES (?, ?, ?, ?)
    """, (ahora, usuario, accion, detalle))
    con.commit()
    con.close()


def ultimos(n=20):
    """Devuelve los ultimos n registros del historial (mas recientes primero)."""
    con = base_propia.conectar()
    cur = con.cursor()
    cur.execute("""
        SELECT fecha_hora, usuario, accion, detalle
        FROM historial
        ORDER BY id DESC
        LIMIT ?
    """, (n,))
    filas = cur.fetchall()
    con.close()
    return filas


if __name__ == "__main__":
    base_propia.inicializar_base()
    registrar("SISTEMA", "RESPALDO", "Prueba de registro de auditoria")
    print("Ultimos registros del historial:")
    for f in ultimos(5):
        print("  ", f)
