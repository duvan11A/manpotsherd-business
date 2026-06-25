# -*- coding: utf-8 -*-
"""
MPS REPORTS - Diagnostico de STOCK REAL (SOLO LECTURA)

El stock sale negativo porque solo leemos movite del ano activo. Este
diagnostico busca la fuente correcta de la existencia, para unos productos
de control que salieron negativos:
  1. SumaDirecta usando SOLO movite26.
  2. SumaDirecta usando TODOS los movite*.dbf (todos los anos).
  3. Campos de items.dbf que parezcan de existencia (SALD/EXIST/CANT/DISP/INV).
  4. Otros .dbf de la carpeta que parezcan tabla de saldos/existencias.

Uso:  python diagnostico_stock.py
Genera: diagnostico_stock_resultado.txt
"""

import os
import re
import sys
from pathlib import Path

DIR_CORE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "core")
sys.path.insert(0, DIR_CORE if os.path.isdir(DIR_CORE)
                else os.path.dirname(os.path.abspath(__file__)))

import business_reader as BR
from dbfread import DBF

DIR_RAIZ = os.path.dirname(os.path.abspath(__file__))
RUTA_REP = os.path.join(DIR_RAIZ, "diagnostico_stock_resultado.txt")

# Productos que salieron negativos en pantalla (ajusta si quieres otros)
CONTROL = ["FT5043234-TM", "FT4319227-TS", "MW3220276-T8",
           "FT4870132-TXL", "FT4996263-T10"]

_OUT = []


def out(t=""):
    print(t)
    _OUT.append(t)


def _sumadirecta(archivos, codigos):
    """{codigo: {bodega: stock}} sobre los archivos dados, solo codigos pedidos."""
    res = {c: {} for c in codigos}
    pedidos = set(codigos)
    for arch in archivos:
        try:
            tabla = DBF(str(arch), load=False, ignore_missing_memofile=True,
                        char_decode_errors="ignore", encoding="latin1")
            for r in tabla:
                cod = ("" if r.get("CODIGO") is None
                       else str(r.get("CODIGO"))).strip()
                if cod not in pedidos:
                    continue
                bod = ("" if r.get("BODEGA") is None
                       else str(r.get("BODEGA"))).strip()
                mov = ("" if r.get("MOV") is None
                       else str(r.get("MOV"))).strip().upper()
                try:
                    cant = float(r.get("CANT") or 0)
                except (ValueError, TypeError):
                    cant = 0.0
                signo = cant if mov == "E" else (-cant if mov == "S" else 0)
                res[cod][bod] = res[cod].get(bod, 0.0) + signo
        except Exception as e:
            out("   (error leyendo {}: {})".format(arch.name, e))
    return res


def main():
    out("MPS REPORTS - DIAGNOSTICO DE STOCK REAL  (SOLO LECTURA)")
    out("Productos de control: " + ", ".join(CONTROL))
    out("")

    datos = BR.detectar_ruta()
    if not datos:
        out("Sin conexion a Business.")
        _guardar()
        return
    carpeta = Path(datos)

    todos = sorted(carpeta.glob("movite*.dbf"))
    solo26 = [p for p in todos if p.name.lower() == "movite26.dbf"]
    out("Archivos movite encontrados: " + ", ".join(p.name for p in todos))
    out("")

    s26 = _sumadirecta(solo26, CONTROL)
    stodos = _sumadirecta(todos, CONTROL)

    out("STOCK TOTAL POR PRODUCTO:")
    out("   {:<16} {:>14} {:>16}".format("CODIGO", "solo 2026", "todos los anos"))
    for c in CONTROL:
        t26 = sum(s26[c].values())
        tall = sum(stodos[c].values())
        out("   {:<16} {:>14.0f} {:>16.0f}".format(c, t26, tall))
    out("")
    out("   (si 'todos los anos' da positivo y coherente, esa es la fuente)")
    out("")

    # 3. Campos de items.dbf que parezcan existencia
    items = None
    for p in carpeta.glob("items.dbf"):
        items = p
        break
    if items:
        tabla = DBF(str(items), load=False, ignore_missing_memofile=True,
                    char_decode_errors="ignore", encoding="latin1")
        patron = re.compile(r"(SALD|EXIST|CANT|DISP|INV|STOCK)", re.I)
        campos_stock = [f for f in tabla.field_names if patron.search(f)]
        out("CAMPOS DE items.dbf QUE PARECEN EXISTENCIA:")
        out("   " + (", ".join(campos_stock) if campos_stock else "(ninguno)"))
        out("")
        if campos_stock:
            out("VALORES DE ESOS CAMPOS PARA LOS PRODUCTOS DE CONTROL:")
            pedidos = set(CONTROL)
            for r in tabla:
                cod = ("" if r.get("CODIGO") is None
                       else str(r.get("CODIGO"))).strip()
                if cod in pedidos:
                    vals = {c: r.get(c) for c in campos_stock}
                    out("   {:<16} {}".format(cod, vals))
            out("")

    # 4. Otros DBF que parezcan saldos/existencias
    patron_arch = re.compile(r"(sald|exist|stock|inven)", re.I)
    otros = [p.name for p in carpeta.glob("*.dbf") if patron_arch.search(p.name)]
    out("OTROS ARCHIVOS .dbf QUE PARECEN DE SALDOS/EXISTENCIAS:")
    out("   " + (", ".join(otros) if otros else "(ninguno)"))

    _guardar()


def _guardar():
    try:
        with open(RUTA_REP, "w", encoding="utf-8") as f:
            f.write("\n".join(_OUT))
        out("")
        out("Reporte guardado en: " + RUTA_REP)
    except Exception as e:
        out("No se pudo guardar: " + str(e))


if __name__ == "__main__":
    main()
