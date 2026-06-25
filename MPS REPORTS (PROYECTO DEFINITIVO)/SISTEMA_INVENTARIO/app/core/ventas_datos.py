# -*- coding: utf-8 -*-
"""
MPS REPORTS - Capa de datos del modulo Ventas (Fase 5)

Calcula ventas netas por producto en un periodo, desde los movimientos
que ya tiene el almacen en memoria (no vuelve a leer Business).

Ventas netas (seccion 4.4): FE suma, NCF resta.
  - unidades = CANT de FE menos CANT de NCF dentro del periodo
  - valor vendido = unidades * precio publico (PVTA1I del producto)
  - costo de lo vendido = unidades * costo (COSTO_REP del producto)
  - utilidad = valor - costo
"""

import calendar
from datetime import date

PERIODOS = ["Mes actual", "Ultimos 3 meses", "Ultimos 6 meses", "Ano actual"]
PERIODO_DEFECTO = "Ano actual"


def _hace_meses(meses):
    hoy = date.today()
    m = hoy.month - meses
    y = hoy.year
    while m <= 0:
        m += 12
        y -= 1
    d = min(hoy.day, calendar.monthrange(y, m)[1])
    return date(y, m, d)


def rango_periodo(opcion):
    """Devuelve (desde, hasta) en formato 'AAAA-MM-DD'."""
    hoy = date.today()
    if opcion == "Mes actual":
        desde = date(hoy.year, hoy.month, 1)
    elif opcion == "Ultimos 6 meses":
        desde = _hace_meses(6)
    elif opcion == "Ano actual":
        desde = date(hoy.year, 1, 1)
    else:  # Ultimos 3 meses (defecto)
        desde = _hace_meses(3)
    return desde.strftime("%Y-%m-%d"), hoy.strftime("%Y-%m-%d")


def calcular_ventas(movimientos, productos, opcion):
    """Devuelve (filas, desde, hasta). Una fila por producto con ventas
    netas distintas de cero en el periodo.

    Venta real = movimiento con ES_VTA == 'S' (FE, FE01, NCF, NNR...).
    Signo: MOV 'S' (salida) suma, MOV 'E' (devolucion) resta.
    El valor y el costo salen de los campos reales del movite (VTAS y
    COSTOT), que ya traen los descuentos, igual que el reporte de Business.
    """
    desde, hasta = rango_periodo(opcion)
    acum = {}   # codigo -> [unidades, valor, costo]
    for m in movimientos:
        if m.get("ES_VTA") != "S":
            continue
        f = m["FECHA"]
        if f < desde or f > hasta:
            continue
        cod = m["CODIGO"]
        if not cod:
            continue
        mov = m["MOV"]
        signo = 1 if mov == "S" else (-1 if mov == "E" else 0)
        if signo == 0:
            continue
        a = acum.setdefault(cod, [0.0, 0.0, 0.0])
        a[0] += signo * m["CANT"]
        a[1] += signo * m.get("VTAS", 0.0)
        a[2] += signo * m.get("COSTOT", 0.0)

    filas = []
    for cod, (uni, valor, costo) in acum.items():
        if uni == 0 and valor == 0:
            continue
        p = productos.get(cod, {})
        filas.append({
            "codigo": cod,
            "nombre": p.get("NOMBRE", ""),
            "referencia": p.get("REFER", ""),
            "unidades": uni,
            "valor": valor,
            "costo": costo,
            "utilidad": valor - costo,
        })
    return filas, desde, hasta


def ventas_de_producto(movimientos, codigo):
    """Ventas de UN producto en cada periodo disponible. Devuelve
    { opcion: {unidades, valor, costo, utilidad, desde, hasta} }."""
    rangos = {op: rango_periodo(op) for op in PERIODOS}
    acum = {op: [0.0, 0.0, 0.0] for op in PERIODOS}
    for m in movimientos:
        if m["CODIGO"] != codigo or m.get("ES_VTA") != "S":
            continue
        mov = m["MOV"]
        signo = 1 if mov == "S" else (-1 if mov == "E" else 0)
        if signo == 0:
            continue
        f = m["FECHA"]
        cant = signo * m["CANT"]
        vtas = signo * m.get("VTAS", 0.0)
        cost = signo * m.get("COSTOT", 0.0)
        for op, (d, h) in rangos.items():
            if d <= f <= h:
                a = acum[op]
                a[0] += cant
                a[1] += vtas
                a[2] += cost
    res = {}
    for op, (d, h) in rangos.items():
        a = acum[op]
        res[op] = {"unidades": a[0], "valor": a[1], "costo": a[2],
                   "utilidad": a[1] - a[2], "desde": d, "hasta": h}
    return res


def kpis(filas):
    """KPI del periodo (sobre todas las filas del periodo)."""
    return {
        "unidades": sum(f["unidades"] for f in filas),
        "valor": sum(f["valor"] for f in filas),
        "productos": len(filas),
    }


def totales(filas):
    """Totales de las filas dadas (las visibles, respeta busqueda)."""
    return {
        "unidades": sum(f["unidades"] for f in filas),
        "valor": sum(f["valor"] for f in filas),
        "costo": sum(f["costo"] for f in filas),
        "utilidad": sum(f["utilidad"] for f in filas),
    }


def filtrar(filas, texto=""):
    t = (texto or "").strip().lower()
    if not t:
        return list(filas)
    campos = ("codigo", "nombre", "referencia")
    return [f for f in filas
            if t in " ".join(str(f.get(k, "")) for k in campos).lower()]


_NUMERICAS = {"unidades", "valor", "costo", "utilidad"}


def ordenar(filas, columna, ascendente=True):
    if not columna:
        return list(filas)
    numerica = columna in _NUMERICAS

    def clave(f):
        v = f.get(columna)
        if numerica:
            return (v is None, v if v is not None else 0)
        return (False, (v or "").lower())

    return sorted(filas, key=clave, reverse=not ascendente)
