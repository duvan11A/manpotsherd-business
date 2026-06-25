# -*- coding: utf-8 -*-
"""
MPS REPORTS - Capa de datos del modulo Produccion (Fase 7 + extension Fase 8)

Escribe SOLO en la base propia (sistema.db). Business NUNCA se modifica.
Maneja: registros de produccion en proceso, productos propios (codigo NP-)
y equivalencias referencia->codigo de Business. Cada accion deja auditoria
en la tabla historial.

Extension: busqueda en el programa externo de produccion (GUARDAOP.DBF).
Los codigos con talla se leen de las columnas CO_S, CO_M, CO_L, CO_XL, etc.
La ruta se guarda en la clave 'ruta_produccion_externa' de configuracion.
Los externos se cachean en memoria para no releer el DBF en cada tecla.
"""

import os
from datetime import datetime

import base_propia

# Ruta por defecto del programa externo de produccion
RUTA_EXT_DEFECTO = r"C:\Users\duvan lopez\Downloads\produccion (2)\produccion"
# Archivo dentro de esa ruta que tiene las OPs con tallas
_ARCHIVO_GUARDAOP = os.path.join("TABLAS", "GUARDAOP.DBF")

# Columnas de codigos con talla en GUARDAOP (CO_XX -> sufijo visual)
_COLS_TALLA = [
    ("CO_XS", "XS"), ("CO_S", "S"), ("CO_M", "M"), ("CO_L", "L"),
    ("CO_XL", "XL"), ("CO_2X", "2X"), ("CO_3X", "3X"),
    ("CO_2",  "2"),  ("CO_4",  "4"),  ("CO_6",  "6"),  ("CO_8",  "8"),
    ("CO_10", "10"), ("CO_12", "12"), ("CO_14", "14"), ("CO_16", "16"),
    ("CO_18", "18"), ("CO_20", "20"), ("CO_22", "22"), ("CO_24", "24"),
    ("CO_26", "26"), ("CO_28", "28"), ("CO_30", "30"), ("CO_32", "32"),
    ("CO_34", "34"), ("CO_36", "36"), ("CO_38", "38"), ("CO_40", "40"),
    ("CO_42", "42"), ("CO_44", "44"),
]

# Cache en memoria: { "ruta": str, "datos": [...], "por_codigo": {...} }
_cache_externos = {"ruta": None, "datos": [], "por_codigo": {}}


def _con():
    return base_propia.conectar()


def _ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def asegurar_esquema():
    con = _con()
    cur = con.cursor()
    cols = [r[1] for r in cur.execute("PRAGMA table_info(produccion)")]
    if "fecha_ingreso" not in cols:
        cur.execute("ALTER TABLE produccion ADD COLUMN fecha_ingreso TEXT")
    if "fecha_entregado" not in cols:
        cur.execute("ALTER TABLE produccion ADD COLUMN fecha_entregado TEXT")
    con.commit()
    con.close()


def auditar(usuario, accion, detalle):
    con = _con()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO historial (fecha_hora, usuario, accion, detalle) "
        "VALUES (?, ?, ?, ?)", (_ahora(), usuario or "-", accion, detalle))
    con.commit()
    con.close()


# ----------------------------------------------------------------------
# RUTA DEL PROGRAMA EXTERNO DE PRODUCCION
# ----------------------------------------------------------------------
def leer_ruta_externa():
    try:
        v = base_propia.obtener_config("ruta_produccion_externa")
        return v if v else RUTA_EXT_DEFECTO
    except Exception:
        return RUTA_EXT_DEFECTO


def guardar_ruta_externa(ruta):
    base_propia.guardar_config("ruta_produccion_externa", (ruta or "").strip())
    _cache_externos["ruta"] = None
    _cache_externos["datos"] = []
    _cache_externos["por_codigo"] = {}


