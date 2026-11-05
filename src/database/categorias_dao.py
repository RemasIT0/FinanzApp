"""Operaciones de categorías."""
from database.conexion import consultar, ejecutar, ejecutar_varios

# (nombre, icono, color, es_ingreso)
POR_DEFECTO = [
    ("Comida", "🍔", "#e94560", False),
    ("Supermercado", "🛒", "#ff7f50", False),
    ("Transporte", "🚗", "#3498db", False),
    ("Hogar", "🏠", "#9b59b6", False),
    ("Servicios", "💡", "#f39c12", False),
    ("Salud", "💊", "#1abc9c", False),
    ("Entretenimiento", "🎬", "#e67e22", False),
    ("Compras", "🛍", "#d35400", False),
    ("Educación", "📚", "#2980b9", False),
    ("Otros gastos", "📦", "#7f8c8d", False),
    ("Salario", "💼", "#4ecca3", True),
    ("Ventas", "💰", "#27ae60", True),
    ("Otros ingresos", "✨", "#16a085", True),
]

ICONOS_DISPONIBLES = [
    "🍔", "☕", "🛒", "🚗", "⛽", "🚌", "🏠", "💡", "📱", "💊", "🏥", "🎬",
    "🎮", "🎵", "🛍", "👕", "📚", "🎓", "✈", "🐶", "🎁", "💳", "🏦", "📦",
    "💼", "💰", "✨", "📈", "🧾", "🔧", "💪", "👶",
]


def listar(usuario_id, es_ingreso=None):
    sql = "SELECT * FROM categorias WHERE usuario_id = %s"
    parametros = [usuario_id]
    if es_ingreso is not None:
        sql += " AND es_ingreso = %s"
        parametros.append(es_ingreso)
    return consultar(sql + " ORDER BY nombre", parametros)


def mas_usadas(usuario_id, cantidad=4):
    """Categorías de gasto ordenadas por cuántas veces se usaron (para el gasto rápido)."""
    return consultar(
        """SELECT cat.*, COUNT(t.id) AS usos
           FROM categorias cat
           LEFT JOIN transacciones t ON t.categoria_id = cat.id
           WHERE cat.usuario_id = %s AND cat.es_ingreso = FALSE
           GROUP BY cat.id
           ORDER BY usos DESC, cat.id
           LIMIT %s""",
        (usuario_id, cantidad),
    )


def crear(usuario_id, nombre, icono, color, es_ingreso):
    return ejecutar(
        "INSERT INTO categorias (usuario_id, nombre, icono, color, es_ingreso) VALUES (%s, %s, %s, %s, %s)",
        (usuario_id, nombre, icono, color, es_ingreso),
    )


def actualizar(categoria_id, usuario_id, nombre, icono, color, es_ingreso):
    ejecutar(
        """UPDATE categorias SET nombre = %s, icono = %s, color = %s, es_ingreso = %s
           WHERE id = %s AND usuario_id = %s""",
        (nombre, icono, color, es_ingreso, categoria_id, usuario_id),
    )


def eliminar(categoria_id, usuario_id):
    """Los movimientos de esta categoría quedan 'Sin categoría'."""
    ejecutar("DELETE FROM categorias WHERE id = %s AND usuario_id = %s", (categoria_id, usuario_id))


def crear_por_defecto(usuario_id):
    ejecutar_varios(
        "INSERT INTO categorias (usuario_id, nombre, icono, color, es_ingreso) VALUES (%s, %s, %s, %s, %s)",
        [(usuario_id, *categoria) for categoria in POR_DEFECTO],
    )
