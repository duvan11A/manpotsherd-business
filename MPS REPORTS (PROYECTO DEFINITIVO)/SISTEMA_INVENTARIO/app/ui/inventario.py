# -*- coding: utf-8 -*-
"""
MPS REPORTS - Modulo Inventario (Fase 4)
Cuatro tarjetas KPI, tabla completa con clasificaciones (marca, linea,
sublinea/tipo), busqueda en vivo, filtro de bodega, casilla 'solo con
stock', ordenamiento por columna y refresco manual.

Los datos viven en inventario_store (almacen compartido en memoria) y se
precargan desde el login. Esta pantalla solo se "asoma" al almacen, asi
cambiar de pestana y volver es instantaneo. Mientras carga, el porcentaje
se muestra arriba a la derecha (indicador) y, la primera vez, tambien en
una tarjeta de progreso centrada.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import estilo as E
import inventario_datos as ID
import ventas_datos as VD
import rentabilidad_datos as RD
from inventario_store import store

# Columnas de la tabla: (id, titulo, ancho, alineacion)
COLUMNAS = [
    ("codigo", "Codigo", 95, "w"),
    ("referencia", "Referencia", 100, "w"),
    ("nombre", "Nombre", 220, "w"),
    ("talla", "Talla", 55, "center"),
    ("color", "Color", 60, "center"),
    ("bodega", "Bodega", 150, "w"),
    ("stock", "Stock", 70, "e"),
    ("costo_unit", "Costo Unit", 100, "e"),
    ("precio_pub", "Precio Publico", 110, "e"),
    ("valor_bodega", "Valor Bodega", 120, "e"),
    ("rent_pct", "Rentabilidad %", 110, "e"),
    ("rotacion", "Rotacion", 80, "e"),
    ("marca", "Marca", 205, "w"),
    ("linea", "Linea", 180, "w"),
    ("tipo", "Sublinea", 160, "w"),
]


def _miles(v):
    try:
        return "{:,.0f}".format(float(v or 0)).replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def _money(v):
    return "$ " + _miles(v)


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
            self._set_indicador("Cargando inventario... {}%".format(int(pct or 0)),
                                True)
            store.precargar()

    # ------------------------------------------------------------------
    def _construir(self):
        self.cont = tk.Frame(self.parent, bg=E.FONDO)
        self.cont.pack(fill="both", expand=True, padx=16, pady=14)

        # ----- Tarjetas KPI -----
        fila_kpi = tk.Frame(self.cont, bg=E.FONDO)
        fila_kpi.pack(fill="x")
        self.kpi = {}
        defs = [
            ("productos", "Productos", E.AZUL),
            ("unidades", "Unidades en bodega", E.VERDE),
            ("valor", "Valor inventario al costo", E.AZUL),
            ("pocas", "Pocas unidades", E.ROJO),
        ]
        for i, (clave, titulo, color) in enumerate(defs):
            self.kpi[clave] = self._tarjeta_kpi(fila_kpi, titulo, color)
            self.kpi[clave]["marco"].grid(row=0, column=i, sticky="nsew",
                                          padx=(0 if i == 0 else 12, 0))
            fila_kpi.columnconfigure(i, weight=1)

        # ----- Barra de filtros -----
        barra = tk.Frame(self.cont, bg=E.FONDO)
        barra.pack(fill="x", pady=(14, 8))

        tk.Label(barra, text="Buscar:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_busqueda = tk.StringVar()
        ent = tk.Entry(barra, textvariable=self.var_busqueda, width=34,
                       font=E.F_NORMAL, relief="solid", bd=1)
        ent.pack(side="left", padx=(6, 16))
        ent.bind("<KeyRelease>", lambda e: self._aplicar_filtros())

        tk.Label(barra, text="Bodega:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_bodega = tk.StringVar(value="Todas")
        self.cmb_bodega = ttk.Combobox(barra, textvariable=self.var_bodega,
                                       state="readonly", width=24,
                                       font=E.F_NORMAL, values=["Todas"])
        self.cmb_bodega.pack(side="left", padx=(6, 16))
        self.cmb_bodega.bind("<<ComboboxSelected>>",
                             lambda e: self._aplicar_filtros())

        self.var_stock = tk.BooleanVar(value=True)
        tk.Checkbutton(barra, text="Solo con stock", variable=self.var_stock,
                       bg=E.FONDO, fg=E.TEXTO, font=E.F_NORMAL,
                       activebackground=E.FONDO, selectcolor=E.BLANCO,
                       command=self._aplicar_filtros).pack(side="left")

        tk.Label(barra, text="Rotacion:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left", padx=(16, 0))
        self.var_periodo = tk.StringVar(value="Ano actual")
        self.cmb_periodo = ttk.Combobox(
            barra, textvariable=self.var_periodo, state="readonly", width=16,
            font=E.F_NORMAL, values=VD.PERIODOS)
        self.cmb_periodo.pack(side="left", padx=(6, 0))
        self.cmb_periodo.bind("<<ComboboxSelected>>",
                              lambda e: self._cambiar_periodo())

        self.btn_refrescar = tk.Button(
            barra, text="Actualizar ahora", bg=E.AZUL, fg=E.TEXTO_BLANCO,
            font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
            activebackground=E.AZUL2, activeforeground=E.TEXTO_BLANCO,
            padx=14, pady=6, command=self._refrescar_manual)
        self.btn_refrescar.pack(side="right")

        self.lbl_contador = tk.Label(barra, text="", bg=E.FONDO,
                                     fg=E.TEXTO_SUB, font=E.F_NORMAL_B)
        self.lbl_contador.pack(side="right", padx=(0, 16))

        # ----- Tabla -----
        marco_tabla = tk.Frame(self.cont, bg=E.BORDE, bd=0)
        marco_tabla.pack(fill="both", expand=True)

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
        estilo.configure("MPS.Horizontal.TProgressbar",
                         troughcolor=E.FILA_IMPAR, bordercolor=E.BORDE_SUAVE,
                         background=E.AZUL, lightcolor=E.AZUL, darkcolor=E.AZUL)

        ids = [c[0] for c in COLUMNAS]
        self.tree = ttk.Treeview(marco_tabla, columns=ids, show="headings",
                                 style="MPS.Treeview", selectmode="browse")
        for cid, titulo, ancho, anchor in COLUMNAS:
            self.tree.heading(cid, text=titulo,
                              command=lambda c=cid: self._ordenar(c))
            self.tree.column(cid, width=ancho, anchor=anchor,
                             stretch=(cid == "nombre"))
        self.tree.tag_configure("par", background=E.FILA_PAR)
        self.tree.tag_configure("impar", background=E.FILA_IMPAR)
        self.tree.bind("<Double-1>", self._abrir_detalle)

        vsb = ttk.Scrollbar(marco_tabla, orient="vertical",
                            command=self.tree.yview)
        hsb = ttk.Scrollbar(marco_tabla, orient="horizontal",
                            command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        marco_tabla.rowconfigure(0, weight=1)
        marco_tabla.columnconfigure(0, weight=1)

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

    # ------------------------------------------------------------------
    # Overlay de carga (primera vez)
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

    # ------------------------------------------------------------------
    # Callbacks del almacen
    # ------------------------------------------------------------------
    def _on_prog(self, pct, msg):
        if not self._vivo:
            return
        # Porcentaje arriba a la derecha (siempre, aunque cargue por detras)
        self._set_indicador("Cargando inventario... {}%".format(int(pct)), True)
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
        self._aplicar_filtros(conservar_scroll=True)

    def _recalc_rotacion(self):
        """Recalcula la rotacion de cada producto segun el periodo elegido,
        con la misma formula del modulo Rentabilidad y Rotacion."""
        info = store.obtener() or {}
        movs = info.get("movimientos", [])
        desde, hasta = VD.rango_periodo(self.var_periodo.get())
        rot = RD.calcular_rotacion_periodo(movs, desde, hasta)
        for f in self.filas:
            f["rotacion"] = rot.get(f["codigo"])

    def _cambiar_periodo(self):
        self._recalc_rotacion()
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
        filtradas = ID.filtrar(
            self.filas,
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
        """Dibuja TODAS las filas filtradas. Si conservar_scroll, mantiene
        la posicion del scroll (para que no salte en el refresco automatico)."""
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
        """Conteo real del modulo Pocas Unidades (faltante>0 o stock<=umbral),
        global, no depende del filtro de la tabla."""
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

        # Encabezado azul
        hd = tk.Frame(dlg, bg=E.AZUL)
        hd.pack(fill="x")
        tk.Label(hd, text=fila["nombre"] or "(sin nombre)", bg=E.AZUL,
                 fg=E.TEXTO_BLANCO, font=(E.FUENTE, 15, "bold")).pack(
                     anchor="w", padx=18, pady=(12, 0))
        tk.Label(hd, text="Codigo: " + cod, bg=E.AZUL, fg="#CFE4F5",
                 font=(E.FUENTE, 10)).pack(anchor="w", padx=18, pady=(0, 12))
        tk.Frame(dlg, bg=E.ROJO, height=3).pack(fill="x")

        cuerpo = tk.Frame(dlg, bg=E.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=18, pady=16)

        rent = "N/D" if fila["rent_pct"] is None else "{:.1f}%".format(
            fila["rent_pct"])
        rota = "-" if fila["rotacion"] is None else "{:.2f}".format(
            fila["rotacion"])
        datos = [
            ("Marca", fila["marca"] or "-"),
            ("Linea", fila["linea"] or "-"),
            ("Sublinea", fila["tipo"] or "-"),
            ("Referencia", fila["referencia"] or "-"),
            ("Talla", fila["talla"] or "-"),
            ("Color", fila["color"] or "-"),
            ("Costo unitario", _money(fila["costo_unit"])),
            ("Precio publico", _money(fila["precio_pub"])),
            ("Rentabilidad", rent),
            ("Rotacion", rota),
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
                     font=E.F_NORMAL_B).grid(row=r, column=cc + 1, sticky="w",
                                             padx=(0, 30), pady=3)

        tk.Label(cuerpo, text="Existencias por bodega", bg=E.FONDO, fg=E.AZUL,
                 font=E.F_NORMAL_B).pack(anchor="w", pady=(16, 4))
        tabla = tk.Frame(cuerpo, bg=E.BLANCO,
                         highlightbackground=E.BORDE_SUAVE, highlightthickness=1)
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
                     fg=E.TEXTO, font=E.F_NORMAL, width=16, anchor="e").pack(
                         side="left", padx=6)
        if not hay:
            tk.Label(tabla, text="Sin existencias", bg=E.BLANCO,
                     fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(padx=6, pady=4)
        tf = tk.Frame(tabla, bg=E.FILA_IMPAR)
        tf.pack(fill="x")
        tk.Label(tf, text="TOTAL", bg=E.FILA_IMPAR, fg=E.TEXTO,
                 font=E.F_NORMAL_B, width=22, anchor="w").pack(
                     side="left", padx=6, pady=3)
        tk.Label(tf, text=_miles(tot_stock), bg=E.FILA_IMPAR, fg=E.TEXTO,
                 font=E.F_NORMAL_B, width=10, anchor="e").pack(side="left", padx=6)
        tk.Label(tf, text=_money(tot_valor), bg=E.FILA_IMPAR, fg=E.TEXTO,
                 font=E.F_NORMAL_B, width=16, anchor="e").pack(side="left", padx=6)

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
    ModuloInventario(root, rol="ADMINISTRADOR",
                     indicador_cb=lambda t, c=True: print("IND:", t))
    root.mainloop()