def probar_ruta_externa(ruta=None):
    r = (ruta or leer_ruta_externa()).strip()
    if not r:
        return False, "La ruta esta vacia.", 0
    archivo = os.path.join(r, _ARCHIVO_GUARDAOP)
    if not os.path.isfile(archivo):
        return False, "No se encontro el archivo:\n{}".format(archivo), 0
    try:
        from dbfread import DBF
        tabla = DBF(archivo, encoding="latin-1", ignore_missing_memofile=True)
        n = sum(1 for _ in tabla)
        return True, "OK - {} ordenes de produccion encontradas.".format(n), n
    except Exception as exc:
        return False, "Error al leer el archivo:\n{}".format(str(exc)), 0


def _cargar_externos():
    """Lee GUARDAOP.DBF y construye lista de productos con talla desde los
    campos CO_XX. Usa cache en memoria. Devuelve lista de dicts:
    {codigo, nombre, referencia, talla, cod_base, entregado}
    donde codigo ya incluye el sufijo de talla (FT2859291-TM).
    """
    ruta = leer_ruta_externa()
    if _cache_externos["ruta"] == ruta and _cache_externos["datos"]:
        return _cache_externos["datos"]

    archivo = os.path.join(ruta, _ARCHIVO_GUARDAOP)
    # intentar en minusculas por si el SO distingue
    if not os.path.isfile(archivo):
        archivo_alt = os.path.join(ruta, "TABLAS", "guardaop.dbf")
        if os.path.isfile(archivo_alt):
            archivo = archivo_alt
        else:
            _cache_externos["ruta"] = ruta
            _cache_externos["datos"] = []
            _cache_externos["por_codigo"] = {}
            return []

    try:
        from dbfread import DBF
        tabla = DBF(archivo, encoding="latin-1", ignore_missing_memofile=True)
        vistos = set()   # evitar codigos duplicados entre OPs distintas
        res = []
        por_codigo = {}

        for rec in tabla:
            nombre = str(rec.get("N_PRENDA") or "").strip()
            refer  = str(rec.get("REFEPRENDA") or "").strip()
            entregado = str(rec.get("ENTREGADO") or "").strip()

            for col, sufijo in _COLS_TALLA:
                cod = str(rec.get(col) or "").strip()
                if not cod or cod in vistos:
                    continue
                vistos.add(cod)
                d = {
                    "codigo": cod,
                    "nombre": nombre,
                    "referencia": refer,
                    "talla": sufijo,
                    "cod_base": str(rec.get("COD_BASE") or "").strip(),
                    "entregado": entregado == "1",
                }
                res.append(d)
                por_codigo[cod.lower()] = d
                # indexar tambien por codigo base para busqueda parcial
                base = str(rec.get("COD_BASE") or "").strip().lower()
                if base and base not in por_codigo:
                    por_codigo[base] = d   # apunta al primer codigo con talla

        _cache_externos["ruta"] = ruta
        _cache_externos["datos"] = res
        _cache_externos["por_codigo"] = por_codigo
        return res

    except Exception as exc:
        try:
            import tempfile, traceback
            log = os.path.join(tempfile.gettempdir(), "mps_externo_error.txt")
            with open(log, "w", encoding="utf-8") as f:
                f.write("ERROR cargando externos\n")
                f.write("Archivo: {}\n".format(archivo))
                f.write(traceback.format_exc())
        except Exception:
            pass
        _cache_externos["ruta"] = ruta
        _cache_externos["datos"] = []
        _cache_externos["por_codigo"] = {}
        return []


def recargar_externos():
    _cache_externos["ruta"] = None
    _cache_externos["datos"] = []
    _cache_externos["por_codigo"] = {}
    return _cargar_externos()


# ----------------------------------------------------------------------
# PRODUCTOS PROPIOS
# ----------------------------------------------------------------------
def siguiente_codigo_np():
    con = _con()
    cur = con.cursor()
    cur.execute("SELECT codigo FROM productos_propios WHERE codigo LIKE 'NP-%'")
    maximo = 0
    for (cod,) in cur.fetchall():
        try:
            n = int(str(cod).split("-")[1])
            maximo = max(maximo, n)
        except (IndexError, ValueError):
            pass
    con.close()
    return "NP-{:04d}".format(maximo + 1)


