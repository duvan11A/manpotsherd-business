# -*- coding: utf-8 -*-
"""
MPS REPORTS - Exportacion a PDF (Fase 9)
Genera un .pdf con reportlab en orientacion horizontal.
Mismo contenido que el Excel: encabezado + tabla por modulo.
"""

from datetime import datetime

try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer, PageBreak)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

AZUL  = colors.HexColor("#1E6FB8")
AZUL2 = colors.HexColor("#2E89D6")
ROJO  = colors.HexColor("#D14545")
GRIS  = colors.HexColor("#EEF2F6")
GRIS2 = colors.HexColor("#F1F6FA")
TEXTO = colors.HexColor("#1A2A38")
BLANCO = colors.white


def exportar(ruta, empresa, usuario, pestanas):
    if not REPORTLAB_OK:
        raise ImportError("reportlab no esta instalado. "
                          "Instala con: pip install reportlab")

    doc = SimpleDocTemplate(
        ruta,
        pagesize=landscape(A4),
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    estilos = getSampleStyleSheet()
    st_titulo = ParagraphStyle("titulo", fontName="Helvetica-Bold",
                               fontSize=14, textColor=BLANCO,
                               alignment=TA_CENTER)
    st_sub    = ParagraphStyle("sub", fontName="Helvetica-Bold",
                               fontSize=10, textColor=BLANCO,
                               alignment=TA_CENTER)
    st_info   = ParagraphStyle("info", fontName="Helvetica-Oblique",
                               fontSize=8, textColor=colors.HexColor("#5A7286"),
                               alignment=TA_CENTER)
    st_normal = ParagraphStyle("norm", fontName="Helvetica",
                               fontSize=8, textColor=TEXTO)

    fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
    historia = []

    for i, p in enumerate(pestanas):
        if i > 0:
            historia.append(PageBreak())

        cols   = p["columnas"]
        filas  = p["filas"]
        modulo = p["modulo"]

        # Encabezado
        ancho_pagina = landscape(A4)[0] - 3*cm
        enc_data = [
            [Paragraph("MPS REPORTS - " + empresa, st_titulo)],
            [Paragraph(modulo.upper(), st_sub)],
            [Paragraph("Generado: {}   |   Usuario: {}".format(
                fecha_hora, usuario), st_info)],
        ]
        enc_style = TableStyle([
            ("BACKGROUND", (0,0), (-1,0), AZUL),
            ("BACKGROUND", (0,1), (-1,1), AZUL2),
            ("BACKGROUND", (0,2), (-1,2), GRIS),
            ("TOPPADDING",    (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ("GRID", (0,0), (-1,-1), 0, BLANCO),
        ])
        t_enc = Table(enc_data, colWidths=[ancho_pagina])
        t_enc.setStyle(enc_style)
        historia.append(t_enc)
        historia.append(Spacer(1, 0.3*cm))

        if not filas:
            historia.append(Paragraph("Sin datos para mostrar.", st_normal))
            continue

        # Calcular anchos de columna proporcionales
        n = len(cols)
        col_w = [ancho_pagina / n] * n

        # Tabla de datos
        datos = [cols] + [[str(v) if v is not None else "" for v in fila]
                          for fila in filas]
        t_datos = Table(datos, colWidths=col_w, repeatRows=1)
        estilo_tabla = TableStyle([
            # Encabezado
            ("BACKGROUND",   (0,0), (-1,0), AZUL),
            ("TEXTCOLOR",    (0,0), (-1,0), BLANCO),
            ("FONTNAME",     (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",     (0,0), (-1,0), 8),
            ("ALIGN",        (0,0), (-1,0), "CENTER"),
            ("TOPPADDING",   (0,0), (-1,0), 5),
            ("BOTTOMPADDING",(0,0), (-1,0), 5),
            # Filas de datos
            ("FONTNAME",     (0,1), (-1,-1), "Helvetica"),
            ("FONTSIZE",     (0,1), (-1,-1), 7),
            ("TOPPADDING",   (0,1), (-1,-1), 3),
            ("BOTTOMPADDING",(0,1), (-1,-1), 3),
            ("ROWBACKGROUNDS",(0,1),(-1,-1), [BLANCO, GRIS2]),
            ("GRID",         (0,0), (-1,-1), 0.3,
             colors.HexColor("#B9CCDD")),
            ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ])
        t_datos.setStyle(estilo_tabla)
        historia.append(t_datos)

    doc.build(historia)
    return ruta
