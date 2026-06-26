# -*- coding: utf-8 -*-
"""
MPS REPORTS - Modulo Inventario (Fase 4 + vista por marca)
Vista inicial: resumen por marca (productos, unidades, valor, rentabilidad,
rotacion). Doble clic en una marca -> filtra la tabla de productos por esa
marca. Boton 'Ver todas las marcas' para volver al resumen.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import estilo as E
import inventario_datos as ID
import ventas_datos as VD
import rentabilidad_datos as RD
from inventario_store import store

# Columnas de la tabla de productos
COLUMNAS = [
    ("codigo",      "Codigo",           95,  "w"),
    ("referencia",  "Referencia",       100, "w"),
    ("nombre",      "Nombre",           220, "w"),
    ("talla",       "Talla",            55,  "center"),
    ("color",       "Color",            60,  "center"),
    ("bodega",      "Bodega",           150, "w"),
    ("stock",       "Stock",            70,  "e"),
    ("costo_unit",  "Costo Unit",       100, "e"),
    ("precio_pub",  "Precio Publico",   110, "e"),
    ("valor_bodega","Valor Bodega",     120, "e"),
    ("rent_pct",    "Rentabilidad %",   110, "e"),
    ("rotacion",    "Rotacion",         80,  "e"),
    ("marca",       "Marca",            205, "w"),
    ("linea",       "Linea",            180, "w"),
    ("tipo",        "Sublinea",         160, "w"),
]

# Columnas del resumen por marca
COLS_MARCA = [
    ("marca",       "Marca",                200, "w"),
    ("productos",   "Productos",             90, "e"),
    ("unidades",    "Unidades",              90, "e"),
    ("valor",       "Valor bodega",         130, "e"),
    ("rent_prom",   "Rentabilidad %",       120, "e"),
    ("rotacion",    "Rotacion prom",        110, "e"),
]


def _miles(v):
    try:
        return "{:,.0f}".format(float(v or 0)).replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def _money(v):
    return "$ " + _miles(v)


def _resumen_marcas(filas):
    """Agrupa las filas por marca y calcula el resumen."""
    marcas = {}
    for f in filas:
        if f["stock"] <= 0:
            continue
        m = f["marca"] or "(Sin marca)"
        if m not in marcas:
            marcas[m] = {"productos": set(), "unidades": 0.0,
                         "valor": 0.0, "rents": [], "rots": []}
        marcas[m]["productos"].add(f["codigo"])
        marcas[m]["unidades"] += f["stock"]
        marcas[m]["valor"]    += f["valor_bodega"]
        if f["rent_pct"] is not None:
            marcas[m]["rents"].append(f["rent_pct"])
        if f["rotacion"] is not None:
            marcas[m]["rots"].append(f["rotacion"])

    res = []
    for m, d in sorted(marcas.items()):
        rent = (sum(d["rents"]) / len(d["rents"])) if d["rents"] else None
        rot  = (sum(d["rots"])  / len(d["rots"]))  if d["rots"]  else None
        res.append({
            "marca":     m,
            "productos": len(d["productos"]),
            "unidades":  d["unidades"],
            "valor":     d["valor"],
            "rent_prom": rent,
            "rotacion":  rot,
        })
    return res


class ModuloInventario:
    def __init__(self, parent, rol="CONSULTA", indicador_cb=None):
        self.parent = parent
        self.rol = rol
        self.indicador_cb = indicador_cb or (lambda *a, **k: None)

        self.filas = []
        self.filas_vista = []
        self.bodegas = {}
        self.orden_col = None
        self.orden_asc = True
        self._vivo = True
        self._vista = "marcas"          # "marcas" o "productos"
        self._marca_activa = None       # None = todas

        self._construir()

        store.suscribir(self._on_data)
        store.suscribir_progreso(self._on_prog)

        if store.hay_datos():
            self._render(store.obtener())
            self._indicador_actualizado((0, 0))
        else:
            self._mostrar_overlay()
            pct, msg = store.ultimo_progreso
            self._actualizar_overlay(pct or 3, msg or "Cargando inventario...")
            self._set_indicador(
                "Cargando inventario... {}%".format(int(pct or 0)), True)
            store.precargar()

    # ------------------------------------------------------------------
    # CONSTRUCCION DE LA UI
    # ------------------------------------------------------------------
    def _construir(self):
        self.cont = tk.Frame(self.parent, bg=E.FONDO)
        self.cont.pack(fill="both", expand=True, padx=16, pady=14)

        # KPIs
        fila_kpi = tk.Frame(self.cont, bg=E.FONDO)
        fila_kpi.pack(fill="x")
        self.kpi = {}
        defs = [
            ("productos", "Productos",               E.AZUL),
            ("unidades",  "Unidades en bodega",      E.VERDE),
            ("valor",     "Valor inventario al costo", E.AZUL),
            ("pocas",     "Pocas unidades",           E.ROJO),
        ]
        for i, (clave, titulo, color) in enumerate(defs):
            self.kpi[clave] = self._tarjeta_kpi(fila_kpi, titulo, color)
            self.kpi[clave]["marco"].grid(row=0, column=i, sticky="nsew",
                                          padx=(0 if i == 0 else 12, 0))
            fila_kpi.columnconfigure(i, weight=1)

        # Barra de navegacion (marca activa + boton volver)
        self.barra_nav = tk.Frame(self.cont, bg=E.FONDO)
        self.barra_nav.pack(fill="x", pady=(10, 0))
        self.lbl_nav = tk.Label(
            self.barra_nav, text="", bg=E.FONDO, fg=E.AZUL,
            font=(E.FUENTE, 11, "bold"))
        self.lbl_nav.pack(side="left")
        self.btn_volver = tk.Button(
            self.barra_nav, text="<  Ver todas las marcas",
            bg=E.AZUL2, fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B,
            relief="flat", bd=0, cursor="hand2", padx=12, pady=4,
            command=self._volver_marcas)
        # No se empaca hasta que se entra al detalle de una marca

        # Barra de filtros (solo visible en vista productos)
        self.barra_filtros = tk.Frame(self.cont, bg=E.FONDO)

        tk.Label(self.barra_filtros, text="Buscar:", bg=E.FONDO,
                 fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(side="left")
        self.var_busqueda = tk.StringVar()
        ent = tk.Entry(self.barra_filtros, textvariable=self.var_busqueda,
                       width=28, font=E.F_NORMAL, relief="solid", bd=1)
        ent.pack(side="left", padx=(6, 12))
        ent.bind("<KeyRelease>", lambda e: self._aplicar_filtros())

        tk.Label(self.barra_filtros, text="Bodega:", bg=E.FONDO,
                 fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(side="left")
        self.var_bodega = tk.StringVar(value="Todas")
        self.cmb_bodega = ttk.Combobox(
            self.barra_filtros, textvariable=self.var_bodega,
            state="readonly", width=22, font=E.F_NORMAL, values=["Todas"])
        self.cmb_bodega.pack(side="left", padx=(6, 12))
        self.cmb_bodega.bind("<<ComboboxSelected>>",
                             lambda e: self._aplicar_filtros())

        self.var_stock = tk.BooleanVar(value=True)
        tk.Checkbutton(
            self.barra_filtros, text="Solo con stock",
            variable=self.var_stock, bg=E.FONDO, fg=E.TEXTO,
            font=E.F_NORMAL, activebackground=E.FONDO,
            selectcolor=E.BLANCO,
            command=self._aplicar_filtros).pack(side="left")

        tk.Label(self.barra_filtros, text="Rotacion:", bg=E.FONDO,
                 fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(side="left",
                                                       padx=(12, 0))
        self.var_periodo = tk.StringVar(value="Ano actual")
        self.cmb_periodo = ttk.Combobox(
            self.barra_filtros, textvariable=self.var_periodo,
            state="readonly", width=14, font=E.F_NORMAL, values=VD.PERIODOS)
        self.cmb_periodo.pack(side="left", padx=(6, 0))
        self.cmb_periodo.bind("<<ComboboxSelected>>",
                              lambda e: self._cambiar_periodo())

        self.btn_refrescar = tk.Button(
            self.barra_filtros, text="Actualizar ahora", bg=E.AZUL,
            fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B, relief="flat", bd=0,
            cursor="hand2", activebackground=E.AZUL2,
            activeforeground=E.TEXTO_BLANCO,
            padx=14, pady=6, command=self._refrescar_manual)
        self.btn_refrescar.pack(side="right")

        self.lbl_contador = tk.Label(
            self.barra_filtros, text="", bg=E.FONDO,
            fg=E.TEXTO_SUB, font=E.F_NORMAL_B)
        self.lbl_contador.pack(side="right", padx=(0, 12))

        # Estilo compartido del Treeview
        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("MPS.Treeview", background=E.BLANCO,
                         fieldbackground=E.BLANCO, foreground=E.TEXTO,
                         rowheight=24, font=E.F_NORMAL, borderwidth=0)
        estilo.configure("MPS.Treeview.Heading", background=E.AZUL,
                         foreground=E.TEXTO_BLANCO, font=E.F_NORMAL_B,
                         relief="flat", padding=(4, 6))
        estilo.map("MPS.Treeview.Heading",
                   background=[("active", E.AZUL2)])
        estilo.map("MPS.Treeview",
                   background=[("selected", E.AZUL2)],
                   foreground=[("selected", E.TEXTO_BLANCO)])
        estilo.configure("MPS.Horizontal.TProgressbar",
                         troughcolor=E.FILA_IMPAR, bordercolor=E.BORDE_SUAVE,
                         background=E.AZUL, lightcolor=E.AZUL,
                         darkcolor=E.AZUL)

        # ----- TABLA DE MARCAS -----
        self.marco_marcas = tk.Frame(self.cont, bg=E.BORDE, bd=0)
        ids_m = [c[0] for c in COLS_MARCA]
        self.tree_marcas = ttk.Treeview(
            self.marco_marcas, columns=ids_m, show="headings",
            style="MPS.Treeview", selectmode="browse")
        for cid, titulo, ancho, anchor in COLS_MARCA:
            self.tree_marcas.heading(cid, text=titulo,
                                     command=lambda c=cid: self._ordenar_marcas(c))
            self.tree_marcas.column(cid, width=ancho, anchor=anchor,
                                    stretch=(cid == "marca"))
        self.tree_marcas.tag_configure("par",   background=E.FILA_PAR)
        self.tree_marcas.tag_configure("impar", background=E.FILA_IMPAR)
        self.tree_marcas.bind("<Double-1>", self._abrir_marca)
        vsb_m = ttk.Scrollbar(self.marco_marcas, orient="vertical",
                               command=self.tree_marcas.yview)
        self.tree_marcas.configure(yscrollcommand=vsb_m.set)
        self.tree_marcas.grid(row=0, column=0, sticky="nsew")
        vsb_m.grid(row=0, column=1, sticky="ns")
        self.marco_marcas.rowconfigure(0, weight=1)
        self.marco_marcas.columnconfigure(0, weight=1)
        self._orden_marca_col = "valor"
        self._orden_marca_asc = False

        # Nota debajo de la tabla de marcas
        self.lbl_hint = tk.Label(
            self.cont,
            text="Doble clic en una marca para ver sus productos",
            bg=E.FONDO, fg=E.TEXTO_TENUE, font=E.F_PEQUENA)

        # ----- TABLA DE PRODUCTOS -----
        self.marco_tabla = tk.Frame(self.cont, bg=E.BORDE, bd=0)
        ids_p = [c[0] for c in COLUMNAS]
        self.tree = ttk.Treeview(
            self.marco_tabla, columns=ids_p, show="headings",
            style="MPS.Treeview", selectmode="browse")
        for cid, titulo, ancho, anchor in COLUMNAS:
            self.tree.heading(cid, text=titulo,
                              command=lambda c=cid: self._ordenar(c))
            self.tree.column(cid, width=ancho, anchor=anchor,
                             stretch=(cid == "nombre"))
        self.tree.tag_configure("par",   background=E.FILA_PAR)
        self.tree.tag_configure("impar", background=E.FILA_IMPAR)
        self.tree.bind("<Double-1>", self._abrir_detalle)
        vsb = ttk.Scrollbar(self.marco_tabla, orient="vertical",
                            command=self.tree.yview)
        hsb = ttk.Scrollbar(self.marco_tabla, orient="horizontal",
                            command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        self.marco_tabla.rowconfigure(0, weight=1)
        self.marco_tabla.columnconfigure(0, weight=1)

        self._construir_overlay()
        self._mostrar_vista_marcas()

    # ------------------------------------------------------------------
    # NAVEGACION ENTRE VISTAS
    # ------------------------------------------------------------------
    def _mostrar_vista_marcas(self):
        self._vista = "marcas"
        self._marca_activa = None
        self.barra_filtros.pack_forget()
        self.btn_volver.pack_forget()
        self.marco_tabla.pack_forget()
        self.lbl_nav.config(text="Resumen por marca")
        self.marco_marcas.pack(fill="both", expand=True, pady=(6, 0))
        self.lbl_hint.pack(anchor="w", pady=(4, 0))
        self._pintar_marcas()
        self._actualizar_kpis_marcas()

    def _abrir_marca(self, event=None):
        item = self.tree_marcas.identify_row(event.y)
        if not item:
            return
        idx = self.tree_marcas.index(item)
        datos = self._resumen_filas
        if not (0 <= idx < len(datos)):
            return
        marca = datos[idx]["marca"]
        self._mostrar_vista_productos(marca)

    def _mostrar_vista_productos(self, marca=None):
        self._vista = "productos"
        self._marca_activa = marca
        self.marco_marcas.pack_forget()
        self.lbl_hint.pack_forget()
        if marca:
            self.lbl_nav.config(text="Marca: " + marca)
            self.btn_volver.pack(side="left", padx=(12, 0))
        else:
            self.lbl_nav.config(text="Todos los productos")
            self.btn_volver.pack_forget()
        self.barra_filtros.pack(fill="x", pady=(6, 6))
        self.marco_tabla.pack(fill="both", expand=True)
        self._aplicar_filtros()

    def _volver_marcas(self):
        self.var_busqueda.set("")
        self.var_bodega.set("Todas")
        self._mostrar_vista_marcas()

    # ------------------------------------------------------------------
    # TABLA DE MARCAS
    # ------------------------------------------------------------------
    def _pintar_marcas(self):
        filas_con_stock = [f for f in self.filas if f["stock"] > 0]
        datos = _resumen_marcas(filas_con_stock)
        # Ordenar
        col = self._orden_marca_col
        num = col in ("productos", "unidades", "valor", "rent_prom", "rotacion")
        datos = sorted(
            datos,
            key=lambda d: (d.get(col) is None,
                           d.get(col, 0) if num else str(d.get(col, "")).lower()),
            reverse=not self._orden_marca_asc)
        self._resumen_filas = datos
        try:
            self.tree_marcas.delete(*self.tree_marcas.get_children())
            for i, d in enumerate(datos):
                rent = ("N/D" if d["rent_prom"] is None
                        else "{:.1f}%".format(d["rent_prom"]))
                rot  = ("-" if d["rotacion"] is None
                        else "{:.2f}".format(d["rotacion"]))
                tag = "par" if i % 2 == 0 else "impar"
                self.tree_marcas.insert("", "end", tags=(tag,), values=(
                    d["marca"], _miles(d["productos"]),
                    _miles(d["unidades"]), _money(d["valor"]),
                    rent, rot))
        except tk.TclError:
            pass

    def _ordenar_marcas(self, col):
        if self._orden_marca_col == col:
            self._orden_marca_asc = not self._orden_marca_asc
        else:
            self._orden_marca_col = col
            self._orden_marca_asc = False
        self._pintar_marcas()

    def _actualizar_kpis_marcas(self):
        """KPIs globales en la vista de marcas."""
        filas_stock = [f for f in self.filas if f["stock"] > 0]
        k = ID.calcular_kpis(filas_stock)
        try:
            self.kpi["productos"]["valor"].config(text=_miles(k["productos"]))
            self.kpi["unidades"]["valor"].config(text=_miles(k["unidades"]))
            self.kpi["valor"]["valor"].config(text=_money(k["valor_costo"]))
            self.kpi["pocas"]["valor"].config(text=_miles(self._contar_pocas()))
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # KPI / TARJETAS
    # ------------------------------------------------------------------
    def _tarjeta_kpi(self, padre, titulo, color):
        marco = tk.Frame(padre, bg=E.BLANCO,
                         highlightbackground=E.BORDE_SUAVE,
                         highlightthickness=1, bd=0)
        tk.Frame(marco, bg=color, height=5).pack(fill="x")
        cuerpo = tk.Frame(marco, bg=E.BLANCO)
        cuerpo.pack(fill="both", expand=True, padx=16, pady=12)
        val = tk.Label(cuerpo, text="-", bg=E.BLANCO, fg=E.TEXTO,
                       font=(E.FUENTE, 24, "bold"))
        val.pack(anchor="w")
        tk.Label(cuerpo, text=titulo, bg=E.BLANCO, fg=E.TEXTO_SUB,
                 font=E.F_PEQUENA).pack(anchor="w")
        return {"marco": marco, "valor": val}

    # ------------------------------------------------------------------
    # OVERLAY
    # ------------------------------------------------------------------
    def _construir_overlay(self):
        self.overlay = tk.Frame(self.cont, bg=E.FONDO)
        tarjeta = tk.Frame(self.overlay, bg=E.BLANCO,
                           highlightbackground=E.BORDE_SUAVE,
                           highlightthickness=1)
        tarjeta.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(tarjeta, text="Cargando inventario", bg=E.BLANCO,
                 fg=E.TEXTO, font=(E.FUENTE, 16, "bold")).pack(
                     padx=48, pady=(28, 4))
        self.ov_msg = tk.Label(tarjeta, text="Conectando con Business...",
                               bg=E.BLANCO, fg=E.TEXTO_SUB, font=E.F_NORMAL)
        self.ov_msg.pack(padx=48)
        self.ov_bar = ttk.Progressbar(
            tarjeta, length=380, maximum=100, mode="determinate",
            style="MPS.Horizontal.TProgressbar")
        self.ov_bar.pack(padx=48, pady=(14, 6))
        self.ov_pct = tk.Label(tarjeta, text="0%", bg=E.BLANCO,
                               fg=E.AZUL, font=E.F_NORMAL_B)
        self.ov_pct.pack()
        tk.Label(tarjeta,
                 text="La lectura de movimientos puede tardar 20-40 segundos.",
                 bg=E.BLANCO, fg=E.TEXTO_TENUE,
                 font=(E.FUENTE, 8, "italic")).pack(pady=(4, 28))

    def _mostrar_overlay(self):
        self.overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.overlay.lift()

    def _ocultar_overlay(self):
        try:
            self.overlay.place_forget()
        except tk.TclError:
            pass

    def _overlay_visible(self):
        try:
            return bool(self.overlay.winfo_ismapped())
        except tk.TclError:
            return False

    def _actualizar_overlay(self, pct, msg):
        try:
            self.ov_bar["value"] = pct
            self.ov_msg.config(text=msg)
            self.ov_pct.config(text="{}%".format(int(pct)))
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # CALLBACKS DEL ALMACEN
    # ------------------------------------------------------------------
    def _on_prog(self, pct, msg):
        if not self._vivo:
            return
        self._set_indicador(
            "Cargando inventario... {}%".format(int(pct)), True)
        if self._overlay_visible():
            self._actualizar_overlay(pct, msg)

    def _on_data(self, info, manual, resumen):
        if not self._vivo:
            return
        try:
            self.btn_refrescar.config(state="normal", text="Actualizar ahora")
        except tk.TclError:
            pass
        if not info.get("ok"):
            self._set_indicador("Sin conexion (se reintentara)", False)
            if manual:
                messagebox.showwarning(
                    "Sin conexion",
                    "No se pudo leer Business.\n\n" + (info.get("error") or ""))
            if not store.hay_datos():
                self._actualizar_overlay(100, "Sin conexion con Business")
            return
        self._ocultar_overlay()
        self._render(info)
        self._indicador_actualizado(resumen)

    def _refrescar_manual(self):
        try:
            self.btn_refrescar.config(state="disabled", text="Actualizando...")
        except tk.TclError:
            pass
        store.forzar_refresco()

    # ------------------------------------------------------------------
    def _render(self, info):
        self.filas = info.get("filas", [])
        self.bodegas = info.get("bodegas", {})
        self._llenar_combo_bodegas()
        self._recalc_rotacion()
        if self._vista == "marcas":
            self._mostrar_vista_marcas()
        else:
            self._aplicar_filtros(conservar_scroll=True)

    def _recalc_rotacion(self):
        info = store.obtener() or {}
        movs = info.get("movimientos", [])
        desde, hasta = VD.rango_periodo(self.var_periodo.get())
        rot = RD.calcular_rotacion_periodo(movs, desde, hasta)
        for f in self.filas:
            f["rotacion"] = rot.get(f["codigo"])

    def _cambiar_periodo(self):
        self._recalc_rotacion()
        if self._vista == "marcas":
            self._pintar_marcas()
        else:
            self._aplicar_filtros()

    def _indicador_actualizado(self, resumen):
        if store.ultima_carga is not None:
            ts = store.ultima_carga.strftime("%d/%m/%Y %H:%M")
        else:
            ts = "-"
        texto = "Actualizado: {} - automatico cada 15 min".format(ts)
        if resumen and (resumen[0] or resumen[1]):
            texto += "   |   {} cambiaron, {} nuevos".format(
                resumen[0], resumen[1])
        self._set_indicador(texto, True)

    # ------------------------------------------------------------------
    def _llenar_combo_bodegas(self):
        nombres = ["Todas"] + [self.bodegas[c] for c in sorted(self.bodegas)]
        self._nombre_a_cod = {self.bodegas[c]: c for c in self.bodegas}
        try:
            actual = self.var_bodega.get()
            self.cmb_bodega.config(values=nombres)
            if actual not in nombres:
                self.var_bodega.set("Todas")
        except tk.TclError:
            pass

    def _bodega_cod_actual(self):
        nombre = self.var_bodega.get()
        if nombre == "Todas":
            return ""
        return getattr(self, "_nombre_a_cod", {}).get(nombre, "")

    def _aplicar_filtros(self, conservar_scroll=False):
        if not self._vivo:
            return
        filas_base = self.filas
        # Si hay marca activa, filtrar solo esa marca
        if self._marca_activa:
            filas_base = [f for f in filas_base
                          if (f["marca"] or "(Sin marca)") == self._marca_activa]
        filtradas = ID.filtrar(
            filas_base,
            texto=self.var_busqueda.get(),
            bodega_cod=self._bodega_cod_actual(),
            solo_con_stock=self.var_stock.get())
        if self.orden_col:
            filtradas = ID.ordenar_filas(filtradas, self.orden_col,
                                         self.orden_asc)
        self.filas_vista = filtradas
        self._pintar_tabla(conservar_scroll)
        self._actualizar_kpis()
        try:
            self.lbl_contador.config(
                text="{} resultados".format(len(self.filas_vista)))
        except tk.TclError:
            pass

    def _actualizar_kpis(self):
        k = ID.calcular_kpis(self.filas_vista)
        try:
            self.kpi["productos"]["valor"].config(text=_miles(k["productos"]))
            self.kpi["unidades"]["valor"].config(text=_miles(k["unidades"]))
            self.kpi["valor"]["valor"].config(text=_money(k["valor_costo"]))
            self.kpi["pocas"]["valor"].config(text=_miles(self._contar_pocas()))
        except tk.TclError:
            pass

    def _valor_celda(self, fila, cid):
        v = fila.get(cid)
        if cid in ("costo_unit", "precio_pub", "valor_bodega"):
            return _money(v)
        if cid == "stock":
            return _miles(v)
        if cid == "rent_pct":
            return "N/D" if v is None else "{:.1f}%".format(v)
        if cid == "rotacion":
            return "-" if v is None else "{:.2f}".format(v)
        return v if v not in (None, "") else ""

    def _pintar_tabla(self, conservar_scroll=False):
        ids = [c[0] for c in COLUMNAS]
        try:
            pos = self.tree.yview()[0] if conservar_scroll else None
            self.tree.delete(*self.tree.get_children())
            for i, fila in enumerate(self.filas_vista):
                valores = [self._valor_celda(fila, cid) for cid in ids]
                tag = "par" if i % 2 == 0 else "impar"
                self.tree.insert("", "end", values=valores, tags=(tag,))
            if pos is not None:
                self.tree.yview_moveto(pos)
        except tk.TclError:
            pass

    def _contar_pocas(self):
        try:
            import proyeccion_datos as PY
            info = store.obtener() or {}
            return PY.contar_pocas(info, PY.leer_meses(), PY.leer_umbral())
        except Exception:
            return 0

    def _ordenar(self, columna):
        if self.orden_col == columna:
            self.orden_asc = not self.orden_asc
        else:
            self.orden_col = columna
            self.orden_asc = True
        flecha = "  v" if self.orden_asc else "  ^"
        for cid, titulo, _, _ in COLUMNAS:
            try:
                self.tree.heading(cid, text=titulo +
                                  (flecha if cid == columna else ""))
            except tk.TclError:
                pass
        self._aplicar_filtros()

    # ------------------------------------------------------------------
    # DETALLE DE PRODUCTO (doble clic en tabla de productos)
    # ------------------------------------------------------------------
    def _abrir_detalle(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        try:
            idx = self.tree.index(item)
        except tk.TclError:
            return
        if not (0 <= idx < len(self.filas_vista)):
            return
        self._mostrar_detalle(self.filas_vista[idx])

    def _mostrar_detalle(self, fila):
        cod = fila["codigo"]
        porbod = [f for f in self.filas if f["codigo"] == cod]

        dlg = tk.Toplevel(self.parent, bg=E.FONDO)
        dlg.title("Detalle del producto")
        dlg.resizable(False, False)
        try:
            dlg.transient(self.parent.winfo_toplevel())
        except tk.TclError:
            pass

        hd = tk.Frame(dlg, bg=E.AZUL)
        hd.pack(fill="x")
        tk.Label(hd, text=fila["nombre"] or "(sin nombre)", bg=E.AZUL,
                 fg=E.TEXTO_BLANCO,
                 font=(E.FUENTE, 15, "bold")).pack(anchor="w", padx=18,
                                                   pady=(12, 0))
        tk.Label(hd, text="Codigo: " + cod, bg=E.AZUL, fg="#CFE4F5",
                 font=(E.FUENTE, 10)).pack(anchor="w", padx=18, pady=(0, 12))
        tk.Frame(dlg, bg=E.ROJO, height=3).pack(fill="x")

        cuerpo = tk.Frame(dlg, bg=E.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=18, pady=16)

        rent = ("N/D" if fila["rent_pct"] is None
                else "{:.1f}%".format(fila["rent_pct"]))
        rota = ("-" if fila["rotacion"] is None
                else "{:.2f}".format(fila["rotacion"]))
        datos = [
            ("Marca",          fila["marca"] or "-"),
            ("Linea",          fila["linea"] or "-"),
            ("Sublinea",       fila["tipo"]  or "-"),
            ("Referencia",     fila["referencia"] or "-"),
            ("Talla",          fila["talla"] or "-"),
            ("Color",          fila["color"] or "-"),
            ("Costo unitario", _money(fila["costo_unit"])),
            ("Precio publico", _money(fila["precio_pub"])),
            ("Rentabilidad",   rent),
            ("Rotacion",       rota),
        ]
        grid = tk.Frame(cuerpo, bg=E.FONDO)
        grid.pack(fill="x")
        for i, (k, v) in enumerate(datos):
            r = i // 2
            cc = (i % 2) * 2
            tk.Label(grid, text=k + ":", bg=E.FONDO, fg=E.TEXTO_SUB,
                     font=E.F_PEQUENA).grid(row=r, column=cc, sticky="w",
                                            padx=(0, 6), pady=3)
            tk.Label(grid, text=str(v), bg=E.FONDO, fg=E.TEXTO,
                     font=E.F_NORMAL_B).grid(row=r, column=cc + 1,
                                             sticky="w", padx=(0, 30), pady=3)

        tk.Label(cuerpo, text="Existencias por bodega", bg=E.FONDO,
                 fg=E.AZUL, font=E.F_NORMAL_B).pack(anchor="w", pady=(16, 4))
        tabla = tk.Frame(cuerpo, bg=E.BLANCO,
                         highlightbackground=E.BORDE_SUAVE,
                         highlightthickness=1)
        tabla.pack(fill="x")
        enc = tk.Frame(tabla, bg=E.AZUL)
        enc.pack(fill="x")
        for txt, w, anch in [("Bodega", 22, "w"), ("Stock", 10, "e"),
                              ("Valor", 16, "e")]:
            tk.Label(enc, text=txt, bg=E.AZUL, fg=E.TEXTO_BLANCO,
                     font=E.F_PEQUENA, width=w, anchor=anch).pack(
                         side="left", padx=6, pady=4)
        tot_stock = 0.0
        tot_valor = 0.0
        hay = False
        for f in porbod:
            if f["stock"] == 0:
                continue
            hay = True
            tot_stock += f["stock"]
            tot_valor += f["valor_bodega"]
            rf = tk.Frame(tabla, bg=E.BLANCO)
            rf.pack(fill="x")
            tk.Label(rf, text=f["bodega"], bg=E.BLANCO, fg=E.TEXTO,
                     font=E.F_NORMAL, width=22, anchor="w").pack(
                         side="left", padx=6, pady=2)
            tk.Label(rf, text=_miles(f["stock"]), bg=E.BLANCO, fg=E.TEXTO,
                     font=E.F_NORMAL, width=10, anchor="e").pack(
                         side="left", padx=6)
            tk.Label(rf, text=_money(f["valor_bodega"]), bg=E.BLANCO,
                     fg=E.TEXTO, font=E.F_NORMAL, width=16,
                     anchor="e").pack(side="left", padx=6)
        if not hay:
            tk.Label(tabla, text="Sin existencias", bg=E.BLANCO,
                     fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(padx=6, pady=4)
        tf = tk.Frame(tabla, bg=E.FILA_IMPAR)
        tf.pack(fill="x")
        tk.Label(tf, text="TOTAL", bg=E.FILA_IMPAR, fg=E.TEXTO,
                 font=E.F_NORMAL_B, width=22, anchor="w").pack(
                     side="left", padx=6, pady=3)
        tk.Label(tf, text=_miles(tot_stock), bg=E.FILA_IMPAR, fg=E.TEXTO,
                 font=E.F_NORMAL_B, width=10, anchor="e").pack(
                     side="left", padx=6)
        tk.Label(tf, text=_money(tot_valor), bg=E.FILA_IMPAR, fg=E.TEXTO,
                 font=E.F_NORMAL_B, width=16, anchor="e").pack(
                     side="left", padx=6)

        tk.Button(cuerpo, text="Cerrar", bg=E.AZUL, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  activebackground=E.AZUL2, activeforeground=E.TEXTO_BLANCO,
                  padx=22, pady=7, command=dlg.destroy).pack(pady=(16, 0))

        dlg.update_idletasks()
        w = dlg.winfo_width()
        h = dlg.winfo_height()
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        dlg.geometry("+{}+{}".format(max(0, (sw - w) // 2),
                                     max(0, (sh - h) // 2)))
        try:
            dlg.grab_set()
        except tk.TclError:
            pass

    def _set_indicador(self, texto, conectado):
        try:
            self.indicador_cb(texto, conectado)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def detener(self):
        self._vivo = False
        store.desuscribir(self._on_data)
        store.desuscribir_progreso(self._on_prog)


if __name__ == "__main__":
    import os, sys
    DIR_UI = os.path.dirname(os.path.abspath(__file__))
    DIR_APP = os.path.dirname(DIR_UI)
    sys.path.insert(0, os.path.join(DIR_APP, "core"))
    sys.path.insert(0, DIR_UI)
    root = tk.Tk()
    root.state("zoomed")
    root.configure(bg=E.FONDO)
    store.iniciar(root)
    ModuloInventario(root, rol="ADMINISTRADOR",
                     indicador_cb=lambda t, c=True: print("IND:", t))
    root.mainloop()
