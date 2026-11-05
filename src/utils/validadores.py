"""Validación de datos que escribe el usuario."""
import re

from utils.calculos import leer_monto


def email_valido(email):
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or "") is not None


def password_valida(password):
    return len(password or "") >= 6


def convertir_monto(texto, permitir_cero=False):
    """'1.250,50' o '1250,50' -> 1250.5 (también entiende '1250.50'). None si no es válido."""
    valor = leer_monto(texto or "")
    if valor is None or valor < 0 or (valor == 0 and not permitir_cero):
        return None
    return round(valor, 2)


def ultimos4_validos(texto):
    return texto == "" or re.fullmatch(r"\d{4}", texto) is not None


def texto_requerido(texto, maximo):
    texto = (texto or "").strip()
    return texto if 0 < len(texto) <= maximo else None
