# -*- coding: utf-8 -*-
"""
MPS REPORTS - Modulo Rentabilidad y Rotacion (Fase 6)
Analisis por producto: rentabilidad (margen sobre precio) y rotacion del
periodo, con clasificaciones oficiales de color, filtros por clasificacion,
KPI de rentabilidad promedio ponderada y conteo por clase.
Calcula desde el almacen compartido; se refresca con el ciclo de 15 min.
"""

import tkinter as tk
from tkinter import ttk

import estilo as E
import rentabilidad_datos as RD
from inventario_store import store

COLUMNAS = [
    ("codigo", "Codigo", 100, "w"),
    ("nombre", "Nombre", 230, "w"),
    ("referencia", "Referencia", 105, "w"),
    ("stock", "Stock", 70, "e"),
    ("costo_unit", "Costo Unitario", 110, "e"),
    ("precio_pub", "Precio Publico", 110, "e"),
    ("rent_pct", "Rentabilidad %", 110, "e"),
    ("rent_clase", "Clasif. Rentab.", 120, "center"),
    ("rotacion", "Rotacion", 85, "e"),
    ("rot_clase", "Clasif. Rotac.", 115, "center"),
]

# Tintes de fila por clasificacion de rentabilidad (fondo claro, texto oscuro)
TINTE_RENT = {
    "EXCELENTE": "#E3F4E8",
    "BUENA": "#E4EEF8",
    "REGULAR": "#FBEFE0",
    "BAJA": "#FBE4E4",
    "N/D": "#F4F5F7",
}
COLOR_CLASE = {
    "EXCELENTE": E.VERDE, "BUENA": E.AZUL, "REGULAR": E.NARANJA, "BAJA": E.ROJO,
    "ALTA": E.VERDE, "MEDIA": E.NARANJA, "N/D": E.TEXTO_TENUE,
}


def _miles(v):
    try:
        return "{:,.0f}".format(float(v or 0)).replace(",", ".")
    except (ValueError, TypeError):
        return "0"


# Opciones del selector "Ordenar por" -> (columna, ascendente)
ORDEN_OPCIONES = {
    "Rentabilidad (mayor)": ("rent_pct", False),
    "Rentabilidad (menor)": ("rent_pct", True),
    "Rotacion (mayor)": ("rotacion", False),
    "Rotacion (menor)": ("rotacion", True),
}


def _money(v):
    return "$ " + _miles(v)


