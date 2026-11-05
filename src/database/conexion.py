"""Conexión a MySQL.

Cada consulta abre y cierra su propia conexión. No es lo más rápido del
mundo, pero es muy simple y nunca deja conexiones colgadas.
"""
import mysql.connector

from utils.config import RAIZ, cargar_config

NOMBRE_BD = "finanzapp"
RUTA_SCHEMA = RAIZ / "database_schema.sql"


def obtener_conexion(con_bd=True):
    datos = cargar_config()["mysql"]
    parametros = {
        "host": datos["host"],
        "port": int(datos["puerto"]),
        "user": datos["usuario"],
        "password": datos["password"],
        "autocommit": True,
        "connection_timeout": 5,
    }
    if con_bd:
        parametros["database"] = NOMBRE_BD
    return mysql.connector.connect(**parametros)


def inicializar_bd():
    """Crea la base de datos y las tablas si todavía no existen."""
    lineas = [l for l in RUTA_SCHEMA.read_text(encoding="utf-8").splitlines()
              if not l.strip().startswith("--")]
    sentencias = [s.strip() for s in "\n".join(lineas).split(";") if s.strip()]
    conexion = obtener_conexion(con_bd=False)
    try:
        cursor = conexion.cursor()
        for sentencia in sentencias:
            cursor.execute(sentencia)
        _migrar(cursor)
    finally:
        conexion.close()


# Columnas que se agregaron después de la primera versión. "CREATE TABLE IF NOT EXISTS" no
# toca una tabla que ya existe, así que si a tu base de datos le falta la columna, se agrega aquí.
# (tabla, columna, cómo agregarla)
MIGRACIONES = [
    ("transacciones", "cuenta_destino_id",
     "ALTER TABLE transacciones ADD COLUMN cuenta_destino_id INT NULL AFTER cuenta_id, "
     "ADD FOREIGN KEY (cuenta_destino_id) REFERENCES cuentas(id) ON DELETE CASCADE"),
]


def _migrar(cursor):
    for tabla, columna, sql in MIGRACIONES:
        cursor.execute("""SELECT COUNT(*) FROM information_schema.COLUMNS
                          WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s""",
                       (NOMBRE_BD, tabla, columna))
        if cursor.fetchone()[0] == 0:
            cursor.execute(sql)


def consultar(sql, parametros=()):
    """Ejecuta un SELECT y devuelve una lista de diccionarios."""
    conexion = obtener_conexion()
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute(sql, parametros)
        return cursor.fetchall()
    finally:
        conexion.close()


def consultar_uno(sql, parametros=()):
    filas = consultar(sql, parametros)
    return filas[0] if filas else None


def ejecutar(sql, parametros=()):
    """Ejecuta un INSERT/UPDATE/DELETE y devuelve el id insertado."""
    conexion = obtener_conexion()
    try:
        cursor = conexion.cursor()
        cursor.execute(sql, parametros)
        return cursor.lastrowid
    finally:
        conexion.close()


def ejecutar_varios(sql, lista_parametros):
    """Inserta muchas filas de una sola vez (se usa al importar archivos)."""
    if not lista_parametros:
        return 0
    conexion = obtener_conexion()
    try:
        cursor = conexion.cursor()
        cursor.executemany(sql, lista_parametros)
        return cursor.rowcount
    finally:
        conexion.close()
