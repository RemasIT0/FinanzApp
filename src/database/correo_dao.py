"""Operaciones del correo conectado (tabla cuentas_email) y de los correos
ya procesados (tabla emails_procesados)."""
from database.conexion import consultar, consultar_uno, ejecutar, ejecutar_varios

INTERVALOS = {"Solo manual": 0, "Cada hora": 1, "Cada 3 horas": 3, "Cada 6 horas": 6,
              "Cada 12 horas": 12, "Una vez al día": 24}


# ---------- Cuenta de correo ----------

def obtener(usuario_id):
    return consultar_uno("SELECT * FROM cuentas_email WHERE usuario_id = %s", (usuario_id,))


def guardar(usuario_id, proveedor, email_conexion, intervalo_horas):
    """Crea la conexión o la actualiza (cada usuario tiene una sola)."""
    ejecutar(
        """INSERT INTO cuentas_email (usuario_id, proveedor_email, email_conexion, intervalo_horas)
           VALUES (%s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE proveedor_email = VALUES(proveedor_email),
                                   email_conexion = VALUES(email_conexion),
                                   intervalo_horas = VALUES(intervalo_horas),
                                   sincronizacion_activa = TRUE""",
        (usuario_id, proveedor, email_conexion, intervalo_horas),
    )


def marcar_sincronizado(usuario_id):
    ejecutar("UPDATE cuentas_email SET ultima_sincronizacion = NOW() WHERE usuario_id = %s", (usuario_id,))


def eliminar(usuario_id):
    ejecutar("DELETE FROM cuentas_email WHERE usuario_id = %s", (usuario_id,))


# ---------- Correos ya procesados ----------

def ids_procesados(usuario_id):
    filas = consultar("SELECT message_id FROM emails_procesados WHERE usuario_id = %s", (usuario_id,))
    return {f["message_id"] for f in filas}


def marcar_procesados(usuario_id, message_ids):
    ejecutar_varios("INSERT IGNORE INTO emails_procesados (usuario_id, message_id) VALUES (%s, %s)",
                    [(usuario_id, m) for m in message_ids])
