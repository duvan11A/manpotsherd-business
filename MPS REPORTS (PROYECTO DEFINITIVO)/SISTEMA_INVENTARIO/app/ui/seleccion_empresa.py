# -*- coding: utf-8 -*-
"""
MPS REPORTS - Pantalla de seleccion de empresa (Fase 3)
Diseno profesional ordenado: header con identidad y usuario, titulo
integrado con subtitulo, y dos tarjetas balanceadas con icono, estado,
descripcion y boton. Las tarjetas se dibujan con Pillow (redondeadas,
con sombra). El logo de la empresa va dentro de un circulo superior.
"""

import os
import json
import tkinter as tk
from tkinter import messagebox

import estilo as E

DIR_UI = os.path.dirname(os.path.abspath(__file__))
DIR_APP = os.path.dirname(DIR_UI)
DIR_RAIZ = os.path.dirname(DIR_APP)
RUTA_CONFIG = os.path.join(DIR_RAIZ, "config", "config.json")

DIR_LOGOS = os.path.join(E.DIR_IMAGES, "LOGOS")
LOGOS = {
    "FUTURE COMPANY": "futurecompanylogo.png",
    "JAIME DUQUE": "jaimeduque.png",
}

# Descripcion de cada tarjeta segun estado
DESC_ACTIVA = "Acceda a los reportes, indicadores y\nanalisis correspondientes a esta empresa."
DESC_DESARROLLO = "Esta empresa se encuentra en proceso\nde configuracion y desarrollo."

TARJ_W = 380
TARJ_H = 660


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


