# -*- coding: utf-8 -*-
"""
MPS REPORTS - Modulo Proyeccion (Fase 8 + vista por marca)
Vista inicial: resumen por marca (por producir, faltante, productos).
Doble clic -> productos de esa marca.
"""

import tkinter as tk
from tkinter import ttk

import estilo as E
import proyeccion_datos as PY
from inventario_store import store

LEYENDA = PY.LEYENDA
TINTE_ROJO   = "#FBE4E4"
TINTE_VERDE  = "#E3F4E8"

COLS_MARCA = [
    ("marca",        "Marca",                   220, "w"),
    ("productos",    "Productos",                 90, "e"),
    ("con_faltante", "Con faltante",              90, "e"),
    ("vendido",      "Vendido (N meses)",        130, "e"),
    ("stock",        "Stock bodega",             120, "e"),
    ("en_prod",      "En produccion",            120, "e"),
    ("por_producir", "Por producir",             120, "e"),
]


def _miles(v):
    try:
        return "{:,.0f}".format(float(v or 0)).replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def _resumen_marcas(filas, marca_por_codigo):
    marcas = {}
    for f in filas:
        m = marca_por_codigo.get(f["codigo"]) or "(Sin marca)"
        if m not in marcas:
            marcas[m] = {"productos": 0, "con_faltante": 0,
                         "vendido": 0.0, "stock": 0.0,
                         "en_prod": 0.0, "por_producir": 0.0}
        d = marcas[m]
        d["productos"]    += 1
        d["vendido"]      += f["vendido"]
        d["stock"]        += f["stock"]
        d["en_prod"]      += f["en_produccion"]
        d["por_producir"] += f["producir"]
        if f["producir"] > 0:
            d["con_faltante"] += 1

    res = []
    for m, d in sorted(marcas.items()):
        res.append({"marca": m, **d})
    return res


