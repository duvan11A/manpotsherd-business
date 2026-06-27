# -*- coding: utf-8 -*-
"""
MPS REPORTS - Lector de Business (SOLO LECTURA)
Lee items.dbf, BODEGAS.DBF y movite*.dbf de Business.
NUNCA escribe en Business (RN-01). La libreria dbfread no
tiene capacidad de escritura, lo que garantiza esta regla.
"""

import os
import json
from pathlib import Path
from datetime import datetime

from dbfread import DBF

# Rutas base del proyecto (este archivo esta en app/core/)
DIR_CORE = os.path.dirname(os.path.abspath(__file__))
DIR_APP = os.path.dirname(DIR_CORE)
DIR_RAIZ = os.path.dirname(DIR_APP)
RUTA_CONFIG = os.path.join(DIR_RAIZ, "config", "config.json")


def _cargar_config():
    """Lee config.json. Devuelve el diccionario de configuracion."""
    with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)


def _rutas_y_subcarpeta(empresa="FUTURE COMPANY"):
    """Devuelve (lista_de_rutas, subcarpeta_datos) de la empresa indicada."""
    cfg = _cargar_config()
    emp = cfg.get("empresas", {}).get(empresa, {})
    return emp.get("rutas", []), emp.get("subcarpeta_datos", "")


def detectar_ruta(empresa="FUTURE COMPANY"):
    """
    Prueba las rutas en orden y devuelve la carpeta de datos de la
    primera disponible (donde exista items.dbf). Si ninguna responde,
    devuelve None para que la interfaz muestre 'sin conexion'.
    """
    rutas, subcarpeta = _rutas_y_subcarpeta(empresa)
    for ruta in rutas:
        datos = os.path.join(ruta, subcarpeta)
        if os.path.exists(os.path.join(datos, "items.dbf")):
            return datos
    return None


def _abrir(ruta_dbf):
    """Abre un DBF en modo lectura tolerante."""
    return DBF(ruta_dbf, load=False, ignore_missing_memofile=True,
               char_decode_errors="ignore", encoding="latin1")


def _txt(valor):
    """Convierte a texto limpio."""
    if valor is None:
        return ""
    return str(valor).strip()


def _num(valor):
    """Convierte a numero (float). Si no se puede, 0.0."""
    try:
        return float(valor or 0)
    except (ValueError, TypeError):
        return 0.0


def leer_productos(datos):
    """
    Lee items.dbf y devuelve un diccionario por CODIGO con los campos:
    NOMBRE, REFER, MARCA, TALLA, TCOLOR, LINEA, SUBLINEA,
    COSTO_REP, PVTA1I, IVA, BLOQUEADO.
    """
    productos = {}
    tabla = _abrir(os.path.join(datos, "items.dbf"))
    for r in tabla:
        codigo = _txt(r.get("CODIGO"))
        if not codigo:
            continue
        productos[codigo] = {
            "CODIGO": codigo,
            "NOMBRE": _txt(r.get("NOMBRE")),
            "REFER": _txt(r.get("REFER")),
            "MARCA": _txt(r.get("MARCA")),
            "TALLA": _txt(r.get("TALLA")),
            "TCOLOR": _txt(r.get("TCOLOR")),
            "LINEA": _txt(r.get("LINEA")),
            "SUBLINEA": _txt(r.get("SUBLINEA")),
            "SUBGRUPO": _txt(r.get("SUBGRUPO")),
            "COSTO_REP": _num(r.get("COSTO_REP")),
            "PVTA1I": _num(r.get("PVTA1I")),
            "IVA": _num(r.get("IVA")),
            "BLOQUEADO": _txt(r.get("BLOQUEADO")),
        }
    return productos


def leer_bodegas(datos):
    """Lee BODEGAS.DBF y devuelve el diccionario codigo -> nombre."""
    bodegas = {}
    ruta = os.path.join(datos, "BODEGAS.DBF")
    if not os.path.exists(ruta):
        # Algunos sistemas guardan el nombre en minuscula
        ruta = os.path.join(datos, "bodegas.dbf")
    tabla = _abrir(ruta)
    for r in tabla:
        cod = _txt(r.get("BODEGA"))
        nom = _txt(r.get("NOMBRE"))
        if cod:
            bodegas[cod] = nom
    return bodegas


