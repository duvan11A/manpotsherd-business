# -*- coding: utf-8 -*-
"""
MPS REPORTS - Capa de datos del modulo Inventario (Fase 4, Parte B - Paso 1)

Ensambla, en SOLO LECTURA, todo lo que la pantalla de inventario necesita:
  - una fila por producto y bodega (con stock SumaDirecta ya calculado),
  - los nombres de marca / linea / sublinea / subgrupo (catalogos),
  - rentabilidad por producto,
  - los cuatro KPI,
  - la firma de Business para detectar cambios (refresco automatico).

Usa los modulos ya validados: business_reader, calculos y catalogos.
No escribe nada en Business.

La columna Rotacion queda como None ("-") en esta fase; se calcula en la
Fase 6 (funcion rotacion() de calculos.py: costo de ventas / inventario
promedio sobre un periodo).
"""

import os
import calendar
from datetime import date
from pathlib import Path

import business_reader
import calculos
import catalogos
try:
    import produccion_datos as _PD
    _TIENE_EXTERNO = True
except Exception:
    _TIENE_EXTERNO = False

UMBRAL_POR_DEFECTO = 20
ANO_POR_DEFECTO = 2026
MESES_ROTACION = 3   # periodo por defecto de la rotacion (seccion 4.3)


def _primera_palabra(nombre):
    """Tipo de prenda tomado del nombre del producto (dato de Business).
    En la convencion de FUTURE el nombre empieza por la prenda:
    'SUDADERA HOMBRE' -> SUDADERA, 'BUSO DAMA' -> BUSO."""
    n = (nombre or "").strip()
    if not n:
        return ""
    return n.split()[0]


def _fecha_hace_meses(meses):
    """Devuelve 'AAAA-MM-DD' de hace 'meses' meses desde hoy."""
    hoy = date.today()
    m = hoy.month - meses
    y = hoy.year
    while m <= 0:
        m += 12
        y -= 1
    d = min(hoy.day, calendar.monthrange(y, m)[1])
    return date(y, m, d).strftime("%Y-%m-%d")


def calcular_rotacion(movimientos, meses=MESES_ROTACION):
    """
    Rotacion por producto (seccion 4.3), MISMA formula que el modulo
    Rentabilidad y Rotacion para que no se desincronicen:
      rotacion = unidades vendidas netas del periodo / existencia promedio,
      donde existencia promedio = promedio del stock a fin de cada mes del
      periodo. Ventas netas = movimientos con ES_VTA='S' (salida suma,
      devolucion resta). Si el promedio es 0 o negativo -> None (N/D).
    Periodo: ultimos 3 meses por defecto.
    Devuelve { codigo: rotacion|None }.
    """
    import ventas_datos as _VD
    import rentabilidad_datos as _RD
    opcion = "Ultimos 3 meses" if meses == 3 else (
        "Ultimos 6 meses" if meses == 6 else "Ano actual")
    desde, hasta = _VD.rango_periodo(opcion)
    return _RD.calcular_rotacion_periodo(movimientos, desde, hasta)


# ------------------------------------------------------------------
# Configuracion (umbral y ano) desde la base propia, con respaldo
# ------------------------------------------------------------------
def _config(clave, por_defecto):
    try:
        import base_propia
        valor = base_propia.obtener_config(clave)
        if valor is not None and str(valor).strip() != "":
            return valor
    except Exception:
        pass
    return por_defecto


def umbral_pocas():
    try:
        return int(_config("umbral_pocas_unidades", UMBRAL_POR_DEFECTO))
    except (ValueError, TypeError):
        return UMBRAL_POR_DEFECTO


def ano_activo():
    try:
        return int(_config("ano_activo", ANO_POR_DEFECTO))
    except (ValueError, TypeError):
        return ANO_POR_DEFECTO


# ------------------------------------------------------------------
# Firma de Business (RN-10): nombre + tamano + fecha mod de los DBF
# ------------------------------------------------------------------
def firma_datos(datos, ano=None):
    """Cadena estable que cambia cuando Business registra un movimiento.
    Solo mira items.dbf y el movite del ano activo (que es lo que afecta
    el inventario)."""
    if not datos:
        return ""
    if ano is None:
        ano = ano_activo()
    sufijo = str(ano)[-2:]
    partes = []
    rutas = [os.path.join(datos, "items.dbf")]
    rutas += [str(p) for p in
              sorted(Path(datos).glob("movite{}.dbf".format(sufijo)))]
    for ruta in rutas:
        try:
            st = os.stat(ruta)
            partes.append("{}:{}:{}".format(
                os.path.basename(ruta), st.st_size, int(st.st_mtime)))
        except OSError:
            continue
    return "|".join(partes)


