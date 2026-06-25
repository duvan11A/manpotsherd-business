# -*- coding: utf-8 -*-
"""
MPS REPORTS - Modulo Historial (Fase 9)
Muestra todas las acciones registradas en la tabla historial de sistema.db.
Filtros: usuario, tipo de accion, rango de fechas.
Visible para ADMINISTRADOR y SUPERVISOR. Oculto para CONSULTA.
"""

import tkinter as tk
from tkinter import ttk
from datetime import date, timedelta

import estilo as E
import base_propia


def _todas_acciones():
    con = base_propia.conectar()
    cur = con.cursor()
    cur.execute("SELECT DISTINCT accion FROM historial ORDER BY accion")
    res = [r[0] for r in cur.fetchall()]
    con.close()
    return res


def _todos_usuarios():
    con = base_propia.conectar()
    cur = con.cursor()
    cur.execute("SELECT DISTINCT usuario FROM historial ORDER BY usuario")
    res = [r[0] for r in cur.fetchall()]
    con.close()
    return res


def _cargar(usuario=None, accion=None, desde=None, hasta=None):
    con = base_propia.conectar()
    cur = con.cursor()
    sql = "SELECT fecha_hora, usuario, accion, detalle FROM historial WHERE 1=1"
    params = []
    if usuario and usuario != "Todos":
        sql += " AND usuario = ?"
        params.append(usuario)
    if accion and accion != "Todas":
        sql += " AND accion = ?"
        params.append(accion)
    if desde:
        sql += " AND fecha_hora >= ?"
        params.append(desde + " 00:00:00")
    if hasta:
        sql += " AND fecha_hora <= ?"
        params.append(hasta + " 23:59:59")
    sql += " ORDER BY fecha_hora DESC"
    cur.execute(sql, params)
    filas = cur.fetchall()
    con.close()
    return filas


class ModuloHistorial:
    COLUMNAS = [
        ("fecha_hora", "Fecha y hora",   160, "w"),
        ("usuario",    "Usuario",         130, "w"),
        ("accion",     "Accion",          180, "w"),
        ("detalle",    "Detalle",         600, "w"),
    ]

    def __init__(self, parent, rol="SUPERVISOR", indicador_cb=None):
        self.parent = parent
        self.rol = rol
        self.indicador_cb = indicador_cb or (lambda *a, **k: None)
        self._construir()
        self._cargar()

    def _construir(self):
        cont = tk.Frame(self.parent, bg=E.FONDO)
        cont.pack(fill="both", expand=True, padx=16, pady=14)
        self.cont = cont

        # Titulo
        cab = tk.Frame(cont, bg=E.FONDO)
        cab.pack(fill="x", pady=(0, 10))
        tk.Label(cab, text="Historial de acciones", bg=E.FONDO, fg=E.TEXTO,
                 font=(E.FUENTE, 15, "bold")).pack(side="left")
        self.lbl_total = tk.Label(cab, text="", bg=E.FONDO, fg=E.TEXTO_SUB,
                                  font=E.F_NORMAL_B)
        self.lbl_total.pack(side="right")

        # Filtros
        fil = tk.Frame(cont, bg=E.FONDO)
        fil.pack(fill="x", pady=(0, 8))

        tk.Label(fil, text="Usuario:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_usuario = tk.StringVar(value="Todos")
        usuarios = ["Todos"] + _todos_usuarios()
        self.cb_usuario = ttk.Combobox(fil, textvariable=self.var_usuario,
                                       values=usuarios, width=18,
                                       state="readonly", font=E.F_NORMAL)
        self.cb_usuario.pack(side="left", padx=(4, 14))

        tk.Label(fil, text="Accion:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_accion = tk.StringVar(value="Todas")
        acciones = ["Todas"] + _todas_acciones()
        self.cb_accion = ttk.Combobox(fil, textvariable=self.var_accion,
                                      values=acciones, width=22,
                                      state="readonly", font=E.F_NORMAL)
        self.cb_accion.pack(side="left", padx=(4, 14))

        tk.Label(fil, text="Desde:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        hace30 = (date.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        self.var_desde = tk.StringVar(value=hace30)
        tk.Entry(fil, textvariable=self.var_desde, width=12, font=E.F_NORMAL,
                 relief="solid", bd=1).pack(side="left", padx=(4, 14))

        tk.Label(fil, text="Hasta:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self.var_hasta = tk.StringVar(value=date.today().strftime("%Y-%m-%d"))
        tk.Entry(fil, textvariable=self.var_hasta, width=12, font=E.F_NORMAL,
                 relief="solid", bd=1).pack(side="left", padx=(4, 14))

        tk.Button(fil, text="Filtrar", bg=E.AZUL, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=14, pady=4, command=self._cargar).pack(side="left",
                                                              padx=(0, 6))
        tk.Button(fil, text="Limpiar filtros", bg=E.AZUL2, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=14, pady=4, command=self._limpiar).pack(side="left")

        # Tabla
        marco = tk.Frame(cont, bg=E.BORDE)
        marco.pack(fill="both", expand=True)
        self._estilo()
        ids = [c[0] for c in self.COLUMNAS]
        self.tree = ttk.Treeview(marco, columns=ids, show="headings",
                                 style="MPS.Treeview", selectmode="browse")
        for cid, t, w, anchor in self.COLUMNAS:
            self.tree.heading(cid, text=t)
            self.tree.column(cid, width=w, anchor=anchor, stretch=(cid == "detalle"))
        self.tree.tag_configure("par", background=E.FILA_PAR)
        self.tree.tag_configure("impar", background=E.FILA_IMPAR)
        vsb = ttk.Scrollbar(marco, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)

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

    def _cargar(self):
        filas = _cargar(
            usuario=self.var_usuario.get(),
            accion=self.var_accion.get(),
            desde=self.var_desde.get().strip() or None,
            hasta=self.var_hasta.get().strip() or None,
        )
        try:
            self.tree.delete(*self.tree.get_children())
            for i, (fh, usr, acc, det) in enumerate(filas):
                tag = "par" if i % 2 == 0 else "impar"
                self.tree.insert("", "end",
                                 values=(fh, usr, acc, det or ""),
                                 tags=(tag,))
            self.lbl_total.config(text="{} registros".format(len(filas)))
            # Actualizar combos con nuevos valores
            self.cb_usuario["values"] = ["Todos"] + _todos_usuarios()
            self.cb_accion["values"] = ["Todas"] + _todas_acciones()
        except tk.TclError:
            pass

    def _limpiar(self):
        self.var_usuario.set("Todos")
        self.var_accion.set("Todas")
        self.var_desde.set(
            (date.today() - timedelta(days=30)).strftime("%Y-%m-%d"))
        self.var_hasta.set(date.today().strftime("%Y-%m-%d"))
        self._cargar()

    def detener(self):
        pass
