# -*- coding: utf-8 -*-
"""
MPS REPORTS - Modulo Reportes (Fase 9)
Genera reportes consolidados exportables a Excel y PDF.
Pestanas: Resumen ejecutivo, Inventario, Ventas, Rentabilidad,
          Proyeccion, Pocas Unidades, Produccion activa.
Filtros: periodo (ano actual, ultimo mes, 3m, 6m, personalizado).
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import threading
from datetime import date, datetime, timedelta

import estilo as E
import base_propia
import auditoria
from inventario_store import store
import proyeccion_datos as PY
import produccion_datos as PD
import rentabilidad_datos as RD
import ventas_datos as VD


def _miles(v):
    try:
        return "{:,.0f}".format(float(v or 0)).replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def _money(v):
    try:
        return "$ {:,.0f}".format(float(v or 0)).replace(",", ".")
    except (ValueError, TypeError):
        return "$ 0"


def _pct(v):
    try:
        return "{:.1f}%".format(float(v or 0))
    except (ValueError, TypeError):
        return "0.0%"


# ------------------------------------------------------------------
# Calculos de datos para cada pestaña
# ------------------------------------------------------------------
def _datos_inventario(info):
    filas_raw = info.get("filas", [])
    productos  = info.get("productos", {})
    cols = ["Codigo", "Nombre", "Referencia", "Talla", "Color", "Bodega",
            "Stock", "Costo Unit", "Precio Publico", "Valor Bodega",
            "Rentabilidad %", "Marca", "Linea"]
    filas = []
    for f in filas_raw:
        cod  = f.get("codigo", "")
        p    = productos.get(cod, {})
        cost = f.get("costo_unit", 0) or 0
        prec = f.get("precio_pub", 0) or 0
        rent = ((prec - cost) / prec * 100) if prec else 0
        filas.append([
            cod, f.get("nombre",""), f.get("referencia",""),
            f.get("talla",""), f.get("color",""), f.get("bodega",""),
            _miles(f.get("stock",0)), _money(cost), _money(prec),
            _money(f.get("valor_bodega",0)), _pct(rent),
            p.get("MARCA",""), p.get("LINEA",""),
        ])
    return cols, filas


def _datos_ventas(info, desde_iso, hasta_iso):
    movimientos = info.get("movimientos", [])
    productos   = info.get("productos", {})
    venta = {}
    for m in movimientos:
        if m.get("ES_VTA") != "S":
            continue
        f = m["FECHA"]
        if f < desde_iso or f > hasta_iso:
            continue
        cod = m["CODIGO"]
        mov = m["MOV"]
        signo = 1 if mov == "S" else (-1 if mov == "E" else 0)
        if signo == 0:
            continue
        if cod not in venta:
            venta[cod] = {"cant": 0.0, "valor": 0.0}
        venta[cod]["cant"]  += signo * m["CANT"]
        venta[cod]["valor"] += signo * m.get("VTAS", 0.0)
    cols = ["Codigo", "Nombre", "Referencia", "Unidades vendidas", "Valor ventas"]
    filas = []
    for cod, v in sorted(venta.items(), key=lambda x: -x[1]["valor"]):
        p = productos.get(cod, {})
        filas.append([cod, p.get("NOMBRE",""), p.get("REFER",""),
                      _miles(v["cant"]), _money(v["valor"])])
    return cols, filas


def _datos_rentabilidad(info, desde_iso, hasta_iso):
    filas_raw   = info.get("filas", [])
    productos   = info.get("productos", {})
    movimientos = info.get("movimientos", [])
    stock_d = {}
    for f in filas_raw:
        c = f["codigo"]
        stock_d[c] = stock_d.get(c, 0) + (f.get("stock") or 0)
    venta_d = {}
    for m in movimientos:
        if m.get("ES_VTA") != "S":
            continue
        f = m["FECHA"]
        if f < desde_iso or f > hasta_iso:
            continue
        cod = m["CODIGO"]
        if m["MOV"] == "S":
            venta_d[cod] = venta_d.get(cod, 0) + m["CANT"]
    cols = ["Codigo", "Nombre", "Referencia", "Costo", "Precio",
            "Rentabilidad %", "Stock", "Unidades vendidas"]
    filas = []
    universo = set(stock_d) | set(venta_d)
    for cod in universo:
        if RD._es_excluido(cod, productos):
            continue
        p    = productos.get(cod, {})
        cost = float(p.get("COSTO", 0) or 0)
        prec = float(p.get("PRECIO", 0) or 0)
        rent = ((prec - cost) / prec * 100) if prec else 0
        filas.append([
            cod, p.get("NOMBRE",""), p.get("REFER",""),
            _money(cost), _money(prec), _pct(rent),
            _miles(stock_d.get(cod,0)), _miles(venta_d.get(cod,0)),
        ])
    filas.sort(key=lambda x: float(
        x[5].replace("%","").replace(",",".") or 0), reverse=True)
    return cols, filas


def _datos_proyeccion(info, meses):
    filas_raw = PY.calcular(info, meses)
    filas_raw = PY.ordenar_por_faltante(filas_raw)
    cols = ["Codigo", "Nombre", "Referencia",
            "Vendido (" + str(meses) + " meses)",
            "Stock bodega", "En produccion", "Faltante por producir"]
    filas = []
    for f in filas_raw:
        filas.append([
            f["codigo"], f["nombre"], f.get("referencia",""),
            _miles(f["vendido"]), _miles(f["stock"]),
            _miles(f["en_produccion"]), _miles(f["producir"]),
        ])
    return cols, filas


def _datos_pocas(info, meses, umbral):
    filas_raw = PY.pocas_unidades(info, meses, umbral)
    cols = ["Codigo", "Nombre", "Referencia",
            "Vendido (" + str(meses) + " meses)",
            "Stock bodega", "En produccion", "Faltante", "Motivo"]
    filas = []
    for f in filas_raw:
        if f["producir"] > 0 and f["stock"] <= umbral:
            motivo = "Producir y stock bajo"
        elif f["producir"] > 0:
            motivo = "Hay que producir"
        else:
            motivo = "Stock bajo"
        filas.append([
            f["codigo"], f["nombre"], f.get("referencia",""),
            _miles(f["vendido"]), _miles(f["stock"]),
            _miles(f["en_produccion"]), _miles(f["producir"]), motivo,
        ])
    return cols, filas


def _datos_produccion():
    activas = PD.listar_activas()
    cols = ["Codigo", "Nombre / Descripcion", "Cantidad",
            "Fecha registro", "Fecha ingreso estimada",
            "Usuario", "Observaciones", "Estado"]
    hoy = date.today().strftime("%Y-%m-%d")
    filas = []
    for f in activas:
        nombre = f.get("nombre_propio") or "(en produccion externa)"
        fing   = f.get("fecha_ingreso") or ""
        estado = "ATRASADO" if (fing and fing < hoy) else "EN PRODUCCION"
        filas.append([
            f["codigo"], nombre, _miles(f["cantidad"]),
            (f.get("fecha_registro") or "")[:10],
            fing, f.get("usuario",""), f.get("observaciones",""), estado,
        ])
    return cols, filas


def _resumen_ejecutivo(info, empresa, usuario, desde_iso, hasta_iso, meses):
    """Devuelve (cols, filas) con los KPIs principales."""
    filas_inv   = info.get("filas", [])
    movimientos = info.get("movimientos", [])
    productos   = info.get("productos", {})

    total_prod  = len(set(f["codigo"] for f in filas_inv))
    total_stock = sum(f.get("stock", 0) or 0 for f in filas_inv)
    valor_inv   = sum(f.get("valor_bodega", 0) or 0 for f in filas_inv)

    venta_cant = 0
    venta_val  = 0
    for m in movimientos:
        if m.get("ES_VTA") != "S":
            continue
        f = m["FECHA"]
        if f < desde_iso or f > hasta_iso:
            continue
        mov = m["MOV"]
        signo = 1 if mov == "S" else (-1 if mov == "E" else 0)
        if signo == 0:
            continue
        venta_cant += signo * m["CANT"]
        venta_val  += signo * m.get("VTAS", 0.0)

    enprod  = PD.produccion_activa_por_codigo()
    n_prod  = len(enprod)
    u_prod  = sum(enprod.values())

    proy    = PY.calcular(info, meses)
    n_falt  = sum(1 for f in proy if f["producir"] > 0)
    u_falt  = sum(f["producir"] for f in proy)

    cols = ["Indicador", "Valor"]
    filas = [
        ["Empresa",                    empresa],
        ["Usuario que genera",          usuario],
        ["Periodo analizado",
         "{} al {}".format(desde_iso, hasta_iso)],
        ["Meses de proyeccion",         str(meses)],
        ["",                            ""],
        ["INVENTARIO", ""],
        ["Total productos con stock",   _miles(total_prod)],
        ["Total unidades en bodega",    _miles(total_stock)],
        ["Valor total del inventario",  _money(valor_inv)],
        ["",                            ""],
        ["VENTAS DEL PERIODO", ""],
        ["Unidades vendidas",           _miles(venta_cant)],
        ["Valor ventas",                _money(venta_val)],
        ["",                            ""],
        ["PRODUCCION ACTIVA", ""],
        ["Referencias en produccion",   _miles(n_prod)],
        ["Unidades en produccion",      _miles(u_prod)],
        ["",                            ""],
        ["PROYECCION", ""],
        ["Productos con faltante",      _miles(n_falt)],
        ["Unidades por producir",       _miles(u_falt)],
    ]
    return cols, filas


# ------------------------------------------------------------------
# Pantalla
# ------------------------------------------------------------------
PERIODOS = [
    "Ano actual",
    "Ultimo mes",
    "Ultimos 3 meses",
    "Ultimos 6 meses",
    "Personalizado",
]


def _rango_desde_periodo(periodo):
    hoy = date.today()
    if periodo == "Ano actual":
        return date(hoy.year, 1, 1).strftime("%Y-%m-%d"), hoy.strftime("%Y-%m-%d")
    if periodo == "Ultimo mes":
        d = (hoy - timedelta(days=30))
        return d.strftime("%Y-%m-%d"), hoy.strftime("%Y-%m-%d")
    if periodo == "Ultimos 3 meses":
        d = (hoy - timedelta(days=90))
        return d.strftime("%Y-%m-%d"), hoy.strftime("%Y-%m-%d")
    if periodo == "Ultimos 6 meses":
        d = (hoy - timedelta(days=180))
        return d.strftime("%Y-%m-%d"), hoy.strftime("%Y-%m-%d")
    return None, None


class ModuloReportes:
    def __init__(self, parent, rol="CONSULTA", usuario="-",
                 empresa="", indicador_cb=None):
        self.parent   = parent
        self.rol      = rol
        self.usuario  = usuario
        self.empresa  = empresa
        self.indicador_cb = indicador_cb or (lambda *a, **k: None)
        self._vivo    = True
        self._construir()
        store.suscribir(self._on_data)
        if store.hay_datos():
            self._previsualizar()

    def _on_data(self, info, manual, resumen):
        if self._vivo and info.get("ok"):
            self._previsualizar()

    def _construir(self):
        cont = tk.Frame(self.parent, bg=E.FONDO)
        cont.pack(fill="both", expand=True, padx=16, pady=14)
        self.cont = cont

        # Titulo
        cab = tk.Frame(cont, bg=E.FONDO)
        cab.pack(fill="x", pady=(0, 10))
        tk.Label(cab, text="Reportes y exportacion", bg=E.FONDO, fg=E.TEXTO,
                 font=(E.FUENTE, 15, "bold")).pack(side="left")

        # Panel de filtros
        pan = tk.LabelFrame(cont,
                            text=" Configuracion del reporte ",
                            bg=E.FONDO, fg=E.TEXTO_SUB, font=E.F_NORMAL_B)
        pan.pack(fill="x", pady=(0, 10))

        fil = tk.Frame(pan, bg=E.FONDO)
        fil.pack(fill="x", padx=10, pady=8)

        # Periodo
        tk.Label(fil, text="Periodo:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_periodo = tk.StringVar(value="Ano actual")
        cb = ttk.Combobox(fil, textvariable=self.var_periodo,
                          values=PERIODOS, state="readonly", width=18,
                          font=E.F_NORMAL)
        cb.pack(side="left", padx=(4, 16))
        cb.bind("<<ComboboxSelected>>", self._on_periodo)

        # Fechas personalizadas
        self.lbl_desde = tk.Label(fil, text="Desde:", bg=E.FONDO,
                                  fg=E.TEXTO_SUB, font=E.F_NORMAL)
        self.var_desde = tk.StringVar(
            value=date(date.today().year, 1, 1).strftime("%Y-%m-%d"))
        self.ent_desde = tk.Entry(fil, textvariable=self.var_desde, width=12,
                                  font=E.F_NORMAL, relief="solid", bd=1)
        self.lbl_hasta = tk.Label(fil, text="Hasta:", bg=E.FONDO,
                                  fg=E.TEXTO_SUB, font=E.F_NORMAL)
        self.var_hasta = tk.StringVar(
            value=date.today().strftime("%Y-%m-%d"))
        self.ent_hasta = tk.Entry(fil, textvariable=self.var_hasta, width=12,
                                  font=E.F_NORMAL, relief="solid", bd=1)
        # Meses proyeccion
        tk.Label(fil, text="Meses proyeccion:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left", padx=(16, 0))
        self.var_meses = tk.IntVar(value=PY.leer_meses())
        tk.Spinbox(fil, from_=1, to=12, width=4,
                   textvariable=self.var_meses, font=E.F_NORMAL,
                   relief="solid", bd=1, justify="center").pack(
                       side="left", padx=(4, 16))

        # Botones
        tk.Button(fil, text="Vista previa", bg=E.AZUL2, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=14, pady=5,
                  command=self._previsualizar).pack(side="left", padx=(0, 8))
        tk.Button(fil, text="Exportar Excel", bg=E.VERDE, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=14, pady=5,
                  command=self._exportar_excel).pack(side="left", padx=(0, 8))


        self._ocultar_personalizadas()

        # KPIs resumen
        fila_kpi = tk.Frame(cont, bg=E.FONDO)
        fila_kpi.pack(fill="x", pady=(0, 10))
        self.kpis = {}
        kpi_defs = [
            ("productos",  "Productos con stock",      E.AZUL),
            ("ventas",     "Valor ventas del periodo", E.VERDE),
            ("produccion", "En produccion",            E.NARANJA),
            ("faltante",   "Unidades por producir",    E.ROJO),
        ]
        for i, (clave, titulo, color) in enumerate(kpi_defs):
            marco = tk.Frame(fila_kpi, bg=E.BLANCO,
                             highlightbackground=E.BORDE_SUAVE,
                             highlightthickness=1)
            tk.Frame(marco, bg=color, height=5).pack(fill="x")
            cuerpo = tk.Frame(marco, bg=E.BLANCO)
            cuerpo.pack(fill="both", expand=True, padx=14, pady=10)
            val = tk.Label(cuerpo, text="-", bg=E.BLANCO, fg=E.TEXTO,
                           font=(E.FUENTE, 22, "bold"))
            val.pack(anchor="w")
            tk.Label(cuerpo, text=titulo, bg=E.BLANCO, fg=E.TEXTO_SUB,
                     font=E.F_PEQUENA).pack(anchor="w")
            marco.grid(row=0, column=i, sticky="nsew",
                       padx=(0 if i == 0 else 10, 0))
            fila_kpi.columnconfigure(i, weight=1)
            self.kpis[clave] = val

        # Notebook de previsualizacion
        nb_frame = tk.Frame(cont, bg=E.FONDO)
        nb_frame.pack(fill="both", expand=True)
        estilo_nb = ttk.Style()
        try:
            estilo_nb.theme_use("clam")
        except tk.TclError:
            pass
        estilo_nb.configure("TNotebook", background=E.FONDO,
                            borderwidth=0)
        estilo_nb.configure("TNotebook.Tab", font=E.F_NORMAL_B,
                            padding=(12, 6))

        self.nb = ttk.Notebook(nb_frame)
        self.nb.pack(fill="both", expand=True)
        self._tabs = {}
        tabs_def = ["Resumen", "Inventario", "Ventas", "Rentabilidad",
                    "Proyeccion", "Pocas Unidades", "Produccion activa"]
        for t in tabs_def:
            frame = tk.Frame(self.nb, bg=E.BLANCO)
            self.nb.add(frame, text=t)
            self._tabs[t] = frame
        self._trees = {}

    def _on_periodo(self, event=None):
        if self.var_periodo.get() == "Personalizado":
            self._mostrar_personalizadas()
        else:
            self._ocultar_personalizadas()

    def _mostrar_personalizadas(self):
        self.lbl_desde.pack(side="left", padx=(0, 4))
        self.ent_desde.pack(side="left", padx=(0, 12))
        self.lbl_hasta.pack(side="left", padx=(0, 4))
        self.ent_hasta.pack(side="left", padx=(0, 16))

    def _ocultar_personalizadas(self):
        self.lbl_desde.pack_forget()
        self.ent_desde.pack_forget()
        self.lbl_hasta.pack_forget()
        self.ent_hasta.pack_forget()

    def _get_rango(self):
        periodo = self.var_periodo.get()
        if periodo == "Personalizado":
            return self.var_desde.get().strip(), self.var_hasta.get().strip()
        return _rango_desde_periodo(periodo)

    def _previsualizar(self):
        if not store.hay_datos():
            return
        info = store.obtener() or {}
        desde, hasta = self._get_rango()
        meses = self.var_meses.get()
        if not desde or not hasta:
            messagebox.showwarning("Reportes",
                                   "Ingrese el rango de fechas.")
            return

        # Calcular datos de cada pestaña
        datos = {
            "Resumen":          _resumen_ejecutivo(info, self.empresa,
                                                   self.usuario, desde,
                                                   hasta, meses),
            "Inventario":       _datos_inventario(info),
            "Ventas":           _datos_ventas(info, desde, hasta),
            "Rentabilidad":     _datos_rentabilidad(info, desde, hasta),
            "Proyeccion":       _datos_proyeccion(info, meses),
            "Pocas Unidades":   _datos_pocas(info, meses,
                                             PY.leer_umbral()),
            "Produccion activa": _datos_produccion(),
        }

        # Actualizar KPIs
        filas_inv = info.get("filas", [])
        prods_stock = len(set(f["codigo"] for f in filas_inv))
        _, f_ventas = datos["Ventas"]
        val_ventas = 0
        for fila in f_ventas:
            try:
                val_ventas += float(
                    str(fila[4]).replace("$ ","").replace(".","")
                    .replace(",",".") or 0)
            except (ValueError, IndexError):
                pass
        enprod = PD.produccion_activa_por_codigo()
        u_prod = sum(enprod.values())
        _, f_proy = datos["Proyeccion"]
        u_falt = 0
        for fila in f_proy:
            try:
                u_falt += float(
                    str(fila[6]).replace(".","").replace(",",".") or 0)
            except (ValueError, IndexError):
                pass
        try:
            self.kpis["productos"].config(text=_miles(prods_stock))
            self.kpis["ventas"].config(text=_money(val_ventas))
            self.kpis["produccion"].config(text=_miles(u_prod))
            self.kpis["faltante"].config(text=_miles(u_falt))
        except tk.TclError:
            pass

        # Poblar cada pestaña con un Treeview
        for tab_nombre, (cols, filas) in datos.items():
            frame = self._tabs.get(tab_nombre)
            if not frame:
                continue
            for w in frame.winfo_children():
                w.destroy()
            if not cols:
                continue
            marco = tk.Frame(frame, bg=E.BORDE)
            marco.pack(fill="both", expand=True)
            tree = ttk.Treeview(marco, columns=cols, show="headings",
                                style="MPS.Treeview", selectmode="browse")
            for col in cols:
                tree.heading(col, text=col)
                tree.column(col, width=max(80, len(col)*9), anchor="w",
                            stretch=True)
            tree.tag_configure("par",   background=E.FILA_PAR)
            tree.tag_configure("impar", background=E.FILA_IMPAR)
            tree.tag_configure("seccion", background=E.AZUL,
                               foreground=E.TEXTO_BLANCO,
                               font=E.F_NORMAL_B)
            vsb = ttk.Scrollbar(marco, orient="vertical",
                                command=tree.yview)
            hsb = ttk.Scrollbar(marco, orient="horizontal",
                                command=tree.xview)
            tree.configure(yscrollcommand=vsb.set,
                           xscrollcommand=hsb.set)
            tree.grid(row=0, column=0, sticky="nsew")
            vsb.grid(row=0, column=1, sticky="ns")
            hsb.grid(row=1, column=0, sticky="ew")
            marco.rowconfigure(0, weight=1)
            marco.columnconfigure(0, weight=1)
            for i, fila in enumerate(filas):
                if len(fila) == 2 and fila[0].isupper() and fila[1] == "":
                    tag = "seccion"
                elif i % 2 == 0:
                    tag = "par"
                else:
                    tag = "impar"
                tree.insert("", "end", values=fila, tags=(tag,))

    def _construir_pestanas(self, info, desde, hasta, meses):
        """Devuelve lista de pestanas para exportar."""
        datos_tabs = [
            ("Resumen",   "Resumen Ejecutivo",
             *_resumen_ejecutivo(info, self.empresa, self.usuario,
                                 desde, hasta, meses)),
            ("Inventario", "Inventario",        *_datos_inventario(info)),
            ("Ventas",     "Ventas del periodo", *_datos_ventas(info, desde, hasta)),
            ("Rentabilidad","Rentabilidad",      *_datos_rentabilidad(info, desde, hasta)),
            ("Proyeccion", "Proyeccion",         *_datos_proyeccion(info, meses)),
            ("Pocas Unidades","Pocas Unidades",  *_datos_pocas(info, meses,
                                                                PY.leer_umbral())),
            ("Produccion","Produccion activa",   *_datos_produccion()),
        ]
        return [{"nombre": n, "modulo": m, "columnas": c, "filas": f}
                for n, m, c, f in datos_tabs]

    def _exportar_excel(self):
        self._exportar("excel")

    def _mostrar_cargando(self, mensaje="Generando reporte..."):
        """Cartel grande de cargando que bloquea la pantalla."""
        self._overlay = tk.Toplevel(self.parent, bg=E.AZUL)
        self._overlay.overrideredirect(True)
        self._overlay.attributes("-topmost", True)
        # Centrar en pantalla con buen tamaño
        w, h = 520, 260
        sw = self._overlay.winfo_screenwidth()
        sh = self._overlay.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self._overlay.geometry("{}x{}+{}+{}".format(w, h, x, y))

        # Borde rojo en la parte superior
        tk.Frame(self._overlay, bg=E.ROJO, height=6).pack(fill="x")

        cuerpo = tk.Frame(self._overlay, bg=E.AZUL)
        cuerpo.pack(fill="both", expand=True, padx=40, pady=30)

        tk.Label(cuerpo, text="MPS REPORTS", bg=E.AZUL, fg=E.TEXTO_BLANCO,
                 font=(E.FUENTE, 13, "bold")).pack(anchor="center")
        tk.Label(cuerpo, text=mensaje, bg=E.AZUL, fg=E.TEXTO_BLANCO,
                 font=(E.FUENTE, 20, "bold")).pack(anchor="center", pady=(16, 8))
        tk.Label(cuerpo, text="Por favor espere, esto puede tardar unos segundos.",
                 bg=E.AZUL, fg="#CFE4F5",
                 font=(E.FUENTE, 10)).pack(anchor="center")

        self._barra_var = tk.DoubleVar(value=0)
        barra = ttk.Progressbar(cuerpo, variable=self._barra_var,
                                maximum=100, mode="indeterminate",
                                length=400)
        barra.pack(pady=(20, 0))
        barra.start(12)
        self._overlay.update()

    def _ocultar_cargando(self):
        try:
            self._overlay.destroy()
        except Exception:
            pass

    def _exportar(self, formato):
        if not store.hay_datos():
            messagebox.showwarning("Reportes",
                                   "Espere a que carguen los datos.")
            return
        desde, hasta = self._get_rango()
        if not desde or not hasta:
            messagebox.showwarning("Reportes",
                                   "Ingrese el rango de fechas.")
            return
        meses = self.var_meses.get()
        nombre_def = "MPS_Reporte_{}.xlsx".format(
            datetime.now().strftime("%Y%m%d_%H%M"))
        ruta = filedialog.asksaveasfilename(
            title="Guardar reporte Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("Todos", "*.*")],
            initialfile=nombre_def)
        if not ruta:
            return

        # Preparar datos ANTES del hilo (en hilo principal)
        info     = store.obtener() or {}
        pestanas = self._construir_pestanas(info, desde, hasta, meses)

        self._mostrar_cargando("Generando reporte Excel...")

        def _generar():
            error = None
            try:
                import exportar_excel as EX
                EX.exportar(ruta, self.empresa, self.usuario, pestanas)
            except Exception as e:
                error = str(e)
            # Volver al hilo principal para actualizar UI
            self.parent.after(0, lambda: self._tras_exportar(ruta, error))

        hilo = threading.Thread(target=_generar, daemon=True)
        hilo.start()

    def _tras_exportar(self, ruta, error):
        self._ocultar_cargando()
        if error:
            messagebox.showerror("Error al exportar",
                                 "No se pudo generar el archivo:\n" + error)
            return
        auditoria.registrar(
            self.usuario, "EXPORTACION",
            "Reporte Excel exportado: {}".format(os.path.basename(ruta)))
        if messagebox.askyesno(
                "Exportacion exitosa",
                "Reporte Excel generado correctamente.\n\n{}\n\n"
                "Desea abrirlo ahora?".format(ruta)):
            try:
                os.startfile(ruta)
            except Exception:
                pass

    def detener(self):
        self._vivo = False
        store.desuscribir(self._on_data)