class ModuloRentabilidad:
    def __init__(self, parent, rol="CONSULTA", indicador_cb=None):
        self.parent = parent
        self.rol = rol
        self.indicador_cb = indicador_cb or (lambda *a, **k: None)

        self.filas_base = []
        self.filas_vista = []
        self.orden_col = "rent_pct"
        self.orden_asc = False
        self._vivo = True

        self._construir()
        store.suscribir(self._on_data)
        store.suscribir_progreso(self._on_prog)

        if store.hay_datos():
            self._recalcular()
        else:
            self._mostrar_overlay()
            pct, msg = getattr(store, "ultimo_progreso", (0, ""))
            self._actualizar_overlay(pct or 3, msg or "Cargando analisis...")
            self._set_indicador(
                "Cargando analisis... {}%".format(int(pct or 0)), True)
            store.precargar()

    # ------------------------------------------------------------------
    def _construir(self):
        self.cont = tk.Frame(self.parent, bg=E.FONDO)
        self.cont.pack(fill="both", expand=True, padx=16, pady=14)

        # ----- Periodo + filtros -----
        top = tk.Frame(self.cont, bg=E.FONDO)
        top.pack(fill="x")
        tk.Label(top, text="Periodo:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_periodo = tk.StringVar(value=RD.VD.PERIODO_DEFECTO)
        cmb = ttk.Combobox(top, textvariable=self.var_periodo, state="readonly",
                           width=16, font=E.F_NORMAL, values=RD.VD.PERIODOS)
        cmb.pack(side="left", padx=(6, 14))
        cmb.bind("<<ComboboxSelected>>", lambda e: self._recalcular())

        tk.Label(top, text="Rentabilidad:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_rent = tk.StringVar(value="Todas")
        cr = ttk.Combobox(top, textvariable=self.var_rent, state="readonly",
                          width=12, font=E.F_NORMAL,
                          values=["Todas"] + RD.CLASES_RENT)
        cr.pack(side="left", padx=(6, 14))
        cr.bind("<<ComboboxSelected>>", lambda e: self._aplicar())

        tk.Label(top, text="Rotacion:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_rot = tk.StringVar(value="Todas")
        cx = ttk.Combobox(top, textvariable=self.var_rot, state="readonly",
                          width=10, font=E.F_NORMAL,
                          values=["Todas"] + RD.CLASES_ROT)
        cx.pack(side="left", padx=(6, 14))
        cx.bind("<<ComboboxSelected>>", lambda e: self._aplicar())

        tk.Label(top, text="Marca:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_marca = tk.StringVar(value="Todas")
        self.cmb_marca = ttk.Combobox(top, textvariable=self.var_marca,
                                      state="readonly", width=22,
                                      font=E.F_NORMAL, values=["Todas"])
        self.cmb_marca.pack(side="left", padx=(6, 14))
        self.cmb_marca.bind("<<ComboboxSelected>>", lambda e: self._aplicar())

        tk.Label(top, text="Ordenar por:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_orden = tk.StringVar(value="Rentabilidad (mayor)")
        co = ttk.Combobox(top, textvariable=self.var_orden, state="readonly",
                          width=20, font=E.F_NORMAL,
                          values=list(ORDEN_OPCIONES.keys()))
        co.pack(side="left", padx=(6, 14))
        co.bind("<<ComboboxSelected>>", lambda e: self._cambiar_orden())

        self.lbl_rango = tk.Label(top, text="", bg=E.FONDO, fg=E.TEXTO_TENUE,
                                  font=E.F_PEQUENA)
        self.lbl_rango.pack(side="left")

        # ----- KPI -----
        fila_kpi = tk.Frame(self.cont, bg=E.FONDO)
        fila_kpi.pack(fill="x", pady=(12, 0))
        self.kpi = {}
        d1 = self._tarjeta_kpi(fila_kpi, "Rentabilidad promedio", E.AZUL)
        d1["marco"].grid(row=0, column=0, sticky="nsew")
        self.kpi["rent"] = d1
        d2 = self._tarjeta_kpi(fila_kpi, "Productos analizados", E.VERDE)
        d2["marco"].grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self.kpi["total"] = d2
        fila_kpi.columnconfigure(0, weight=1)
        fila_kpi.columnconfigure(1, weight=1)

        # Conteo por clasificacion (chips de color)
        chips = tk.Frame(fila_kpi, bg=E.FONDO)
        chips.grid(row=0, column=2, sticky="nsew", padx=(12, 0))
        fila_kpi.columnconfigure(2, weight=2)
        self.chip = {}
        for i, clase in enumerate(RD.CLASES_RENT):
            c = tk.Frame(chips, bg=E.BLANCO, highlightbackground=E.BORDE_SUAVE,
                         highlightthickness=1)
            c.grid(row=i // 2, column=i % 2, sticky="nsew", padx=4, pady=4)
            chips.columnconfigure(i % 2, weight=1)
            tk.Frame(c, bg=COLOR_CLASE[clase], width=6).pack(side="left",
                                                             fill="y")
            num = tk.Label(c, text="0", bg=E.BLANCO, fg=E.TEXTO,
                           font=E.F_NORMAL_B, width=4, anchor="e")
            num.pack(side="left", padx=(8, 4), pady=6)
            tk.Label(c, text=clase, bg=E.BLANCO, fg=E.TEXTO_SUB,
                     font=E.F_PEQUENA).pack(side="left", padx=(0, 10))
            self.chip[clase] = num

        # ----- Busqueda -----
        barra = tk.Frame(self.cont, bg=E.FONDO)
        barra.pack(fill="x", pady=(14, 8))
        tk.Label(barra, text="Buscar:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_busqueda = tk.StringVar()
        ent = tk.Entry(barra, textvariable=self.var_busqueda, width=34,
                       font=E.F_NORMAL, relief="solid", bd=1)
        ent.pack(side="left", padx=(6, 16))
        ent.bind("<KeyRelease>", lambda e: self._aplicar())
        self.lbl_contador = tk.Label(barra, text="", bg=E.FONDO,
                                     fg=E.TEXTO_SUB, font=E.F_NORMAL_B)
        self.lbl_contador.pack(side="right")

        # ----- Tabla -----
        marco = tk.Frame(self.cont, bg=E.BORDE, bd=0)
        marco.pack(fill="both", expand=True)
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
        estilo.map("MPS.Treeview.Heading", background=[("active", E.AZUL2)])
        estilo.configure("MPS.Horizontal.TProgressbar",
                         troughcolor=E.FILA_IMPAR, bordercolor=E.BORDE_SUAVE,
                         background=E.AZUL, lightcolor=E.AZUL, darkcolor=E.AZUL)

        ids = [c[0] for c in COLUMNAS]
        self.tree = ttk.Treeview(marco, columns=ids, show="headings",
                                 style="MPS.Treeview", selectmode="browse")
        for cid, titulo, ancho, anchor in COLUMNAS:
            self.tree.heading(cid, text=titulo,
                              command=lambda c=cid: self._ordenar(c))
            self.tree.column(cid, width=ancho, anchor=anchor,
                             stretch=(cid == "nombre"))
        for clase, color in TINTE_RENT.items():
            self.tree.tag_configure("rent_" + clase, background=color)
        self.tree.bind("<Double-1>", self._abrir_detalle)

        vsb = ttk.Scrollbar(marco, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(marco, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)

        self._construir_overlay()

    def _tarjeta_kpi(self, padre, titulo, color):
        marco = tk.Frame(padre, bg=E.BLANCO, highlightbackground=E.BORDE_SUAVE,
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

    # ----- Overlay -----
    def _construir_overlay(self):
        self.overlay = tk.Frame(self.cont, bg=E.FONDO)
        tarjeta = tk.Frame(self.overlay, bg=E.BLANCO,
                           highlightbackground=E.BORDE_SUAVE,
                           highlightthickness=1)
        tarjeta.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(tarjeta, text="Cargando analisis", bg=E.BLANCO, fg=E.TEXTO,
                 font=(E.FUENTE, 16, "bold")).pack(padx=48, pady=(28, 4))
        self.ov_msg = tk.Label(tarjeta, text="Conectando con Business...",
                               bg=E.BLANCO, fg=E.TEXTO_SUB, font=E.F_NORMAL)
        self.ov_msg.pack(padx=48)
        self.ov_bar = ttk.Progressbar(tarjeta, length=380, maximum=100,
                                      mode="determinate",
                                      style="MPS.Horizontal.TProgressbar")
        self.ov_bar.pack(padx=48, pady=(14, 6))
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

    def _actualizar_overlay(self, pct, msg):
        try:
            self.ov_bar["value"] = pct
            self.ov_msg.config(text=msg)
            self.ov_pct.config(text="{}%".format(int(pct)))
        except tk.TclError:
            pass

    def _on_prog(self, pct, msg):
        if not self._vivo:
            return
        self._set_indicador("Cargando analisis... {}%".format(int(pct)), True)
        if self._overlay_visible():
            self._actualizar_overlay(pct, msg)

    def _set_indicador(self, texto, conectado):
        try:
            self.indicador_cb(texto, conectado)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _on_data(self, info, manual, resumen):
        if not self._vivo:
            return
        if info.get("ok"):
            self._ocultar_overlay()
            self._recalcular()
            if store.ultima_carga is not None:
                ts = store.ultima_carga.strftime("%d/%m/%Y %H:%M")
                self._set_indicador(
                    "Actualizado: {} - automatico cada 15 min".format(ts), True)
        elif not store.hay_datos():
            self._actualizar_overlay(100, "Sin conexion con Business")
            self._set_indicador("Sin conexion (se reintentara)", False)

    def _recalcular(self):
        if not self._vivo:
            return
        info = store.obtener() or {}
        filas, desde, hasta = RD.construir_filas(info, self.var_periodo.get())
        self.filas_base = filas
        # Llenar marcas disponibles
        try:
            marcas = ["Todas"] + RD.marcas_disponibles(filas)
            actual = self.var_marca.get()
            self.cmb_marca.config(values=marcas)
            if actual not in marcas:
                self.var_marca.set("Todas")
        except tk.TclError:
            pass
        try:
            self.lbl_rango.config(text="rotacion del {} al {}".format(
                _fecha(desde), _fecha(hasta)))
        except tk.TclError:
            pass
        self._aplicar()

    def _cambiar_orden(self):
        col, asc = ORDEN_OPCIONES.get(self.var_orden.get(), ("rent_pct", False))
        self.orden_col = col
        self.orden_asc = asc
        flecha = "  v" if self.orden_asc else "  ^"
        for cid, titulo, _, _ in COLUMNAS:
            try:
                self.tree.heading(cid, text=titulo +
                                  (flecha if cid == col else ""))
            except tk.TclError:
                pass
        self._aplicar()

    def _aplicar(self):
        if not self._vivo:
            return
        filas = RD.filtrar(self.filas_base, self.var_busqueda.get(),
                           self.var_rent.get(), self.var_rot.get(),
                           self.var_marca.get())
        if self.orden_col:
            filas = RD.ordenar(filas, self.orden_col, self.orden_asc)
        self.filas_vista = filas
        self._pintar()
        self._actualizar_kpis()
        try:
            self.lbl_contador.config(
                text="{} productos".format(len(self.filas_vista)))
        except tk.TclError:
            pass

    def _valor_celda(self, fila, cid):
        v = fila.get(cid)
        if cid in ("costo_unit", "precio_pub"):
            return _money(v)
        if cid == "stock":
            return _miles(v)
        if cid == "rent_pct":
            return "N/D" if v is None else "{:.1f}%".format(v)
        if cid == "rotacion":
            return "-" if v is None else "{:.2f}".format(v)
        return v if v not in (None, "") else ""

    def _pintar(self):
        ids = [c[0] for c in COLUMNAS]
        try:
            self.tree.delete(*self.tree.get_children())
            for fila in self.filas_vista:
                valores = [self._valor_celda(fila, cid) for cid in ids]
                self.tree.insert("", "end", values=valores,
                                 tags=("rent_" + fila["rent_clase"],))
        except tk.TclError:
            pass

    def _actualizar_kpis(self):
        k = RD.kpis(self.filas_vista)
        prom = k["rent_prom"]
        try:
            self.kpi["rent"]["valor"].config(
                text="N/D" if prom is None else "{:.1f}%".format(prom))
            self.kpi["total"]["valor"].config(text=_miles(k["total"]))
            for clase in RD.CLASES_RENT:
                self.chip[clase].config(text=str(k["conteo"].get(clase, 0)))
        except tk.TclError:
            pass

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
        self._aplicar()

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
        dlg = tk.Toplevel(self.parent, bg=E.FONDO)
        dlg.title("Analisis del producto")
        dlg.resizable(False, False)
        try:
            dlg.transient(self.parent.winfo_toplevel())
        except tk.TclError:
            pass

        hd = tk.Frame(dlg, bg=E.AZUL)
        hd.pack(fill="x")
        tk.Label(hd, text=fila["nombre"] or "(sin nombre)", bg=E.AZUL,
                 fg=E.TEXTO_BLANCO, font=(E.FUENTE, 15, "bold")).pack(
                     anchor="w", padx=18, pady=(12, 0))
        tk.Label(hd, text="Codigo: " + fila["codigo"], bg=E.AZUL, fg="#CFE4F5",
                 font=(E.FUENTE, 10)).pack(anchor="w", padx=18, pady=(0, 12))
        tk.Frame(dlg, bg=E.ROJO, height=3).pack(fill="x")

        cuerpo = tk.Frame(dlg, bg=E.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=18, pady=16)

        datos = [
            ("Stock", _miles(fila["stock"])),
            ("Costo unitario", _money(fila["costo_unit"])),
            ("Precio publico", _money(fila["precio_pub"])),
        ]
        for k, v in datos:
            r = tk.Frame(cuerpo, bg=E.FONDO)
            r.pack(fill="x", pady=2)
            tk.Label(r, text=k + ":", bg=E.FONDO, fg=E.TEXTO_SUB,
                     font=E.F_NORMAL, width=16, anchor="w").pack(side="left")
            tk.Label(r, text=v, bg=E.FONDO, fg=E.TEXTO,
                     font=E.F_NORMAL_B).pack(side="left")

        # Rentabilidad y rotacion con su color
        for titulo, val, clase in [
            ("Rentabilidad",
             ("N/D" if fila["rent_pct"] is None
              else "{:.1f}%".format(fila["rent_pct"])), fila["rent_clase"]),
            ("Rotacion",
             ("-" if fila["rotacion"] is None
              else "{:.2f}".format(fila["rotacion"])), fila["rot_clase"]),
        ]:
            caja = tk.Frame(cuerpo, bg=TINTE_RENT.get(clase, E.BLANCO),
                            highlightbackground=E.BORDE_SUAVE,
                            highlightthickness=1)
            caja.pack(fill="x", pady=(10, 0))
            tk.Label(caja, text=titulo, bg=caja["bg"], fg=E.TEXTO_SUB,
                     font=E.F_PEQUENA).pack(anchor="w", padx=12, pady=(8, 0))
            linea = tk.Frame(caja, bg=caja["bg"])
            linea.pack(fill="x", padx=12, pady=(0, 10))
            tk.Label(linea, text=val, bg=caja["bg"], fg=E.TEXTO,
                     font=(E.FUENTE, 18, "bold")).pack(side="left")
            tk.Label(linea, text="  " + clase,
                     bg=caja["bg"], fg=COLOR_CLASE.get(clase, E.TEXTO),
                     font=E.F_NORMAL_B).pack(side="left", pady=(6, 0))

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

    # ------------------------------------------------------------------
    def detener(self):
        self._vivo = False
        store.desuscribir(self._on_data)
        store.desuscribir_progreso(self._on_prog)


def _fecha(aaaammdd):
    try:
        y, m, d = aaaammdd.split("-")
        return "{}/{}/{}".format(d, m, y)
    except Exception:
        return aaaammdd


if __name__ == "__main__":
    import os
    import sys
    DIR_UI = os.path.dirname(os.path.abspath(__file__))
    DIR_APP = os.path.dirname(DIR_UI)
    sys.path.insert(0, os.path.join(DIR_APP, "core"))
    sys.path.insert(0, DIR_UI)

    root = tk.Tk()
    root.state("zoomed")
    root.configure(bg=E.FONDO)
    store.iniciar(root)
    store.precargar()
    ModuloRentabilidad(root, rol="ADMINISTRADOR")
    root.mainloop()
