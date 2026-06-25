# -*- coding: utf-8 -*-
"""
MPS REPORTS - Capa de datos del modulo Rentabilidad y Rotacion (Fase 6)

Trabaja por PRODUCTO (no por bodega), desde el almacen en memoria.

- rentabilidad: (precio - costo) / precio * 100  (seccion 4.2). N/D si precio<=0.
- rotacion del periodo: unidades vendidas netas / existencia promedio.
  La existencia promedio es el PROMEDIO del stock a fin de cada mes del
  periodo (mas un corte al inicio), calculado con SumaDirecta. Si el
  promedio es 0 o negativo -> N/D. Si las ventas netas dan negativo
  (mas devoluciones que ventas), la rotacion se aterriza a 0.
- Clasificaciones oficiales de color.

ITEMS EXCLUIDOS DEL ANALISIS (no son productos de inventario):
  - Lineas en EXCLUIR_LINEAS (05=ADMINISTRATIVO, 07=ASESORIAS FUT)
  - Codigos en EXCLUIR_CODIGOS (DESC = descuento)
Ajusta estas dos listas si quieres incluir o excluir algo.
"""

import calendar

import calculos
import ventas_datos as VD

# Items que NO son productos (servicios, descuentos, administrativo)
EXCLUIR_LINEAS = {"05", "07"}
EXCLUIR_CODIGOS = {"DESC"}

# Rangos oficiales de clasificacion
RENT_EXCELENTE = 50.0
RENT_BUENA = 35.0
RENT_REGULAR = 20.0
ROT_ALTA = 2.0
ROT_MEDIA = 1.0

CLASES_RENT = ["EXCELENTE", "BUENA", "REGULAR", "BAJA"]
CLASES_ROT = ["ALTA", "MEDIA", "BAJA"]


def clasificar_rentabilidad(pct):
    if pct is None:
        return "N/D"
    if pct >= RENT_EXCELENTE:
        return "EXCELENTE"
    if pct >= RENT_BUENA:
        return "BUENA"
    if pct >= RENT_REGULAR:
        return "REGULAR"
    return "BAJA"


def clasificar_rotacion(v):
    if v is None:
        return "N/D"
    if v >= ROT_ALTA:
        return "ALTA"
    if v >= ROT_MEDIA:
        return "MEDIA"
    return "BAJA"


def _stock_hasta(movimientos, fecha_limite):
    """Existencia por producto con todos los movimientos hasta 'fecha_limite'
    (SumaDirecta: E suma, S resta)."""
    st = {}
    for m in movimientos:
        if m["FECHA"] <= fecha_limite:
            cant = m["CANT"]
            mov = m["MOV"]
            signo = cant if mov == "E" else (-cant if mov == "S" else 0)
            if signo:
                st[m["CODIGO"]] = st.get(m["CODIGO"], 0.0) + signo
    return st


def _cortes_mensuales(desde, hasta):
    """Fechas de corte: inicio del periodo + fin de cada mes + fecha final."""
    y, m, _ = (int(x) for x in desde.split("-"))
    yh, mh, _ = (int(x) for x in hasta.split("-"))
    cortes = [desde]
    cy, cm = y, m
    while (cy, cm) < (yh, mh):
        ult = calendar.monthrange(cy, cm)[1]
        cortes.append("{:04d}-{:02d}-{:02d}".format(cy, cm, ult))
        cm += 1
        if cm > 12:
            cm = 1
            cy += 1
    cortes.append(hasta)
    return sorted(set(cortes))


def calcular_rotacion_periodo(movimientos, desde, hasta):
    """Rotacion por producto en [desde, hasta] con existencia promedio
    mensual. Devuelve { codigo: rotacion|None }."""
    cortes = _cortes_mensuales(desde, hasta)
    acumulados = [_stock_hasta(movimientos, c) for c in cortes]

    ventas = {}
    for m in movimientos:
        f = m["FECHA"]
        if desde <= f <= hasta and m.get("ES_VTA") == "S":
            cant = m["CANT"]
            mov = m["MOV"]
            vsig = cant if mov == "S" else (-cant if mov == "E" else 0)
            if vsig:
                ventas[m["CODIGO"]] = ventas.get(m["CODIGO"], 0.0) + vsig

    cods = set(ventas)
    for a in acumulados:
        cods |= set(a)

    n = len(cortes)
    rot = {}
    for cod in cods:
        prom = sum(a.get(cod, 0.0) for a in acumulados) / n
        if prom > 0:
            rot[cod] = max(0.0, ventas.get(cod, 0.0)) / prom
        else:
            rot[cod] = None
    return rot


