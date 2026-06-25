# -*- coding: utf-8 -*-
"""
MPS REPORTS - Modulo Usuarios (Fase 9)
Solo visible para ADMINISTRADOR.
Lista usuarios, crea nuevos, activa/desactiva. Nunca se borran (RN-13).
Cada operacion queda en historial.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import estilo as E
import base_propia
import seguridad
import auditoria


def _listar():
    con = base_propia.conectar()
    cur = con.cursor()
    cur.execute("SELECT id, nombre, rol, activo FROM usuarios ORDER BY nombre")
    filas = cur.fetchall()
    con.close()
    return filas


def _crear_usuario(nombre, contrasena, rol, usuario_admin):
    salt, hash_c = seguridad.generar_hash(contrasena)
    con = base_propia.conectar()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO usuarios (nombre, hash_contrasena, salt, rol, activo)
        VALUES (?, ?, ?, ?, 1)
    """, (nombre.strip(), hash_c, salt, rol))
    con.commit()
    con.close()
    auditoria.registrar(usuario_admin, "CREACION_USUARIO",
                        "Usuario {} creado con rol {}".format(nombre, rol))


def _cambiar_estado(id_usuario, activo, nombre, usuario_admin):
    con = base_propia.conectar()
    cur = con.cursor()
    cur.execute("UPDATE usuarios SET activo = ? WHERE id = ?",
                (1 if activo else 0, id_usuario))
    con.commit()
    con.close()
    accion = "ACTIVACION_USUARIO" if activo else "DESACTIVACION_USUARIO"
    auditoria.registrar(usuario_admin, accion,
                        "Usuario {} {}".format(nombre,
                                               "activado" if activo else "desactivado"))


def _cambiar_contrasena(nombre, nueva, usuario_admin, es_propio=False):
    salt, hash_c = seguridad.generar_hash(nueva)
    con = base_propia.conectar()
    cur = con.cursor()
    cur.execute("UPDATE usuarios SET hash_contrasena = ?, salt = ? WHERE nombre = ?",
                (hash_c, salt, nombre))
    con.commit()
    con.close()
    det = "Cambio de contrasena propio" if es_propio else \
          "Contrasena de {} cambiada por admin".format(nombre)
    auditoria.registrar(usuario_admin, "CAMBIO_CONTRASENA", det)


ROLES = ["ADMINISTRADOR", "SUPERVISOR", "CONSULTA"]


