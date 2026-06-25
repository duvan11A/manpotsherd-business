# -*- coding: utf-8 -*-
"""
MPS REPORTS - Modulo Pocas Unidades (Fase 8)
Lista de alertas: productos con faltante > 0 (hay que producir) o con stock
menor o igual al umbral. Orden: faltante de mayor a menor. El ADMINISTRADOR
puede cambiar el umbral (se guarda en configuracion).
"""

import tkinter as tk
from tkinter import ttk, messagebox

import estilo as E
import proyeccion_datos as PY
from inventario_store import store

TINTE_ROJO = "#FBE4E4"
TINTE_VERDE = "#E3F4E8"


def _miles(v):
    try:
        return "{:,.0f}".format(float(v or 0)).replace(",", ".")
    except (ValueError, TypeError):
        return "0"


class ModuloPocasUnidades:
    COLUMNAS = [
        ("codigo", "Codigo", 110, "w"),
        ("nombre", "Nombre", 270, "w"),
        ("referencia", "Referencia", 110, "w"),
        ("vendido", "Vendido (N meses)", 140, "e"),
        ("stock", "Stock bodega", 110, "e"),
        ("en_produccion", "En produccion", 120, "e"),
        ("producir", "Faltante por producir", 160, "e"),
        ("motivo", "Motivo", 170, "w"),
    ]

    def __init__(self, parent, rol="CONSULTA", indicador_cb=None):
        self.parent = parent
        self.rol = rol
        self.indicador_cb = indicador_cb or (lambda *a, **k: None)
        self._vivo = True
        self.filas = []

        self._construir()
        store.suscribir(self._on_data)
        store.suscribir_progreso(self._on_prog)
        if store.hay_datos():
            self._recalcular()
        else:
            self._mostrar_overlay()
            store.precargar()

    def _construir(self):
        self.cont = tk.Frame(self.parent, bg=E.FONDO)
        self.cont.pack(fill="both", expand=True, padx=16, pady=14)

        cab = tk.Frame(self.cont, bg=E.FONDO)
        cab.pack(fill="x")
        tk.Label(cab, text="Alertas: productos por producir o con stock bajo",
                 bg=E.FONDO, fg=E.TEXTO, font=(E.FUENTE, 15, "bold")).pack(
                     side="left")
        self.lbl_total = tk.Label(cab, text="", bg=E.FONDO, fg=E.ROJO,
                                  font=E.F_NORMAL_B)
        self.lbl_total.pack(side="right")

        barra = tk.Frame(self.cont, bg=E.FONDO)
        barra.pack(fill="x", pady=(10, 8))
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
                      fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B, relief="flat", bd=0,
                      cursor="hand2", padx=12, pady=4,
                      command=self._guardar_umbral).pack(side="left")
        else:
            tk.Label(barra, text="(solo el administrador puede cambiarlo)",
                     bg=E.FONDO, fg=E.TEXTO_TENUE, font=E.F_PEQUENA).pack(
                         side="left")
        tk.Label(barra, text="Buscar:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left", padx=(16, 0))
        self.var_busqueda = tk.StringVar()
        ent = tk.Entry(barra, textvariable=self.var_busqueda, width=26,
                       font=E.F_NORMAL, relief="solid", bd=1)
        ent.pack(side="left", padx=(6, 0))
        ent.bind("<KeyRelease>", lambda e: self._pintar())

        marco = tk.Frame(self.cont, bg=E.BORDE)
        marco.pack(fill="both", expand=True)
        self._estilo()
        ids = [c[0] for c in self.COLUMNAS]
        self.tree = ttk.Treeview(marco, columns=ids, show="headings",
                                 style="MPS.Treeview", selectmode="browse")
        for cid, t, w, anchor in self.COLUMNAS:
            self.tree.heading(cid, text=t)
            self.tree.column(cid, width=w, anchor=anchor, stretch=False)
        self.tree.tag_configure("rojo", background=TINTE_ROJO)
        self.tree.tag_configure("verde", background=TINTE_VERDE)
        vsb = ttk.Scrollbar(marco, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)
        self._construir_overlay()

    def _estilo(self):
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
        s.configure("MPS.Horizontal.TProgressbar", troughcolor=E.FILA_IMPAR,
                    background=E.AZUL)

    def _construir_overlay(self):
        self.overlay = tk.Frame(self.cont, bg=E.FONDO)
        t = tk.Frame(self.overlay, bg=E.BLANCO,
                     highlightbackground=E.BORDE_SUAVE, highlightthickness=1)
        t.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(t, text="Cargando alertas", bg=E.BLANCO, fg=E.TEXTO,
                 font=(E.FUENTE, 16, "bold")).pack(padx=48, pady=(28, 10))
        self.ov_bar = ttk.Progressbar(t, length=360, maximum=100,
                                      mode="determinate",
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
        self._pintar()

    def _pintar(self):
        umbral = PY.leer_umbral()
        t = self.var_busqueda.get().strip().lower()
        try:
            self.tree.delete(*self.tree.get_children())
        except tk.TclError:
            return
        n = 0
        for f in self.filas:
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
        self.lbl_total.config(text="{} alertas".format(n))

    def detener(self):
        self._vivo = False
        store.desuscribir(self._on_data)
        store.desuscribir_progreso(self._on_prog)