def crear_producto_propio(nombre, referencia, talla, color, costo, precio,
                          usuario):
    codigo = siguiente_codigo_np()
    con = _con()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO productos_propios
        (codigo, nombre, referencia, talla, color, costo, precio,
         fecha_creacion, usuario)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (codigo, nombre, referencia, talla, color,
          float(costo or 0), float(precio or 0), _ahora(), usuario))
    id_nuevo = cur.lastrowid
    con.commit()
    con.close()
    auditar(usuario, "CREACION_PRODUCTO",
            "Producto propio {} ({})".format(codigo, nombre))
    return id_nuevo, codigo


def listar_productos_propios():
    con = _con()
    cur = con.cursor()
    cur.execute("""
        SELECT id, codigo, nombre, referencia, talla, color, costo, precio
        FROM productos_propios ORDER BY codigo
    """)
    cols = [c[0] for c in cur.description]
    filas = [dict(zip(cols, r)) for r in cur.fetchall()]
    con.close()
    return filas


def obtener_producto_propio(id_propio):
    con = _con()
    cur = con.cursor()
    cur.execute("SELECT id, codigo, nombre, referencia, talla, color, costo, "
                "precio FROM productos_propios WHERE id = ?", (id_propio,))
    r = cur.fetchone()
    cols = [c[0] for c in cur.description] if r else []
    con.close()
    return dict(zip(cols, r)) if r else None


# ----------------------------------------------------------------------
# EQUIVALENCIAS
# ----------------------------------------------------------------------
def buscar_equivalencia(referencia):
    if not referencia:
        return None
    con = _con()
    cur = con.cursor()
    cur.execute("SELECT codigo_business FROM equivalencias "
                "WHERE referencia_produccion = ?", (str(referencia).strip(),))
    r = cur.fetchone()
    con.close()
    return r[0] if r else None


def crear_equivalencia(referencia_produccion, codigo_business, usuario):
    ref = str(referencia_produccion).strip()
    con = _con()
    cur = con.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO equivalencias
        (id, referencia_produccion, codigo_business, fecha_creacion, usuario)
        VALUES ((SELECT id FROM equivalencias WHERE referencia_produccion = ?),
                ?, ?, ?, ?)
    """, (ref, ref, codigo_business, _ahora(), usuario))
    con.commit()
    con.close()
    auditar(usuario, "CREACION_EQUIVALENCIA",
            "{} -> {}".format(ref, codigo_business))


def listar_equivalencias():
    con = _con()
    cur = con.cursor()
    cur.execute("SELECT id, referencia_produccion, codigo_business, "
                "fecha_creacion, usuario FROM equivalencias "
                "ORDER BY referencia_produccion")
    cols = [c[0] for c in cur.description]
    filas = [dict(zip(cols, r)) for r in cur.fetchall()]
    con.close()
    return filas


# ----------------------------------------------------------------------
# PRODUCCION
# ----------------------------------------------------------------------
def buscar_activo(codigo_business=None, id_producto_propio=None):
    con = _con()
    cur = con.cursor()
    if codigo_business:
        cur.execute("SELECT id, cantidad, fecha_ingreso, observaciones "
                    "FROM produccion WHERE activo = 1 AND codigo_business = ?",
                    (codigo_business,))
    else:
        cur.execute("SELECT id, cantidad, fecha_ingreso, observaciones "
                    "FROM produccion WHERE activo = 1 AND id_producto_propio = ?",
                    (id_producto_propio,))
    r = cur.fetchone()
    cols = [c[0] for c in cur.description] if r else []
    con.close()
    return dict(zip(cols, r)) if r else None


def crear_registro(codigo_business, id_producto_propio, cantidad,
                   fecha_ingreso, usuario, observaciones=""):
    cantidad = int(cantidad)
    con = _con()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO produccion
        (codigo_business, id_producto_propio, cantidad, fecha_registro,
         fecha_ingreso, usuario, observaciones, activo)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
    """, (codigo_business, id_producto_propio, cantidad, _ahora(),
          fecha_ingreso, usuario, observaciones))
    id_nuevo = cur.lastrowid
    con.commit()
    con.close()
    ref = codigo_business or "propio#{}".format(id_producto_propio)
    auditar(usuario, "REGISTRO_PRODUCCION",
            "{} cant {} ingreso {}".format(ref, cantidad, fecha_ingreso))
    return id_nuevo


