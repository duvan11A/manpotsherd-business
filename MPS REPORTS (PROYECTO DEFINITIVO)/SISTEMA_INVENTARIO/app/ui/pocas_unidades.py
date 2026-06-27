# -*- coding: utf-8 -*-
"""
MPS REPORTS - Modulo Pocas Unidades (Fase 8 + vista por marca)
Vista inicial: resumen por marca (alertas, faltante, stock bajo).
Doble clic -> productos de esa marca.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import estilo as E
import proyeccion_datos as PY
from inventario_store import store

TINTE_ROJO  = "#FBE4E4"
TINTE_VERDE = "#E3F4E8"

COLS_MARCA = [
    ("marca",       "Marca",               220, "w"),
    ("alertas",     "Total alertas",        100, "e"),
    ("producir",    "Hay que producir",     120, "e"),
    ("stock_bajo",  "Stock bajo",           100, "e"),
    ("ambos",       "Producir + stock bajo",150, "e"),
    ("por_producir","Unidades faltantes",   130, "e"),
]


def _miles(v):
    try:
        return "{:,.0f}".format(float(v or 0)).replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def _resumen_marcas(filas, marca_por_codigo, umbral):
    marcas = {}
    for f in filas:
        m = marca_por_codigo.get(f["codigo"]) or "(Sin marca)"
        if m not in marcas:
            marcas[m] = {"alertas": 0, "producir": 0,
                         "stock_bajo": 0, "ambos": 0, "por_producir": 0.0}
        d = marcas[m]
        d["alertas"] += 1
        d["por_producir"] += f["producir"]
        prod = f["producir"] > 0
        bajo = f["stock"] <= umbral
        if prod and bajo:
            d["ambos"] += 1
        elif prod:
            d["producir"] += 1
        else:
            d["stock_bajo"] += 1

    res = []
    for m, d in sorted(marcas.items()):
        res.append({"marca": m, **d})
    return res


class ModuloPocasUnidades:
    COLUMNAS = [
        ("codigo",       "Codigo",               110, "w"),
        ("nombre",       "Nombre",               270, "w"),
        ("referencia",   "Referencia",           110, "w"),
        ("vendido",      "Vendido (N meses)",    140, "e"),
        ("stock",        "Stock bodega",         110, "e"),
        ("en_produccion","En produccion",        120, "e"),
        ("producir",     "Faltante por producir",160, "e"),
        ("motivo",       "Motivo",               170, "w"),
    ]

    def __init__(self, parent, rol="CONSULTA", indicador_cb=None):
        self.parent = parent
        self.rol = rol
        self.indicador_cb = indicador_cb or (lambda *a, **k: None)
        self._vivo = True
        self.filas = []
        self._marca_por_codigo = {}
        self._resumen_filas    = []
        self._vista            = "marcas"
        self._marca_activa     = None
        self._orden_marca_col  = "alertas"
        self._orden_marca_asc  = False

        self._construir()
        store.suscribir(self._on_data)
        store.suscribir_progreso(self._on_prog)
        if store.hay_datos():
            self._recalcular()
        else:
            self._mostrar_overlay()
            store.precargar()

    # ------------------------------------------------------------------
    def _construir(self):
        self.cont = tk.Frame(self.parent, bg=E.FONDO)
        self.cont.pack(fill="both", expand=True, padx=16, pady=14)

        # Cabecera
        cab = tk.Frame(self.cont, bg=E.FONDO)
        cab.pack(fill="x")
        tk.Label(cab, text="Alertas: productos por producir o con stock bajo",
                 bg=E.FONDO, fg=E.TEXTO,
                 font=(E.FUENTE, 15, "bold")).pack(side="left")
        self.lbl_total = tk.Label(cab, text="", bg=E.FONDO, fg=E.ROJO,
                                  font=E.F_NORMAL_B)
        self.lbl_total.pack(side="right")

        # Barra de controles
        barra = tk.Frame(self.cont, bg=E.FONDO)
        barra.pack(fill="x", pady=(10, 0))
        tk.Label(barra, text="Umbral de stock bajo:", bg=E.FONDO,
                 fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(side="left")
        self.var_umbral = tk.IntVar(value=PY.leer_umbral())
        estado = "normal" if self.rol == "ADMINISTRADOR" else "readonly"
        self.spin = tk.Spinbox(barra, from_=0, to=100000, width=7,
                               textvariable=self.var_umbral, font=E.F_NORMAL,
                               relief="solid", bd=1, justify="center",
                               state=estado)
        self.spin.pack(side="left", padx=(6, 6))
        if self.rol == "ADMINISTRADOR":
            tk.Button(barra, text="Guardar umbral", bg=E.AZUL,
                      fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B, relief="flat",
                      bd=0, cursor="hand2", padx=12, pady=4,
                      command=self._guardar_umbral).pack(side="left")
        else:
            tk.Label(barra, text="(solo el administrador puede cambiarlo)",
                     bg=E.FONDO, fg=E.TEXTO_TENUE,
                     font=E.F_PEQUENA).pack(side="left")

        # Busqueda (solo en vista productos)
        self.barra_busqueda = tk.Frame(self.cont, bg=E.FONDO)
        tk.Label(self.barra_busqueda, text="Buscar:", bg=E.FONDO,
                 fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(side="left",
                                                        padx=(16, 0))
        self.var_busqueda = tk.StringVar()
        ent = tk.Entry(self.barra_busqueda, textvariable=self.var_busqueda,
                       width=26, font=E.F_NORMAL, relief="solid", bd=1)
        ent.pack(side="left", padx=(6, 0))
        ent.bind("<KeyRelease>", lambda e: self._pintar())

        # Barra de navegacion
        self.barra_nav = tk.Frame(self.cont, bg=E.FONDO)
        self.barra_nav.pack(fill="x", pady=(6, 0))
        self.lbl_nav = tk.Label(self.barra_nav, text="", bg=E.FONDO,
                                fg=E.AZUL, font=(E.FUENTE, 11, "bold"))
        self.lbl_nav.pack(side="left")
        self.btn_volver = tk.Button(
            self.barra_nav, text="<  Ver todas las marcas",
            bg=E.AZUL2, fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B,
            relief="flat", bd=0, cursor="hand2", padx=12, pady=4,
            command=self._volver_marcas)

        # Estilo
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("MPS.Treeview", background=E.BLANCO,
                    fieldbackground=E.BLANCO, foreground=E.TEXTO,
                    rowheight=24, font=E.F_NORMAL)
        s.configure("MPS.Treeview.Heading", background=E.AZUL,
                    foreground=E.TEXTO_BLANCO, font=E.F_NORMAL_B,
                    relief="flat", padding=(4, 6))
        s.map("MPS.Treeview.Heading", background=[("active", E.AZUL2)])
        s.map("MPS.Treeview",
              background=[("selected", E.AZUL2)],
              foreground=[("selected", E.TEXTO_BLANCO)])
        s.configure("MPS.Horizontal.TProgressbar",
                    troughcolor=E.FILA_IMPAR, background=E.AZUL)

        # Tabla de marcas
        self.marco_marcas = tk.Frame(self.cont, bg=E.BORDE)
        ids_m = [c[0] for c in COLS_MARCA]
        self.tree_marcas = ttk.Treeview(
            self.marco_marcas, columns=ids_m, show="headings",
            style="MPS.Treeview", selectmode="browse")
        for cid, titulo, ancho, anchor in COLS_MARCA:
            self.tree_marcas.heading(
                cid, text=titulo,
                command=lambda c=cid: self._ordenar_marcas(c))
            self.tree_marcas.column(cid, width=ancho, anchor=anchor,
                                    stretch=(cid == "marca"))
        self.tree_marcas.tag_configure("alerta", background=TINTE_ROJO)
        self.tree_marcas.tag_configure("par",    background=E.FILA_PAR)
        self.tree_marcas.tag_configure("impar",  background=E.FILA_IMPAR)
        self.tree_marcas.bind("<Double-1>", self._abrir_marca)
        vsb_m = ttk.Scrollbar(self.marco_marcas, orient="vertical",
                               command=self.tree_marcas.yview)
        self.tree_marcas.configure(yscrollcommand=vsb_m.set)
        self.tree_marcas.grid(row=0, column=0, sticky="nsew")
        vsb_m.grid(row=0, column=1, sticky="ns")
        self.marco_marcas.rowconfigure(0, weight=1)
        self.marco_marcas.columnconfigure(0, weight=1)

        self.lbl_hint = tk.Label(
            self.cont,
            text="Doble clic en una marca para ver sus alertas",
            bg=E.FONDO, fg=E.TEXTO_TENUE, font=E.F_PEQUENA)

        # Tabla de productos
        self.marco_tabla = tk.Frame(self.cont, bg=E.BORDE)
        ids_p = [c[0] for c in self.COLUMNAS]
        self.tree = ttk.Treeview(
            self.marco_tabla, columns=ids_p, show="headings",
            style="MPS.Treeview", selectmode="browse")
        for cid, t, w, anchor in self.COLUMNAS:
            self.tree.heading(cid, text=t)
            self.tree.column(cid, width=w, anchor=anchor, stretch=False)
        self.tree.tag_configure("rojo",  background=TINTE_ROJO)
        self.tree.tag_configure("verde", background=TINTE_VERDE)
        vsb = ttk.Scrollbar(self.marco_tabla, orient="vertical",
                             command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.marco_tabla.rowconfigure(0, weight=1)
        self.marco_tabla.columnconfigure(0, weight=1)

        self._construir_overlay()
        self._mostrar_vista_marcas()

    # ------------------------------------------------------------------
    # NAVEGACION
    # ------------------------------------------------------------------
    def _mostrar_vista_marcas(self):
        self._vista = "marcas"
        self._marca_activa = None
        self.barra_busqueda.pack_forget()
        self.btn_volver.pack_forget()
        self.marco_tabla.pack_forget()
        self.lbl_nav.config(text="Resumen por marca")
        self.marco_marcas.pack(fill="both", expand=True, pady=(4, 0))
        self.lbl_hint.pack(anchor="w", pady=(4, 0))
        self._pintar_marcas()

    def _abrir_marca(self, event=None):
        item = self.tree_marcas.identify_row(event.y)
        if not item:
            return
        idx = self.tree_marcas.index(item)
        if not (0 <= idx < len(self._resumen_filas)):
            return
        self._mostrar_vista_productos(self._resumen_filas[idx]["marca"])

    def _mostrar_vista_productos(self, marca=None):
        self._vista = "productos"
        self._marca_activa = marca
        self.marco_marcas.pack_forget()
        self.lbl_hint.pack_forget()
        if marca:
            self.lbl_nav.config(text="Marca: " + marca)
            self.btn_volver.pack(side="left", padx=(12, 0))
        else:
            self.lbl_nav.config(text="Todas las marcas")
            self.btn_volver.pack_forget()
        self.barra_busqueda.pack(fill="x", pady=(6, 6))
        self.marco_tabla.pack(fill="both", expand=True)
        self._pintar()

    def _volver_marcas(self):
        self.var_busqueda.set("")
        self._mostrar_vista_marcas()

    # ------------------------------------------------------------------
    # TABLA MARCAS
    # ------------------------------------------------------------------
    def _pintar_marcas(self):
        umbral = PY.leer_umbral()
        datos = _resumen_marcas(self.filas, self._marca_por_codigo, umbral)
        col = self._orden_marca_col
        num = col in ("alertas", "producir", "stock_bajo",
                      "ambos", "por_producir")
        datos = sorted(
            datos,
            key=lambda d: (d.get(col) is None,
                           d.get(col, 0) if num
                           else str(d.get(col, "")).lower()),
            reverse=not self._orden_marca_asc)
        self._resumen_filas = datos
        total = sum(d["alertas"] for d in datos)
        try:
            self.lbl_total.config(text="{} alertas".format(total))
            self.tree_marcas.delete(*self.tree_marcas.get_children())
            for i, d in enumerate(datos):
                tag = "alerta" if d["por_producir"] > 0 else (
                    "par" if i % 2 == 0 else "impar")
                self.tree_marcas.insert("", "end", tags=(tag,), values=(
                    d["marca"], _miles(d["alertas"]),
                    _miles(d["producir"]), _miles(d["stock_bajo"]),
                    _miles(d["ambos"]), _miles(d["por_producir"])))
        except tk.TclError:
            pass

    def _ordenar_marcas(self, col):
        if self._orden_marca_col == col:
            self._orden_marca_asc = not self._orden_marca_asc
        else:
            self._orden_marca_col = col
            self._orden_marca_asc = False
        self._pintar_marcas()

    # ------------------------------------------------------------------
    # OVERLAY
    # ------------------------------------------------------------------
    def _construir_overlay(self):
        self.overlay = tk.Frame(self.cont, bg=E.FONDO)
        t = tk.Frame(self.overlay, bg=E.BLANCO,
                     highlightbackground=E.BORDE_SUAVE, highlightthickness=1)
        t.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(t, text="Cargando alertas", bg=E.BLANCO, fg=E.TEXTO,
                 font=(E.FUENTE, 16, "bold")).pack(padx=48, pady=(28, 10))
        self.ov_bar = ttk.Progressbar(
            t, length=360, maximum=100, mode="determinate",
            style="MPS.Horizontal.TProgressbar")
        self.ov_bar.pack(padx=48, pady=(0, 28))

    def _mostrar_overlay(self):
        self.overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self.overlay.lift()

    def _ocultar_overlay(self):
        try:
            self.overlay.place_forget()
        except tk.TclError:
            pass

    def _on_prog(self, pct, msg):
        if self._vivo:
            try:
                if self.overlay.winfo_ismapped():
                    self.ov_bar["value"] = pct
            except tk.TclError:
                pass

    def _on_data(self, info, manual, resumen):
        if self._vivo and info.get("ok"):
            self._ocultar_overlay()
            self._recalcular()

    # ------------------------------------------------------------------
    def _guardar_umbral(self):
        try:
            n = int(self.var_umbral.get())
        except (ValueError, tk.TclError):
            messagebox.showwarning("Umbral", "El umbral debe ser un numero.")
            return
        n = PY.guardar_umbral(n)
        self.var_umbral.set(n)
        self._recalcular()
        messagebox.showinfo("Umbral", "Umbral guardado en {}.".format(n))

    def _recalcular(self):
        if not self._vivo:
            return
        info = store.obtener() or {}
        self.filas = PY.pocas_unidades(info, PY.leer_meses(), PY.leer_umbral())
        # Mapa codigo -> marca desde filas de inventario
        self._marca_por_codigo = {}
        for fila_inv in info.get("filas", []):
            cod = fila_inv.get("codigo")
            if cod and fila_inv.get("marca"):
                self._marca_por_codigo[cod] = fila_inv["marca"]
        if self._vista == "marcas":
            self._pintar_marcas()
        else:
            self._pintar()

    def _pintar(self):
        umbral = PY.leer_umbral()
        t = self.var_busqueda.get().strip().lower()
        filas = self.filas
        if self._marca_activa:
            filas = [f for f in filas
                     if (self._marca_por_codigo.get(f["codigo"]) or
                         "(Sin marca)") == self._marca_activa]
        try:
            self.tree.delete(*self.tree.get_children())
        except tk.TclError:
            return
        n = 0
        for f in filas:
            if t and t not in (str(f["codigo"]) + " " + f["nombre"] + " " +
                               str(f.get("referencia", ""))).lower():
                continue
            producir = f["producir"]
            if producir > 0 and f["stock"] <= umbral:
                motivo = "Producir y stock bajo"
            elif producir > 0:
                motivo = "Hay que producir"
            else:
                motivo = "Stock bajo"
            tag = "rojo" if producir > 0 else "verde"
            self.tree.insert("", "end", tags=(tag,), values=(
                f["codigo"], f["nombre"], f.get("referencia", ""),
                _miles(f["vendido"]), _miles(f["stock"]),
                _miles(f["en_produccion"]), _miles(producir), motivo))
            n += 1
        try:
            self.lbl_total.config(text="{} alertas".format(n))
        except tk.TclError:
            pass

    def detener(self):
        self._vivo = False
        store.desuscribir(self._on_data)
        store.desuscribir_progreso(self._on_prog)
