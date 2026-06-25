# -*- coding: utf-8 -*-
"""
MPS REPORTS - Seguridad
Manejo seguro de contrasenas con SHA-256 mas salt unico por usuario.
Las contrasenas NUNCA se guardan en texto plano (RN-12).
Incluye verificacion de login y control de intentos fallidos
(5 intentos bloquean 5 minutos).
"""

import hashlib
import secrets
from datetime import datetime, timedelta

import base_propia
import auditoria

# Control de intentos fallidos en memoria (por usuario)
_intentos = {}

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 5


def generar_hash(contrasena):
    """Genera (salt, hash) para guardar por separado."""
    salt = secrets.token_hex(16)
    hash_c = _calcular(salt, contrasena)
    return salt, hash_c


def verificar_hash(contrasena, salt, hash_guardado):
    """Verifica si una contrasena coincide con el hash guardado."""
    return _calcular(salt, contrasena) == hash_guardado


def _calcular(salt, contrasena):
    """Calcula SHA-256 de (salt + contrasena)."""
    texto = (salt + contrasena).encode("utf-8")
    return hashlib.sha256(texto).hexdigest()


def listar_usuarios_activos():
    """Devuelve la lista de nombres de usuarios activos, ordenada."""
    con = base_propia.conectar()
    cur = con.cursor()
    cur.execute("SELECT nombre FROM usuarios WHERE activo = 1 ORDER BY nombre")
    nombres = [f[0] for f in cur.fetchall()]
    con.close()
    return nombres


def esta_bloqueado(usuario):
    """Segundos restantes de bloqueo, o 0 si no esta bloqueado."""
    info = _intentos.get(usuario)
    if not info:
        return 0
    hasta = info.get("bloqueado_hasta")
    if hasta and datetime.now() < hasta:
        return int((hasta - datetime.now()).total_seconds())
    return 0


def verificar(usuario, contrasena):
    """
    Verifica credenciales. Devuelve un diccionario:
      {"ok": True,  "rol": "..."}                          -> correcto
      {"ok": False, "motivo": "bloqueado", "segundos": n}  -> bloqueado
      {"ok": False, "motivo": "credenciales", "restantes": n} -> mal
    """
    seg = esta_bloqueado(usuario)
    if seg > 0:
        return {"ok": False, "motivo": "bloqueado", "segundos": seg}

    con = base_propia.conectar()
    cur = con.cursor()
    cur.execute("""
        SELECT hash_contrasena, salt, rol
        FROM usuarios WHERE nombre = ? AND activo = 1
    """, (usuario,))
    fila = cur.fetchone()
    con.close()

    if not fila:
        return {"ok": False, "motivo": "credenciales", "restantes": MAX_INTENTOS}

    hash_guardado, salt, rol = fila

    if verificar_hash(contrasena, salt, hash_guardado):
        _intentos.pop(usuario, None)
        auditoria.registrar(usuario, "INICIO_SESION", "Ingreso correcto al sistema")
        return {"ok": True, "rol": rol}

    info = _intentos.get(usuario, {"fallos": 0, "bloqueado_hasta": None})
    info["fallos"] += 1
    auditoria.registrar(usuario, "INTENTO_FALLIDO",
                        "Contrasena incorrecta (intento {})".format(info["fallos"]))

    if info["fallos"] >= MAX_INTENTOS:
        info["bloqueado_hasta"] = datetime.now() + timedelta(minutes=MINUTOS_BLOQUEO)
        info["fallos"] = 0
        _intentos[usuario] = info
        auditoria.registrar(usuario, "INTENTO_FALLIDO",
                            "Usuario bloqueado por {} intentos fallidos".format(MAX_INTENTOS))
        return {"ok": False, "motivo": "bloqueado", "segundos": MINUTOS_BLOQUEO * 60}

    _intentos[usuario] = info
    return {"ok": False, "motivo": "credenciales", "restantes": MAX_INTENTOS - info["fallos"]}


if __name__ == "__main__":
    s, h = generar_hash("Prueba123")
    print("salt:", s)
    print("hash:", h)
    print("verifica correcta:", verificar_hash("Prueba123", s, h))
    print("verifica incorrecta:", verificar_hash("Otra", s, h))
