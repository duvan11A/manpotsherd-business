# -*- coding: utf-8 -*-
"""
MPS REPORTS - Punto de entrada del programa
Flujo: arranque -> respaldo si corresponde -> login -> seleccion de
empresa -> (Fase 4: ventana principal).
La ventana funciona en pantalla completa (maximizada).
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox

DIR_APP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(DIR_APP, "core"))
sys.path.insert(0, os.path.join(DIR_APP, "ui"))

import base_propia
import respaldo
from login import PantallaLogin
from seleccion_empresa import PantallaSeleccionEmpresa
from principal import PantallaPrincipal
from inventario_store import store


class App:
    def __init__(self):
        base_propia.inicializar_base()
        try:
            respaldo.respaldar_si_corresponde()
        except Exception:
            pass

        self.root = tk.Tk()
        self._pantalla_completa()
        store.iniciar(self.root)

        self.usuario = None
        self.rol = None
        self.empresa = None
        self._mostrar_login()

    def _pantalla_completa(self):
        """Maximiza la ventana. Esc no la cierra; se usa el flujo normal."""
        try:
            self.root.state("zoomed")          # Windows: maximizada
        except tk.TclError:
            # Por si el sistema no soporta 'zoomed'
            self.root.attributes("-zoomed", True)
        self.root.configure(bg="#EEF2F6")

    def _limpiar(self):
        for w in self.root.winfo_children():
            w.destroy()

    def _mostrar_login(self):
        # Al volver al login se limpia la sesion anterior
        self.usuario = None
        self.rol = None
        self.empresa = None
        self._limpiar()
        PantallaLogin(self.root, self._tras_login)

    def _tras_login(self, usuario, rol):
        self.usuario = usuario
        self.rol = rol
        # Empezar a cargar el inventario en segundo plano ya, para que al
        # entrar a la empresa el inventario aparezca de una.
        store.precargar()
        self._mostrar_seleccion_empresa()

    def _mostrar_seleccion_empresa(self):
        self._limpiar()
        PantallaSeleccionEmpresa(
            self.root, self.usuario, self.rol, self._tras_empresa,
            al_cerrar_sesion=self._mostrar_login)

    def _tras_empresa(self, empresa):
        self.empresa = empresa
        self._limpiar()
        self.pantalla = PantallaPrincipal(
            self.root, self.usuario, self.rol, self.empresa,
            al_cerrar_sesion=self._mostrar_login)

    def ejecutar(self):
        self.root.mainloop()


if __name__ == "__main__":
    App().ejecutar()
