"""Recuperar contraseña: lo usan igual la app de escritorio y la versión web.

1. solicitar(email): crea un código de 6 dígitos y lo manda al correo.
2. usuarios_dao.cambiar_password_con_codigo(email, codigo, nueva): lo valida y cambia la contraseña.
"""
from database import usuarios_dao
from utils import enviar_correo

# Mismo mensaje exista o no el correo: así nadie puede averiguar quién tiene cuenta
MENSAJE_ENVIADO = "Si ese correo tiene cuenta, te llegará un código en unos segundos. Revisa también spam."


def disponible():
    """True si ya hay un Gmail configurado para enviar los códigos."""
    return bool(enviar_correo.remitente())


def solicitar(email):
    """Manda el código. Lanza ValueError con un mensaje listo para mostrar si algo falla."""
    if not disponible():
        raise ValueError("Falta configurar el correo de envío de la app.")
    resultado = usuarios_dao.crear_codigo_recuperacion(email)  # puede lanzar ValueError (espera 1 min)
    if resultado is None:
        return MENSAJE_ENVIADO
    usuario, codigo = resultado
    try:
        enviar_correo.enviar_codigo(email, usuario["nombre"], codigo, usuarios_dao.MINUTOS_CODIGO)
    except Exception as e:
        usuarios_dao.borrar_codigo(email)  # para que pueda reintentar sin esperar
        raise ValueError(enviar_correo.mensaje_error(e)) from e
    return MENSAJE_ENVIADO
