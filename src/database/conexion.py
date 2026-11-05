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
    finally:
        conexion.close()


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
