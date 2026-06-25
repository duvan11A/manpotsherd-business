# -*- coding: utf-8 -*-
"""
MPS REPORTS - Estilo visual compartido
Paleta corporativa oficial (seccion 7 de la documentacion), fuentes
y utilidades visuales (fondo de pantalla). Lo usan todas las pantallas
para mantener un aspecto consistente, tipo aplicacion de escritorio.
"""

import os
import tkinter as tk

# ----- Paleta oficial -----
AZUL          = "#1E6FB8"
AZUL2         = "#2E89D6"
AZUL_OSCURO   = "#155A96"
ROJO          = "#D14545"
VERDE         = "#1E9E6A"
NARANJA       = "#E08A2B"
FONDO         = "#EEF2F6"
BLANCO        = "#FFFFFF"
FILA_PAR      = "#FFFFFF"
FILA_IMPAR    = "#F1F6FA"
HOVER         = "#D6E8F7"
BORDE         = "#B9CCDD"
BORDE_SUAVE   = "#DDE6EE"
TEXTO         = "#1A2A38"
TEXTO_SUB     = "#5A7286"
TEXTO_TENUE   = "#8FA3B5"
TEXTO_BLANCO  = "#FFFFFF"
GRIS_DESHAB   = "#C7D2DC"

# ----- Fuentes -----
FUENTE = "Segoe UI"
F_TITULO     = (FUENTE, 18, "bold")
F_SUBTITULO  = (FUENTE, 13)
F_NORMAL     = (FUENTE, 10)
F_NORMAL_B   = (FUENTE, 10, "bold")
F_PEQUENA    = (FUENTE, 9)
F_GRANDE     = (FUENTE, 22, "bold")
F_KPI        = (FUENTE, 26, "bold")

# ----- Nombre del sistema -----
NOMBRE_SISTEMA = "MPS REPORTS"
SUBNOMBRE = "Sistema de Informes y Analisis"

# ----- Rutas de imagenes -----
DIR_UI = os.path.dirname(os.path.abspath(__file__))
DIR_IMAGES = os.path.join(DIR_UI, "images")
RUTA_FONDO = os.path.join(DIR_IMAGES, "fondo2.png")


def imagen_fondo(ancho, alto):
    """
    Devuelve un PhotoImage del fondo escalado a (ancho, alto), o None
    si no existe la imagen o no esta disponible Pillow.
    Mantener una referencia al resultado para que no lo borre el GC.
    """
    if not os.path.exists(RUTA_FONDO):
        return None
    try:
        from PIL import Image, ImageTk
        img = Image.open(RUTA_FONDO).convert("RGB")
        img = img.resize((max(1, ancho), max(1, alto)), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


def poner_fondo(contenedor, ancho, alto):
    """
    Coloca un Label con la imagen de fondo cubriendo el contenedor.
    Devuelve el Label (con .image guardada) o None si no hay imagen.
    """
    foto = imagen_fondo(ancho, alto)
    if foto is None:
        return None
    lbl = tk.Label(contenedor, image=foto, bg=FONDO, bd=0)
    lbl.image = foto  # evitar que el recolector de basura la borre
    lbl.place(x=0, y=0, relwidth=1, relheight=1)
    return lbl
