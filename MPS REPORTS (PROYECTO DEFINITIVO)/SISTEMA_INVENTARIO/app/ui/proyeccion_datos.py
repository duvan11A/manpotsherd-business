# -*- coding: utf-8 -*-
"""
MPS REPORTS - Capa de datos de Proyeccion y Pocas Unidades (Fase 8)

Formula (seccion 4.5), por producto:
  Vendido (N meses) = ventas netas reales de los ultimos N meses (ES_VTA='S')
  Stock bodega      = existencia actual (SumaDirecta)
  En produccion     = suma de registros ACTIVOS de la tabla produccion
  Faltante          = Vendido - (Stock + En produccion)

Faltante > 0  -> hay que producir esa cantidad.
Faltante <= 0 -> hay suficiente (sobrante = -faltante).

Excluye items que no son productos (servicios, descuento), igual que el
modulo de Rentabilidad. El periodo es en MESES (1 a 12), guardado en la
clave de configuracion 'meses_proyeccion'.

Los productos externos (en produccion pero aun no en Business) aparecen
con vendido=0 y stock=0 pero con su en_produccion real.
"""

from datetime import date

import base_propia
import ventas_datos as VD
import rentabilidad_datos as RD
import produccion_datos as PD

MESES_DEFECTO = 3
UMBRAL_DEFECTO = 20
LEYENDA = "Proyeccion estimada basada en ventas historicas."


def leer_meses():
    v = base_propia.obtener_config("meses_proyeccion")
    try:
        n = int(v)
    except (ValueError, TypeError):
        n = MESES_DEFECTO
    return min(12, max(1, n))


def guardar_meses(n):
    try:
        n = int(n)
    except (ValueError, TypeError):
        n = MESES_DEFECTO
    n = min(12, max(1, n))
    base_propia.guardar_config("meses_proyeccion", n)
    return n


def leer_umbral():
    v = base_propia.obtener_config("umbral_pocas_unidades")
    try:
        return max(0, int(v))
    except (ValueError, TypeError):
        return UMBRAL_DEFECTO


def guardar_umbral(n):
    try:
        n = max(0, int(n))
    except (ValueError, TypeError):
        n = UMBRAL_DEFECTO
    base_propia.guardar_config("umbral_pocas_unidades", n)
    return n


def _vendido_n_meses(movimientos, meses):
    """Ventas netas (ES_VTA='S', salida suma, devolucion resta) de los
    ultimos 'meses' meses, por producto."""
    desde = VD._hace_meses(meses).strftime("%Y-%m-%d")
    hasta = date.today().strftime("%Y-%m-%d")
    v = {}
    for m in movimientos:
        if m.get("ES_VTA") != "S":
            continue
        f = m["FECHA"]
        if f < desde or f > hasta:
            continue
        mov = m["MOV"]
        sig = m["CANT"] if mov == "S" else (-m["CANT"] if mov == "E" else 0)
        if sig:
            v[m["CODIGO"]] = v.get(m["CODIGO"], 0.0) + sig
    return v


def _info_externos():
    """Devuelve dict { codigo: {nombre, referencia} } de los productos del
    programa externo, para completar nombre/referencia de los que no estan
    en Business todavia."""
    try:
        externos = PD._cargar_externos()
        return {e["codigo"]: {"nombre": e["nombre"],
                              "referencia": e["referencia"]}
                for e in externos}
    except Exception:
        return {}


def calcular(info, meses):
    """Devuelve lista de dicts por producto con vendido, stock, en_produccion,
    faltante (real) y producir (max(0, faltante)).
    Incluye productos externos activos aunque no tengan ventas ni stock."""
    movimientos = info.get("movimientos", [])
    productos = info.get("productos", {})
    filas = info.get("filas", [])

    vendido = _vendido_n_meses(movimientos, meses)
    enprod = PD.produccion_activa_por_codigo()

    stock = {}
    nombre = {}
    referencia = {}
    for f in filas:
        c = f["codigo"]
        stock[c] = stock.get(c, 0.0) + f["stock"]
        nombre.setdefault(c, f["nombre"])
        referencia.setdefault(c, f.get("referencia", ""))

    # Info de externos para completar nombre/referencia si no estan en Business
    externos = _info_externos()

    universo = set(stock) | set(vendido) | set(enprod)
    res = []
    for c in universo:
        if RD._es_excluido(c, productos):
            continue
        vend = vendido.get(c, 0.0)
        st = stock.get(c, 0.0)
        ep = float(enprod.get(c, 0.0) or 0.0)
        falt = vend - (st + ep)

        # Nombre y referencia: Business primero, luego externo, luego vacio
        nom = (nombre.get(c)
               or productos.get(c, {}).get("NOMBRE", "")
               or externos.get(c, {}).get("nombre", ""))
        ref = (referencia.get(c)
               or productos.get(c, {}).get("REFER", "")
               or externos.get(c, {}).get("referencia", ""))

        res.append({
            "codigo": c,
            "nombre": nom,
            "referencia": ref,
            "vendido": vend,
            "stock": st,
            "en_produccion": ep,
            "faltante": falt,
            "producir": max(0.0, falt),
            "sobrante": max(0.0, -falt),
        })
    return res


def filtrar(filas, texto=""):
    t = (texto or "").strip().lower()
    if not t:
        return list(filas)
    return [f for f in filas
            if t in (str(f["codigo"]) + " " + str(f["nombre"]) + " " +
                     str(f.get("referencia", ""))).lower()]


def ordenar_por_faltante(filas):
    return sorted(filas, key=lambda f: f["faltante"], reverse=True)


def pocas_unidades(info, meses, umbral):
    """Productos con faltante > 0 O stock <= umbral, ordenados por faltante
    de mayor a menor (RN-09)."""
    todas = calcular(info, meses)
    sel = [f for f in todas if f["faltante"] > 0 or f["stock"] <= umbral]
    return ordenar_por_faltante(sel)


def contar_pocas(info, meses, umbral):
    """Conteo para el KPI de Inventario."""
    todas = calcular(info, meses)
    return sum(1 for f in todas if f["faltante"] > 0 or f["stock"] <= umbral)