class PantallaSeleccionEmpresa:
    def __init__(self, root, usuario, rol, al_seleccionar, al_cerrar_sesion=None):
        self.root = root
        self.usuario = usuario
        self.rol = rol
        self.al_seleccionar = al_seleccionar
        self.al_cerrar_sesion = al_cerrar_sesion
        self._refs = []
        self.root.title(E.NOMBRE_SISTEMA + " - Seleccion de empresa")
        self.root.configure(bg=E.FONDO)
        self._cargar_empresas()
        self._construir()

    def _cargar_empresas(self):
        try:
            with open(RUTA_CONFIG, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            self.empresas = cfg.get("empresas", {})
        except Exception:
            self.empresas = {}

    def _construir(self):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()

        # ---------- HEADER ----------
        header = tk.Frame(self.root, bg=E.AZUL, height=78)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Icono + nombre + subtitulo (izquierda)
        izq = tk.Frame(header, bg=E.AZUL)
        izq.pack(side="left", padx=26, pady=12)
        self._icono_logo(izq)
        textos = tk.Frame(izq, bg=E.AZUL)
        textos.pack(side="left", padx=12)
        tk.Label(textos, text=E.NOMBRE_SISTEMA, bg=E.AZUL, fg=E.TEXTO_BLANCO,
                 font=(E.FUENTE, 18, "bold")).pack(anchor="w")
        tk.Label(textos, text="SELECCION DE EMPRESA", bg=E.AZUL, fg="#CFE4F5",
                 font=(E.FUENTE, 8, "bold")).pack(anchor="w")

        # Usuario + cerrar sesion (derecha)
        der = tk.Frame(header, bg=E.AZUL)
        der.pack(side="right", padx=26)

        self._icono_usuario(der)  # mas a la derecha

        info = tk.Frame(der, bg=E.AZUL)
        info.pack(side="right", padx=(0, 4))
        tk.Label(info, text="Usuario: " + self.usuario, bg=E.AZUL,
                 fg=E.TEXTO_BLANCO, font=(E.FUENTE, 10, "bold")).pack(anchor="e")
        tk.Label(info, text=self.rol.capitalize(), bg=E.AZUL, fg="#CFE4F5",
                 font=(E.FUENTE, 9)).pack(anchor="e")

        # Separador vertical sutil
        tk.Frame(der, bg="#3F86C4", width=1, height=40).pack(side="right", padx=18)

        # Boton CERRAR SESION
        btn_salir = tk.Button(der, text="Cerrar sesion", bg=E.AZUL2,
                              fg=E.TEXTO_BLANCO, font=(E.FUENTE, 10, "bold"),
                              relief="flat", cursor="hand2", bd=0,
                              activebackground="#0E4D86", activeforeground=E.TEXTO_BLANCO,
                              padx=16, pady=8, command=self._cerrar_sesion)
        btn_salir.pack(side="right")
        btn_salir.bind("<Enter>", lambda e: btn_salir.config(bg="#0E4D86"))
        btn_salir.bind("<Leave>", lambda e: btn_salir.config(bg=E.AZUL2))

        tk.Frame(self.root, bg=E.ROJO, height=3).pack(fill="x")

        # ---------- AREA CON FONDO ----------
        alto_area = sh - 81
        self.canvas = tk.Canvas(self.root, highlightthickness=0, bd=0)
        self.canvas.pack(expand=True, fill="both")
        self.bg_img = E.imagen_fondo(sw, alto_area)
        if self.bg_img is not None:
            self.canvas.create_image(0, 0, image=self.bg_img, anchor="nw")
        else:
            self.canvas.configure(bg=E.FONDO)

        cx = sw // 2

        # Titulo (azul oscuro, limpio) + linea azul corta + subtitulo
        ty = int(alto_area * 0.13)
        self.canvas.create_text(cx, ty, text="Seleccione la empresa con la cual desea trabajar",
                                font=(E.FUENTE, 24, "bold"), fill="#0E4D86")
        self.canvas.create_rectangle(cx - 70, ty + 24, cx + 70, ty + 27,
                                     fill=E.AZUL2, outline="")
        self.canvas.create_text(cx, ty + 50,
                                text="Elija la empresa para acceder a los reportes y analisis correspondientes.",
                                font=(E.FUENTE, 11), fill=E.TEXTO_SUB)

        # Tarjetas
        empresas = list(self.empresas.items())
        n = len(empresas)
        sep = 50
        total = n * TARJ_W + (n - 1) * sep
        x0 = cx - total // 2 + TARJ_W // 2
        y_centro = int(alto_area * 0.56)
        for i, (nombre, datos) in enumerate(empresas):
            x = x0 + i * (TARJ_W + sep)
            self._tarjeta(x, y_centro, nombre, datos.get("estado", ""))

    # ---------- Iconos del header ----------
    def _icono_logo(self, padre):
        """Icono de barras (logo del sistema) dibujado con Pillow."""
        from PIL import Image, ImageDraw, ImageTk
        esc = 2
        s = 40 * esc
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, s-1, s-1], radius=8*esc, fill=(255, 255, 255, 40))
        # barras
        cols = [(0.22, 0.55), (0.40, 0.35), (0.58, 0.60), (0.76, 0.25)]
        for fx, fh in cols:
            x = int(s * fx)
            h = int(s * fh)
            d.rectangle([x, s - h - 6*esc, x + int(s*0.10), s - 6*esc],
                        fill=(255, 255, 255, 255))
        img = img.resize((40, 40), Image.LANCZOS)
        foto = ImageTk.PhotoImage(img)
        self._refs.append(foto)
        tk.Label(padre, image=foto, bg=E.AZUL).pack(side="left")

    def _icono_usuario(self, padre):
        from PIL import Image, ImageDraw, ImageTk
        esc = 2
        s = 42 * esc
        img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([0, 0, s-1, s-1], fill=(255, 255, 255, 230))
        # cabeza y cuerpo
        d.ellipse([s*0.32, s*0.20, s*0.68, s*0.52], fill=_rgb(E.AZUL))
        d.pieslice([s*0.18, s*0.55, s*0.82, s*1.10], 180, 360, fill=_rgb(E.AZUL))
        img = img.resize((42, 42), Image.LANCZOS)
        foto = ImageTk.PhotoImage(img)
        self._refs.append(foto)
        tk.Label(padre, image=foto, bg=E.AZUL).pack(side="right", padx=(0, 14))

    # ---------- Tarjeta ----------
    def _tarjeta(self, cx, cy, nombre, estado):
        activa = (estado.upper() == "ACTIVA")
        img = self._dibujar_tarjeta(nombre, activa)
        self.canvas.create_image(cx, cy, image=img)
        self._refs.append(img)

        # Boton como widget
        by = cy + TARJ_H // 2 - 56
        if activa:
            btn = tk.Button(self.canvas, text="INGRESAR  \u2192", bg=E.AZUL,
                            fg=E.TEXTO_BLANCO, font=(E.FUENTE, 12, "bold"),
                            relief="flat", cursor="hand2", activebackground=E.AZUL2,
                            activeforeground=E.TEXTO_BLANCO, pady=10, bd=0,
                            command=lambda: self._elegir(nombre))
            btn.bind("<Enter>", lambda e: btn.config(bg=E.AZUL2))
            btn.bind("<Leave>", lambda e: btn.config(bg=E.AZUL))
            self.canvas.create_window(cx, by, window=btn, width=TARJ_W - 110)
            zona = self.canvas.create_rectangle(
                cx - TARJ_W//2 + 16, cy - TARJ_H//2 + 16,
                cx + TARJ_W//2 - 16, by - 26, fill="", outline="")
            self.canvas.tag_bind(zona, "<Button-1>", lambda e: self._elegir(nombre))
        else:
            btn = tk.Button(self.canvas, text="NO DISPONIBLE", bg=E.GRIS_DESHAB,
                            fg=E.TEXTO_BLANCO, font=(E.FUENTE, 12, "bold"),
                            relief="flat", state="disabled", pady=10, bd=0)
            self.canvas.create_window(cx, by, window=btn, width=TARJ_W - 110)

    def _dibujar_tarjeta(self, nombre, activa):
        from PIL import ImageTk
        base = self._componer_tarjeta(nombre, activa)
        return ImageTk.PhotoImage(base)

    def _componer_tarjeta(self, nombre, activa):
        from PIL import Image, ImageDraw, ImageFilter
        esc = 2
        W, H = TARJ_W * esc, TARJ_H * esc
        radio = 18 * esc
        margen = 14 * esc

        base = Image.new("RGBA", (W, H), (0, 0, 0, 0))

        # Sombra
        sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sombra).rounded_rectangle(
            [margen + 4, margen + 7, W - margen + 4, H - margen + 7],
            radius=radio, fill=(20, 45, 75, 70))
        sombra = sombra.filter(ImageFilter.GaussianBlur(7 * esc))
        base = Image.alpha_composite(base, sombra)

        # Cuerpo blanco con borde
        cuerpo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dc = ImageDraw.Draw(cuerpo)
        borde = _rgb(E.AZUL) if activa else _rgb(E.GRIS_DESHAB)
        dc.rounded_rectangle([margen, margen, W - margen, H - margen],
                             radius=radio, fill=(255, 255, 255, 255),
                             outline=borde + (255,), width=2 * esc)
        base = Image.alpha_composite(base, cuerpo)

        # Barra superior de color SOLO en la tarjeta activa (como tu diseno)
        if activa:
            barra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            db = ImageDraw.Draw(barra)
            db.rounded_rectangle([margen, margen, W - margen, margen + 14 * esc],
                                 radius=radio, fill=_rgb(E.AZUL) + (255,))
            db.rectangle([margen, margen + 8 * esc, W - margen, margen + 14 * esc],
                         fill=_rgb(E.AZUL) + (255,))
            mascara = Image.new("L", (W, H), 0)
            ImageDraw.Draw(mascara).rounded_rectangle(
                [margen, margen, W - margen, H - margen], radius=radio, fill=255)
            recorte = Image.composite(barra, Image.new("RGBA", (W, H), (0,0,0,0)), mascara)
            base = Image.alpha_composite(base, recorte)

        # Zona del logo (SIN circulo de fondo, logo grande y centrado)
        cxi = W // 2
        logo_cy = margen + 92 * esc

        # Logo grande (si existe), si no, un icono de edificio
        logo = self._cargar_logo_pil(nombre, max_w=int(W * 0.62), max_h=150 * esc)
        if logo is not None:
            lw, lh = logo.size
            base.alpha_composite(logo, (cxi - lw // 2, logo_cy - lh // 2))
        else:
            # Icono de edificio simple (azul/gris) sin circulo
            self._icono_edificio_color(base, cxi, logo_cy, 70 * esc,
                                       _rgb(E.AZUL) if activa else _rgb("#A9B7C4"))

        # Nombre de la empresa (mas grande)
        nombre_completo = nombre + (" SAS" if nombre == "FUTURE COMPANY" else "")
        ny = logo_cy + 90 * esc
        self._texto_centrado(base, nombre_completo, ny,
                              _rgb(E.TEXTO) if activa else _rgb(E.TEXTO_TENUE),
                              25 * esc, W, bold=True)

        # Linea divisoria
        ly = ny + 44 * esc
        ImageDraw.Draw(base).line([margen + 40 * esc, ly, W - margen - 40 * esc, ly],
                                  fill=_rgb(E.BORDE_SUAVE) + (255,), width=1 * esc)

        # Estado con puntico (mas grande)
        ey = ly + 24 * esc
        punto_color = _rgb(E.VERDE) if activa else _rgb(E.NARANJA)
        texto_estado = "EMPRESA ACTIVA" if activa else "EN PROCESO DE DESARROLLO"
        self._estado_con_punto(base, texto_estado, ey, punto_color,
                               14 * esc, W, esc)

        # Descripcion (mas grande)
        desc = DESC_ACTIVA if activa else DESC_DESARROLLO
        dy = ey + 36 * esc
        for linea in desc.split("\n"):
            self._texto_centrado(base, linea, dy, _rgb(E.TEXTO_SUB), 12 * esc, W)
            dy += 24 * esc

        # ----- Bloque que llena el espacio: modulos incluidos -----
        sep_y = dy + 14 * esc
        ImageDraw.Draw(base).line(
            [margen + 40 * esc, sep_y, W - margen - 40 * esc, sep_y],
            fill=_rgb(E.BORDE_SUAVE) + (255,), width=1 * esc)

        etiqueta = "MODULOS INCLUIDOS" if activa else "MODULOS PREVISTOS"
        ety = sep_y + 16 * esc
        self._texto_centrado(base, etiqueta, ety,
                             _rgb(E.AZUL) if activa else _rgb(E.TEXTO_TENUE),
                             11 * esc, W, bold=True)

        items = [
            "Inventario en tiempo real",
            "Ventas por periodo",
            "Rentabilidad y rotacion",
            "Produccion y proyeccion",
            "Exportacion a Excel y PDF",
        ]
        self._lista_modulos(base, items, ety + 32 * esc, W, esc, activa)

        base = base.resize((TARJ_W, TARJ_H), Image.LANCZOS)
        return base

    def _lista_modulos(self, base, items, y, W, esc, activa):
        """Lista de modulos con palomita, alineada a la izquierda dentro
        de la tarjeta. Llena el espacio inferior de forma util."""
        from PIL import ImageDraw
        d = ImageDraw.Draw(base)
        fuente = self._fuente(12 * esc, bold=False)
        x_check = int(W * 0.16)
        x_text = x_check + 22 * esc
        col_check = _rgb(E.AZUL) if activa else _rgb("#B6C2CE")
        col_text = _rgb(E.TEXTO) if activa else _rgb(E.TEXTO_TENUE)
        paso = 30 * esc
        for i, it in enumerate(items):
            cy = y + i * paso
            r = 8 * esc
            mid = cy + 8 * esc
            # circulo suave de fondo
            d.ellipse([x_check - r, mid - r, x_check + r, mid + r],
                      fill=col_check + (38,))
            # palomita
            d.line([x_check - 4 * esc, mid, x_check - 1 * esc, mid + 3 * esc],
                   fill=col_check + (255,), width=2 * esc)
            d.line([x_check - 1 * esc, mid + 3 * esc, x_check + 4 * esc, mid - 3 * esc],
                   fill=col_check + (255,), width=2 * esc)
            d.text((x_text, cy), it, fill=col_text + (255,), font=fuente)

    def _icono_edificio_color(self, base, cx, cy, r, color):
        from PIL import ImageDraw
        d = ImageDraw.Draw(base)
        w = int(r * 1.1)
        h = int(r * 1.5)
        x0, y0 = cx - w//2, cy - h//2
        d.rectangle([x0, y0, x0 + w, y0 + h], fill=color + (255,))
        # ventanitas blancas
        pad = w // 6
        for fila in range(4):
            for col in range(2):
                vx = x0 + pad + col * (w//2)
                vy = y0 + pad + fila * (h//5)
                d.rectangle([vx, vy, vx + w//6, vy + h//10],
                            fill=(255, 255, 255, 255))

    def _cargar_logo_pil(self, nombre, max_w, max_h):
        archivo = LOGOS.get(nombre)
        ruta = os.path.join(DIR_LOGOS, archivo) if archivo else None
        if not (ruta and os.path.exists(ruta)):
            return None
        try:
            from PIL import Image
            img = Image.open(ruta).convert("RGBA")
            img.thumbnail((max_w, max_h), Image.LANCZOS)
            return img
        except Exception:
            return None

    def _texto_centrado(self, base, texto, y, color, tam, W, bold=False):
        from PIL import ImageDraw
        d = ImageDraw.Draw(base)
        fuente = self._fuente(tam, bold)
        try:
            bbox = d.textbbox((0, 0), texto, font=fuente)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(texto) * tam // 2
        d.text(((W - tw) // 2, y), texto, fill=color + (255,), font=fuente)

    def _estado_con_punto(self, base, texto, y, color, tam, W, esc):
        from PIL import ImageDraw
        d = ImageDraw.Draw(base)
        fuente = self._fuente(tam, bold=True)
        try:
            bbox = d.textbbox((0, 0), texto, font=fuente)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(texto) * tam // 2
        rp = 5 * esc
        total = rp * 2 + 8 * esc + tw
        x0 = (W - total) // 2
        d.ellipse([x0, y + tam//2 - rp, x0 + rp*2, y + tam//2 + rp], fill=color + (255,))
        d.text((x0 + rp*2 + 8*esc, y), texto, fill=color + (255,), font=fuente)

    def _fuente(self, tam, bold):
        from PIL import ImageFont
        candidatos = [
            "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for c in candidatos:
            try:
                return ImageFont.truetype(c, tam)
            except Exception:
                continue
        return ImageFont.load_default()

    def _elegir(self, nombre):
        self.al_seleccionar(nombre)

    def _cerrar_sesion(self):
        if not messagebox.askyesno(
                "Cerrar sesion",
                "Seguro que desea cerrar la sesion de " + self.usuario + "?\n\n"
                "Volvera a la pantalla de inicio de sesion."):
            return
        if callable(self.al_cerrar_sesion):
            self.al_cerrar_sesion()
        else:
            # Respaldo: si no se conecto el callback, limpiar la pantalla
            for w in self.root.winfo_children():
                w.destroy()
            messagebox.showinfo(
                "Sesion cerrada",
                "La sesion fue cerrada. Vuelva a abrir el programa para ingresar.")

    def _aviso(self, nombre):
        messagebox.showinfo(
            "Empresa en desarrollo",
            "La empresa {} aun no esta disponible.\n\n"
            "Se encuentra en proceso de desarrollo.".format(nombre))


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(DIR_APP, "core"))

    def elegida(nombre):
        messagebox.showinfo("Empresa elegida", "Entrando a: " + nombre)

    def cerrar():
        messagebox.showinfo("Cerrar sesion", "Aqui main.py mostraria de nuevo el login.")

    root = tk.Tk()
    root.state("zoomed")
    PantallaSeleccionEmpresa(root, "INGENIERO DUVAN", "ADMINISTRADOR",
                             elegida, al_cerrar_sesion=cerrar)
    root.mainloop()
