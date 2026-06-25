# -*- coding: utf-8 -*-
"""
MPS REPORTS - Base de datos propia (SQLite)
Crea y administra sistema.db: las seis tablas, la configuracion
inicial y los usuarios iniciales. Unico lugar de escritura del sistema.
"""

import os
import sqlite3
from datetime import datetime

# Rutas base del proyecto (este archivo esta en app/core/)
DIR_CORE = os.path.dirname(os.path.abspath(__file__))
DIR_APP = os.path.dirname(DIR_CORE)
DIR_RAIZ = os.path.dirname(DIR_APP)
DIR_DATOS = os.path.join(DIR_RAIZ, "datos")
RUTA_DB = os.path.join(DIR_DATOS, "sistema.db")


def conectar():
    """Devuelve una conexion a la base propia."""
    os.makedirs(DIR_DATOS, exist_ok=True)
    con = sqlite3.connect(RUTA_DB)
    return con


def inicializar_base():
    """Crea las seis tablas si no existen y carga datos iniciales."""
    con = conectar()
    cur = con.cursor()

    # 1. usuarios
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE NOT NULL,
            hash_contrasena TEXT NOT NULL,
            salt TEXT NOT NULL,
            rol TEXT NOT NULL,
            activo INTEGER NOT NULL DEFAULT 1,
            fecha_creacion TEXT,
            creado_por TEXT
        )
    """)

    # 2. produccion
    cur.execute("""
        CREATE TABLE IF NOT EXISTS produccion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_business TEXT,
            id_producto_propio INTEGER,
            cantidad INTEGER NOT NULL,
            fecha_registro TEXT,
            usuario TEXT,
            observaciones TEXT,
            activo INTEGER NOT NULL DEFAULT 1
        )
    """)

    # 3. equivalencias
    cur.execute("""
        CREATE TABLE IF NOT EXISTS equivalencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referencia_produccion TEXT UNIQUE NOT NULL,
            codigo_business TEXT NOT NULL,
            fecha_creacion TEXT,
            usuario TEXT
        )
    """)

    # 4. productos_propios
    cur.execute("""
        CREATE TABLE IF NOT EXISTS productos_propios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT,
            referencia TEXT,
            talla TEXT,
            color TEXT,
            costo REAL,
            precio REAL,
            fecha_creacion TEXT,
            usuario TEXT
        )
    """)

    # 5. historial
    cur.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT,
            usuario TEXT,
            accion TEXT,
            detalle TEXT
        )
    """)

    # 6. configuracion
    cur.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
    """)

    con.commit()
    _cargar_configuracion_inicial(con)
    con.close()

    # Los usuarios se cargan despues de crear las tablas
    _cargar_usuarios_iniciales()


def _cargar_configuracion_inicial(con):
    """Inserta las siete claves de configuracion si no existen."""
    valores = {
        "meses_proyeccion": "3",
        "umbral_pocas_unidades": "20",
        "intervalo_actualizacion_min": "15",
        "dias_entre_respaldos": "3",
        "copias_a_conservar": "10",
        "ultima_copia_seguridad": "",
        "ano_activo": "2026",
    }
    cur = con.cursor()
    for clave, valor in valores.items():
        cur.execute(
            "INSERT OR IGNORE INTO configuracion (clave, valor) VALUES (?, ?)",
            (clave, valor))
    con.commit()


def obtener_config(clave):
    """Lee un valor de configuracion."""
    con = conectar()
    cur = con.cursor()
    cur.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,))
    fila = cur.fetchone()
    con.close()
    return fila[0] if fila else None


def guardar_config(clave, valor):
    """Guarda o actualiza un valor de configuracion."""
    con = conectar()
    cur = con.cursor()
    cur.execute("UPDATE configuracion SET valor = ? WHERE clave = ?",
                (str(valor), clave))
    con.commit()
    con.close()


def _cargar_usuarios_iniciales():
    """Crea los cuatro usuarios iniciales si la tabla esta vacia (Anexo B)."""
    # Import dentro de la funcion para evitar dependencias circulares
    import seguridad

    con = conectar()
    cur = con.cursor()
    cur.execute("SELECT COUNT(*) FROM usuarios")
    if cur.fetchone()[0] > 0:
        con.close()
        return  # ya hay usuarios, no duplicar

    usuarios_iniciales = [
        ("INGENIERO DUVAN", "Duvan#Admin2026", "ADMINISTRADOR"),
        ("GERENCIA", "Gerencia#Fut2026", "SUPERVISOR"),
        ("BODEGA", "Bodega#Fut2026", "SUPERVISOR"),
        ("VENTAS", "Ventas#Fut2026", "CONSULTA"),
    ]

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for nombre, contrasena, rol in usuarios_iniciales:
        salt, hash_c = seguridad.generar_hash(contrasena)
        cur.execute("""
            INSERT INTO usuarios
            (nombre, hash_contrasena, salt, rol, activo, fecha_creacion, creado_por)
            VALUES (?, ?, ?, ?, 1, ?, ?)
        """, (nombre, hash_c, salt, rol, ahora, "SISTEMA"))

    con.commit()
    con.close()


# Permite ejecutar este archivo directamente para crear la base
if __name__ == "__main__":
    inicializar_base()
    print("Base de datos creada/verificada en:")
    print("  " + RUTA_DB)
