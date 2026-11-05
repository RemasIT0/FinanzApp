"""Plantillas para leer los avisos de cada banco que llegan al correo.

Cada patrón es una expresión regular. Del monto, la fecha y el comercio se
toma lo que quede dentro del primer paréntesis (el "grupo 1").
Son aproximadas: cada banco redacta sus avisos a su manera, así que se
pueden ajustar desde la pantalla Correo.
"""
from database.conexion import consultar, consultar_uno, ejecutar, ejecutar_varios

# Palabras típicas de los asuntos de avisos en Argentina ("Consumo aprobado", "Acreditación de haberes"…)
_ASUNTO = (r"(?i)compra|consumo|cargo|pago|d[eé]bito|retiro|extracci[oó]n|transferencia|"
           r"acreditaci[oó]n|dep[oó]sito|cobro")
# "$ 1.250,50", "$1250,50", "ARS 1.250,50" (y también "$1,250.50"): se toma el número y la app lo interpreta
_MONTO = r"(?:ARS|\$)\s*(\d[\d.,]*\d|\d)"
_FECHA = r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
# Lo que sigue a "Comercio:" hasta el punto, la coma, la palabra "fecha" / "el día" / "por $" o el fin de línea
_COMERCIO = (r"(?im)(?:comercio|establecimiento|negocio|destino|lugar)\s*:?\s*(.{3,60}?)\s*"
             r"(?:\.(?:\s|$)|,|;|\bfecha\b|\bel d[ií]a\b|\bpor\s+(?:\$|ARS)|$)")

# Patrones de la primera versión (formato de México). Si una plantilla todavía los tiene
# sin cambios, se actualiza sola a los de Argentina.
_VIEJOS = {
    "patron_asunto": (r"(?i)compra|cargo|pago|retiro|transferencia|dep[oó]sito", _ASUNTO),
    "patron_monto": (r"\$\s?([\d,]+\.\d{2})", _MONTO),
    "patron_fecha": (r"(\d{1,2}/\d{1,2}/\d{2,4})", _FECHA),
    "patron_comercio": (r"(?i)(?:comercio|establecimiento|negocio|destino)\s*:?\s*([^\n$]{3,60})", _COMERCIO),
}

# Bancos y billeteras de Argentina: (banco, remitente). El remitente es aproximado: si tus avisos
# vienen de otra dirección, cámbialo con ✎ (basta una parte, ej. "galicia").
BANCOS = [("Banco Nación", "bna"), ("Galicia", "galicia"), ("Santander", "santander"), ("BBVA", "bbva"),
          ("Macro", "macro"), ("ICBC", "icbc"), ("Brubank", "brubank"), ("Mercado Pago", "mercadopago"),
          ("Ualá", "uala"), ("Naranja X", "naranjax")]
# (banco, remitente, patron_asunto, patron_monto, patron_fecha, patron_comercio)
POR_DEFECTO = [(banco, remitente, _ASUNTO, _MONTO, _FECHA, _COMERCIO) for banco, remitente in BANCOS]
_DE_MEXICO = ("Banorte", "Nu")  # venían en la primera versión

_COLUMNAS = "banco, remitente, patron_asunto, patron_monto, patron_fecha, patron_comercio"


def crear_por_defecto():
    """Deja la lista de bancos al día (se llama cada vez que se abre la pantalla Correo):
    1. Agrega los bancos argentinos que falten (los que ya existen no se tocan).
    2. Pasa a formato argentino los patrones que nadie modificó.
    3. Quita los bancos de México que vienen de la primera versión, si están apagados.
    """
    ejecutar_varios(f"INSERT IGNORE INTO plantillas_email ({_COLUMNAS}) VALUES (%s, %s, %s, %s, %s, %s)",
                    POR_DEFECTO)
    for columna, (viejo, nuevo) in _VIEJOS.items():
        ejecutar(f"UPDATE plantillas_email SET {columna} = %s WHERE {columna} = %s", (nuevo, viejo))
    ejecutar("DELETE FROM plantillas_email WHERE activo = FALSE AND banco IN (%s, %s)", _DE_MEXICO)


def listar(solo_activas=False):
    sql = "SELECT * FROM plantillas_email"
    if solo_activas:
        sql += " WHERE activo = TRUE"
    return consultar(sql + " ORDER BY banco")


def crear(banco, remitente, asunto, monto, fecha, comercio):
    """Las plantillas nuevas nacen activas: si la agregas es porque la vas a usar."""
    return ejecutar(f"INSERT INTO plantillas_email ({_COLUMNAS}, activo) VALUES (%s, %s, %s, %s, %s, %s, TRUE)",
                    (banco, remitente, asunto, monto, fecha, comercio))


def actualizar(plantilla_id, banco, remitente, asunto, monto, fecha, comercio):
    ejecutar(
        """UPDATE plantillas_email SET banco = %s, remitente = %s, patron_asunto = %s, patron_monto = %s,
                  patron_fecha = %s, patron_comercio = %s
           WHERE id = %s""",
        (banco, remitente, asunto, monto, fecha, comercio, plantilla_id),
    )


def cambiar_activo(plantilla_id, activo):
    ejecutar("UPDATE plantillas_email SET activo = %s WHERE id = %s", (activo, plantilla_id))


def eliminar(plantilla_id):
    ejecutar("DELETE FROM plantillas_email WHERE id = %s", (plantilla_id,))
