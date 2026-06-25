# -*- coding: utf-8 -*-
"""
MPS REPORTS - Almacen compartido del inventario (Fase 4)

Mantiene EN MEMORIA el inventario cargado una sola vez, de modo que
cambiar de pestana y volver no obligue a recargar. Se encarga ademas de:
  - precargar en segundo plano desde el login (para entrar rapido),
  - auto-refrescar cada 15 min SOLO si Business cambio (firma),
  - avisar a la pantalla que este mirando, con progreso y resumen.

La pantalla de inventario solo se "asoma" a este almacen; no carga datos
por su cuenta. Asi la barra de carga aparece una sola vez (la primera).
"""

import threading
from datetime import datetime

import inventario_datos as ID


class _Store:
    def __init__(self):
        self.data = None              # ultimo info de obtener_inventario (ok)
        self.cargando = False
        self.root = None              # para programar after() en el hilo UI
        self.ultimo_progreso = (0, "")
        self.ultima_carga = None      # datetime de la ultima carga exitosa
        self.subs = []                # callbacks de datos: cb(info, manual, resumen)
        self.subs_prog = []           # callbacks de progreso: cb(pct, mensaje)
        self._auto_job = None
        self._vivo = False

    # ---------------- ciclo de vida ----------------
    def iniciar(self, root):
        """Se llama una vez al arrancar la app (le da el root para after)."""
        self.root = root
        self._vivo = True

    def apagar(self):
        self._vivo = False
        self._cancelar_auto()

    # ---------------- suscripciones ----------------
    def suscribir(self, cb):
        if cb not in self.subs:
            self.subs.append(cb)

    def desuscribir(self, cb):
        if cb in self.subs:
            self.subs.remove(cb)

    def suscribir_progreso(self, cb):
        if cb not in self.subs_prog:
            self.subs_prog.append(cb)

    def desuscribir_progreso(self, cb):
        if cb in self.subs_prog:
            self.subs_prog.remove(cb)

    # ---------------- consultas ----------------
    def hay_datos(self):
        return self.data is not None and self.data.get("ok")

    def obtener(self):
        return self.data

    # ---------------- cargas ----------------
    def precargar(self):
        """Carga inicial en segundo plano. Idempotente."""
        if self.hay_datos() or self.cargando:
            return
        self._cargar(manual=False)

    def forzar_refresco(self):
        """Recarga manual (boton 'Actualizar ahora')."""
        if self.cargando:
            return
        self._cargar(manual=True)

    def _cargar(self, manual):
        if self.cargando:
            return
        self.cargando = True

        def trabajo():
            info = ID.obtener_inventario(progreso=self._emitir_progreso)
            self._marshal(lambda: self._aplicar(info, manual))

        threading.Thread(target=trabajo, daemon=True).start()

    def _aplicar(self, info, manual):
        self.cargando = False
        resumen = (0, 0)
        if info.get("ok"):
            if self.data and self.data.get("ok"):
                resumen = ID.resumen_cambios(self.data["filas"], info["filas"])
            self.data = info
            self.ultima_carga = datetime.now()
        for cb in list(self.subs):
            try:
                cb(info, manual, resumen)
            except Exception:
                pass
        if self._vivo:
            self._programar_auto()

    # ---------------- progreso ----------------
    def _emitir_progreso(self, pct, mensaje):
        # Llega desde el hilo de carga; se reenvia al hilo de UI.
        def fn():
            self.ultimo_progreso = (pct, mensaje)
            for cb in list(self.subs_prog):
                try:
                    cb(pct, mensaje)
                except Exception:
                    pass
        self._marshal(fn)

    # ---------------- auto-refresco ----------------
    def _intervalo_ms(self):
        try:
            minutos = int(ID._config("intervalo_actualizacion_min", 15))
        except (ValueError, TypeError):
            minutos = 15
        return max(1, minutos) * 60 * 1000

    def _programar_auto(self):
        self._cancelar_auto()
        if not self._vivo or self.root is None:
            return
        try:
            self._auto_job = self.root.after(self._intervalo_ms(),
                                             self._chequeo)
        except Exception:
            pass

    def _cancelar_auto(self):
        if self._auto_job is not None and self.root is not None:
            try:
                self.root.after_cancel(self._auto_job)
            except Exception:
                pass
        self._auto_job = None

    def _chequeo(self):
        """Cada 15 min: mira la firma; si cambio, recarga silencioso."""
        if not self._vivo:
            return

        def trabajo():
            try:
                import business_reader
                datos = business_reader.detectar_ruta()
                nueva = ID.firma_datos(datos) if datos else ""
            except Exception:
                nueva = ""
            actual = self.data["firma"] if self.hay_datos() else None
            if nueva and nueva != actual:
                self._cargar(manual=False)          # Business cambio
            elif not nueva:
                self._marshal(self._sin_conexion)    # sin conexion
            else:
                self._marshal(self._programar_auto)  # sin cambios

        threading.Thread(target=trabajo, daemon=True).start()

    def _sin_conexion(self):
        for cb in list(self.subs):
            try:
                cb({"ok": False, "error": "Sin conexion"}, False, (0, 0))
            except Exception:
                pass
        self._programar_auto()

    # ---------------- util ----------------
    def _marshal(self, fn):
        """Ejecuta fn en el hilo de la interfaz (Tkinter)."""
        if self.root is not None:
            try:
                self.root.after(0, fn)
                return
            except Exception:
                pass
        fn()


# Instancia unica compartida por toda la aplicacion
store = _Store()