def sumar_a_registro(id_registro, cantidad, usuario):
    cantidad = int(cantidad)
    con = _con()
    cur = con.cursor()
    cur.execute("UPDATE produccion SET cantidad = cantidad + ? WHERE id = ?",
                (cantidad, id_registro))
    con.commit()
    cur.execute("SELECT cantidad FROM produccion WHERE id = ?", (id_registro,))
    total = cur.fetchone()[0]
    con.close()
    auditar(usuario, "EDICION_PRODUCCION",
            "Registro {} sumar {} (total {})".format(id_registro, cantidad, total))
    return total


def reemplazar_registro(id_registro, cantidad, fecha_ingreso, observaciones,
                        usuario):
    cantidad = int(cantidad)
    con = _con()
    cur = con.cursor()
    cur.execute("""UPDATE produccion SET cantidad = ?, fecha_ingreso = ?,
                   observaciones = ? WHERE id = ?""",
                (cantidad, fecha_ingreso, observaciones, id_registro))
    con.commit()
    con.close()
    auditar(usuario, "EDICION_PRODUCCION",
            "Registro {} reemplazar a {} ingreso {}".format(
                id_registro, cantidad, fecha_ingreso))


def editar_cantidad(id_registro, cantidad, usuario):
    cantidad = int(cantidad)
    con = _con()
    cur = con.cursor()
    cur.execute("UPDATE produccion SET cantidad = ? WHERE id = ?",
                (cantidad, id_registro))
    con.commit()
    con.close()
    auditar(usuario, "EDICION_PRODUCCION",
            "Registro {} cantidad -> {}".format(id_registro, cantidad))


def marcar_entregado(id_registro, usuario):
    con = _con()
    cur = con.cursor()
    cur.execute("UPDATE produccion SET activo = 0, fecha_entregado = ? "
                "WHERE id = ?", (_ahora(), id_registro))
    con.commit()
    con.close()
    auditar(usuario, "ENTREGA_PRODUCCION",
            "Registro {} marcado ENTREGADO".format(id_registro))


def eliminar_registro(id_registro, usuario):
    con = _con()
    cur = con.cursor()
    cur.execute("SELECT codigo_business, id_producto_propio, cantidad "
                "FROM produccion WHERE id = ?", (id_registro,))
    r = cur.fetchone()
    cur.execute("DELETE FROM produccion WHERE id = ?", (id_registro,))
    con.commit()
    con.close()
    ref = "-"
    cant = "-"
    if r:
        ref = r[0] or "propio#{}".format(r[1])
        cant = r[2]
    auditar(usuario, "ELIMINACION_PRODUCCION",
            "Registro {} eliminado ({} cant {})".format(id_registro, ref, cant))


def produccion_activa_por_codigo():
    con = _con()
    cur = con.cursor()
    cur.execute("SELECT codigo_business, SUM(cantidad) FROM produccion "
                "WHERE activo = 1 AND codigo_business IS NOT NULL "
                "GROUP BY codigo_business")
    res = {cod: (tot or 0) for cod, tot in cur.fetchall()}
    con.close()
    return res


