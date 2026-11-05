"""Lectura de los avisos del banco que llegan al correo (IMAP).

Pasos:
1. Entrar al correo con una contraseña de aplicación guardada en el llavero de Windows.
2. Buscar los correos de los últimos días que mandó algún banco activo.
3. Con las expresiones regulares de su plantilla, sacar monto, fecha y comercio.
Los movimientos NO se guardan aquí: se muestran primero en la vista previa.
"""
import email
import imaplib
import re
from datetime import date, timedelta
from email import policy
from email.utils import parsedate_to_datetime

import keyring
from bs4 import BeautifulSoup

from database import correo_dao, plantillas_dao
from utils.procesador_csv import convertir_fecha, convertir_monto, normalizar

SERVIDORES = {"gmail": "imap.gmail.com", "yahoo": "imap.mail.yahoo.com"}
SERVICIO_LLAVERO = "FinanzApp-correo"
DIAS_ATRAS = 30          # Hasta dónde se busca en cada sincronización
MAXIMO_CORREOS = 300     # Para no tardar demasiado si hay muchísimos
PALABRAS_INGRESO = ("deposito", "abono", "transferencia recibida", "recibiste", "te enviaron", "te transfirieron",
                    "acreditacion", "acreditamos", "acreditaron", "cobraste", "haberes", "ingreso de dinero")
_MESES_IMAP = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---------- Contraseña en el llavero de Windows ----------

def guardar_password(email_conexion, password):
    keyring.set_password(SERVICIO_LLAVERO, email_conexion, password)


def leer_password(email_conexion):
    return keyring.get_password(SERVICIO_LLAVERO, email_conexion)


def borrar_password(email_conexion):
    try:
        keyring.delete_password(SERVICIO_LLAVERO, email_conexion)
    except keyring.errors.PasswordDeleteError:
        pass  # ya no estaba


# ---------- Conexión ----------

def conectar(proveedor, email_conexion, password):
    """Abre la sesión. Lanza imaplib.IMAP4.error si el correo o la contraseña están mal."""
    servidor = imaplib.IMAP4_SSL(SERVIDORES[proveedor], 993, timeout=20)
    servidor.login(email_conexion, password)
    return servidor


def probar_conexion(proveedor, email_conexion, password):
    conectar(proveedor, email_conexion, password).logout()


# ---------- Sincronizar ----------

def sincronizar(usuario_id):
    """Busca avisos nuevos del banco. Devuelve (movimientos, correos_sin_monto, ignorados).

    ignorados: correos que SÍ vienen del remitente de un banco, pero cuyo asunto no
    coincidió con su patrón. Se muestran para que el usuario sepa que llegaron.
    """
    cuenta = correo_dao.obtener(usuario_id)
    if cuenta is None:
        raise ValueError("Primero conecta tu correo.")
    password = leer_password(cuenta["email_conexion"])
    if not password:
        raise ValueError("No se encontró la contraseña en el llavero. Vuelve a configurar el correo.")
    plantillas = plantillas_dao.listar(solo_activas=True)
    if not plantillas:
        raise ValueError("Activa al menos un banco en la lista «Bancos que se leen».")

    servidor = conectar(cuenta["proveedor_email"], cuenta["email_conexion"], password)
    try:
        resultado = _leer_avisos(servidor, plantillas, correo_dao.ids_procesados(usuario_id))
    finally:
        servidor.logout()
    correo_dao.marcar_sincronizado(usuario_id)
    return resultado


