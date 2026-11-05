"""Operaciones de transacciones (movimientos) y consultas para reportes.

Recordatorio: el monto siempre se guarda en positivo; el campo "tipo"
indica si es 'gasto', 'ingreso' o 'transferencia'.
Una transferencia saca dinero de cuenta_id y lo pone en cuenta_destino_id: cambia los
saldos de esas cuentas, pero NO cuenta como gasto ni como ingreso en los totales.
"""
from database.conexion import consultar, consultar_uno, ejecutar, ejecutar_varios

_SQL_BASE = """
    SELECT t.*, c.nombre AS cuenta, d.nombre AS cuenta_destino, cat.nombre AS categoria, cat.icono, cat.color
    FROM transacciones t
    JOIN cuentas c ON c.id = t.cuenta_id
    LEFT JOIN cuentas d ON d.id = t.cuenta_destino_id
    LEFT JOIN categorias cat ON cat.id = t.categoria_id
    WHERE c.usuario_id = %s
"""

_SQL_INSERTAR = """INSERT INTO transacciones (cuenta_id, categoria_id, descripcion, monto, fecha, tipo, origen)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)"""


# ---------- Altas, cambios y bajas ----------

def crear(cuenta_id, categoria_id, descripcion, monto, fecha, tipo, origen="manual", cuenta_destino_id=None):
    """cuenta_destino_id solo se usa en las transferencias (a qué cuenta va el dinero)."""
    return ejecutar(
        """INSERT INTO transacciones (cuenta_id, cuenta_destino_id, categoria_id, descripcion, monto, fecha, tipo, origen)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (cuenta_id, cuenta_destino_id, categoria_id, descripcion, abs(monto), fecha, tipo, origen))


def crear_varias(filas):
    """filas: lista de tuplas (cuenta_id, categoria_id, descripcion, monto, fecha, tipo, origen)."""
    return ejecutar_varios(_SQL_INSERTAR, filas)


def actualizar(transaccion_id, usuario_id, cuenta_id, categoria_id, descripcion, monto, fecha, tipo,
               cuenta_destino_id=None):
    ejecutar(
        """UPDATE transacciones t JOIN cuentas c ON c.id = t.cuenta_id
           SET t.cuenta_id = %s, t.cuenta_destino_id = %s, t.categoria_id = %s, t.descripcion = %s,
               t.monto = %s, t.fecha = %s, t.tipo = %s
           WHERE t.id = %s AND c.usuario_id = %s""",
        (cuenta_id, cuenta_destino_id, categoria_id, descripcion, abs(monto), fecha, tipo, transaccion_id, usuario_id),
    )


def eliminar(transaccion_id, usuario_id):
    ejecutar(
        """DELETE t FROM transacciones t JOIN cuentas c ON c.id = t.cuenta_id
           WHERE t.id = %s AND c.usuario_id = %s""",
        (transaccion_id, usuario_id),
    )


# ---------- Búsquedas ----------

def buscar(usuario_id, desde=None, hasta=None, categoria_id=None, cuenta_id=None,
           tipo=None, texto="", limite=None):
    sql = _SQL_BASE
    parametros = [usuario_id]
    if desde:
        sql += " AND t.fecha >= %s"
        parametros.append(desde)
    if hasta:
        sql += " AND t.fecha <= %s"
        parametros.append(hasta)
    if categoria_id:
        sql += " AND t.categoria_id = %s"
        parametros.append(categoria_id)
    if cuenta_id:  # en esa cuenta, o una transferencia que llega a ella
        sql += " AND (t.cuenta_id = %s OR t.cuenta_destino_id = %s)"
        parametros += [cuenta_id, cuenta_id]
    if tipo:
        sql += " AND t.tipo = %s"
        parametros.append(tipo)
    if texto:
        sql += " AND t.descripcion LIKE %s"
        parametros.append(f"%{texto}%")
    sql += " ORDER BY t.fecha DESC, t.id DESC"
    if limite:
        sql += " LIMIT %s"
        parametros.append(limite)
    return consultar(sql, parametros)


def obtener(transaccion_id, usuario_id):
    """Un movimiento, solo si pertenece al usuario (si no, None)."""
    return consultar_uno(_SQL_BASE + " AND t.id = %s", (usuario_id, transaccion_id))


def ultimas(usuario_id, cantidad=5):
    return buscar(usuario_id, limite=cantidad)


def firmas_existentes(cuenta_id):
    """Conjunto (fecha, monto, descripcion) de la cuenta, para detectar duplicados al importar."""
    filas = consultar("SELECT fecha, monto, descripcion FROM transacciones WHERE cuenta_id = %s", (cuenta_id,))
    return {(f["fecha"], round(float(f["monto"]), 2), f["descripcion"]) for f in filas}


# ---------- Totales para dashboard y reportes ----------

def totales(usuario_id, desde, hasta):
    fila = consultar_uno(
        """SELECT COALESCE(SUM(CASE WHEN t.tipo = 'ingreso' THEN t.monto END), 0) AS ingresos,
                  COALESCE(SUM(CASE WHEN t.tipo = 'gasto'   THEN t.monto END), 0) AS gastos
           FROM transacciones t JOIN cuentas c ON c.id = t.cuenta_id
           WHERE c.usuario_id = %s AND t.fecha BETWEEN %s AND %s""",
        (usuario_id, desde, hasta),
    )
    return {"ingresos": float(fila["ingresos"]), "gastos": float(fila["gastos"])}


def gastos_por_categoria(usuario_id, desde, hasta):
    filas = consultar(
        """SELECT COALESCE(cat.nombre, 'Sin categoría') AS nombre,
                  COALESCE(cat.color, '#7f8c8d') AS color,
                  COALESCE(cat.icono, '❔') AS icono,
                  SUM(t.monto) AS total
           FROM transacciones t
           JOIN cuentas c ON c.id = t.cuenta_id
           LEFT JOIN categorias cat ON cat.id = t.categoria_id
           WHERE c.usuario_id = %s AND t.tipo = 'gasto' AND t.fecha BETWEEN %s AND %s
           GROUP BY cat.id, cat.nombre, cat.color, cat.icono
           ORDER BY total DESC""",
        (usuario_id, desde, hasta),
    )
    for fila in filas:
        fila["total"] = float(fila["total"])
    return filas


def totales_por_mes(usuario_id, desde, hasta):
    """Devuelve {(anio, mes): {"ingresos": x, "gastos": y}}."""
    filas = consultar(
        """SELECT YEAR(t.fecha) AS anio, MONTH(t.fecha) AS mes,
                  COALESCE(SUM(CASE WHEN t.tipo = 'ingreso' THEN t.monto END), 0) AS ingresos,
                  COALESCE(SUM(CASE WHEN t.tipo = 'gasto'   THEN t.monto END), 0) AS gastos
           FROM transacciones t JOIN cuentas c ON c.id = t.cuenta_id
           WHERE c.usuario_id = %s AND t.fecha BETWEEN %s AND %s
           GROUP BY anio, mes""",
        (usuario_id, desde, hasta),
    )
    return {(f["anio"], f["mes"]): {"ingresos": float(f["ingresos"]), "gastos": float(f["gastos"])}
            for f in filas}
