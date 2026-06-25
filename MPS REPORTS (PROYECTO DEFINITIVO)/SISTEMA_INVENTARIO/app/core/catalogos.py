# -*- coding: utf-8 -*-
"""
MPS REPORTS - Catalogos de clasificacion (SOLO LECTURA)
Fase 4 - Parte A.

Resuelve los NOMBRES de:
  - MARCA            -> MARCAS.DBF        (campo MARCA -> NOMBRE)
  - LINEA            -> LINEAS.DBF        (solo LINEA llena)
  - SUBLINEA         -> LINEAS.DBF        (LINEA + SUBLINEA llenas)
  - SUBGRUPO         -> LINEAS.DBF        (LINEA + SUBLINEA + SUBGRUPO)
  - SUBGRUP2         -> LINEAS.DBF        (los cuatro niveles llenos)

En este Business LINEA / SUBLINEA / SUBGRUPO viven todos en una sola
tabla (LINEAS.DBF); el nivel se deduce por cuantas columnas del codigo
vienen llenas. MARCA es una clasificacion aparte (MARCAS.DBF), no es
padre de LINEA.

NUNCA escribe en Business. Usa dbfread (solo lectura).
"""

import os
import json
import sys

from dbfread import DBF

DIR_CORE = os.path.dirname(os.path.abspath(__file__))
DIR_APP = os.path.dirname(DIR_CORE)
DIR_RAIZ = os.path.dirname(DIR_APP)
RUTA_CONFIG = os.path.join(DIR_RAIZ, "config", "config.json")


# ------------------------------------------------------------------
# Utilidades de lectura
# ------------------------------------------------------------------
def _abrir(ruta_dbf):
    """Abre un DBF en modo lectura tolerante (no escribe nunca)."""
    return DBF(ruta_dbf, load=False, ignore_missing_memofile=True,
               char_decode_errors="ignore", encoding="latin1")


def _txt(v):
    return ("" if v is None else str(v)).strip()


def _ruta_insensible(datos, nombre):
    """Devuelve la ruta del archivo sin importar mayus/minus del nombre."""
    objetivo = nombre.lower()
    try:
        for f in os.listdir(datos):
            if f.lower() == objetivo:
                return os.path.join(datos, f)
    except OSError:
        pass
    return os.path.join(datos, nombre)


def _campo(tabla, *nombres):
    """Devuelve el nombre real de campo que coincida (ignorando mayus)."""
    disp = {c.upper(): c for c in tabla.field_names}
    for n in nombres:
        if n.upper() in disp:
            return disp[n.upper()]
    return None


def _nombre_de_fila(tabla, r, campo_nombre):
    if campo_nombre:
        return _txt(r.get(campo_nombre))
    return ""


# ------------------------------------------------------------------
# Carga de catalogos
# ------------------------------------------------------------------
class Catalogos:
    """Carga y resuelve los nombres de marca, linea, sublinea y subgrupo."""

    def __init__(self, datos):
        self.datos = datos
        self.marcas = {}                 # cod_marca -> nombre
        self.lineas = {}                 # linea -> nombre
        self.sublineas = {}              # (linea, sublinea) -> nombre
        self.subgrupos = {}              # (linea, sublinea, subgrupo) -> nombre
        self.subgrupos2 = {}             # (l, s, g, g2) -> nombre
        self._cargar_marcas()
        self._cargar_lineas()

    def _cargar_marcas(self):
        ruta = _ruta_insensible(self.datos, "MARCAS.DBF")
        if not os.path.exists(ruta):
            return
        try:
            tabla = _abrir(ruta)
            c_cod = _campo(tabla, "MARCA")
            c_nom = _campo(tabla, "NOMBRE", "DESCRIP", "DESCRIPCION")
            for r in tabla:
                cod = _txt(r.get(c_cod)) if c_cod else ""
                if cod:
                    self.marcas[cod] = _nombre_de_fila(tabla, r, c_nom)
        except Exception:
            pass

    def _cargar_lineas(self):
        ruta = _ruta_insensible(self.datos, "LINEAS.DBF")
        if not os.path.exists(ruta):
            return
        try:
            tabla = _abrir(ruta)
            c_l = _campo(tabla, "LINEA")
            c_s = _campo(tabla, "SUBLINEA")
            c_g = _campo(tabla, "SUBGRUPO")
            c_g2 = _campo(tabla, "SUBGRUP2")
            c_nom = _campo(tabla, "NOMBRE", "DESCRIP", "DESCRIPCION")
            for r in tabla:
                l = _txt(r.get(c_l)) if c_l else ""
                s = _txt(r.get(c_s)) if c_s else ""
                g = _txt(r.get(c_g)) if c_g else ""
                g2 = _txt(r.get(c_g2)) if c_g2 else ""
                nom = _nombre_de_fila(tabla, r, c_nom)
                if not l:
                    continue
                if g2:
                    self.subgrupos2[(l, s, g, g2)] = nom
                elif g:
                    self.subgrupos[(l, s, g)] = nom
                elif s:
                    self.sublineas[(l, s)] = nom
                else:
                    self.lineas[l] = nom
        except Exception:
            pass

    # -------- Nombres simples --------
    def nombre_marca(self, cod):
        return self.marcas.get(_txt(cod), "")

    def nombre_linea(self, l):
        return self.lineas.get(_txt(l), "")

    def nombre_sublinea(self, l, s):
        return self.sublineas.get((_txt(l), _txt(s)), "")

    def nombre_subgrupo(self, l, s, g):
        return self.subgrupos.get((_txt(l), _txt(s), _txt(g)), "")

    # -------- Etiquetas "Nombre - codigo" --------
    @staticmethod
    def _limpiar(nombre, cod):
        """Quita un sufijo '(codigo)' repetido al final del nombre."""
        n = (nombre or "").strip()
        suf = "(" + cod + ")"
        if n.endswith(suf):
            n = n[:-len(suf)].strip()
        return n

    def etiqueta_marca(self, cod):
        cod = _txt(cod)
        if not cod:
            return ""
        nom = self._limpiar(self.nombre_marca(cod), cod)
        return "{} - {}".format(nom, cod) if nom else cod

    def etiqueta_linea(self, l):
        l = _txt(l)
        if not l:
            return ""
        nom = self._limpiar(self.nombre_linea(l), l)
        return "{} - {}".format(nom, l) if nom else l

    def etiqueta_sublinea(self, l, s):
        s = _txt(s)
        if not s:
            return ""
        nom = self._limpiar(self.nombre_sublinea(l, s), s)
        return "{} - {}".format(nom, s) if nom else s

    def etiqueta_subgrupo(self, l, s, g):
        g = _txt(g)
        if not g:
            return ""
        nom = self._limpiar(self.nombre_subgrupo(l, s, g), g)
        return "{} - {}".format(nom, g) if nom else g

    def resolver(self, marca, linea, sublinea, subgrupo=""):
        """Devuelve las etiquetas listas para mostrar en la tabla."""
        return {
            "marca": self.etiqueta_marca(marca),
            "linea": self.etiqueta_linea(linea),
            "sublinea": self.etiqueta_sublinea(linea, sublinea),
            "subgrupo": self.etiqueta_subgrupo(linea, sublinea, subgrupo),
        }


