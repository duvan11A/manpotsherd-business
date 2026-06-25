# -*- coding: utf-8 -*-
"""
MPS REPORTS - Ventana principal (Fase 4)
Barra superior con identidad, empresa activa, usuario e indicador de
actualizacion. Linea de acento roja. Menu lateral con permisos por rol.
El area central cambia segun el modulo elegido. El primer modulo es
Inventario; los demas se construyen en fases posteriores.
"""

import tkinter as tk
from datetime import datetime

import estilo as E
from inventario import ModuloInventario
from ventas import ModuloVentas
from rentabilidad import ModuloRentabilidad
from produccion import ModuloProduccion
from proyeccion import ModuloProyeccion
from pocas_unidades import ModuloPocasUnidades
from historial import ModuloHistorial
from usuarios import ModuloUsuarios
from reportes import ModuloReportes

# Orden del menu lateral (seccion 6.1)
MODULOS = [
    "Inventario", "Ventas", "Rentabilidad y Rotacion", "Proyeccion",
    "Produccion", "Pocas Unidades", "Reportes", "Historial", "Usuarios",
]


def puede_ver(rol, modulo):
    """Permisos del menu (matriz seccion 6.1)."""
    r = (rol or "").upper()
    if modulo == "Usuarios":
        return r == "ADMINISTRADOR"
    if modulo == "Historial":
        return r in ("ADMINISTRADOR", "SUPERVISOR")
    return True


