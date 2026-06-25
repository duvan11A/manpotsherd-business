# -*- coding: utf-8 -*-
"""
MPS REPORTS - Modulo Ventas (Fase 5)
Selector de periodo, 3 KPI del periodo, tabla de ventas netas por
producto (unidades, valor, costo, utilidad) con totales al pie,
busqueda en vivo y ordenamiento. Calcula desde el almacen compartido
(mismos movimientos del inventario); se refresca con el ciclo de 15 min.
"""

import tkinter as tk
from tkinter import ttk

import estilo as E
import ventas_datos as VD
from inventario_store import store

COLUMNAS = [
    ("codigo", "Codigo", 100, "w"),
    ("nombre", "Nombre", 250, "w"),
    ("referencia", "Referencia", 110, "w"),
    ("unidades", "Unidades vendidas", 130, "e"),
    ("valor", "Valor vendido", 130, "e"),
    ("costo", "Costo de lo vendido", 150, "e"),
    ("utilidad", "Utilidad", 130, "e"),
]


def _miles(v):
    try:
        return "{:,.0f}".format(float(v or 0)).replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def _money(v):
    return "$ " + _miles(v)


class ModuloVentas:
    def __init__(self, parent, rol="CONSULTA", indicador_cb=None):
        self.parent = parent
        self.rol = rol
        self.indicador_cb = indicador_cb or (lambda *a, **k: None)

        self.filas_periodo = []   # todas las del periodo
        self.filas_vista = []     # filtradas + ordenadas
        self.orden_col = None
        self.orden_asc = True
        self._vivo = True

        self._construir()
        store.suscribir(self._on_data)
        store.suscribir_progreso(self._on_prog)

        if store.hay_datos():
            self._recalcular()
        else:
            self._mostrar_overlay()
            pct, msg = getattr(store, "ultimo_progreso", (0, ""))
            self._actualizar_overlay(pct or 3, msg or "Cargando ventas...")
            self._set_indicador(
                "Cargando ventas... {}%".format(int(pct or 0)), True)
            store.precargar()

    # ------------------------------------------------------------------
    def _construir(self):
        self.cont = tk.Frame(self.parent, bg=E.FONDO)
        self.cont.pack(fill="both", expand=True, padx=16, pady=14)

        # ----- Selector de periodo -----
        top = tk.Frame(self.cont, bg=E.FONDO)
        top.pack(fill="x")
        tk.Label(top, text="Periodo:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_periodo = tk.StringVar(value=VD.PERIODO_DEFECTO)
        self.cmb_periodo = ttk.Combobox(top, textvariable=self.var_periodo,
                                        state="readonly", width=18,
                                        font=E.F_NORMAL, values=VD.PERIODOS)
        self.cmb_periodo.pack(side="left", padx=(6, 14))
        self.cmb_periodo.bind("<<ComboboxSelected>>",
                              lambda e: self._recalcular())
        self.lbl_rango = tk.Label(top, text="", bg=E.FONDO, fg=E.TEXTO_TENUE,
                                  font=E.F_PEQUENA)
        self.lbl_rango.pack(side="left")
        self.lbl_estado = tk.Label(top, text="", bg=E.FONDO, fg=E.TEXTO_SUB,
                                   font=E.F_PEQUENA)
        self.lbl_estado.pack(side="right")

        # ----- KPI del periodo -----
        fila_kpi = tk.Frame(self.cont, bg=E.FONDO)
        fila_kpi.pack(fill="x", pady=(12, 0))
        self.kpi = {}
        defs = [
            ("unidades", "Unidades vendidas", E.AZUL),
            ("valor", "Valor vendido", E.VERDE),
            ("productos", "Productos distintos vendidos", E.AZUL),
        ]
        for i, (clave, titulo, color) in enumerate(defs):
            self.kpi[clave] = self._tarjeta_kpi(fila_kpi, titulo, color)
            self.kpi[clave]["marco"].grid(row=0, column=i, sticky="nsew",
                                          padx=(0 if i == 0 else 12, 0))
            fila_kpi.columnconfigure(i, weight=1)

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
        estilo.map("MPS.Treeview",
                   background=[("selected", E.AZUL2)],
                   foreground=[("selected", E.TEXTO_BLANCO)])

        ids = [c[0] for c in COLUMNAS]
        self.tree = ttk.Treeview(marco, columns=ids, show="headings",
                                 style="MPS.Treeview", selectmode="browse")
        for cid, titulo, ancho, anchor in COLUMNAS:
            self.tree.heading(cid, text=titulo,
                              command=lambda c=cid: self._ordenar(c))
            self.tree.column(cid, width=ancho, anchor=anchor,
                             stretch=(cid == "nombre"))
        self.tree.tag_configure("par", background=E.FILA_PAR)
        self.tree.tag_configure("impar", background=E.FILA_IMPAR)
        self.tree.bind("<Double-1>", self._abrir_detalle)

        vsb = ttk.Scrollbar(marco, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)

        # ----- Fila de totales -----
        self.tot = tk.Frame(self.cont, bg=E.AZUL)
        self.tot.pack(fill="x", pady=(8, 0))
        self.lbl_tot = tk.Label(self.tot, text="", bg=E.AZUL,
                                fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B,
                                anchor="w")
        self.lbl_tot.pack(fill="x", padx=12, pady=7)

        self._construir_overlay()

    # ------------------------------------------------------------------
    # Overlay de carga
    # ------------------------------------------------------------------
    def _construir_overlay(self):
        estilo = ttk.Style()
        estilo.configure("MPS.Horizontal.TProgressbar",
                         troughcolor=E.FILA_IMPAR, bordercolor=E.BORDE_SUAVE,
                         background=E.AZUL, lightcolor=E.AZUL, darkcolor=E.AZUL)
        self.overlay = tk.Frame(self.cont, bg=E.FONDO)
        tarjeta = tk.Frame(self.overlay, bg=E.BLANCO,
                           highlightbackground=E.BORDE_SUAVE,
                           highlightthickness=1)
        tarjeta.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(tarjeta, text="Cargando ventas", bg=E.BLANCO, fg=E.TEXTO,
                 font=(E.FUENTE, 16, "bold")).pack(padx=48, pady=(28, 4))
        self.ov_msg = tk.Label(tarjeta, text="Conectando con Business...",
                               bg=E.BLANCO, fg=E.TEXTO_SUB, font=E.F_NORMAL)
        self.ov_msg.pack(padx=48)
        self.ov_bar = ttk.Progressbar(
            tarjeta, length=380, maximum=100, mode="determinate",
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
        self._set_indicador("Cargando ventas... {}%".format(int(pct)), True)
        if self._overlay_visible():
            self._actualizar_overlay(pct, msg)

    def _set_indicador(self, texto, conectado):
        try:
            self.indicador_cb(texto, conectado)
        except Exception:
            pass

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
        """Recalcula ventas del periodo desde el almacen y repinta."""
        if not self._vivo:
            return
        info = store.obtener() or {}
        movimientos = info.get("movimientos", [])
        productos = info.get("productos", {})
        filas, desde, hasta = VD.calcular_ventas(
            movimientos, productos, self.var_periodo.get())
        self.filas_periodo = filas
        try:
            self.lbl_rango.config(text="del {} al {}".format(
                _fecha(desde), _fecha(hasta)))
            self.lbl_estado.config(text="")
        except tk.TclError:
            pass
        # KPI del periodo (sobre todo el periodo)
        k = VD.kpis(filas)
        try:
            self.kpi["unidades"]["valor"].config(text=_miles(k["unidades"]))
            self.kpi["valor"]["valor"].config(text=_money(k["valor"]))
            self.kpi["productos"]["valor"].config(text=_miles(k["productos"]))
        except tk.TclError:
            pass
        self._aplicar()

    def _aplicar(self):
        if not self._vivo:
            return
        filas = VD.filtrar(self.filas_periodo, self.var_busqueda.get())
        if self.orden_col:
            filas = VD.ordenar(filas, self.orden_col, self.orden_asc)
        self.filas_vista = filas
        self._pintar()
        self._actualizar_totales()
        try:
            self.lbl_contador.config(
                text="{} productos".format(len(self.filas_vista)))
        except tk.TclError:
            pass

    def _valor_celda(self, fila, cid):
        v = fila.get(cid)
        if cid in ("valor", "costo", "utilidad"):
            return _money(v)
        if cid == "unidades":
            return _miles(v)
        return v if v not in (None, "") else ""

    def _pintar(self):
        ids = [c[0] for c in COLUMNAS]
        try:
            self.tree.delete(*self.tree.get_children())
            for i, fila in enumerate(self.filas_vista):
                valores = [self._valor_celda(fila, cid) for cid in ids]
                tag = "par" if i % 2 == 0 else "impar"
                self.tree.insert("", "end", values=valores, tags=(tag,))
        except tk.TclError:
            pass

    def _actualizar_totales(self):
        t = VD.totales(self.filas_vista)
        texto = ("TOTALES (visibles)      Unidades: {}      "
                 "Valor: {}      Costo: {}      Utilidad: {}").format(
            _miles(t["unidades"]), _money(t["valor"]),
            _money(t["costo"]), _money(t["utilidad"]))
        try:
            self.lbl_tot.config(text=texto)
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
        info = store.obtener() or {}
        movimientos = info.get("movimientos", [])
        porper = VD.ventas_de_producto(movimientos, cod)

        dlg = tk.Toplevel(self.parent, bg=E.FONDO)
        dlg.title("Detalle de ventas del producto")
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
        sub = "Codigo: {}".format(cod)
        if fila.get("referencia"):
            sub += "     Referencia: {}".format(fila["referencia"])
        tk.Label(hd, text=sub, bg=E.AZUL, fg="#CFE4F5",
                 font=(E.FUENTE, 10)).pack(anchor="w", padx=18, pady=(0, 12))
        tk.Frame(dlg, bg=E.ROJO, height=3).pack(fill="x")

        cuerpo = tk.Frame(dlg, bg=E.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=18, pady=16)
        tk.Label(cuerpo, text="Ventas por periodo", bg=E.FONDO, fg=E.AZUL,
                 font=E.F_NORMAL_B).pack(anchor="w", pady=(0, 6))

        tabla = tk.Frame(cuerpo, bg=E.BLANCO,
                         highlightbackground=E.BORDE_SUAVE, highlightthickness=1)
        tabla.pack(fill="x")
        cols = [("Periodo", 22, "w"), ("Unidades", 11, "e"),
                ("Valor vendido", 16, "e"), ("Costo", 16, "e"),
                ("Utilidad", 16, "e")]
        enc = tk.Frame(tabla, bg=E.AZUL)
        enc.pack(fill="x")
        for txt, w, anch in cols:
            tk.Label(enc, text=txt, bg=E.AZUL, fg=E.TEXTO_BLANCO,
                     font=E.F_PEQUENA, width=w, anchor=anch).pack(
                         side="left", padx=6, pady=4)
        # Mostrar primero "Ano actual", luego los periodos cortos
        orden = ["Ano actual", "Ultimos 6 meses", "Ultimos 3 meses",
                 "Mes actual"]
        for i, op in enumerate(orden):
            d = porper.get(op)
            if not d:
                continue
            bg = E.FILA_PAR if i % 2 == 0 else E.FILA_IMPAR
            rf = tk.Frame(tabla, bg=bg)
            rf.pack(fill="x")
            vals = [op, _miles(d["unidades"]), _money(d["valor"]),
                    _money(d["costo"]), _money(d["utilidad"])]
            for (txt, w, anch), val in zip(cols, vals):
                tk.Label(rf, text=val, bg=bg, fg=E.TEXTO, font=E.F_NORMAL,
                         width=w, anchor=anch).pack(side="left", padx=6, pady=2)

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
    """'2026-03-20' -> '20/03/2026'."""
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
    ModuloVentas(root, rol="ADMINISTRADOR")
    root.mainloop()