# ------------------------------------------------------------------
# Carga completa del inventario
# ------------------------------------------------------------------
def obtener_inventario(empresa="FUTURE COMPANY", progreso=None):
    """
    Devuelve un diccionario:
      {
        "ok": True/False,
        "datos": ruta_de_datos o None,
        "filas": [ {fila}, ... ],
        "bodegas": { cod: nombre },
        "firma": "...",
        "ano": 2026,
        "error": None o texto,
      }
    'progreso', si se pasa, se llama como progreso(porcentaje, mensaje).
    Cada fila tiene las claves:
      codigo, referencia, nombre, talla, color,
      bodega_cod, bodega, stock, costo_unit, precio_pub, valor_bodega,
      rent_pct (float o None), rotacion (None), marca, linea, sublinea, subgrupo
    """
    def prog(p, m):
        if progreso:
            try:
                progreso(p, m)
            except Exception:
                pass

    base = {"ok": False, "datos": None, "filas": [], "bodegas": {},
            "firma": "", "ano": ano_activo(), "error": None}

    prog(4, "Conectando con Business...")
    datos = business_reader.detectar_ruta(empresa)
    if not datos:
        base["error"] = "Sin conexion a Business."
        prog(100, "Sin conexion")
        return base

    try:
        prog(12, "Leyendo catalogo de productos...")
        productos = business_reader.leer_productos(datos)
        prog(20, "Leyendo bodegas y ubicaciones...")
        bodegas = business_reader.leer_bodegas(datos)

        def mov_prog(hechos, total):
            pct = 40 + int(33 * hechos / total) if total else 73
            if total:
                prog(pct, "Leyendo movimientos {} de {} - por favor espere...".format(
                    hechos, total))
            else:
                prog(pct, "Leyendo historial de movimientos...")

        prog(35, "Leyendo movimientos del ano (esto puede tomar unos segundos)...")
        movimientos = business_reader.leer_movimientos(
            datos, base["ano"], progreso=mov_prog)
        prog(78, "Calculando existencias y rentabilidad...")
        stock = calculos.inventario_sumadirecta(movimientos)
        rotacion = calcular_rotacion(movimientos)
        prog(88, "Resolviendo marcas y lineas...")
        cat = catalogos.Catalogos(datos)
    except Exception as e:
        base["error"] = "Error leyendo Business: " + str(e)
        prog(100, "Error")
        return base

    prog(92, "Armando tabla de inventario...")

    # Cache del programa externo para completar productos sin datos en Business
    _cache_ext = {}
    if _TIENE_EXTERNO:
        try:
            _cache_ext = _PD._info_externos() or {}
        except Exception:
            _cache_ext = {}

    filas = []
    for (codigo, bod_cod), st in stock.items():
        p = productos.get(codigo, {})
        costo = float(p.get("COSTO_REP", 0) or 0)
        precio = float(p.get("PVTA1I", 0) or 0)
        nombre = p.get("NOMBRE", "") or ""
        marca  = p.get("MARCA",  "") or ""
        linea  = p.get("LINEA",  "") or ""
        sublinea = p.get("SUBLINEA", "") or ""
        subgrupo = p.get("SUBGRUPO", "") or ""

        # Si el producto esta incompleto en Business, completar con externo
        if _cache_ext and (not nombre or not marca or costo == 0):
            ext = _cache_ext.get(codigo)
            if ext:
                if not nombre:
                    nombre = ext.get("nombre", "") or nombre
                if not marca:
                    marca = ext.get("marca", "") or marca

        et = cat.resolver(marca, linea, sublinea, subgrupo)
        filas.append({
            "codigo": codigo,
            "referencia": p.get("REFER", ""),
            "nombre": nombre,
            "talla": p.get("TALLA", ""),
            "color": p.get("TCOLOR", ""),
            "bodega_cod": bod_cod,
            "bodega": bodegas.get(bod_cod, bod_cod),
            "stock": st,
            "costo_unit": costo,
            "precio_pub": precio,
            "valor_bodega": st * costo,
            "rent_pct": calculos.rentabilidad(precio, costo),
            "rotacion": rotacion.get(codigo),
            "marca": et["marca"],
            "linea": et["linea"],
            "sublinea": et["sublinea"],
            "subgrupo": et["subgrupo"],
            "tipo": _primera_palabra(nombre),
        })

    base.update({"ok": True, "datos": datos, "filas": filas,
                 "bodegas": bodegas, "firma": firma_datos(datos),
                 "movimientos": movimientos, "productos": productos})
    prog(100, "Listo")
    return base