class PantallaPrincipal:
    def __init__(self, root, usuario, rol, empresa, al_cerrar_sesion=None):
        self.root = root
        self.usuario = usuario
        self.rol = rol
        self.empresa = empresa
        self.al_cerrar_sesion = al_cerrar_sesion
        self._refs = []
        self.botones_menu = {}
        self.modulo_actual = None
        self.modulo_obj = None

        self.root.title(E.NOMBRE_SISTEMA + " - " + empresa)
        self.root.configure(bg=E.FONDO)
        self._construir()
        self._mostrar_modulo("Inventario")

    # ------------------------------------------------------------------
    def _construir(self):
        # ---------- BARRA SUPERIOR ----------
        header = tk.Frame(self.root, bg=E.AZUL, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Izquierda: nombre del sistema
        izq = tk.Frame(header, bg=E.AZUL)
        izq.pack(side="left", padx=20)
        tk.Label(izq, text=E.NOMBRE_SISTEMA, bg=E.AZUL, fg=E.TEXTO_BLANCO,
                 font=(E.FUENTE, 16, "bold")).pack(anchor="w", pady=(10, 0))
        tk.Label(izq, text=E.SUBNOMBRE, bg=E.AZUL, fg="#CFE4F5",
                 font=(E.FUENTE, 8)).pack(anchor="w")

        # Derecha: usuario + cerrar sesion + indicador
        der = tk.Frame(header, bg=E.AZUL)
        der.pack(side="right", padx=20)

        btn_cambiar = tk.Button(der, text="Cambiar contrasena", bg=E.AZUL_OSCURO,
                              fg=E.TEXTO_BLANCO, font=(E.FUENTE, 9, "bold"),
                              relief="flat", cursor="hand2", bd=0,
                              activebackground="#0E4D86",
                              activeforeground=E.TEXTO_BLANCO,
                              padx=12, pady=6, command=self._cambiar_contrasena_propio)
        btn_cambiar.pack(side="right", padx=(14, 0))
        btn_cambiar.bind("<Enter>", lambda e: btn_cambiar.config(bg="#0E4D86"))
        btn_cambiar.bind("<Leave>", lambda e: btn_cambiar.config(bg=E.AZUL_OSCURO))

        btn_salir = tk.Button(der, text="Cerrar sesion", bg=E.AZUL_OSCURO,
                              fg=E.TEXTO_BLANCO, font=(E.FUENTE, 9, "bold"),
                              relief="flat", cursor="hand2", bd=0,
                              activebackground="#0E4D86",
                              activeforeground=E.TEXTO_BLANCO,
                              padx=12, pady=6, command=self._cerrar_sesion)
        btn_salir.pack(side="right", padx=(14, 0))
        btn_salir.bind("<Enter>", lambda e: btn_salir.config(bg="#0E4D86"))
        btn_salir.bind("<Leave>", lambda e: btn_salir.config(bg=E.AZUL_OSCURO))

        info = tk.Frame(der, bg=E.AZUL)
        info.pack(side="right", padx=(14, 0))
        tk.Label(info, text=self.usuario, bg=E.AZUL, fg=E.TEXTO_BLANCO,
                 font=(E.FUENTE, 10, "bold")).pack(anchor="e")
        tk.Label(info, text=self.rol.capitalize(), bg=E.AZUL, fg="#CFE4F5",
                 font=(E.FUENTE, 9)).pack(anchor="e")

        # Indicador de actualizacion (punto + texto)
        ind = tk.Frame(der, bg=E.AZUL)
        ind.pack(side="right", padx=(0, 4))
        self.dot = tk.Canvas(ind, width=12, height=12, bg=E.AZUL,
                             highlightthickness=0, bd=0)
        self.dot.pack(side="left", padx=(0, 6), pady=2)
        self._dibujar_punto(E.VERDE)
        self.lbl_indicador = tk.Label(
            ind, text="Iniciando...", bg=E.AZUL, fg="#E6F1FB",
            font=(E.FUENTE, 9))
        self.lbl_indicador.pack(side="left")

        # Centro: empresa activa (encima de la barra, centrado)
        self.lbl_empresa = tk.Label(
            header, text=self.empresa, bg=E.AZUL, fg=E.TEXTO_BLANCO,
            font=(E.FUENTE, 13, "bold"))
        self.lbl_empresa.place(relx=0.5, rely=0.5, anchor="center")

        # Linea de acento roja
        tk.Frame(self.root, bg=E.ROJO, height=3).pack(fill="x")

        # ---------- CUERPO: menu lateral + contenido ----------
        cuerpo = tk.Frame(self.root, bg=E.FONDO)
        cuerpo.pack(fill="both", expand=True)

        self.menu = tk.Frame(cuerpo, bg=E.BLANCO, width=210)
        self.menu.pack(side="left", fill="y")
        self.menu.pack_propagate(False)
        tk.Frame(self.menu, bg=E.BORDE_SUAVE, width=1).pack(side="right",
                                                            fill="y")
        self._construir_menu()

        self.contenido = tk.Frame(cuerpo, bg=E.FONDO)
        self.contenido.pack(side="left", fill="both", expand=True)

    def _dibujar_punto(self, color):
        self.dot.delete("all")
        self.dot.create_oval(1, 1, 11, 11, fill=color, outline="")

    def _construir_menu(self):
        tk.Label(self.menu, text="MENU", bg=E.BLANCO, fg=E.TEXTO_TENUE,
                 font=(E.FUENTE, 8, "bold")).pack(anchor="w", padx=18,
                                                  pady=(16, 8))
        for nombre in MODULOS:
            if not puede_ver(self.rol, nombre):
                continue
            b = tk.Button(self.menu, text="   " + nombre, anchor="w",
                          bg=E.BLANCO, fg=E.TEXTO, font=(E.FUENTE, 11),
                          relief="flat", bd=0, cursor="hand2",
                          activebackground=E.HOVER, activeforeground=E.AZUL,
                          padx=10, pady=10,
                          command=lambda n=nombre: self._mostrar_modulo(n))
            b.pack(fill="x")
            b.bind("<Enter>", lambda e, x=nombre: self._hover(x, True))
            b.bind("<Leave>", lambda e, x=nombre: self._hover(x, False))
            self.botones_menu[nombre] = b

    def _hover(self, nombre, entra):
        b = self.botones_menu.get(nombre)
        if not b:
            return
        if nombre == self.modulo_actual:
            return
        b.config(bg=E.HOVER if entra else E.BLANCO)

    def _resaltar_activo(self):
        for nombre, b in self.botones_menu.items():
            if nombre == self.modulo_actual:
                b.config(bg=E.AZUL, fg=E.TEXTO_BLANCO,
                         font=(E.FUENTE, 11, "bold"))
            else:
                b.config(bg=E.BLANCO, fg=E.TEXTO, font=(E.FUENTE, 11))

    # ------------------------------------------------------------------
    def _mostrar_modulo(self, nombre):
        if not puede_ver(self.rol, nombre):
            return
        self.modulo_actual = nombre
        self._resaltar_activo()
        # Detener el modulo anterior si tiene limpieza (hilos, etc.)
        if self.modulo_obj is not None and hasattr(self.modulo_obj, "detener"):
            try:
                self.modulo_obj.detener()
            except Exception:
                pass
        self.modulo_obj = None
        for w in self.contenido.winfo_children():
            w.destroy()

        if nombre == "Inventario":
            self.modulo_obj = ModuloInventario(
                self.contenido, rol=self.rol,
                indicador_cb=self.actualizar_indicador)
        elif nombre == "Ventas":
            self.modulo_obj = ModuloVentas(
                self.contenido, rol=self.rol,
                indicador_cb=self.actualizar_indicador)
        elif nombre == "Rentabilidad y Rotacion":
            self.modulo_obj = ModuloRentabilidad(
                self.contenido, rol=self.rol,
                indicador_cb=self.actualizar_indicador)
        elif nombre == "Produccion":
            self.modulo_obj = ModuloProduccion(
                self.contenido, rol=self.rol, usuario=self.usuario,
                indicador_cb=self.actualizar_indicador)
        elif nombre == "Proyeccion":
            self.modulo_obj = ModuloProyeccion(
                self.contenido, rol=self.rol,
                indicador_cb=self.actualizar_indicador)
        elif nombre == "Pocas Unidades":
            self.modulo_obj = ModuloPocasUnidades(
                self.contenido, rol=self.rol,
                indicador_cb=self.actualizar_indicador)
        elif nombre == "Historial":
            self.modulo_obj = ModuloHistorial(
                self.contenido, rol=self.rol,
                indicador_cb=self.actualizar_indicador)
        elif nombre == "Usuarios":
            self.modulo_obj = ModuloUsuarios(
                self.contenido, rol=self.rol, usuario=self.usuario,
                indicador_cb=self.actualizar_indicador)
        elif nombre == "Reportes":
            self.modulo_obj = ModuloReportes(
                self.contenido, rol=self.rol, usuario=self.usuario,
                empresa=self.empresa,
                indicador_cb=self.actualizar_indicador)
        else:
            self._placeholder(nombre)

    def _placeholder(self, nombre):
        cont = tk.Frame(self.contenido, bg=E.FONDO)
        cont.pack(fill="both", expand=True)
        tk.Label(cont, text=nombre, bg=E.FONDO, fg=E.TEXTO,
                 font=(E.FUENTE, 20, "bold")).pack(pady=(80, 8))
        tk.Label(cont, text="Este modulo se construye en una proxima fase.",
                 bg=E.FONDO, fg=E.TEXTO_SUB,
                 font=(E.FUENTE, 11)).pack()

    # ------------------------------------------------------------------
    def actualizar_indicador(self, texto, conectado=True):
        """Lo llama el modulo para reflejar el estado de actualizacion."""
        try:
            self.lbl_indicador.config(text=texto)
            self._dibujar_punto(E.VERDE if conectado else E.ROJO)
        except tk.TclError:
            pass

    def _cambiar_contrasena_propio(self):
        from tkinter import simpledialog, messagebox
        import seguridad
        import base_propia
        import auditoria
        dlg = tk.Toplevel(self.root, bg="#EEF2F6")
        dlg.title("Cambiar mi contrasena")
        dlg.resizable(False, False)
        try:
            dlg.transient(self.root)
        except tk.TclError:
            pass
        tk.Label(dlg, text="Cambiar mi contrasena", bg="#EEF2F6",
                 fg="#1A2A38", font=("Segoe UI", 13, "bold")).pack(
                     padx=24, pady=(18,4))
        tk.Label(dlg, text="Usuario: " + self.usuario, bg="#EEF2F6",
                 fg="#5A7286", font=("Segoe UI", 10)).pack(padx=24)
        form = tk.Frame(dlg, bg="#EEF2F6")
        form.pack(padx=24, pady=12)
        vars_ = {}
        for i, (etq, clave) in enumerate([
                ("Contrasena actual", "actual"),
                ("Nueva contrasena",  "nueva"),
                ("Confirmar nueva",   "conf")]):
            tk.Label(form, text=etq+":", bg="#EEF2F6", fg="#5A7286",
                     font=("Segoe UI",10)).grid(row=i, column=0, sticky="w", pady=4)
            v = tk.StringVar()
            tk.Entry(form, textvariable=v, width=24, show="*",
                     font=("Segoe UI",10), relief="solid", bd=1).grid(
                         row=i, column=1, pady=4, padx=(8,0))
            vars_[clave] = v
        def guardar():
            actual = vars_["actual"].get()
            nueva  = vars_["nueva"].get()
            conf   = vars_["conf"].get()
            res = seguridad.verificar(self.usuario, actual)
            if not res.get("ok"):
                messagebox.showwarning("Contrasena",
                    "La contrasena actual no es correcta.", parent=dlg)
                return
            if not nueva:
                messagebox.showwarning("Contrasena",
                    "La nueva contrasena no puede estar vacia.", parent=dlg)
                return
            if nueva != conf:
                messagebox.showwarning("Contrasena",
                    "Las contrasenas nuevas no coinciden.", parent=dlg)
                return
            salt, hash_c = seguridad.generar_hash(nueva)
            con = base_propia.conectar()
            cur = con.cursor()
            cur.execute("UPDATE usuarios SET hash_contrasena=?, salt=? "
                        "WHERE nombre=?", (hash_c, salt, self.usuario))
            con.commit()
            con.close()
            auditoria.registrar(self.usuario, "CAMBIO_CONTRASENA",
                                "Cambio de contrasena propio")
            dlg.destroy()
            messagebox.showinfo("Contrasena",
                                "Contrasena actualizada correctamente.")
        tk.Button(dlg, text="Guardar", bg="#1E6FB8", fg="#FFFFFF",
                  font=("Segoe UI",10,"bold"), relief="flat", bd=0,
                  cursor="hand2", padx=20, pady=7,
                  command=guardar).pack(pady=(0,18))
        dlg.update_idletasks()
        w=dlg.winfo_width(); h=dlg.winfo_height()
        sw=dlg.winfo_screenwidth(); sh=dlg.winfo_screenheight()
        dlg.geometry("+{}+{}".format(max(0,(sw-w)//2), max(0,(sh-h)//2)))
        dlg.grab_set()

    def _cerrar_sesion(self):
        from tkinter import messagebox
        if not messagebox.askyesno(
                "Cerrar sesion",
                "Seguro que desea cerrar la sesion de " + self.usuario + "?"):
            return
        if self.modulo_obj is not None and hasattr(self.modulo_obj, "detener"):
            try:
                self.modulo_obj.detener()
            except Exception:
                pass
        if callable(self.al_cerrar_sesion):
            self.al_cerrar_sesion()


if __name__ == "__main__":
    import os
    import sys
    DIR_UI = os.path.dirname(os.path.abspath(__file__))
    DIR_APP = os.path.dirname(DIR_UI)
    sys.path.insert(0, os.path.join(DIR_APP, "core"))
    sys.path.insert(0, DIR_UI)

    root = tk.Tk()
    root.state("zoomed")
    PantallaPrincipal(root, "INGENIERO DUVAN", "ADMINISTRADOR",
                      "FUTURE COMPANY",
                      al_cerrar_sesion=lambda: root.destroy())
    root.mainloop()