def _fecha_a_texto(valor):
    """Normaliza una fecha de DBF a 'AAAA-MM-DD' para comparar."""
    if valor is None:
        return ""
    if isinstance(valor, (datetime,)):
        return valor.strftime("%Y-%m-%d")
    # dbfread suele devolver datetime.date
    try:
        return valor.strftime("%Y-%m-%d")
    except AttributeError:
        return str(valor)[:10]


def leer_movimientos(datos, ano=2026, progreso=None):
    """
    Lee los movimientos del ano indicado. En Business los movimientos van
    separados por ano en archivos moviteAA.dbf (movite26 = 2026), por eso
    SOLO se abre el archivo del ano activo: leer los anteriores es perder
    tiempo porque igual se descartan por fecha. Si no se encuentra el del
    ano, se cae al modo antiguo (todos los movite*.dbf) como respaldo.
    Devuelve la lista de movimientos con: CODIGO, BODEGA, FECHA, DOCUM,
    MOV, CANT, COSTOT, VTAS, IVA, ES_VTA, NUMERO. Una venta real es la que
    tiene ES_VTA == 'S' (FE, FE01, NCF, NNR...). Si se pasa 'progreso', se
    llama progreso(archivos_hechos, total).
    """
    desde = "{}-01-01".format(ano)
    movimientos = []

    sufijo = str(ano)[-2:]
    archivos = [p for p in Path(datos).glob("movite{}.dbf".format(sufijo))
                if p.is_file()]
    if not archivos:
        # Respaldo: comportamiento antiguo
        archivos = sorted(Path(datos).glob("movite*.dbf"))
    archivos = [a for a in archivos if a.is_file() and a.stat().st_size > 100]
    total = len(archivos)

    for idx, archivo in enumerate(archivos):
        try:
            tabla = _abrir(str(archivo))
            registros = list(tabla)          # carga en memoria una sola vez
            total_reg = len(registros)
            intervalo = max(1, total_reg // 20)  # reportar cada 5% del archivo
            for i, r in enumerate(registros):
                fecha = _fecha_a_texto(r.get("FECHA"))
                if fecha < desde:
                    continue
                movimientos.append({
                    "CODIGO": _txt(r.get("CODIGO")),
                    "BODEGA": _txt(r.get("BODEGA")),
                    "FECHA": fecha,
                    "DOCUM": _txt(r.get("DOCUM")).upper(),
                    "MOV": _txt(r.get("MOV")).upper(),
                    "CANT": _num(r.get("CANT")),
                    "COSTOT": _num(r.get("COSTOT")),
                    "VTAS": _num(r.get("VTAS")),
                    "IVA": _num(r.get("IVA")),
                    "ES_VTA": _txt(r.get("ES_VTA")).upper(),
                    "NUMERO": _txt(r.get("NUMERO")),
                })
                # Reportar progreso cada intervalo de registros
                if progreso and total_reg > 0 and (i + 1) % intervalo == 0:
                    try:
                        # Simula avance parcial dentro del archivo actual
                        parcial = (idx + (i + 1) / total_reg) / max(total, 1)
                        progreso(int(parcial * total), total)
                    except Exception:
                        pass
        except Exception:
            pass
        if progreso:
            try:
                progreso(idx + 1, total)
            except Exception:
                pass

    return movimientos


if __name__ == "__main__":
    datos = detectar_ruta()
    if not datos:
        print("Sin conexion a Business.")
    else:
        print("Carpeta de datos:", datos)
        prods = leer_productos(datos)
        print("Productos leidos:", len(prods))
        bods = leer_bodegas(datos)
        print("Bodegas:", bods)
        movs = leer_movimientos(datos, 2026)
        print("Movimientos 2026:", len(movs))
