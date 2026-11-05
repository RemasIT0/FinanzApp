"""Operaciones de presupuestos mensuales por categoría."""
from database.conexion import consultar, ejecutar


def listar(usuario_id, anio, mes):
    """Presupuestos del mes con lo que ya se gastó en cada uno."""
    return consultar(
        """SELECT p.id, p.categoria_id, p.monto_limite, cat.nombre, cat.icono, cat.color,
                  COALESCE((SELECT SUM(t.monto)
                            FROM transacciones t
                            JOIN cuentas c ON c.id = t.cuenta_id
                            WHERE c.usuario_id = p.usuario_id
                              AND t.categoria_id = p.categoria_id
                              AND t.tipo = 'gasto'
                              AND YEAR(t.fecha) = p.anio AND MONTH(t.fecha) = p.mes), 0) AS gastado
           FROM presupuestos p
           JOIN categorias cat ON cat.id = p.categoria_id
           WHERE p.usuario_id = %s AND p.anio = %s AND p.mes = %s
           ORDER BY cat.nombre""",
        (usuario_id, anio, mes),
    )


def alertas(usuario_id, anio, mes, umbral=0.8):
    """Presupuestos que ya llegaron al 80% (o más) de su límite."""
    return [p for p in listar(usuario_id, anio, mes)
            if p["monto_limite"] > 0 and float(p["gastado"]) >= float(p["monto_limite"]) * umbral]


def guardar(usuario_id, categoria_id, monto_limite, anio, mes):
    """Crea el presupuesto, o lo actualiza si ya existía para esa categoría y mes."""
    ejecutar(
        """INSERT INTO presupuestos (usuario_id, categoria_id, monto_limite, mes, anio)
           VALUES (%s, %s, %s, %s, %s)
           ON DUPLICATE KEY UPDATE monto_limite = VALUES(monto_limite)""",
        (usuario_id, categoria_id, monto_limite, mes, anio),
    )


def eliminar(presupuesto_id, usuario_id):
    ejecutar("DELETE FROM presupuestos WHERE id = %s AND usuario_id = %s", (presupuesto_id, usuario_id))


def copiar_de_mes(usuario_id, anio_origen, mes_origen, anio, mes):
    """Copia los presupuestos de otro mes (sin pisar los que ya existan)."""
    ejecutar(
        """INSERT IGNORE INTO presupuestos (usuario_id, categoria_id, monto_limite, mes, anio)
           SELECT usuario_id, categoria_id, monto_limite, %s, %s
           FROM presupuestos WHERE usuario_id = %s AND anio = %s AND mes = %s""",
        (mes, anio, usuario_id, anio_origen, mes_origen),
    )