def _leer_avisos(servidor, plantillas, ya_procesados):
    servidor.select("INBOX", readonly=True)  # readonly: no los marca como leídos
    desde = date.today() - timedelta(days=DIAS_ATRAS)
    fecha_imap = f"{desde.day:02d}-{_MESES_IMAP[desde.month - 1]}-{desde.year}"

    # El servidor filtra por remitente, así solo bajamos los correos de bancos
    numeros = set()
    for plantilla in plantillas:
        criterio = ["SINCE", fecha_imap]
        if plantilla["remitente"]:
            criterio += ["FROM", f'"{plantilla["remitente"]}"']
        _, datos = servidor.search(None, *criterio)
        numeros.update(datos[0].split())
    numeros = sorted(numeros, key=int)[-MAXIMO_CORREOS:]
    if not numeros:
        return [], 0, []

    # Primero solo las cabeceras (rápido); el cuerpo solo de los que sí son avisos
    movimientos, sin_monto, ignorados = [], 0, []
    for numero, cabecera in _descargar(servidor, numeros, "BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)]"):
        asunto = str(cabecera["Subject"] or "")
        message_id = str(cabecera["Message-ID"] or f"{cabecera['From']}|{cabecera['Date']}|{asunto}").strip()[:255]
        if message_id in ya_procesados:
            continue
        remitente = str(cabecera["From"] or "")
        plantilla = plantilla_para(remitente, asunto, plantillas)
        if plantilla is None:
            # Si es de un banco pero el asunto no coincidió, se avisa (no se descarta en silencio)
            banco = banco_del_remitente(remitente, plantillas)
            if banco:
                ignorados.append({"banco": banco["banco"], "asunto": asunto or "(sin asunto)"})
            continue
        _, mensaje = next(_descargar(servidor, [numero], "BODY.PEEK[]"))
        movimiento = extraer(texto_del_correo(mensaje), asunto, plantilla, _fecha_del_correo(cabecera))
        if movimiento is None:
            sin_monto += 1
            continue
        movimiento["message_id"] = message_id
        movimientos.append(movimiento)
    return movimientos, sin_monto, ignorados


def _descargar(servidor, numeros, que):
    """Pide varios correos de una vez y devuelve (número, mensaje) de cada uno."""
    _, datos = servidor.fetch(b",".join(numeros), f"({que})")
    for parte in datos:
        if isinstance(parte, tuple):  # el servidor mezcla tuplas (datos) con b")" (cierres)
            yield parte[0].split()[0], email.message_from_bytes(parte[1], policy=policy.default)


# ---------- Extraer datos ----------

def plantilla_para(remitente, asunto, plantillas):
    """La primera plantilla cuyo remitente y asunto coinciden con el correo."""
    remitente = remitente.lower()
    for plantilla in plantillas:
        if plantilla["remitente"] and plantilla["remitente"].lower() not in remitente:
            continue
        if re.search(plantilla["patron_asunto"], asunto):
            return plantilla
    return None


def banco_del_remitente(remitente, plantillas):
    """La plantilla cuyo remitente aparece en el correo (sin mirar el asunto), o None.
    Las plantillas sin remitente no cuentan: con ellas cualquier correo "sería del banco"."""
    remitente = remitente.lower()
    return next((p for p in plantillas if p["remitente"] and p["remitente"].lower() in remitente), None)


def texto_del_correo(mensaje):
    """Texto legible del correo: si viene en HTML se le quitan las etiquetas."""
    cuerpo = mensaje.get_body(preferencelist=("html", "plain"))
    if cuerpo is None:
        return ""
    contenido = cuerpo.get_content()
    if cuerpo.get_content_subtype() == "html":
        contenido = BeautifulSoup(contenido, "lxml").get_text("\n")
    return re.sub(r"[ \t\xa0]+", " ", contenido)


def extraer(texto, asunto, plantilla, fecha_correo):
    """Devuelve el movimiento {fecha, descripcion, monto, tipo, banco} o None si no hay monto."""
    completo = f"{asunto}\n{texto}"
    monto = convertir_monto(_grupo(plantilla["patron_monto"], completo))
    if not monto:
        return None
    fecha = convertir_fecha(_grupo(plantilla["patron_fecha"], completo)) or fecha_correo
    descripcion = (_grupo(plantilla["patron_comercio"], completo) or asunto).strip()[:200]
    es_ingreso = any(p in normalizar(asunto) for p in PALABRAS_INGRESO)
    return {"fecha": fecha, "descripcion": descripcion or "(sin descripción)", "monto": round(abs(monto), 2),
            "tipo": "ingreso" if es_ingreso else "gasto", "banco": plantilla["banco"]}


def _grupo(patron, texto):
    """Lo que encontró el patrón: el grupo 1 si tiene paréntesis, si no todo."""
    encontrado = re.search(patron, texto) if patron else None
    if not encontrado:
        return ""
    return encontrado.group(1) if encontrado.groups() else encontrado.group(0)


def _fecha_del_correo(cabecera):
    try:
        return parsedate_to_datetime(str(cabecera["Date"])).date()
    except (TypeError, ValueError):
        return date.today()
