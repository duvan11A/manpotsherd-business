# -*- coding: utf-8 -*-
"""
MPS REPORTS - Modulo Produccion (Fase 7 + extension Fase 8)
Registro manual de la produccion en proceso (lo que Business no tiene).
Buscar producto (Business + propios + equivalencias + programa externo),
registrar cantidad y fecha estimada de ingreso, lista de produccion activa
con editar / marcar entregado, crear productos nuevos (NP-), emparejar
equivalencias y configurar la ruta del programa externo de produccion.
Escribe SOLO en la base propia. Business no se modifica.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date
import calendar as _calmod

import estilo as E
import produccion_datos as PD
from inventario_store import store

NOTA = ("Estos datos se guardan unicamente en la base propia del sistema. "
        "Business no se modifica.")
ADVERTENCIA = ("Importante: cuando la mercancia llegue a la bodega, marca el "
               "registro como ENTREGADO. Si se te olvida, el sistema va a "
               "seguir contando esas unidades como si todavia no hubieran "
               "llegado, y los numeros del inventario no te van a cuadrar.")

MESES = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

# Colores para el origen en el buscador
_COLOR_ORIGEN = {
    "business": "#E8F4FD",   # azul muy claro
    "propio":   "#EDF7ED",   # verde muy claro
    "externo":  "#FEF9E7",   # amarillo muy claro
}
_LABEL_ORIGEN = {
    "business": "Business",
    "propio":   "Propio",
    "externo":  "Externo",
}


def _hoy_iso():
    return date.today().strftime("%Y-%m-%d")


def _a_iso(ddmmaaaa):
    """'10/07/2026' -> '2026-07-10'. None si invalida."""
    s = (ddmmaaaa or "").strip()
    for sep in ("/", "-", "."):
        if sep in s:
            p = s.split(sep)
            if len(p) == 3 and p[0].isdigit() and p[1].isdigit() and p[2].isdigit():
                d, m, a = p
                if len(a) == 4:
                    try:
                        date(int(a), int(m), int(d))
                        return "{:04d}-{:02d}-{:02d}".format(int(a), int(m), int(d))
                    except ValueError:
                        return None
    return None


def _a_vista(iso):
    """'2026-07-10' -> '10/07/2026'."""
    try:
        a, m, d = iso.split("-")
        return "{}/{}/{}".format(d, m, a)
    except (AttributeError, ValueError):
        return iso or ""


def abrir_calendario(parent, var):
    """Calendario emergente que escribe la fecha elegida (DD/MM/AAAA) en var."""
    iso = _a_iso(var.get())
    if iso:
        y, m, d = (int(x) for x in iso.split("-"))
    else:
        h = date.today()
        y, m, d = h.year, h.month, h.day
    est = {"y": y, "m": m}

    top = tk.Toplevel(parent, bg=E.BLANCO)
    top.title("Elegir fecha")
    top.resizable(False, False)
    try:
        top.transient(parent.winfo_toplevel())
    except tk.TclError:
        pass

    hdr = tk.Frame(top, bg=E.AZUL)
    hdr.pack(fill="x")
    lbl = tk.Label(hdr, text="", bg=E.AZUL, fg=E.TEXTO_BLANCO,
                   font=E.F_NORMAL_B)

    def mover(delta):
        nm = est["m"] + delta
        ny = est["y"]
        if nm < 1:
            nm = 12
            ny -= 1
        elif nm > 12:
            nm = 1
            ny += 1
        est["m"] = nm
        est["y"] = ny
        render()

    tk.Button(hdr, text="<", bg=E.AZUL, fg=E.TEXTO_BLANCO, relief="flat", bd=0,
              cursor="hand2", font=E.F_NORMAL_B, padx=10,
              command=lambda: mover(-1)).pack(side="left")
    lbl.pack(side="left", expand=True, pady=6)
    tk.Button(hdr, text=">", bg=E.AZUL, fg=E.TEXTO_BLANCO, relief="flat", bd=0,
              cursor="hand2", font=E.F_NORMAL_B, padx=10,
              command=lambda: mover(1)).pack(side="right")

    grid = tk.Frame(top, bg=E.BLANCO)
    grid.pack(padx=10, pady=10)

    def elegir(dia):
        var.set("{:02d}/{:02d}/{:04d}".format(dia, est["m"], est["y"]))
        top.destroy()

    def render():
        for w in grid.winfo_children():
            w.destroy()
        lbl.config(text="{} {}".format(MESES[est["m"]], est["y"]))
        for i, d in enumerate(["Lu", "Ma", "Mi", "Ju", "Vi", "Sa", "Do"]):
            tk.Label(grid, text=d, bg=E.BLANCO, fg=E.TEXTO_SUB,
                     font=E.F_PEQUENA, width=3).grid(row=0, column=i, pady=2)
        cal = _calmod.Calendar(firstweekday=0)
        fila = 1
        hoy = date.today()
        for semana in cal.monthdayscalendar(est["y"], est["m"]):
            for col, dia in enumerate(semana):
                if dia == 0:
                    continue
                es_hoy = (dia == hoy.day and est["m"] == hoy.month
                          and est["y"] == hoy.year)
                b = tk.Button(grid, text=str(dia), width=3, relief="flat",
                              bd=0, cursor="hand2", font=E.F_NORMAL,
                              bg=E.AZUL2 if es_hoy else E.FILA_IMPAR,
                              fg=E.TEXTO_BLANCO if es_hoy else E.TEXTO,
                              activebackground=E.HOVER,
                              command=lambda dd=dia: elegir(dd))
                b.grid(row=fila, column=col, padx=1, pady=1)
            fila += 1

    render()
    top.update_idletasks()
    w = top.winfo_width()
    hgt = top.winfo_height()
    sw = top.winfo_screenwidth()
    sh = top.winfo_screenheight()
    top.geometry("+{}+{}".format(max(0, (sw - w) // 2), max(0, (sh - hgt) // 2)))
    top.grab_set()


class ModuloProduccion:
    def __init__(self, parent, rol="CONSULTA", usuario="-", indicador_cb=None):
        self.parent = parent
        self.rol = rol
        self.usuario = usuario
        self.indicador_cb = indicador_cb or (lambda *a, **k: None)
        self._vivo = True
        self.sel_busqueda = None   # producto seleccionado en el buscador

        PD.asegurar_esquema()
        self._construir()
        self._refrescar_activas()
        self._buscar()
        store.suscribir(self._on_data)

    # ------------------------------------------------------------------
    def _prods_business(self):
        info = store.obtener() or {}
        return info.get("productos", {}) or {}

    def _construir(self):
        cont = tk.Frame(self.parent, bg=E.FONDO)
        cont.pack(fill="both", expand=True, padx=16, pady=12)
        self.cont = cont

        # Encabezado + contador de atrasadas
        cab = tk.Frame(cont, bg=E.FONDO)
        cab.pack(fill="x")
        tk.Label(cab, text="Produccion en proceso", bg=E.FONDO, fg=E.TEXTO,
                 font=(E.FUENTE, 16, "bold")).pack(side="left")
        self.lbl_atrasadas = tk.Label(cab, text="", bg=E.FONDO, fg=E.ROJO,
                                      font=E.F_NORMAL_B)
        self.lbl_atrasadas.pack(side="right")

        # Nota fija + advertencia
        tk.Label(cont, text=NOTA, bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_PEQUENA).pack(anchor="w", pady=(2, 0))
        adv = tk.Frame(cont, bg="#FBEFE0", highlightbackground=E.NARANJA,
                       highlightthickness=1)
        adv.pack(fill="x", pady=(6, 10))
        tk.Label(adv, text="!  " + ADVERTENCIA, bg="#FBEFE0", fg=E.TEXTO,
                 font=E.F_PEQUENA, justify="left", wraplength=1100).pack(
                     anchor="w", padx=10, pady=6)

        # ---- Seccion registrar ----
        reg = tk.LabelFrame(cont, text=" Registrar produccion ", bg=E.FONDO,
                            fg=E.TEXTO_SUB, font=E.F_NORMAL_B)
        reg.pack(fill="x")

        barra = tk.Frame(reg, bg=E.FONDO)
        barra.pack(fill="x", padx=10, pady=8)
        tk.Label(barra, text="Buscar (codigo o referencia):", bg=E.FONDO,
                 fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(side="left")
        self.var_busqueda = tk.StringVar()
        ent = tk.Entry(barra, textvariable=self.var_busqueda, width=32,
                       font=E.F_NORMAL, relief="solid", bd=1)
        ent.pack(side="left", padx=(6, 10))
        ent.bind("<KeyRelease>", lambda e: self._buscar())
        tk.Button(barra, text="Actualizar", bg=E.AZUL2, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=12, pady=5, command=self._actualizar).pack(
                      side="left", padx=(0, 10))
        self.lbl_estado = tk.Label(barra, text="", bg=E.FONDO, fg=E.TEXTO_TENUE,
                                   font=E.F_PEQUENA)
        self.lbl_estado.pack(side="left")
        tk.Button(barra, text="Crear producto nuevo", bg=E.VERDE,
                  fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B, relief="flat", bd=0,
                  cursor="hand2", padx=12, pady=5,
                  command=self._dlg_producto_nuevo).pack(side="right")
        self.btn_emparejar = tk.Button(
            barra, text="Emparejar referencia", bg=E.AZUL, fg=E.TEXTO_BLANCO,
            font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2", padx=12,
            pady=5, command=self._dlg_emparejar)
        if self.rol == "ADMINISTRADOR":
            self.btn_emparejar.pack(side="right", padx=(0, 8))

        cuerpo = tk.Frame(reg, bg=E.FONDO)
        cuerpo.pack(fill="x", padx=10, pady=(0, 10))

        # Resultados de busqueda
        cols = [("origen", "Origen", 80), ("codigo", "Codigo", 130),
                ("nombre", "Nombre", 280), ("referencia", "Referencia", 130)]
        self.tree_busq = ttk.Treeview(
            cuerpo, columns=[c[0] for c in cols], show="headings", height=5,
            style="MPS.Treeview", selectmode="browse")
        for cid, t, w in cols:
            self.tree_busq.heading(cid, text=t)
            self.tree_busq.column(cid, width=w, anchor="w")
        # Tags de color por origen
        self.tree_busq.tag_configure("tag_business",
                                     background=_COLOR_ORIGEN["business"])
        self.tree_busq.tag_configure("tag_propio",
                                     background=_COLOR_ORIGEN["propio"])
        self.tree_busq.tag_configure("tag_externo",
                                     background=_COLOR_ORIGEN["externo"])
        self.tree_busq.pack(side="left", fill="x", expand=True)
        self.tree_busq.bind("<<TreeviewSelect>>", self._sel_resultado)
        self._estilo_tree()

        # Leyenda de colores del buscador
        ley = tk.Frame(cuerpo, bg=E.FONDO)
        ley.pack(side="left", fill="y", padx=(8, 0), anchor="n")
        for origen, color in _COLOR_ORIGEN.items():
            fila_ley = tk.Frame(ley, bg=E.FONDO)
            fila_ley.pack(anchor="w", pady=2)
            tk.Frame(fila_ley, bg=color, width=14, height=14,
                     highlightbackground=E.BORDE_SUAVE,
                     highlightthickness=1).pack(side="left")
            tk.Label(fila_ley, text=" " + _LABEL_ORIGEN[origen], bg=E.FONDO,
                     fg=E.TEXTO_SUB, font=E.F_PEQUENA).pack(side="left")

        # Formulario de registro
        form = tk.Frame(cuerpo, bg=E.FONDO)
        form.pack(side="left", fill="y", padx=(12, 0))
        self.lbl_sel = tk.Label(form, text="Seleccione un producto",
                                bg=E.FONDO, fg=E.TEXTO_SUB, font=E.F_NORMAL_B,
                                wraplength=240, justify="left")
        self.lbl_sel.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        tk.Label(form, text="Cantidad:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).grid(row=1, column=0, sticky="w")
        self.var_cant = tk.StringVar()
        tk.Entry(form, textvariable=self.var_cant, width=12, font=E.F_NORMAL,
                 relief="solid", bd=1).grid(row=1, column=1, sticky="w", pady=2)
        tk.Label(form, text="Fecha ingreso:", bg=E.FONDO,
                 fg=E.TEXTO_SUB, font=E.F_NORMAL).grid(row=2, column=0,
                                                       sticky="w")
        self.var_fecha = tk.StringVar(value=_a_vista(_hoy_iso()))
        ent_f = tk.Entry(form, textvariable=self.var_fecha, width=12,
                         font=E.F_NORMAL, relief="solid", bd=1,
                         state="readonly", cursor="hand2")
        ent_f.grid(row=2, column=1, sticky="w", pady=2)
        ent_f.bind("<Button-1>",
                   lambda e: abrir_calendario(self.parent, self.var_fecha))
        tk.Label(form, text="(clic para abrir el calendario)", bg=E.FONDO,
                 fg=E.TEXTO_TENUE, font=E.F_PEQUENA).grid(
                     row=2, column=2, sticky="w", padx=(6, 0))
        tk.Label(form, text="Observacion:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).grid(row=3, column=0, sticky="w")
        self.var_obs = tk.StringVar()
        tk.Entry(form, textvariable=self.var_obs, width=20, font=E.F_NORMAL,
                 relief="solid", bd=1).grid(row=3, column=1, sticky="w", pady=2)
        tk.Button(form, text="Guardar produccion", bg=E.AZUL,
                  fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B, relief="flat", bd=0,
                  cursor="hand2", padx=14, pady=6,
                  command=self._guardar).grid(row=4, column=0, columnspan=2,
                                              sticky="we", pady=(8, 0))

        # ---- Configuracion de ruta (solo ADMINISTRADOR) ----
        if self.rol == "ADMINISTRADOR":
            self._construir_panel_ruta(cont)

        # ---- Seccion produccion activa ----
        act = tk.LabelFrame(cont, text=" Produccion activa ", bg=E.FONDO,
                            fg=E.TEXTO_SUB, font=E.F_NORMAL_B)
        act.pack(fill="both", expand=True, pady=(12, 0))

        acc = tk.Frame(act, bg=E.FONDO)
        acc.pack(fill="x", padx=10, pady=(8, 4))
        tk.Button(acc, text="Editar produccion", bg=E.AZUL, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=12, pady=5, command=self._editar_produccion).pack(
                      side="left")
        tk.Button(acc, text="Marcar como entregado", bg=E.VERDE,
                  fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B, relief="flat", bd=0,
                  cursor="hand2", padx=12, pady=5,
                  command=self._marcar_entregado).pack(side="left", padx=(8, 0))
        tk.Button(acc, text="Eliminar", bg=E.ROJO, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=12, pady=5, command=self._eliminar).pack(
                      side="left", padx=(8, 0))
        tk.Label(acc, text="(Las filas en rojo ya pasaron su fecha de ingreso)",
                 bg=E.FONDO, fg=E.TEXTO_TENUE, font=E.F_PEQUENA).pack(
                     side="right")

        marco = tk.Frame(act, bg=E.BORDE)
        marco.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols2 = [("codigo", "Codigo", 130), ("nombre", "Nombre", 250),
                 ("cantidad", "Cantidad", 80), ("freg", "Fecha registro", 130),
                 ("fing", "Fecha ingreso", 110), ("usuario", "Usuario", 130),
                 ("obs", "Observaciones", 200), ("estado", "Estado", 120)]
        self.tree_act = ttk.Treeview(
            marco, columns=[c[0] for c in cols2], show="headings",
            style="MPS.Treeview", selectmode="browse")
        for cid, t, w in cols2:
            self.tree_act.heading(cid, text=t)
            self.tree_act.column(cid, width=w,
                                 anchor="e" if cid == "cantidad" else "w")
        self.tree_act.tag_configure("atrasado", background="#FBE4E4")
        self.tree_act.bind("<Double-1>", self._resumen)
        self.tree_act.tag_configure("ingreso", background="#FDEFC2")
        vsb = ttk.Scrollbar(marco, orient="vertical",
                            command=self.tree_act.yview)
        self.tree_act.configure(yscrollcommand=vsb.set)
        self.tree_act.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # Panel configuracion de ruta (solo ADMINISTRADOR)
    # ------------------------------------------------------------------
    def _construir_panel_ruta(self, cont):
        panel = tk.LabelFrame(
            cont,
            text=" Configuracion de ruta - Programa externo de produccion ",
            bg=E.FONDO, fg=E.TEXTO_SUB, font=E.F_NORMAL_B)
        panel.pack(fill="x", pady=(8, 0))

        fila1 = tk.Frame(panel, bg=E.FONDO)
        fila1.pack(fill="x", padx=10, pady=(8, 4))

        tk.Label(fila1, text="Ruta:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).pack(side="left")
        self._ruta_guardada = PD.leer_ruta_externa()
        self.var_ruta = tk.StringVar(value=self._ruta_guardada)
        self.var_ruta.trace_add("write", self._ruta_modificada)
        ent_ruta = tk.Entry(fila1, textvariable=self.var_ruta, width=68,
                            font=E.F_NORMAL, relief="solid", bd=1)
        ent_ruta.pack(side="left", padx=(6, 8))

        self.btn_guardar_probar = tk.Button(
            fila1, text="Guardar ruta y probar conexion",
            bg=E.AZUL, fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B,
            relief="flat", bd=0, cursor="hand2", padx=12, pady=4,
            command=self._guardar_y_probar_ruta)
        self.btn_guardar_probar.pack(side="left")

        fila2 = tk.Frame(panel, bg=E.FONDO)
        fila2.pack(fill="x", padx=10, pady=(0, 8))
        self.lbl_ruta_estado = tk.Label(
            fila2,
            text="Ruta actual: {}".format(self._ruta_guardada),
            bg=E.FONDO, fg=E.TEXTO_TENUE, font=E.F_PEQUENA,
            wraplength=900, justify="left")
        self.lbl_ruta_estado.pack(anchor="w")
        tk.Label(fila2,
                 text="El archivo que se lee dentro de esa ruta es: "
                      "TABLAS\\proter.DBF",
                 bg=E.FONDO, fg=E.TEXTO_TENUE, font=E.F_PEQUENA).pack(
                     anchor="w")

    def _ruta_modificada(self, *_):
        """Detecta si el campo de ruta fue editado y aun no se guardo."""
        try:
            actual = self.var_ruta.get().strip()
            if actual != self._ruta_guardada:
                self.btn_guardar_probar.config(bg=E.NARANJA)
                self.lbl_ruta_estado.config(
                    text="! Ruta modificada pero NO guardada. "
                         "Presiona 'Guardar ruta y probar conexion'.",
                    fg=E.NARANJA)
            else:
                self.btn_guardar_probar.config(bg=E.AZUL)
                self.lbl_ruta_estado.config(
                    text="Ruta actual: {}".format(self._ruta_guardada),
                    fg=E.TEXTO_TENUE)
        except tk.TclError:
            pass

    def _hay_ruta_sin_guardar(self):
        """Devuelve True si el campo tiene una ruta distinta a la guardada."""
        try:
            return self.var_ruta.get().strip() != self._ruta_guardada
        except (AttributeError, tk.TclError):
            return False

    def _guardar_y_probar_ruta(self):
        ruta = self.var_ruta.get().strip()
        if not ruta:
            messagebox.showwarning("Guardar ruta", "La ruta no puede estar vacia.")
            return
        # Indicador de cargando
        self.btn_guardar_probar.config(
            text="Verificando...", state="disabled", bg=E.TEXTO_TENUE)
        self.lbl_ruta_estado.config(
            text="Probando conexion con el programa externo...",
            fg=E.TEXTO_SUB)
        self.cont.update_idletasks()
        # Probar conexion
        ok, msg, n = PD.probar_ruta_externa(ruta)
        # Restaurar boton
        self.btn_guardar_probar.config(
            text="Guardar ruta y probar conexion", state="normal")
        if not ok:
            self.btn_guardar_probar.config(bg=E.ROJO)
            messagebox.showwarning(
                "Error de conexion",
                "No se pudo conectar con esa ruta. La ruta NO fue guardada.\n\n"
                "{}".format(msg))
            self.lbl_ruta_estado.config(
                text="Error: {}".format(msg), fg=E.ROJO)
            return
        # Si funciona, guardar y recargar cache
        PD.guardar_ruta_externa(ruta)
        PD.recargar_externos()
        self._ruta_guardada = ruta
        self.btn_guardar_probar.config(bg=E.AZUL)
        self.lbl_ruta_estado.config(
            text="Ruta guardada y verificada OK ({} OPs). "
                 "Busqueda activa.".format(n),
            fg=E.VERDE)
        messagebox.showinfo(
            "Ruta guardada",
            "Conexion exitosa. Ruta guardada correctamente.\n\n"
            "{} ordenes de produccion encontradas en el programa externo.".format(n))

    # ------------------------------------------------------------------
    def _estilo_tree(self):
        estilo = ttk.Style()
        try:
            estilo.theme_use("clam")
        except tk.TclError:
            pass
        estilo.configure("MPS.Treeview", background=E.BLANCO,
                         fieldbackground=E.BLANCO, foreground=E.TEXTO,
                         rowheight=24, font=E.F_NORMAL)
        estilo.configure("MPS.Treeview.Heading", background=E.AZUL,
                         foreground=E.TEXTO_BLANCO, font=E.F_NORMAL_B,
                         relief="flat", padding=(4, 6))

    # ------------------------------------------------------------------
    # Buscador
    # ------------------------------------------------------------------
    def _alertar_ruta_sin_guardar(self):
        """Muestra cartel si la ruta fue editada pero no guardada.
        Devuelve True si hay ruta pendiente (el llamador debe detenerse)."""
        if self.rol == "ADMINISTRADOR" and self._hay_ruta_sin_guardar():
            messagebox.showwarning(
                "Ruta sin guardar",
                "Modificaste la ruta del programa externo pero no la guardaste.\n\n"
                "Presiona 'Guardar ruta y probar conexion' antes de continuar.")
            return True
        return False

    def _buscar(self):
        if self._alertar_ruta_sin_guardar():
            return
        texto = self.var_busqueda.get()
        self.tree_busq.delete(*self.tree_busq.get_children())
        self.sel_busqueda = None
        self._res_map = {}
        if not texto.strip():
            self._llenar_default()
            return
        # Fila de cargando dentro de la tabla
        try:
            self.tree_busq.insert("", "end",
                                  values=("...", "Buscando...", "", ""),
                                  tags=("cargando",))
            self.tree_busq.tag_configure("cargando", foreground=E.TEXTO_TENUE,
                                         font=E.F_PEQUENA)
            self.cont.update_idletasks()
        except tk.TclError:
            pass
        resultados = PD.buscar(texto, self._prods_business())
        # Limpiar fila cargando y pintar resultados
        try:
            self.tree_busq.delete(*self.tree_busq.get_children())
            self.lbl_estado.config(text="{} resultado(s)".format(len(resultados))
                                   if resultados else "Sin resultados")
        except tk.TclError:
            pass
        for r in resultados:
            origen = r["origen"]
            etq = _LABEL_ORIGEN.get(origen, origen)
            if r.get("por_equivalencia"):
                etq = "Equiv."
            tag = "tag_" + origen
            iid = self.tree_busq.insert(
                "", "end",
                values=(etq, r["codigo"], r["nombre"], r["referencia"]),
                tags=(tag,))
            self._res_map[iid] = r

    def _llenar_default(self, muestra=30):
        """Sin texto de busqueda: muestra los productos propios y una
        muestra de productos de Business."""
        for pp in PD.listar_productos_propios():
            iid = self.tree_busq.insert(
                "", "end",
                values=("Propio", pp["codigo"], pp.get("nombre", ""),
                        pp.get("referencia", "")),
                tags=("tag_propio",))
            self._res_map[iid] = {
                "origen": "propio", "codigo": pp["codigo"],
                "nombre": pp.get("nombre", ""),
                "referencia": pp.get("referencia", ""),
                "id_propio": pp["id"], "por_equivalencia": False}
        n = 0
        for cod, p in self._prods_business().items():
            if n >= muestra:
                break
            iid = self.tree_busq.insert(
                "", "end",
                values=("Business", cod, p.get("NOMBRE", ""),
                        p.get("REFER", "")),
                tags=("tag_business",))
            self._res_map[iid] = {
                "origen": "business", "codigo": cod,
                "nombre": p.get("NOMBRE", ""),
                "referencia": p.get("REFER", ""),
                "id_propio": None, "por_equivalencia": False}
            n += 1

    def _sel_resultado(self, event=None):
        sel = self.tree_busq.selection()
        if not sel:
            return
        r = self._res_map.get(sel[0])
        if not r:
            return
        self.sel_busqueda = r
        origen_txt = _LABEL_ORIGEN.get(r["origen"], r["origen"])
        self.lbl_sel.config(
            text="[{}]  {}  {}".format(origen_txt, r["codigo"], r["nombre"]),
            fg=E.TEXTO)

    # ------------------------------------------------------------------
    # Guardar produccion
    # ------------------------------------------------------------------
    def _guardar(self):
        if self._alertar_ruta_sin_guardar():
            return
        r = self.sel_busqueda
        if not r:
            messagebox.showinfo("Produccion",
                                "Primero busque y seleccione un producto.")
            return
        try:
            cantidad = int(self.var_cant.get())
        except ValueError:
            messagebox.showwarning("Produccion", "La cantidad debe ser un "
                                   "numero entero.")
            return
        if cantidad <= 0:
            messagebox.showwarning("Produccion",
                                   "La cantidad debe ser mayor que cero.")
            return
        fecha = _a_iso(self.var_fecha.get())
        if not fecha:
            messagebox.showwarning("Produccion", "Escriba la fecha de ingreso "
                                   "en formato DD/MM/AAAA.")
            return

        origen = r["origen"]
        # Los productos externos se tratan como codigo_business porque ya
        # tienen su propio codigo; cuando lleguen a Business estaran con ese
        # mismo codigo y se podra marcar entregado normalmente.
        if origen in ("business", "externo"):
            cod_bus = r["codigo"]
            id_prop = None
        else:
            cod_bus = None
            id_prop = r["id_propio"]

        obs = self.var_obs.get().strip()

        existente = PD.buscar_activo(codigo_business=cod_bus,
                                     id_producto_propio=id_prop)
        if existente:
            resp = self._preguntar_duplicado(existente["cantidad"])
            if resp == "cancelar":
                return
            if resp == "sumar":
                PD.sumar_a_registro(existente["id"], cantidad, self.usuario)
            else:  # reemplazar
                PD.reemplazar_registro(existente["id"], cantidad, fecha, obs,
                                       self.usuario)
        else:
            PD.crear_registro(cod_bus, id_prop, cantidad, fecha, self.usuario,
                              obs)

        self.var_cant.set("")
        self.var_fecha.set(_a_vista(_hoy_iso()))
        self.var_obs.set("")
        self._refrescar_activas()
        messagebox.showinfo("Produccion", "Produccion guardada.")

    def _preguntar_duplicado(self, cantidad_actual):
        """Devuelve 'sumar', 'reemplazar' o 'cancelar'."""
        dlg = tk.Toplevel(self.parent, bg=E.FONDO)
        dlg.title("Ya existe en produccion")
        dlg.resizable(False, False)
        try:
            dlg.transient(self.parent.winfo_toplevel())
        except tk.TclError:
            pass
        tk.Label(dlg, text="Ese producto ya tiene un registro activo de {} "
                 "unidades.".format(cantidad_actual), bg=E.FONDO, fg=E.TEXTO,
                 font=E.F_NORMAL, wraplength=320, justify="left").pack(
                     padx=20, pady=(18, 6))
        tk.Label(dlg, text="Que desea hacer con la nueva cantidad?",
                 bg=E.FONDO, fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(padx=20)
        res = {"v": "cancelar"}

        def elegir(v):
            res["v"] = v
            dlg.destroy()

        barra = tk.Frame(dlg, bg=E.FONDO)
        barra.pack(padx=20, pady=16)
        tk.Button(barra, text="Sumar", bg=E.VERDE, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=14, pady=6, command=lambda: elegir("sumar")).pack(
                      side="left", padx=4)
        tk.Button(barra, text="Reemplazar", bg=E.AZUL, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=14, pady=6, command=lambda: elegir("reemplazar")).pack(
                      side="left", padx=4)
        tk.Button(barra, text="Cancelar", bg=E.GRIS_DESHAB, fg=E.TEXTO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=14, pady=6, command=lambda: elegir("cancelar")).pack(
                      side="left", padx=4)
        self._centrar(dlg)
        dlg.grab_set()
        self.parent.wait_window(dlg)
        return res["v"]

    # ------------------------------------------------------------------
    # Lista activa
    # ------------------------------------------------------------------
    def _refrescar_activas(self):
        if not self._vivo:
            return
        info = store.obtener() or {}
        prods = info.get("productos", {}) or {}
        movimientos = info.get("movimientos", []) or []
        try:
            self.tree_act.delete(*self.tree_act.get_children())
        except tk.TclError:
            return
        activas = PD.listar_activas()
        detectados = PD.detectar_ingresos(activas, movimientos)
        hoy = _hoy_iso()
        atrasadas = 0
        llegaron = 0
        self._act_map = {}
        for f in activas:
            if f["es_propio"]:
                nombre = f["nombre_propio"] or ""
            else:
                # Puede ser de Business o externo; si no esta en Business
                # aun, el nombre viene vacio hasta que llegue
                nombre = prods.get(f["codigo_business"], {}).get("NOMBRE", "")
                if not nombre and f["codigo_business"]:
                    nombre = "(en produccion externa)"
            fing = f["fecha_ingreso"] or ""
            atrasado = bool(fing and fing < hoy)
            ingreso = f["id"] in detectados
            if ingreso:
                estado = "YA INGRESO - MARCAR ENTREGADO"
                tag = "ingreso"
                llegaron += 1
            elif atrasado:
                estado = "ATRASADO"
                tag = "atrasado"
                atrasadas += 1
            else:
                estado = "EN PRODUCCION"
                tag = ""
            iid = self.tree_act.insert(
                "", "end",
                values=(f["codigo"], nombre, f["cantidad"],
                        _a_vista(f["fecha_registro"][:10]
                                 if f["fecha_registro"] else ""),
                        _a_vista(fing), f["usuario"], f["observaciones"],
                        estado),
                tags=(tag,) if tag else ())
            self._act_map[iid] = f
        avisos = []
        if llegaron:
            avisos.append("{} ya ingreso(aron) a Business (revisar)".format(
                llegaron))
        if atrasadas:
            avisos.append("{} atrasada(s)".format(atrasadas))
        self.lbl_atrasadas.config(text="   ".join(avisos))

    def _registro_seleccionado(self):
        sel = self.tree_act.selection()
        if not sel:
            messagebox.showinfo("Produccion",
                                "Seleccione un registro de la lista.")
            return None
        return self._act_map.get(sel[0])

    def _editar_produccion(self):
        f = self._registro_seleccionado()
        if not f:
            return
        dlg = tk.Toplevel(self.parent, bg=E.FONDO)
        dlg.title("Editar produccion")
        dlg.resizable(False, False)
        try:
            dlg.transient(self.parent.winfo_toplevel())
        except tk.TclError:
            pass
        tk.Label(dlg, text="Editar produccion - {}".format(f["codigo"]),
                 bg=E.FONDO, fg=E.TEXTO, font=(E.FUENTE, 13, "bold")).pack(
                     padx=20, pady=(16, 8))
        cuerpo = tk.Frame(dlg, bg=E.FONDO)
        cuerpo.pack(padx=20, pady=(0, 8))

        tk.Label(cuerpo, text="Cantidad:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).grid(row=0, column=0, sticky="w", pady=4)
        var_c = tk.StringVar(value=str(f["cantidad"]))
        tk.Entry(cuerpo, textvariable=var_c, width=14, font=E.F_NORMAL,
                 relief="solid", bd=1).grid(row=0, column=1, sticky="w", pady=4)

        tk.Label(cuerpo, text="Fecha ingreso:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).grid(row=1, column=0, sticky="w", pady=4)
        var_f = tk.StringVar(value=_a_vista(f["fecha_ingreso"] or _hoy_iso()))
        ef = tk.Entry(cuerpo, textvariable=var_f, width=14, font=E.F_NORMAL,
                      relief="solid", bd=1, state="readonly", cursor="hand2")
        ef.grid(row=1, column=1, sticky="w", pady=4)
        ef.bind("<Button-1>", lambda e: abrir_calendario(self.parent, var_f))
        tk.Label(cuerpo, text="(clic para calendario)", bg=E.FONDO,
                 fg=E.TEXTO_TENUE, font=E.F_PEQUENA).grid(row=1, column=2,
                                                          padx=(6, 0))

        tk.Label(cuerpo, text="Observacion:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).grid(row=2, column=0, sticky="w", pady=4)
        var_o = tk.StringVar(value=f["observaciones"])
        tk.Entry(cuerpo, textvariable=var_o, width=28, font=E.F_NORMAL,
                 relief="solid", bd=1).grid(row=2, column=1, columnspan=2,
                                            sticky="w", pady=4)

        def guardar():
            try:
                c = int(var_c.get())
            except ValueError:
                messagebox.showwarning("Editar", "Cantidad invalida.")
                return
            if c <= 0:
                messagebox.showwarning("Editar", "Debe ser mayor que cero.")
                return
            fiso = _a_iso(var_f.get())
            if not fiso:
                messagebox.showwarning("Editar", "Fecha invalida.")
                return
            PD.reemplazar_registro(f["id"], c, fiso, var_o.get().strip(),
                                   self.usuario)
            dlg.destroy()
            self._refrescar_activas()

        tk.Button(dlg, text="Guardar cambios", bg=E.AZUL, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=16, pady=6, command=guardar).pack(pady=(4, 16))
        self._centrar(dlg)
        dlg.grab_set()

    def _resumen(self, event=None):
        f = self._registro_seleccionado()
        if not f:
            return
        prods = self._prods_business()
        if f["es_propio"]:
            nombre = f["nombre_propio"] or ""
        else:
            nombre = prods.get(f["codigo_business"], {}).get("NOMBRE", "")
            if not nombre:
                nombre = "(en produccion externa)"
        hoy = _hoy_iso()
        atrasado = bool(f["fecha_ingreso"] and f["fecha_ingreso"] < hoy)

        dlg = tk.Toplevel(self.parent, bg=E.FONDO)
        dlg.title("Resumen de la produccion")
        dlg.resizable(False, False)
        try:
            dlg.transient(self.parent.winfo_toplevel())
        except tk.TclError:
            pass
        hd = tk.Frame(dlg, bg=E.AZUL)
        hd.pack(fill="x")
        tk.Label(hd, text=nombre or "(sin nombre)", bg=E.AZUL,
                 fg=E.TEXTO_BLANCO, font=(E.FUENTE, 15, "bold")).pack(
                     anchor="w", padx=18, pady=(12, 0))
        tk.Label(hd, text="Codigo: {}    ({})".format(
            f["codigo"], "Producto propio" if f["es_propio"] else "Business / Externo"),
            bg=E.AZUL, fg="#CFE4F5", font=(E.FUENTE, 10)).pack(
                anchor="w", padx=18, pady=(0, 12))
        tk.Frame(dlg, bg=E.ROJO, height=3).pack(fill="x")

        cuerpo = tk.Frame(dlg, bg=E.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=18, pady=16)
        datos = [
            ("Cantidad en produccion", str(f["cantidad"])),
            ("Fecha de registro", _a_vista((f["fecha_registro"] or "")[:10])),
            ("Fecha estimada de ingreso", _a_vista(f["fecha_ingreso"] or "")),
            ("Registrado por", f["usuario"] or "-"),
            ("Observaciones", f["observaciones"] or "(sin observaciones)"),
            ("Estado", "ATRASADO (ya paso la fecha)" if atrasado
             else "EN PRODUCCION"),
        ]
        for k, v in datos:
            r = tk.Frame(cuerpo, bg=E.FONDO)
            r.pack(fill="x", pady=3)
            tk.Label(r, text=k + ":", bg=E.FONDO, fg=E.TEXTO_SUB,
                     font=E.F_NORMAL, width=24, anchor="w").pack(side="left")
            tk.Label(r, text=v, bg=E.FONDO,
                     fg=E.ROJO if (k == "Estado" and atrasado) else E.TEXTO,
                     font=E.F_NORMAL_B, wraplength=300, justify="left").pack(
                         side="left")

        tk.Button(cuerpo, text="Cerrar", bg=E.AZUL, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=22, pady=7, command=dlg.destroy).pack(pady=(14, 0))
        self._centrar(dlg)
        dlg.grab_set()

    def _eliminar(self):
        f = self._registro_seleccionado()
        if not f:
            return
        if not messagebox.askyesno(
                "Eliminar registro",
                "Seguro que desea ELIMINAR este registro de produccion?\n\n"
                "{}  -  {} unidades\n\nEsta accion no se puede deshacer.".format(
                    f["codigo"], f["cantidad"])):
            return
        PD.eliminar_registro(f["id"], self.usuario)
        self._refrescar_activas()

    def _marcar_entregado(self):
        f = self._registro_seleccionado()
        if not f:
            return
        if not messagebox.askyesno(
                "Marcar entregado",
                "Confirma que '{}' ({} unidades) ya ingreso a bodega?\n\n"
                "Dejara de descontarse en la proyeccion.".format(
                    f["codigo"], f["cantidad"])):
            return
        PD.marcar_entregado(f["id"], self.usuario)
        self._refrescar_activas()

    # ------------------------------------------------------------------
    # Crear producto nuevo
    # ------------------------------------------------------------------
    def _dlg_producto_nuevo(self):
        dlg = tk.Toplevel(self.parent, bg=E.FONDO)
        dlg.title("Crear producto nuevo")
        dlg.resizable(False, False)
        try:
            dlg.transient(self.parent.winfo_toplevel())
        except tk.TclError:
            pass
        tk.Label(dlg, text="Producto nuevo (base propia)", bg=E.FONDO,
                 fg=E.TEXTO, font=(E.FUENTE, 13, "bold")).pack(
                     padx=20, pady=(16, 2))
        tk.Label(dlg, text="Se le asignara un codigo NP- automatico. No se "
                 "crea en Business.", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_PEQUENA, wraplength=320).pack(padx=20)
        cuerpo = tk.Frame(dlg, bg=E.FONDO)
        cuerpo.pack(padx=20, pady=12)
        campos = [("Nombre", ""), ("Referencia", ""), ("Talla", ""),
                  ("Color", ""), ("Costo estimado", ""), ("Precio estimado", "")]
        variables = {}
        for i, (etq, _) in enumerate(campos):
            tk.Label(cuerpo, text=etq + ":", bg=E.FONDO, fg=E.TEXTO_SUB,
                     font=E.F_NORMAL).grid(row=i, column=0, sticky="w", pady=3)
            v = tk.StringVar()
            tk.Entry(cuerpo, textvariable=v, width=26, font=E.F_NORMAL,
                     relief="solid", bd=1).grid(row=i, column=1, pady=3)
            variables[etq] = v

        def guardar():
            nombre = variables["Nombre"].get().strip()
            if not nombre:
                messagebox.showwarning("Producto nuevo", "El nombre es "
                                       "obligatorio.")
                return
            try:
                costo = float(variables["Costo estimado"].get() or 0)
                precio = float(variables["Precio estimado"].get() or 0)
            except ValueError:
                messagebox.showwarning("Producto nuevo", "Costo y precio deben "
                                       "ser numeros.")
                return
            _, cod = PD.crear_producto_propio(
                nombre, variables["Referencia"].get().strip(),
                variables["Talla"].get().strip(),
                variables["Color"].get().strip(), costo, precio, self.usuario)
            dlg.destroy()
            messagebox.showinfo("Producto nuevo",
                                "Creado con codigo {}.".format(cod))
            self.var_busqueda.set(cod)
            self._buscar()

        tk.Button(dlg, text="Crear", bg=E.VERDE, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=18, pady=6, command=guardar).pack(pady=(0, 16))
        self._centrar(dlg)
        dlg.grab_set()

    # ------------------------------------------------------------------
    # Emparejar equivalencia (solo ADMINISTRADOR)
    # ------------------------------------------------------------------
    def _dlg_emparejar(self):
        if self.rol != "ADMINISTRADOR":
            return
        dlg = tk.Toplevel(self.parent, bg=E.FONDO)
        dlg.title("Emparejar referencia con producto de Business")
        dlg.resizable(False, False)
        try:
            dlg.transient(self.parent.winfo_toplevel())
        except tk.TclError:
            pass
        tk.Label(dlg, text="Referencia de produccion:", bg=E.FONDO,
                 fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(padx=20, pady=(16, 2),
                                                       anchor="w")
        var_ref = tk.StringVar(value=self.var_busqueda.get().strip())
        tk.Entry(dlg, textvariable=var_ref, width=34, font=E.F_NORMAL,
                 relief="solid", bd=1).pack(padx=20, anchor="w")
        tk.Label(dlg, text="Buscar producto de Business:", bg=E.FONDO,
                 fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(padx=20, pady=(10, 2),
                                                       anchor="w")
        var_b = tk.StringVar()
        tk.Entry(dlg, textvariable=var_b, width=34, font=E.F_NORMAL,
                 relief="solid", bd=1).pack(padx=20, anchor="w")
        tree = ttk.Treeview(dlg, columns=("codigo", "nombre"), show="headings",
                            height=6, style="MPS.Treeview", selectmode="browse")
        tree.heading("codigo", text="Codigo")
        tree.heading("nombre", text="Nombre")
        tree.column("codigo", width=130)
        tree.column("nombre", width=280)
        tree.pack(padx=20, pady=8)
        mapa = {}

        def buscar_bus(*_):
            tree.delete(*tree.get_children())
            mapa.clear()
            t = var_b.get().strip().lower()
            if not t:
                return
            n = 0
            for cod, p in self._prods_business().items():
                if (t in cod.lower() or t in str(p.get("REFER", "")).lower()
                        or t in str(p.get("NOMBRE", "")).lower()):
                    iid = tree.insert("", "end",
                                      values=(cod, p.get("NOMBRE", "")))
                    mapa[iid] = cod
                    n += 1
                    if n >= 40:
                        break

        var_b.trace_add("write", buscar_bus)

        def guardar():
            ref = var_ref.get().strip()
            sel = tree.selection()
            if not ref or not sel:
                messagebox.showwarning("Emparejar", "Escriba la referencia y "
                                       "seleccione el producto de Business.")
                return
            PD.crear_equivalencia(ref, mapa[sel[0]], self.usuario)
            dlg.destroy()
            messagebox.showinfo("Emparejar", "Equivalencia guardada. Esa "
                                "referencia se resolvera sola.")

        tk.Button(dlg, text="Guardar equivalencia", bg=E.AZUL,
                  fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B, relief="flat", bd=0,
                  cursor="hand2", padx=16, pady=6, command=guardar).pack(
                      pady=(0, 16))
        self._centrar(dlg)
        dlg.grab_set()

    # ------------------------------------------------------------------
    def _centrar(self, dlg):
        dlg.update_idletasks()
        w = dlg.winfo_width()
        h = dlg.winfo_height()
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        dlg.geometry("+{}+{}".format(max(0, (sw - w) // 2),
                                     max(0, (sh - h) // 2)))

    def _actualizar(self):
        """Vuelve a leer Business al instante para traer codigos nuevos."""
        self.lbl_estado.config(text="Actualizando productos desde Business...")
        try:
            store.forzar_refresco()
        except Exception:
            self.lbl_estado.config(text="")

    def _on_data(self, info, manual, resumen):
        if not self._vivo:
            return
        if info.get("ok"):
            self._refrescar_activas()
            self._buscar()
            n = len(info.get("productos", {}) or {})
            self.lbl_estado.config(
                text="Productos actualizados ({} de Business)".format(n))

    def detener(self):
        self._vivo = False
        store.desuscribir(self._on_data)


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
    ModuloProduccion(root, rol="ADMINISTRADOR", usuario="INGENIERO DUVAN")
    root.mainloop()