def _es_excluido(codigo, productos):
    if codigo in EXCLUIR_CODIGOS:
        return True
    linea = str(productos.get(codigo, {}).get("LINEA", "") or "").strip()
    return linea in EXCLUIR_LINEAS


def construir_filas(info, opcion):
    """Una fila por producto con rentabilidad, rotacion y clasificaciones.
    Devuelve (filas, desde, hasta)."""
    filas_inv = info.get("filas", [])
    movimientos = info.get("movimientos", [])
    productos = info.get("productos", {})
    desde, hasta = VD.rango_periodo(opcion)
    rot = calcular_rotacion_periodo(movimientos, desde, hasta)

    porcod = {}
    for f in filas_inv:
        c = f["codigo"]
        if _es_excluido(c, productos):
            continue
        g = porcod.get(c)
        if g is None:
            porcod[c] = {
                "codigo": c,
                "nombre": f["nombre"],
                "referencia": f.get("referencia", ""),
                "marca": f.get("marca", ""),
                "costo_unit": f["costo_unit"],
                "precio_pub": f["precio_pub"],
                "stock": 0.0,
                "valor_costo": 0.0,
            }
            g = porcod[c]
        g["stock"] += f["stock"]
        g["valor_costo"] += f["valor_bodega"]

    filas = []
    for c, g in porcod.items():
        if g["stock"] < 0:
            # Solo se sacan los de stock negativo; los de cero se mantienen
            continue
        rent = calculos.rentabilidad(g["precio_pub"], g["costo_unit"])
        rotv = rot.get(c)
        g["rent_pct"] = rent
        g["rent_clase"] = clasificar_rentabilidad(rent)
        g["rotacion"] = rotv
        g["rot_clase"] = clasificar_rotacion(rotv)
        filas.append(g)
    return filas, desde, hasta


def filtrar(filas, texto="", rent_clase="Todas", rot_clase="Todas",
            marca="Todas"):
    t = (texto or "").strip().lower()
    out = []
    for f in filas:
        if t and t not in (str(f["codigo"]) + " " + str(f["nombre"]) + " " +
                           str(f.get("referencia", ""))).lower():
            continue
        if rent_clase != "Todas" and f["rent_clase"] != rent_clase:
            continue
        if rot_clase != "Todas" and f["rot_clase"] != rot_clase:
            continue
        if marca != "Todas" and f.get("marca", "") != marca:
            continue
        out.append(f)
    return out


def marcas_disponibles(filas):
    return sorted({f.get("marca", "") for f in filas if f.get("marca", "")})


_NUMERICAS = {"stock", "costo_unit", "precio_pub", "rent_pct", "rotacion"}


def ordenar(filas, columna, ascendente=True):
    """Ordena por columna. Los N/D (None) van SIEMPRE al final, sin importar
    la direccion, para que al ordenar de mayor a menor salgan primero los
    valores reales mas altos."""
    if not columna:
        return list(filas)
    if columna in _NUMERICAS:
        con = [f for f in filas if f.get(columna) is not None]
        sin = [f for f in filas if f.get(columna) is None]
        con.sort(key=lambda f: f.get(columna), reverse=not ascendente)
        return con + sin
    return sorted(filas, key=lambda f: (f.get(columna) or "").lower(),
                  reverse=not ascendente)


def kpis(filas):
    """Rentabilidad promedio ponderada por valor al costo + conteo por clase."""
    num = 0.0
    den = 0.0
    conteo = {"EXCELENTE": 0, "BUENA": 0, "REGULAR": 0, "BAJA": 0, "N/D": 0}
    for f in filas:
        conteo[f["rent_clase"]] = conteo.get(f["rent_clase"], 0) + 1
        # En el promedio no entran errores de precio absurdos (precio muy por
        # debajo del costo, rent < -100%), para que no danen el indicador.
        if (f["rent_pct"] is not None and f["valor_costo"] > 0
                and f["rent_pct"] > -100):
            num += f["rent_pct"] * f["valor_costo"]
            den += f["valor_costo"]
    prom = (num / den) if den > 0 else None
    return {"rent_prom": prom, "conteo": conteo, "total": len(filas)}