def listar_activas():
    con = _con()
    cur = con.cursor()
    cur.execute("""
        SELECT p.id, p.codigo_business, p.id_producto_propio, p.cantidad,
               p.fecha_registro, p.fecha_ingreso, p.usuario, p.observaciones,
               pp.codigo, pp.nombre
        FROM produccion p
        LEFT JOIN productos_propios pp ON pp.id = p.id_producto_propio
        WHERE p.activo = 1
        ORDER BY p.fecha_ingreso
    """)
    filas = []
    for r in cur.fetchall():
        (rid, cb, idp, cant, freg, fing, usr, obs, cod_pp, nom_pp) = r
        filas.append({
            "id": rid,
            "codigo_business": cb,
            "id_producto_propio": idp,
            "codigo": cb if cb else (cod_pp or "?"),
            "nombre_propio": nom_pp,
            "es_propio": idp is not None,
            "cantidad": cant,
            "fecha_registro": freg,
            "fecha_ingreso": fing,
            "usuario": usr,
            "observaciones": obs or "",
        })
    con.close()
    return filas


# ----------------------------------------------------------------------
# BUSCADOR COMBINADO
# ----------------------------------------------------------------------
def detectar_ingresos(activas, movimientos):
    objetivo = {}
    for f in activas:
        cb = f.get("codigo_business")
        if cb:
            objetivo.setdefault(cb, []).append(f)
    detect = set()
    if not objetivo:
        return detect
    for m in movimientos:
        if m.get("DOCUM") != "ENTP":
            continue
        cb = m.get("CODIGO")
        if cb not in objetivo:
            continue
        fecha = m.get("FECHA", "")
        for f in objetivo[cb]:
            reg = (f.get("fecha_registro") or "")[:10]
            if reg and fecha >= reg:
                detect.add(f["id"])
    return detect


def buscar(texto, productos_business, limite=40):
    """Busca en:
      1. Equivalencias exactas
      2. Productos de Business
      3. Productos propios (NP-)
      4. Programa externo (GUARDAOP.DBF) — codigos CON talla incluida
    origen puede ser: 'business', 'propio', 'externo'.
    """
    t = (texto or "").strip().lower()
    if not t:
        return []
    res = []
    vistos = set()

    # 1. Equivalencia exacta
    cod_eq = buscar_equivalencia(texto.strip())
    if cod_eq and cod_eq in productos_business:
        p = productos_business[cod_eq]
        res.append({"origen": "business", "codigo": cod_eq,
                    "nombre": p.get("NOMBRE", ""),
                    "referencia": p.get("REFER", ""),
                    "id_propio": None, "por_equivalencia": True})
        vistos.add(cod_eq)

    # 2. Productos de Business
    for cod, p in productos_business.items():
        if cod in vistos:
            continue
        ref = str(p.get("REFER", "") or "")
        nom = str(p.get("NOMBRE", "") or "")
        if t in cod.lower() or t in ref.lower() or t in nom.lower():
            res.append({"origen": "business", "codigo": cod, "nombre": nom,
                        "referencia": ref, "id_propio": None,
                        "por_equivalencia": False})
            vistos.add(cod)
            if len(res) >= limite:
                break

    # 3. Productos propios (NP-)
    for pp in listar_productos_propios():
        cod = pp["codigo"]
        ref = str(pp.get("referencia", "") or "")
        nom = str(pp.get("nombre", "") or "")
        if t in cod.lower() or t in ref.lower() or t in nom.lower():
            res.append({"origen": "propio", "codigo": cod, "nombre": nom,
                        "referencia": ref, "id_propio": pp["id"],
                        "por_equivalencia": False})
            if len(res) >= limite + 10:
                break

    # 4. Programa externo (GUARDAOP) — codigos con talla
    externos = _cargar_externos()
    for ext in externos:
        cod = ext["codigo"]
        if cod in vistos:
            continue
        ref  = ext["referencia"]
        nom  = ext["nombre"]
        base = ext["cod_base"]
        if (t in cod.lower() or t in ref.lower() or t in nom.lower()
                or (base and t in base.lower())):
            res.append({"origen": "externo", "codigo": cod, "nombre": nom,
                        "referencia": ref, "id_propio": None,
                        "por_equivalencia": False})
            vistos.add(cod)
            if len(res) >= limite + 20:
                break

    return res