class ModuloUsuarios:
    COLUMNAS = [
        ("nombre", "Nombre",  200, "w"),
        ("rol",    "Rol",     160, "w"),
        ("estado", "Estado",  100, "center"),
    ]

    def __init__(self, parent, rol="ADMINISTRADOR", usuario="-",
                 indicador_cb=None):
        self.parent = parent
        self.rol = rol
        self.usuario = usuario
        self.indicador_cb = indicador_cb or (lambda *a, **k: None)
        self._construir()
        self._cargar()

    def _construir(self):
        cont = tk.Frame(self.parent, bg=E.FONDO)
        cont.pack(fill="both", expand=True, padx=16, pady=14)
        self.cont = cont

        cab = tk.Frame(cont, bg=E.FONDO)
        cab.pack(fill="x", pady=(0, 10))
        tk.Label(cab, text="Administracion de usuarios", bg=E.FONDO,
                 fg=E.TEXTO, font=(E.FUENTE, 15, "bold")).pack(side="left")

        acciones = tk.Frame(cont, bg=E.FONDO)
        acciones.pack(fill="x", pady=(0, 8))
        tk.Button(acciones, text="Crear usuario nuevo", bg=E.VERDE,
                  fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B, relief="flat", bd=0,
                  cursor="hand2", padx=14, pady=6,
                  command=self._dlg_crear).pack(side="left")
        tk.Button(acciones, text="Cambiar contrasena", bg=E.AZUL2,
                  fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B, relief="flat", bd=0,
                  cursor="hand2", padx=14, pady=6,
                  command=self._dlg_cambiar_contrasena).pack(side="left",
                                                             padx=(8, 0))
        tk.Button(acciones, text="Activar / Desactivar", bg=E.NARANJA,
                  fg=E.TEXTO_BLANCO, font=E.F_NORMAL_B, relief="flat", bd=0,
                  cursor="hand2", padx=14, pady=6,
                  command=self._toggle_estado).pack(side="left", padx=(8, 0))
        tk.Label(acciones,
                 text="Los usuarios nunca se borran, solo se desactivan.",
                 bg=E.FONDO, fg=E.TEXTO_TENUE, font=E.F_PEQUENA).pack(
                     side="right")

        marco = tk.Frame(cont, bg=E.BORDE)
        marco.pack(fill="both", expand=True)
        self._estilo()
        ids = [c[0] for c in self.COLUMNAS]
        self.tree = ttk.Treeview(marco, columns=ids, show="headings",
                                 style="MPS.Treeview", selectmode="browse",
                                 height=20)
        for cid, t, w, anchor in self.COLUMNAS:
            self.tree.heading(cid, text=t)
            self.tree.column(cid, width=w, anchor=anchor)
        self.tree.tag_configure("activo",   background="#EDF7ED")
        self.tree.tag_configure("inactivo", background="#FBE4E4",
                                foreground=E.TEXTO_TENUE)
        vsb = ttk.Scrollbar(marco, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        marco.rowconfigure(0, weight=1)
        marco.columnconfigure(0, weight=1)
        self._fila_map = {}

    def _estilo(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("MPS.Treeview", background=E.BLANCO,
                    fieldbackground=E.BLANCO, foreground=E.TEXTO,
                    rowheight=28, font=E.F_NORMAL)
        s.configure("MPS.Treeview.Heading", background=E.AZUL,
                    foreground=E.TEXTO_BLANCO, font=E.F_NORMAL_B,
                    relief="flat", padding=(4, 6))

    def _cargar(self):
        try:
            self.tree.delete(*self.tree.get_children())
        except tk.TclError:
            return
        self._fila_map = {}
        for id_u, nombre, rol, activo in _listar():
            estado = "Activo" if activo else "Inactivo"
            tag = "activo" if activo else "inactivo"
            iid = self.tree.insert("", "end",
                                   values=(nombre, rol, estado),
                                   tags=(tag,))
            self._fila_map[iid] = {"id": id_u, "nombre": nombre,
                                   "rol": rol, "activo": activo}

    def _seleccionado(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Usuarios", "Seleccione un usuario de la lista.")
            return None
        return self._fila_map.get(sel[0])

    def _toggle_estado(self):
        u = self._seleccionado()
        if not u:
            return
        if u["nombre"] == self.usuario:
            messagebox.showwarning("Usuarios",
                                   "No puede desactivar su propia cuenta.")
            return
        nuevo = not u["activo"]
        accion = "activar" if nuevo else "desactivar"
        if not messagebox.askyesno("Usuarios",
                                   "Seguro que desea {} a {}?".format(
                                       accion, u["nombre"])):
            return
        _cambiar_estado(u["id"], nuevo, u["nombre"], self.usuario)
        self._cargar()

    def _dlg_crear(self):
        dlg = tk.Toplevel(self.parent, bg=E.FONDO)
        dlg.title("Crear usuario nuevo")
        dlg.resizable(False, False)
        try:
            dlg.transient(self.parent.winfo_toplevel())
        except tk.TclError:
            pass

        tk.Label(dlg, text="Crear usuario nuevo", bg=E.FONDO, fg=E.TEXTO,
                 font=(E.FUENTE, 13, "bold")).pack(padx=24, pady=(18, 4))

        form = tk.Frame(dlg, bg=E.FONDO)
        form.pack(padx=24, pady=8)

        campos = [("Nombre de usuario", "nombre"),
                  ("Contrasena inicial", "contra"),
                  ("Confirmar contrasena", "contra2")]
        vars_ = {}
        for i, (etq, clave) in enumerate(campos):
            tk.Label(form, text=etq + ":", bg=E.FONDO, fg=E.TEXTO_SUB,
                     font=E.F_NORMAL).grid(row=i, column=0, sticky="w", pady=4)
            v = tk.StringVar()
            show = "*" if "contra" in clave else ""
            tk.Entry(form, textvariable=v, width=26, font=E.F_NORMAL,
                     relief="solid", bd=1, show=show).grid(
                         row=i, column=1, pady=4, padx=(8, 0))
            vars_[clave] = v

        tk.Label(form, text="Rol:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).grid(row=3, column=0, sticky="w", pady=4)
        var_rol = tk.StringVar(value="CONSULTA")
        ttk.Combobox(form, textvariable=var_rol, values=ROLES,
                     state="readonly", width=24,
                     font=E.F_NORMAL).grid(row=3, column=1, pady=4, padx=(8, 0))

        def guardar():
            nombre = vars_["nombre"].get().strip()
            contra = vars_["contra"].get()
            contra2 = vars_["contra2"].get()
            rol_nuevo = var_rol.get()
            if not nombre:
                messagebox.showwarning("Crear usuario",
                                       "El nombre no puede estar vacio.")
                return
            if not contra:
                messagebox.showwarning("Crear usuario",
                                       "La contrasena no puede estar vacia.")
                return
            if contra != contra2:
                messagebox.showwarning("Crear usuario",
                                       "Las contrasenas no coinciden.")
                return
            # Verificar que no exista
            existentes = [r[1] for r in _listar()]
            if nombre in existentes:
                messagebox.showwarning("Crear usuario",
                                       "Ya existe un usuario con ese nombre.")
                return
            _crear_usuario(nombre, contra, rol_nuevo, self.usuario)
            dlg.destroy()
            self._cargar()
            messagebox.showinfo("Crear usuario",
                                "Usuario {} creado con rol {}.".format(
                                    nombre, rol_nuevo))

        tk.Button(dlg, text="Crear", bg=E.VERDE, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=20, pady=7, command=guardar).pack(pady=(4, 18))
        self._centrar(dlg)
        dlg.grab_set()

    def _dlg_cambiar_contrasena(self):
        u = self._seleccionado()
        if not u:
            return
        dlg = tk.Toplevel(self.parent, bg=E.FONDO)
        dlg.title("Cambiar contrasena - " + u["nombre"])
        dlg.resizable(False, False)
        try:
            dlg.transient(self.parent.winfo_toplevel())
        except tk.TclError:
            pass

        tk.Label(dlg, text="Cambiar contrasena",
                 bg=E.FONDO, fg=E.TEXTO,
                 font=(E.FUENTE, 13, "bold")).pack(padx=24, pady=(18, 4))
        tk.Label(dlg, text="Usuario: " + u["nombre"],
                 bg=E.FONDO, fg=E.TEXTO_SUB, font=E.F_NORMAL).pack(padx=24)

        form = tk.Frame(dlg, bg=E.FONDO)
        form.pack(padx=24, pady=12)
        var_nueva = tk.StringVar()
        var_conf  = tk.StringVar()
        tk.Label(form, text="Nueva contrasena:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).grid(row=0, column=0, sticky="w", pady=4)
        tk.Entry(form, textvariable=var_nueva, width=24, show="*",
                 font=E.F_NORMAL, relief="solid", bd=1).grid(
                     row=0, column=1, pady=4, padx=(8, 0))
        tk.Label(form, text="Confirmar:", bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=E.F_NORMAL).grid(row=1, column=0, sticky="w", pady=4)
        tk.Entry(form, textvariable=var_conf, width=24, show="*",
                 font=E.F_NORMAL, relief="solid", bd=1).grid(
                     row=1, column=1, pady=4, padx=(8, 0))

        def guardar():
            nueva = var_nueva.get()
            conf  = var_conf.get()
            if not nueva:
                messagebox.showwarning("Contrasena",
                                       "La contrasena no puede estar vacia.")
                return
            if nueva != conf:
                messagebox.showwarning("Contrasena",
                                       "Las contrasenas no coinciden.")
                return
            _cambiar_contrasena(u["nombre"], nueva, self.usuario)
            dlg.destroy()
            messagebox.showinfo("Contrasena",
                                "Contrasena de {} actualizada.".format(
                                    u["nombre"]))

        tk.Button(dlg, text="Guardar", bg=E.AZUL, fg=E.TEXTO_BLANCO,
                  font=E.F_NORMAL_B, relief="flat", bd=0, cursor="hand2",
                  padx=20, pady=7, command=guardar).pack(pady=(0, 18))
        self._centrar(dlg)
        dlg.grab_set()

    def _centrar(self, dlg):
        dlg.update_idletasks()
        w = dlg.winfo_width()
        h = dlg.winfo_height()
        sw = dlg.winfo_screenwidth()
        sh = dlg.winfo_screenheight()
        dlg.geometry("+{}+{}".format(max(0, (sw - w) // 2),
                                     max(0, (sh - h) // 2)))

    def detener(self):
        pass