def _totales_por_producto(filas):
    tot = {}
    for f in filas:
        tot[f["codigo"]] = tot.get(f["codigo"], 0.0) + f["stock"]
    return tot


def resumen_cambios(viejas, nuevas):
    """Devuelve (cuantos productos cambiaron de stock, cuantos nuevos con stock)."""
    if not viejas:
        return (0, 0)
    ant = _totales_por_producto(viejas)
    nue = _totales_por_producto(nuevas)
    cambiaron = sum(1 for c, s in nue.items() if c in ant and s != ant[c])
    nuevos = sum(1 for c, s in nue.items() if c not in ant and s > 0)
    return (cambiaron, nuevos)


# ------------------------------------------------------------------
# Filtros, KPI y ordenamiento (logica pura, usada por la pantalla)
# ------------------------------------------------------------------
def filtrar(filas, texto="", bodega_cod="", solo_con_stock=True):
    """Filtra por texto (en todas las columnas), bodega y stock."""
    t = (texto or "").strip().lower()
    campos = ("codigo", "nombre", "referencia", "marca", "linea",
              "tipo", "bodega", "talla", "color")
    res = []
    for f in filas:
        if solo_con_stock and f["stock"] <= 0:
            continue
        if bodega_cod and f["bodega_cod"] != bodega_cod:
            continue
        if t:
            blob = " ".join(str(f.get(k, "")) for k in campos).lower()
            if t not in blob:
                continue
        res.append(f)
    return res


def calcular_kpis(filas, umbral=None):
    """
    Calcula los cuatro KPI sobre las filas dadas (ya filtradas):
      productos (distintos), unidades, valor_costo, pocas (distintos).
    'pocas' = productos cuyo stock total (en las filas dadas) esta entre
    1 y umbral, inclusive.
    """
    if umbral is None:
        umbral = umbral_pocas()
    productos = set()
    unidades = 0.0
    valor = 0.0
    total_por_producto = {}
    for f in filas:
        productos.add(f["codigo"])
        unidades += f["stock"]
        valor += f["valor_bodega"]
        total_por_producto[f["codigo"]] = \
            total_por_producto.get(f["codigo"], 0.0) + f["stock"]
    pocas = sum(1 for c, s in total_por_producto.items() if 0 < s <= umbral)
    return {
        "productos": len(productos),
        "unidades": unidades,
        "valor_costo": valor,
        "pocas": pocas,
        "umbral": umbral,
    }


# Columnas que se pueden ordenar y si son numericas
_NUMERICAS = {"stock", "costo_unit", "precio_pub", "valor_bodega",
              "rent_pct", "rotacion"}


def ordenar_filas(filas, columna, ascendente=True):
    """Ordena por una columna; texto o numerico. None va al final."""
    if not columna:
        return list(filas)
    numerica = columna in _NUMERICAS

    def clave(f):
        v = f.get(columna)
        if numerica:
            return (v is None, v if v is not None else 0)
        return (False, (v or "").lower())

    return sorted(filas, key=clave, reverse=not ascendente)


if __name__ == "__main__":
    datos = business_reader.detectar_ruta()
    info = obtener_inventario()
    print("ok:", info["ok"], "| error:", info["error"])
    print("datos:", info["datos"])
    print("bodegas:", info["bodegas"])
    print("filas:", len(info["filas"]))
    print("firma:", info["firma"][:80], "...")
    print("-" * 60)
    for f in info["filas"]:
        rent = "N/D" if f["rent_pct"] is None else "{:.1f}%".format(f["rent_pct"])
        print("{} bod {} stock {:.0f} costo {:.0f} valor {:.0f} rent {}".format(
            f["codigo"], f["bodega_cod"], f["stock"], f["costo_unit"],
            f["valor_bodega"], rent))
        print("    marca: {} | linea: {} | subl: {} | subg: {}".format(
            f["marca"], f["linea"], f["sublinea"] or "-", f["subgrupo"] or "-"))
    print("-" * 60)
    visibles = filtrar(info["filas"])
    print("KPIs (solo con stock):", calcular_kpis(visibles))