# ------------------------------------------------------------------
# Deteccion de la carpeta de datos (para el autotest)
# ------------------------------------------------------------------
def detectar_datos(empresa="FUTURE COMPANY"):
    try:
        with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    emp = cfg.get("empresas", {}).get(empresa, {})
    rutas = emp.get("rutas", [])
    sub = emp.get("subcarpeta_datos", "")
    for ruta in rutas:
        d = os.path.join(ruta, sub) if sub else ruta
        if os.path.exists(_ruta_insensible(d, "items.dbf")):
            return d
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        return sys.argv[1]
    return None


# ------------------------------------------------------------------
# Autotest contra Business real (solo lectura)
# ------------------------------------------------------------------
def _autotest():
    lineas_out = []

    def out(t=""):
        print(t)
        lineas_out.append(t)

    out("MPS REPORTS - PRUEBA DE CATALOGOS (marca / linea / sublinea)")
    out("SOLO LECTURA")
    out("")
    datos = detectar_datos()
    if not datos:
        out("No se encontro la carpeta de datos. Revisa config.json o pasa")
        out("la ruta: python catalogos.py \"C:\\ruta\\a\\datos\"")
        return
    out("Carpeta: " + datos)
    cat = Catalogos(datos)
    out("Marcas cargadas:    " + str(len(cat.marcas)))
    out("Lineas cargadas:    " + str(len(cat.lineas)))
    out("Sublineas cargadas: " + str(len(cat.sublineas)))
    out("Subgrupos cargados: " + str(len(cat.subgrupos)))
    out("")

    out("MARCAS (etiqueta que se vera en la tabla):")
    for cod in sorted(cat.marcas):
        out("   " + cat.etiqueta_marca(cod))
    out("")

    out("ARBOL DE LINEAS / SUBLINEAS (primeras 20 lineas):")
    for l in sorted(cat.lineas)[:20]:
        out("   " + cat.etiqueta_linea(l))
        subs = sorted(s for (ll, s) in cat.sublineas if ll == l)
        for s in subs:
            out("       - " + cat.etiqueta_sublinea(l, s))
    out("")

    # Resolver algunos productos reales de items.dbf
    ruta_items = _ruta_insensible(datos, "items.dbf")
    if os.path.exists(ruta_items):
        out("EJEMPLO CON 12 PRODUCTOS REALES (items.dbf):")
        tabla = _abrir(ruta_items)
        c_cod = _campo(tabla, "CODIGO")
        c_m = _campo(tabla, "MARCA")
        c_l = _campo(tabla, "LINEA")
        c_s = _campo(tabla, "SUBLINEA")
        n = 0
        for r in tabla:
            res = cat.resolver(r.get(c_m), r.get(c_l), r.get(c_s))
            out("   {}".format(_txt(r.get(c_cod))))
            out("       Marca:    " + (res["marca"] or "(vacio)"))
            out("       Linea:    " + (res["linea"] or "(vacio)"))
            out("       Sublinea: " + (res["sublinea"] or "(vacio)"))
            n += 1
            if n >= 12:
                break
    # Guardar reporte para revisar/enviar
    try:
        ruta_rep = os.path.join(DIR_RAIZ, "catalogos_resultado.txt")
        with open(ruta_rep, "w", encoding="utf-8") as f:
            f.write("\n".join(lineas_out))
        out("")
        out("Reporte guardado en: " + ruta_rep)
    except Exception:
        pass


if __name__ == "__main__":
    _autotest()
