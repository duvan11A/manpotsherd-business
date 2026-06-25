# -*- coding: utf-8 -*-
"""
MPS REPORTS - Pantalla de inicio de sesion (Fase 3)
Pantalla completa con imagen de fondo y tarjeta de acceso centrada.
"""

import tkinter as tk
from tkinter import ttk, messagebox

import estilo as E
import seguridad


class PantallaLogin:
    def __init__(self, root, al_ingresar):
        self.root = root
        self.al_ingresar = al_ingresar
        self.root.title(E.NOMBRE_SISTEMA + " - Acceso al sistema")
        self.root.configure(bg=E.FONDO)
        self._construir()

    def _construir(self):
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        # Lienzo de fondo a pantalla completa
        self.fondo = tk.Frame(self.root, bg=E.FONDO)
        self.fondo.pack(expand=True, fill="both")

        # Imagen de fondo (si existe)
        lbl_fondo = E.poner_fondo(self.fondo, sw, sh)
        if lbl_fondo is None:
            # Sin imagen: degradado simulado con color solido corporativo
            self.fondo.configure(bg=E.AZUL_OSCURO)

        # ---- Tarjeta de acceso centrada ----
        tarjeta = tk.Frame(self.fondo, bg=E.BLANCO,
                           highlightbackground=E.AZUL, highlightthickness=1)
        tarjeta.place(relx=0.5, rely=0.5, anchor="center", width=440, height=560)

        # Barra superior azul
        barra = tk.Frame(tarjeta, bg=E.AZUL, height=84)
        barra.pack(fill="x")
        barra.pack_propagate(False)
        tk.Label(barra, text=E.NOMBRE_SISTEMA, bg=E.AZUL, fg=E.TEXTO_BLANCO,
                 font=(E.FUENTE, 24, "bold")).pack(anchor="w", padx=24, pady=(16, 0))
        tk.Label(barra, text=E.SUBNOMBRE, bg=E.AZUL, fg="#CFE4F5",
                 font=(E.FUENTE, 10)).pack(anchor="w", padx=24)

        # Linea de acento roja
        tk.Frame(tarjeta, bg=E.ROJO, height=3).pack(fill="x")

        # Cuerpo
        cuerpo = tk.Frame(tarjeta, bg=E.BLANCO)
        cuerpo.pack(expand=True, fill="both", padx=34, pady=28)

        tk.Label(cuerpo, text="Acceso al sistema", bg=E.BLANCO, fg=E.TEXTO,
                 font=(E.FUENTE, 14, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Label(cuerpo, text="Seleccione su usuario y escriba su contrasena",
                 bg=E.BLANCO, fg=E.TEXTO_SUB, font=(E.FUENTE, 9)).pack(
                 anchor="w", pady=(0, 20))

        tk.Label(cuerpo, text="Usuario", bg=E.BLANCO, fg=E.TEXTO,
                 font=(E.FUENTE, 10, "bold")).pack(anchor="w")
        self.var_usuario = tk.StringVar()
        usuarios = seguridad.listar_usuarios_activos()
        self.combo = ttk.Combobox(cuerpo, textvariable=self.var_usuario,
                                  values=usuarios, state="readonly",
                                  font=(E.FUENTE, 11))
        self.combo.pack(fill="x", pady=(6, 18), ipady=5)
        if usuarios:
            self.combo.current(0)

        tk.Label(cuerpo, text="Contrasena", bg=E.BLANCO, fg=E.TEXTO,
                 font=(E.FUENTE, 10, "bold")).pack(anchor="w")
        self.var_clave = tk.StringVar()
        self.entry_clave = tk.Entry(cuerpo, textvariable=self.var_clave,
                                    show="*", font=(E.FUENTE, 12),
                                    relief="flat",
                                    highlightbackground=E.BORDE,
                                    highlightcolor=E.AZUL,
                                    highlightthickness=1)
        self.entry_clave.pack(fill="x", pady=(6, 6), ipady=7)
        self.entry_clave.bind("<Return>", lambda e: self._intentar())

        self.var_mostrar = tk.BooleanVar(value=False)
        chk = tk.Checkbutton(cuerpo, text="Mostrar contrasena",
                             variable=self.var_mostrar, bg=E.BLANCO,
                             fg=E.TEXTO_SUB, activebackground=E.BLANCO,
                             font=(E.FUENTE, 9), cursor="hand2",
                             command=self._toggle_mostrar)
        chk.pack(anchor="w", pady=(2, 18))

        self.btn = tk.Button(cuerpo, text="INGRESAR", bg=E.AZUL, fg=E.TEXTO_BLANCO,
                             font=(E.FUENTE, 12, "bold"), relief="flat",
                             cursor="hand2", activebackground=E.AZUL2,
                             activeforeground=E.TEXTO_BLANCO,
                             command=self._intentar, pady=11)
        self.btn.pack(fill="x")
        self.btn.bind("<Enter>", lambda e: self.btn.config(bg=E.AZUL2))
        self.btn.bind("<Leave>", lambda e: self.btn.config(bg=E.AZUL))

        self.lbl_msg = tk.Label(cuerpo, text="", bg=E.BLANCO, fg=E.ROJO,
                                font=(E.FUENTE, 9), wraplength=360, justify="left")
        self.lbl_msg.pack(anchor="w", pady=(14, 0))

        # Pie de la tarjeta
        tk.Label(tarjeta, text="MANPOTSHERD", bg=E.BLANCO, fg=E.TEXTO_TENUE,
                 font=(E.FUENTE, 8)).pack(side="bottom", pady=8)

        self.entry_clave.focus_set()

    def _toggle_mostrar(self):
        self.entry_clave.config(show="" if self.var_mostrar.get() else "*")

    def _intentar(self):
        usuario = self.var_usuario.get().strip()
        clave = self.var_clave.get()
        if not usuario:
            self.lbl_msg.config(text="Seleccione un usuario.")
            return
        if not clave:
            self.lbl_msg.config(text="Escriba la contrasena.")
            return

        res = seguridad.verificar(usuario, clave)
        if res["ok"]:
            self.lbl_msg.config(text="")
            self.al_ingresar(usuario, res["rol"])
            return

        if res["motivo"] == "bloqueado":
            minutos = max(1, res["segundos"] // 60)
            self.lbl_msg.config(
                text="Usuario bloqueado temporalmente por intentos fallidos. "
                     "Intente de nuevo en {} minuto(s).".format(minutos))
        else:
            restantes = res.get("restantes", "")
            extra = " Le quedan {} intento(s).".format(restantes) \
                if isinstance(restantes, int) else ""
            self.lbl_msg.config(text="Usuario o contrasena incorrectos." + extra)
        self.var_clave.set("")
        self.entry_clave.focus_set()


if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))
    import base_propia
    base_propia.inicializar_base()

    def entrar(usuario, rol):
        messagebox.showinfo("Ingreso correcto",
                            "Bienvenido {}\nRol: {}".format(usuario, rol))

    root = tk.Tk()
    root.state("zoomed")
    PantallaLogin(root, entrar)
    root.mainloop()
