"""Operaciones de cuentas (bancos, tarjetas, efectivo)."""
from database.conexion import consultar, ejecutar

TIPOS = {
    "banco": "Cuenta bancaria",
    "tarjeta_debito": "Tarjeta de débito",
    "tarjeta_credito": "Tarjeta de crédito",
    "monedero": "Efectivo / monedero",
}

# El saldo actual se calcula al vuelo:
#   saldo inicial + ingresos - gastos - transferencias que salen + transferencias que entran
# es_predeterminada: 1 si es la cuenta elegida para el gasto rápido y los movimientos nuevos
_SQL_LISTAR = """
    SELECT c.*,
           c.saldo_inicial
           + COALESCE((SELECT SUM(CASE WHEN t.tipo = 'ingreso' THEN t.monto ELSE -t.monto END)
                       FROM transacciones t WHERE t.cuenta_id = c.id), 0)
           + COALESCE((SELECT SUM(t.monto) FROM transacciones t
                       WHERE t.cuenta_destino_id = c.id AND t.tipo = 'transferencia'), 0) AS saldo_actual,
           COALESCE(p.cuenta_predeterminada_id = c.id, 0) AS es_predeterminada
    FROM cuentas c
    LEFT JOIN preferencias p ON p.usuario_id = c.usuario_id
    WHERE c.usuario_id = %s {filtro}
    ORDER BY c.nombre
"""


def listar(usuario_id, solo_activas=False):
    filtro = "AND c.activa = TRUE" if solo_activas else ""
    return consultar(_SQL_LISTAR.format(filtro=filtro), (usuario_id,))


def predeterminada(cuentas):
    """De una lista de cuentas, la predeterminada; si no hay ninguna marcada, la primera (o None)."""
    return next((c for c in cuentas if c["es_predeterminada"]), cuentas[0] if cuentas else None)


def marcar_predeterminada(usuario_id, cuenta_id):
    """Elige la cuenta del gasto rápido y de los movimientos nuevos (None = ninguna)."""
    ejecutar("""INSERT INTO preferencias (usuario_id, cuenta_predeterminada_id) VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE cuenta_predeterminada_id = VALUES(cuenta_predeterminada_id)""",
             (usuario_id, cuenta_id))


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
