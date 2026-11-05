"""Envío de correos de la app (por ahora, los códigos para recuperar la contraseña).

Se envían desde UNA cuenta Gmail "de la app" (no la del usuario):
- El correo remitente se guarda en data/config.json ("correo_app").
- Su contraseña de aplicación va en el llavero de Windows, igual que la del lector de avisos.
"""
import smtplib
from email.message import EmailMessage
from html import escape

import keyring

from utils.config import actualizar_config, cargar_config

SERVIDOR_SMTP = ("smtp.gmail.com", 465)
SERVICIO_LLAVERO = "FinanzApp-envio"


# ---------- Cuenta remitente ----------

def remitente():
    """Correo desde el que se envía, o "" si todavía no se configura."""
    correo = cargar_config()["correo_app"]
    return correo if correo and keyring.get_password(SERVICIO_LLAVERO, correo) else ""


def configurar_remitente(correo, password):
    """Prueba la entrada a Gmail y, si funciona, guarda el remitente.
    Lanza smtplib.SMTPAuthenticationError u OSError si algo falla."""
    with smtplib.SMTP_SSL(*SERVIDOR_SMTP, timeout=20) as smtp:
        _entrar(smtp, correo, password)
    anterior = cargar_config()["correo_app"]
    if anterior and anterior != correo:
        _borrar_password(anterior)
    keyring.set_password(SERVICIO_LLAVERO, correo, password)
    actualizar_config(correo_app=correo)


def _borrar_password(correo):
    try:
        keyring.delete_password(SERVICIO_LLAVERO, correo)
    except keyring.errors.PasswordDeleteError:
        pass


def mensaje_error(error):
    if isinstance(error, smtplib.SMTPAuthenticationError):
        return "Gmail rechazó la entrada. Usa una contraseña de aplicación (no tu contraseña normal)."
    if isinstance(error, (OSError, smtplib.SMTPException)):
        return "No se pudo conectar con Gmail. Revisa tu internet."
    return str(error)


# ---------- Enviar ----------

def enviar(destino, asunto, texto, html=None):
    correo = remitente()
    if not correo:
        raise ValueError("Falta configurar el correo de envío de la app.")
    mensaje = EmailMessage()
    mensaje["From"] = f"FinanzApp <{correo}>"
    mensaje["To"] = destino
    mensaje["Subject"] = asunto
    mensaje.set_content(texto)
    if html:
        mensaje.add_alternative(html, subtype="html")
    with smtplib.SMTP_SSL(*SERVIDOR_SMTP, timeout=20) as smtp:
        _entrar(smtp, correo, keyring.get_password(SERVICIO_LLAVERO, correo))
        smtp.send_message(mensaje)


def _entrar(smtp, correo, password):
    """Gmail a veces, en lugar de responder "contraseña incorrecta", simplemente corta la
    conexión. Como ya estábamos conectados, eso también significa que rechazó la entrada."""
    try:
        smtp.login(correo, password)
    except smtplib.SMTPServerDisconnected as e:
        raise smtplib.SMTPAuthenticationError(535, b"Gmail cerro la conexion al entrar") from e


def enviar_codigo(destino, nombre, codigo, minutos):
    texto = (f"Hola {nombre}:\n\nTu código para cambiar la contraseña de FinanzApp es: {codigo}\n\n"
             f"Vence en {minutos} minutos. Si tú no lo pediste, ignora este correo.")
    html = f"""
    <div style="font-family:Segoe UI,Arial,sans-serif;max-width:420px;margin:auto;color:#1a1a2e">
      <h2 style="color:#e94560;margin-bottom:4px">◈ FinanzApp</h2>
      <p>Hola {escape(nombre)}, usa este código para cambiar tu contraseña:</p>
      <p style="font-size:34px;font-weight:bold;letter-spacing:8px;background:#eef0f7;
                padding:16px;border-radius:12px;text-align:center">{codigo}</p>
      <p style="color:#5f6577;font-size:13px">Vence en {minutos} minutos.
         Si tú no lo pediste, ignora este correo: tu contraseña sigue igual.</p>
    </div>"""
    enviar(destino, f"Tu código de FinanzApp: {codigo}", texto, html)
