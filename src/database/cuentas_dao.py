"""Operaciones de cuentas (bancos, tarjetas, efectivo)."""
from database.conexion import consultar, ejecutar

TIPOS = {
    "banco": "Cuenta bancaria",
    "tarjeta_debito": "Tarjeta de débito",
    "tarjeta_credito": "Tarjeta de crédito",
    "monedero": "Efectivo / monedero",
}

# El saldo actual se calcula al vuelo: saldo inicial + ingresos - gastos
_SQL_LISTAR = """
    SELECT c.*,
           c.saldo_inicial + COALESCE(SUM(
               CASE WHEN t.tipo = 'ingreso' THEN t.monto
                    WHEN t.tipo = 'gasto'   THEN -t.monto
                    ELSE 0 END), 0) AS saldo_actual
    FROM cuentas c
    LEFT JOIN transacciones t ON t.cuenta_id = c.id
    WHERE c.usuario_id = %s {filtro}
    GROUP BY c.id
    ORDER BY c.nombre
"""


def listar(usuario_id, solo_activas=False):
    filtro = "AND c.activa = TRUE" if solo_activas else ""
    return consultar(_SQL_LISTAR.format(filtro=filtro), (usuario_id,))


def crear(usuario_id, nombre, tipo, banco, ultimos_4, saldo_inicial, color):
    return ejecutar(
        """INSERT INTO cuentas (usuario_id, nombre, tipo, banco, ultimos_4_digitos, saldo_inicial, color_icono)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (usuario_id, nombre, tipo, banco, ultimos_4 or None, saldo_inicial, color),
    )


def actualizar(cuenta_id, usuario_id, nombre, tipo, banco, ultimos_4, saldo_inicial, color, activa=True):
    ejecutar(
        """UPDATE cuentas SET nombre = %s, tipo = %s, banco = %s, ultimos_4_digitos = %s,
                  saldo_inicial = %s, color_icono = %s, activa = %s
           WHERE id = %s AND usuario_id = %s""",
        (nombre, tipo, banco, ultimos_4 or None, saldo_inicial, color, activa, cuenta_id, usuario_id),
    )


def eliminar(cuenta_id, usuario_id):
    """Ojo: borra también todos los movimientos de la cuenta."""
    ejecutar("DELETE FROM cuentas WHERE id = %s AND usuario_id = %s", (cuenta_id, usuario_id))
