"""Operaciones de usuarios: registro, inicio de sesión y recuperar contraseña."""
import secrets
from datetime import datetime, timedelta

import bcrypt

from database import categorias_dao, cuentas_dao
from database.conexion import consultar_uno, ejecutar

MINUTOS_CODIGO = 15     # Cuánto dura el código de recuperación
MAXIMO_INTENTOS = 5     # Después de 5 códigos equivocados hay que pedir otro
ESPERA_REENVIO = 60     # Segundos mínimos entre un código y el siguiente


def existe_email(email):
    return consultar_uno("SELECT id FROM usuarios WHERE email = %s", (email,)) is not None


def registrar(nombre, email, password):
    """Crea el usuario con sus categorías por defecto y una cuenta de efectivo."""
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    usuario_id = ejecutar(
        "INSERT INTO usuarios (nombre, email, password_hash) VALUES (%s, %s, %s)",
        (nombre, email, password_hash),
    )
    categorias_dao.crear_por_defecto(usuario_id)
    cuentas_dao.crear(usuario_id, "Efectivo", "monedero", "", None, 0, "#4ecca3")
    return usuario_id


def iniciar_sesion(email, password):
    """Devuelve el usuario si email y contraseña son correctos, si no None."""
    usuario = consultar_uno("SELECT * FROM usuarios WHERE email = %s", (email,))
    if usuario and bcrypt.checkpw(password.encode(), usuario["password_hash"].encode()):
        return usuario
    return None


def obtener(usuario_id):
    return consultar_uno("SELECT * FROM usuarios WHERE id = %s", (usuario_id,))


# ---------- Tutorial de bienvenida ----------

def vio_tutorial(usuario_id):
    return consultar_uno("SELECT usuario_id FROM tutoriales_vistos WHERE usuario_id = %s", (usuario_id,)) is not None


def marcar_tutorial_visto(usuario_id):
    ejecutar("INSERT IGNORE INTO tutoriales_vistos (usuario_id) VALUES (%s)", (usuario_id,))


# ---------- Recuperar contraseña ----------

def crear_codigo_recuperacion(email):
    """Genera un código de 6 dígitos para ese correo.

    Devuelve (usuario, codigo), o None si el correo no está registrado.
    Lanza ValueError si se pidió otro código hace menos de un minuto.
    """
    usuario = consultar_uno("SELECT * FROM usuarios WHERE email = %s", (email,))
    if usuario is None:
        return None
    previo = consultar_uno("SELECT expira FROM recuperaciones WHERE usuario_id = %s", (usuario["id"],))
    if previo:
        creado = previo["expira"] - timedelta(minutes=MINUTOS_CODIGO)
        if (datetime.now() - creado).total_seconds() < ESPERA_REENVIO:
            raise ValueError("Espera un minuto antes de pedir otro código.")

    codigo = f"{secrets.randbelow(1_000_000):06d}"
    codigo_hash = bcrypt.hashpw(codigo.encode(), bcrypt.gensalt()).decode()
    expira = datetime.now() + timedelta(minutes=MINUTOS_CODIGO)
    # Si ya había un código, el nuevo lo reemplaza (y se reinician los intentos)
    ejecutar("""INSERT INTO recuperaciones (usuario_id, codigo_hash, expira) VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE codigo_hash = VALUES(codigo_hash), expira = VALUES(expira), intentos = 0""",
             (usuario["id"], codigo_hash, expira))
    return usuario, codigo


def borrar_codigo(email):
    """Por si el correo no se pudo enviar: así se puede volver a pedir enseguida."""
    ejecutar("DELETE r FROM recuperaciones r JOIN usuarios u ON u.id = r.usuario_id WHERE u.email = %s", (email,))


def cambiar_password_con_codigo(email, codigo, nueva):
    """Cambia la contraseña si el código es correcto. Devuelve None si salió bien,
    o el texto del error para mostrarlo."""
    fila = consultar_uno("""SELECT r.* FROM recuperaciones r JOIN usuarios u ON u.id = r.usuario_id
                            WHERE u.email = %s""", (email,))
    if fila is None:
        return "Primero pide un código."
    if fila["expira"] < datetime.now():
        return "El código ya venció. Pide uno nuevo."
    if fila["intentos"] >= MAXIMO_INTENTOS:
        return "Demasiados intentos. Pide un código nuevo."
    if not bcrypt.checkpw(codigo.strip().encode(), fila["codigo_hash"].encode()):
        ejecutar("UPDATE recuperaciones SET intentos = intentos + 1 WHERE usuario_id = %s", (fila["usuario_id"],))
        restantes = MAXIMO_INTENTOS - fila["intentos"] - 1
        return f"Código incorrecto. Te quedan {restantes} intentos." if restantes else \
            "Código incorrecto. Pide un código nuevo."

    password_hash = bcrypt.hashpw(nueva.encode(), bcrypt.gensalt()).decode()
    ejecutar("UPDATE usuarios SET password_hash = %s WHERE id = %s", (password_hash, fila["usuario_id"]))
    ejecutar("DELETE FROM recuperaciones WHERE usuario_id = %s", (fila["usuario_id"],))  # el código ya no sirve
    return None
