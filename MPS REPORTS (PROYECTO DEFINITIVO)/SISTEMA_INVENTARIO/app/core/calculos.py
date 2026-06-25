# -*- coding: utf-8 -*-
"""
MPS REPORTS - Calculos oficiales
SumaDirecta (inventario) y ventas por periodo.
Formulas definidas en las secciones 4.1 y 4.4 de la documentacion.
"""

from collections import defaultdict


def inventario_sumadirecta(movimientos):
    """
    Calcula el inventario por producto y bodega con la formula SumaDirecta
    (seccion 4.1, RN-02, RN-03):
        las entradas (MOV = E) suman, las salidas (MOV = S) restan.
    El documento AJUS cuenta como un movimiento normal segun su MOV.

    Devuelve un diccionario:
        { (codigo, bodega): stock, ... }
    """
    stock = defaultdict(float)
    for m in movimientos:
        clave = (m["CODIGO"], m["BODEGA"])
        if m["MOV"] == "E":
            stock[clave] += m["CANT"]
        elif m["MOV"] == "S":
            stock[clave] -= m["CANT"]
    return dict(stock)


def inventario_por_producto(movimientos):
    """
    Igual que SumaDirecta pero sumando TODAS las bodegas de cada producto.
    Devuelve un diccionario { codigo: stock_total }.
    """
    stock = defaultdict(float)
    for m in movimientos:
        if m["MOV"] == "E":
            stock[m["CODIGO"]] += m["CANT"]
        elif m["MOV"] == "S":
            stock[m["CODIGO"]] -= m["CANT"]
    return dict(stock)


def stock_de(movimientos, codigo, bodega=None):
    """
    Stock de un producto. Si se indica bodega, solo esa bodega;
    si no, la suma de todas las bodegas.
    """
    total = 0.0
    for m in movimientos:
        if m["CODIGO"] != codigo:
            continue
        if bodega is not None and m["BODEGA"] != bodega:
            continue
        if m["MOV"] == "E":
            total += m["CANT"]
        elif m["MOV"] == "S":
            total -= m["CANT"]
    return total


def ventas_periodo(movimientos, fecha_desde, fecha_hasta):
    """
    Ventas netas por producto en el rango [fecha_desde, fecha_hasta]
    (formato 'AAAA-MM-DD'), segun la seccion 4.4:
        ventas = salidas FE  -  devoluciones NCF

    Devuelve un diccionario:
        { codigo: {"unidades": x, "valor": y}, ... }
    """
    resultado = defaultdict(lambda: {"unidades": 0.0, "valor": 0.0})

    for m in movimientos:
        fecha = m["FECHA"]
        if fecha < fecha_desde or fecha > fecha_hasta:
            continue

        docum = m["DOCUM"]
        # Prefijo de letras del documento (FE, NCF, etc.)
        prefijo = "".join(ch for ch in docum if ch.isalpha())

        if prefijo == "FE":
            # Venta: la salida suma a las ventas
            resultado[m["CODIGO"]]["unidades"] += m["CANT"]
            resultado[m["CODIGO"]]["valor"] += m["COSTOT"]
        elif prefijo == "NCF":
            # Devolucion de cliente: resta de las ventas
            resultado[m["CODIGO"]]["unidades"] -= m["CANT"]
            resultado[m["CODIGO"]]["valor"] -= m["COSTOT"]

    return dict(resultado)


def rentabilidad(precio, costo):
    """
    Rentabilidad porcentual (seccion 4.2):
        (precio - costo) / precio * 100
    Si el precio es cero o invalido, devuelve None (mostrar N/D).
    """
    if not precio or precio <= 0:
        return None
    return (precio - costo) / precio * 100


if __name__ == "__main__":
    # Prueba minima con datos de ejemplo
    movs = [
        {"CODIGO": "X1", "BODEGA": "01", "FECHA": "2026-02-17",
         "DOCUM": "AJUS", "MOV": "E", "CANT": 650, "COSTOT": 0, "NUMERO": "1"},
        {"CODIGO": "X1", "BODEGA": "01", "FECHA": "2026-02-25",
         "DOCUM": "FE", "MOV": "S", "CANT": 45, "COSTOT": 90000, "NUMERO": "2"},
        {"CODIGO": "X1", "BODEGA": "01", "FECHA": "2026-03-10",
         "DOCUM": "NCF", "MOV": "E", "CANT": 6, "COSTOT": 12000, "NUMERO": "3"},
    ]
    print("Stock X1:", stock_de(movs, "X1"))  # 650 - 45 + 6 = 611
    print("Ventas:", ventas_periodo(movs, "2026-01-01", "2026-12-31"))
    print("Rentabilidad 65000/28500:", round(rentabilidad(65000, 28500), 1))