class ModuloProyeccion:
    COLUMNAS = [
        ("codigo",       "Codigo",               110, "w"),
        ("nombre",       "Nombre",               270, "w"),
        ("referencia",   "Referencia",           110, "w"),
        ("vendido",      "Vendido (N meses)",    140, "e"),
        ("stock",        "Stock bodega",         110, "e"),
        ("en_produccion","En produccion",        120, "e"),
        ("producir",     "Faltante por producir",160, "e"),
    ]

    def __init__(self, parent, rol="CONSULTA", indicador_cb=None):
        self.parent = parent
        self.rol = rol
        self.indicador_cb = indicador_cb or (lambda *a, **k: None)
        self._vivo = True
        self.filas_base  = []
        self.filas_vista = []
        self._marca_por_codigo = {}
        self._resumen_filas    = []
        self._vista            = "marcas"
        self._marca_activa     = None
        self.orden_col = "faltante"
        self.orden_asc = False
        self._orden_marca_col = "por_producir"
        self._orden_marca_asc = False

        self._construir()
        store.suscribir(self._on_data)
        store.suscribir_progreso(self._on_prog)
        if store.hay_datos():
            self._recalcular()
        else:
            self._mostrar_overlay()
            pct, msg = getattr(store, "ultimo_progreso", (0, ""))
            self._actualizar_overlay(pct or 3, msg or "Cargando...")
            store.precargar()

    # ------------------------------------------------------------------
    def _construir(self):
        self.cont = tk.Frame(self.parent, bg=E.FONDO)
        self.cont.pack(fill="both", expand=True, padx=16, pady=14)

        # Controles superiores
        top = tk.Frame(self.cont, bg=E.FONDO)
        top.pack(fill="x")
        tk.Label(top, text="Meses a proyectar:", bg=E.FONDO,
                 fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(side="left")
        self.var_meses = tk.IntVar(value=PY.leer_meses())
        self.spin = tk.Spinbox(top, from_=1, to=12, width=4,
                               textvariable=self.var_meses, font=E.F_NORMAL,
                               relief="solid", bd=1, justify="center",
                               command=self._cambiar_meses)
        self.spin.pack(side="left", padx=(6, 4))
        self.spin.bind("<Return>",   lambda e: self._cambiar_meses())
        self.spin.bind("<FocusOut>", lambda e: self._cambiar_meses())
        tk.Label(top, text="(1 a 12, se guarda para la proxima vez)",
                 bg=E.FONDO, fg=E.TEXTO_TENUE,
                 font=E.F_PEQUENA).pack(side="left", padx=(0, 16))
        self.lbl_contador = tk.Label(top, text="", bg=E.FONDO,
                                     fg=E.TEXTO_SUB, font=E.F_NORMAL_B)
        self.lbl_contador.pack(side="right")

        # KPIs
        fila_kpi = tk.Frame(self.cont, bg=E.FONDO)
        fila_kpi.pack(fill="x", pady=(12, 0))
        self.kpi = {}
        for i, (clave, titulo, color) in enumerate([
                ("producir_tot", "Unidades por producir",  E.ROJO),
                ("productos",    "Productos con faltante", E.NARANJA),
                ("analizados",   "Productos analizados",   E.AZUL)]):
            self.kpi[clave] = self._tarjeta(fila_kpi, titulo, color)
            self.kpi[clave]["marco"].grid(row=0, column=i, sticky="nsew",
                                          padx=(0 if i == 0 else 12, 0))
            fila_kpi.columnconfigure(i, weight=1)

        tk.Label(self.cont, text=LEYENDA, bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=(E.FUENTE, 10, "italic")).pack(anchor="w", pady=(10, 0))

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

        # Busqueda (solo en vista productos)
        self.barra_filtros = tk.Frame(self.cont, bg=E.FONDO)
        tk.Label(self.barra_filtros, text="Buscar:", bg=E.FONDO,
                 fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(side="left")
        self.var_busqueda = tk.StringVar()
        ent = tk.Entry(self.barra_filtros, textvariable=self.var_busqueda,
                       width=28, font=E.F_NORMAL, relief="solid", bd=1)
        ent.pack(side="left", padx=(6, 0))
        ent.bind("<KeyRelease>", lambda e: self._aplicar())

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
        self.marco_marcas = tk.Frame(self.cont, bg=E.BORDE, bd=0)
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
        self.tree_marcas.tag_configure("par",   background=E.FILA_PAR)
        self.tree_marcas.tag_configure("impar", background=E.FILA_IMPAR)
        self.tree_marcas.tag_configure("alerta", background=TINTE_ROJO)
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
            text="Doble clic en una marca para ver sus productos",
            bg=E.FONDO, fg=E.TEXTO_TENUE, font=E.F_PEQUENA)

        # Tabla de productos
        self.marco_tabla = tk.Frame(self.cont, bg=E.BORDE)
        ids_p = [c[0] for c in self.COLUMNAS]
        self.tree = ttk.Treeview(
            self.marco_tabla, columns=ids_p, show="headings",
            style="MPS.Treeview", selectmode="browse")
        for cid, t, w, anchor in self.COLUMNAS:
            self.tree.heading(cid, text=t,
                              command=lambda c=cid: self._ordenar(c))
            self.tree.column(cid, width=w, anchor=anchor, stretch=False)
        self.tree.tag_configure("rojo",  background=TINTE_ROJO)
        self.tree.tag_configure("verde", background=TINTE_VERDE)
        self.tree.bind("<Double-1>", self._detalle)
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
        self.barra_filtros.pack_forget()
        self.btn_volver.pack_forget()
        self.marco_tabla.pack_forget()
        self.lbl_nav.config(text="Resumen por marca")
        self.marco_marcas.pack(fill="both", expand=True, pady=(4, 0))
        self.lbl_hint.pack(anchor="w", pady=(4, 0))
        self._pintar_marcas()
        self._kpis()

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
            self.lbl_nav.config(text="Todos los productos")
            self.btn_volver.pack_forget()
        self.barra_filtros.pack(fill="x", pady=(6, 6))
        self.marco_tabla.pack(fill="both", expand=True)
        self._aplicar()

    def _volver_marcas(self):
        self.var_busqueda.set("")
        self._mostrar_vista_marcas()

    # ------------------------------------------------------------------
    # TABLA MARCAS
    # ------------------------------------------------------------------
    def _pintar_marcas(self):
        datos = _resumen_marcas(self.filas_base, self._marca_por_codigo)
        col = self._orden_marca_col
        num = col in ("productos", "con_faltante", "vendido",
                      "stock", "en_prod", "por_producir")
        datos = sorted(
            datos,
            key=lambda d: (d.get(col) is None,
                           d.get(col, 0) if num
                           else str(d.get(col, "")).lower()),
            reverse=not self._orden_marca_asc)
        self._resumen_filas = datos
        try:
            self.tree_marcas.delete(*self.tree_marcas.get_children())
            for i, d in enumerate(datos):
                tag = "alerta" if d["por_producir"] > 0 else (
                    "par" if i % 2 == 0 else "impar")
                self.tree_marcas.insert("", "end", tags=(tag,), values=(
                    d["marca"], _miles(d["productos"]),
                    _miles(d["con_faltante"]), _miles(d["vendido"]),
                    _miles(d["stock"]), _miles(d["en_prod"]),
                    _miles(d["por_producir"])))
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
    def _tarjeta(self, padre, titulo, color):
        marco = tk.Frame(padre, bg=E.BLANCO,
                         highlightbackground=E.BORDE_SUAVE,
                         highlightthickness=1)
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
        tk.Label(tarjeta, text="Cargando", bg=E.BLANCO, fg=E.TEXTO,
                 font=(E.FUENTE, 16, "bold")).pack(padx=48, pady=(28, 4))
        self.ov_bar = ttk.Progressbar(
            tarjeta, length=360, maximum=100, mode="determinate",
            style="MPS.Horizontal.TProgressbar")
        self.ov_bar.pack(padx=48, pady=(10, 6))
        self.ov_pct = tk.Label(tarjeta, text="0%", bg=E.BLANCO, fg=E.AZUL,
                               font=E.F_NORMAL_B)
        self.ov_pct.pack(pady=(0, 28))

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

    def _actualizar_overlay(self, pct, msg=None):
        try:
            self.ov_bar["value"] = pct
            self.ov_pct.config(text="{}%".format(int(pct)))
        except tk.TclError:
            pass

    def _on_prog(self, pct, msg):
        if self._vivo and self._overlay_visible():
            self._actualizar_overlay(pct, msg)

    def _on_data(self, info, manual, resumen):
        if not self._vivo:
            return
        if info.get("ok"):
            self._ocultar_overlay()
            self._recalcular()

    # ------------------------------------------------------------------
    def _cambiar_meses(self):
        try:
            n = int(self.var_meses.get())
        except (ValueError, tk.TclError):
            n = PY.leer_meses()
        n = PY.guardar_meses(n)
        self.var_meses.set(n)
        self._recalcular()

    def _recalcular(self):
        if not self._vivo:
            return
        info = store.obtener() or {}
        self.filas_base = PY.calcular(info, PY.leer_meses())
        # Construir mapa codigo -> marca desde filas de inventario
        self._marca_por_codigo = {}
        for fila_inv in info.get("filas", []):
            cod = fila_inv.get("codigo")
            if cod and fila_inv.get("marca"):
                self._marca_por_codigo[cod] = fila_inv["marca"]
        if self._vista == "marcas":
            self._mostrar_vista_marcas()
        else:
            self._aplicar()

    def _aplicar(self):
        if not self._vivo:
            return
        filas_base = self.filas_base
        if self._marca_activa:
            filas_base = [
                f for f in filas_base
                if (self._marca_por_codigo.get(f["codigo"]) or
                    "(Sin marca)") == self._marca_activa]
        filas = PY.filtrar(filas_base, self.var_busqueda.get())
        filas = self._ordenar_filas(filas)
        self.filas_vista = filas
        self._pintar()
        self._kpis()
        try:
            self.lbl_contador.config(
                text="{} productos".format(len(filas)))
        except tk.TclError:
            pass

    def _ordenar_filas(self, filas):
        col = self.orden_col
        num = col in ("vendido", "stock", "en_produccion",
                      "producir", "faltante")
        if col == "producir":
            col = "faltante"
        return sorted(
            filas,
            key=(lambda f: f.get(col, 0)) if num
            else (lambda f: str(f.get(col, "")).lower()),
            reverse=not self.orden_asc)

    def _celda(self, f, cid):
        if cid in ("vendido", "stock", "en_produccion", "producir"):
            return _miles(f.get(cid))
        return f.get(cid, "")

    def _pintar(self):
        try:
            self.tree.delete(*self.tree.get_children())
            for f in self.filas_vista:
                tag = "rojo" if f["producir"] > 0 else "verde"
                vals = [self._celda(f, cid) for cid, _, _, _ in self.COLUMNAS]
                self.tree.insert("", "end", values=vals, tags=(tag,))
        except tk.TclError:
            pass

    def _kpis(self):
        filas = self.filas_base if self._vista == "marcas" else self.filas_vista
        prod_tot = sum(f["producir"] for f in filas)
        con_falt = sum(1 for f in filas if f["producir"] > 0)
        try:
            self.kpi["producir_tot"]["valor"].config(text=_miles(prod_tot))
            self.kpi["productos"]["valor"].config(text=_miles(con_falt))
            self.kpi["analizados"]["valor"].config(text=_miles(len(filas)))
        except tk.TclError:
            pass

    def _ordenar(self, col):
        if self.orden_col == col:
            self.orden_asc = not self.orden_asc
        else:
            self.orden_col = col
            self.orden_asc = False
        self._aplicar()

    # ------------------------------------------------------------------
    # DETALLE
    # ------------------------------------------------------------------
    def _detalle(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        if not (0 <= idx < len(self.filas_vista)):
            return
        f = self.filas_vista[idx]
        dlg = tk.Toplevel(self.parent, bg=E.FONDO)
        dlg.title("Detalle de proyeccion")
        dlg.resizable(False, False)
        hd = tk.Frame(dlg, bg=E.AZUL)
        hd.pack(fill="x")
        tk.Label(hd, text=f["nombre"] or "(sin nombre)", bg=E.AZUL,
                 fg=E.TEXTO_BLANCO, font=(E.FUENTE, 15, "bold")).pack(
                     anchor="w", padx=18, pady=(12, 0))
        tk.Label(hd, text="Codigo: " + f["codigo"], bg=E.AZUL,
                 fg="#CFE4F5", font=(E.FUENTE, 10)).pack(
                     anchor="w", padx=18, pady=(0, 12))
        tk.Frame(dlg, bg=E.ROJO, height=3).pack(fill="x")
        cuerpo = tk.Frame(dlg, bg=E.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=18, pady=16)
        if f["producir"] > 0:
            concl = "Hay que producir {} unidades.".format(_miles(f["producir"]))
            color = E.ROJO
        else:
            concl = "Suficiente. Sobran {} unidades.".format(
                _miles(f["sobrante"]))
            color = E.VERDE
        for k, v in [
            ("Vendido (ultimos {} meses)".format(PY.leer_meses()),
             _miles(f["vendido"])),
            ("Stock en bodega",                  _miles(f["stock"])),
            ("En produccion",                    _miles(f["en_produccion"])),
            ("Faltante (vendido - stock - prod)", _miles(f["faltante"])),
        ]:
            r = tk.Frame(cuerpo, bg=E.FONDO)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=k + ":", bg=E.FONDO, fg=E.TEXTO_SUB,
                     font=E.F_NORMAL, width=34, anchor="w").pack(side="left")
            tk.Label(r, text=v, bg=E.FONDO, fg=E.TEXTO,
                     font=E.F_NORMAL_B).pack(side="left")
        tk.Label(cuerpo, text=concl, bg=E.FONDO, fg=color,
                 font=E.F_NORMAL_B).pack(anchor="w", pady=(10, 0))
        tk.Label(cuerpo, text=LEYENDA, bg=E.FONDO, fg=E.TEXTO_TENUE,
                 font=(E.FUENTE, 9, "italic")).pack(anchor="w", pady=(8, 0))
        tk.Button(cuerpo, text="Cerrar", bg=E.AZUL, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=22, pady=7, command=dlg.destroy).pack(pady=(14, 0))
        dlg.update_idletasks()
        w = dlg.winfo_width()
        h = dlg.winfo_height()
        dlg.geometry("+{}+{}".format(
            max(0, (dlg.winfo_screenwidth() - w) // 2),
            max(0, (dlg.winfo_screenheight() - h) // 2)))
        try:
            dlg.transient(self.parent.winfo_toplevel())
            dlg.grab_set()
        except tk.TclError:
            pass

    def _set_indicador(self, texto, conectado):
        try:
            self.indicador_cb(texto, conectado)
        except Exception:
            pass

    def detener(self):
        self._vivo = False
        store.desuscribir(self._on_data)
        store.desuscribir_progreso(self._on_prog)
