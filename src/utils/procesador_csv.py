"""Lectura de estados de cuenta en CSV/Excel y conversión a movimientos.

Cada banco exporta con columnas distintas. La idea es simple:
1. Leer el archivo y encontrar la fila de encabezados.
2. Adivinar qué columna es la fecha, la descripción y el monto.
3. Convertir cada fila en un movimiento {fecha, descripcion, monto, tipo}.
El usuario puede corregir el mapeo desde la pantalla si algo no cuadra.
"""
import csv
import io
import re
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd
from dateutil import parser as parser_fechas

from utils.calculos import leer_monto

CAMPOS = ["fecha", "descripcion", "monto", "cargo", "abono"]

# Nombres de columna que solemos encontrar (sin acentos y en minúsculas)
CANDIDATOS = {
    "fecha": ["fecha", "fecha operacion", "fecha de operacion", "fecha movimiento", "date", "dia"],
    "descripcion": ["descripcion", "concepto", "detalle", "movimiento", "referencia", "description", "comercio"],
    "monto": ["monto", "importe", "cantidad", "amount", "valor", "total"],
    "cargo": ["cargo", "cargos", "retiro", "retiros", "debito", "debitos", "egreso", "egresos"],
    "abono": ["abono", "abonos", "deposito", "depositos", "credito", "creditos", "ingreso", "ingresos"],
}

# Bancos de Argentina. Los nombres de columna son los más comunes en sus exportaciones;
# si tu archivo trae otros, la pantalla te deja elegir la columna a mano.
# "negativo": los gastos vienen con signo menos (lo normal en caja de ahorro / cuenta corriente)
# "positivo": los gastos vienen en positivo (común en resúmenes de tarjeta de crédito)
_DEBITOS_CREDITOS = {"fecha": ["fecha"], "descripcion": ["descripcion", "concepto", "detalle"],
                     "cargo": ["debitos", "debito"], "abono": ["creditos", "credito"], "signo": "negativo"}
FORMATOS_BANCO = {
    "Detectar automáticamente": {"signo": "negativo"},
    "Banco Nación": _DEBITOS_CREDITOS,
    "Galicia": _DEBITOS_CREDITOS,
    "Santander": _DEBITOS_CREDITOS,
    "BBVA": _DEBITOS_CREDITOS,
    "Macro": _DEBITOS_CREDITOS,
    "Mercado Pago": {"fecha": ["release_date", "fecha"], "descripcion": ["transaction_type", "descripcion"],
                     "monto": ["transaction_net_amount", "monto"], "signo": "negativo"},
    "Brubank / Ualá (columna Importe)": {"fecha": ["fecha"], "descripcion": ["descripcion", "concepto"],
                                         "monto": ["importe", "monto"], "signo": "negativo"},
    "Tarjeta de crédito (consumos en positivo)": {"signo": "positivo"},
}

# Palabras clave para sugerir categoría (comercios de Argentina). El orden importa: "uber eats" antes que "uber".
# Las palabras cortas llevan espacios (" dia ") para no coincidir dentro de otras palabras ("media").
PALABRAS_CLAVE = [
    ("Comida", ["pedidosya", "pedidos ya", "rappi", "uber eats", "mcdonald", "burger", "mostaza", "havanna",
                "starbucks", "cafe", "pizzeria", "parrilla", "restaurant", "resto ", "heladeria", "grido"]),
    ("Supermercado", ["coto", "carrefour", "jumbo", " disco ", " dia ", " vea ", "changomas", "la anonima",
                      "walmart", "makro", "vital", "diarco", "maxiconsumo", "autoservicio", "almacen", "verduleria"]),
    ("Transporte", ["sube", "uber", "cabify", "didi", "ypf", "shell", "axion", "puma energy", "nafta", "peaje",
                    "autopista", "estacionamiento", "subte", "trenes argentinos", "colectivo"]),
    ("Servicios", ["edenor", "edesur", "epec", "metrogas", "naturgy", "camuzzi", "aysa", "telecentro", "fibertel",
                   "personal flow", "telecom", "movistar", " claro ", "directv", "expensas", " abl ", "arba", "agip"]),
    ("Entretenimiento", ["netflix", "spotify", "disney", "hbo", " max ", "prime video", "paramount", "steam",
                         "playstation", "xbox", "cinemark", "hoyts", "cine", "teatro", "ticketek"]),
    ("Compras", ["mercado libre", "mercadolibre", "amazon", "shein", "temu", "falabella", "fravega", "garbarino",
                 "musimundo", "on city", "megatone", "dexter", "netshoes"]),
    ("Hogar", ["easy", "sodimac", "blaisten", "alquiler", "ferreteria"]),
    ("Salud", ["farmacity", "farmacia", "osde", "swiss medical", "galeno", "medicus", "omint", "hospital",
               "clinica", "sanatorio", "laboratorio", "odontolog"]),
    ("Educación", ["colegio", "universidad", "facultad", "udemy", "coursera", "libreria", "cuota escolar"]),
    ("Salario", ["haberes", "sueldo", "salario", "aguinaldo", "acreditacion de haberes", "nomina"]),
]


def normalizar(texto):
    """'Descripción ' -> 'descripcion'"""
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return texto.strip().lower()


# ---------- 1. Leer archivo ----------

def _leer_filas_csv(ruta):
    for codificacion in ("utf-8-sig", "latin-1"):
        try:
            texto = Path(ruta).read_text(encoding=codificacion)
            break
        except UnicodeDecodeError:
            continue
    return list(csv.reader(io.StringIO(texto), delimiter=_separador(texto)))


def _separador(texto):
    """Adivina si las columnas se separan con , ; tab o |.
    Se mira la fila de encabezados (la que empieza con "fecha"): ahí no hay montos con comas que confundan.
    Si no se encuentra, se usan las primeras filas."""
    lineas = [l for l in texto.splitlines()[:40] if l.strip()]
    encabezado = next((l for l in lineas if normalizar(l).lstrip('"').startswith(("fecha", "date", "release_date"))), None)
    muestra = [encabezado] if encabezado else lineas
    return max(",;\t|", key=lambda s: sum(l.count(s) for l in muestra))  # empate (ninguno) -> ","


def leer_archivo(ruta):
    """Devuelve un DataFrame con los encabezados correctos (todo como texto)."""
    if Path(ruta).suffix.lower() in (".xlsx", ".xls"):
        crudo = pd.read_excel(ruta, header=None, dtype=str)
        filas = crudo.fillna("").values.tolist()
    else:
        filas = _leer_filas_csv(ruta)

    # Muchos bancos ponen datos del cliente arriba: buscamos la fila que tiene "fecha"
    inicio = 0
    for i, fila in enumerate(filas[:30]):
        if any(normalizar(celda).startswith(("fecha", "date", "release_date")) for celda in fila):
            inicio = i
            break

    ancho = max(len(f) for f in filas[inicio:]) if filas else 0
    encabezados = [str(c).strip() or f"Columna {j + 1}" for j, c in
                   enumerate(filas[inicio] + [""] * (ancho - len(filas[inicio])))] if filas else []
    datos = [f + [""] * (ancho - len(f)) for f in filas[inicio + 1:]]
    df = pd.DataFrame(datos, columns=encabezados, dtype=str)
    return df[~(df.apply(lambda fila: "".join(fila).strip(), axis=1) == "")].reset_index(drop=True)


# ---------- 2. Mapear columnas ----------

def detectar_columnas(df, banco):
    """Devuelve {campo: nombre_de_columna o None}."""
    formato = FORMATOS_BANCO.get(banco, {})
    columnas = {normalizar(c): c for c in df.columns}
    mapeo, usadas = {}, set()

    for campo in CAMPOS:
        mapeo[campo] = None
        candidatos = formato.get(campo, []) + CANDIDATOS[campo]
        # Primero coincidencia exacta, luego "contiene"
        for comparar in (lambda n, c: n == c, lambda n, c: c in n):
            for candidato in candidatos:
                for nombre_norm, original in columnas.items():
                    if original not in usadas and comparar(nombre_norm, candidato):
                        mapeo[campo] = original
                        usadas.add(original)
                        break
                if mapeo[campo]:
                    break
            if mapeo[campo]:
                break

    # Si hay columnas de cargo/abono no hace falta "monto" (y al revés)
    if mapeo["cargo"] or mapeo["abono"]:
        mapeo["monto"] = None
    return mapeo


# ---------- 3. Convertir filas ----------

# Entiende '$ 1.234,56', '1234,56', '-1.234,56', '(1.234,56)' y también '1,234.56'.
# Es la misma función que usa toda la app (está en utils/calculos.py).
convertir_monto = leer_monto


def convertir_fecha(valor):
    texto = str(valor).strip()
    if not texto or texto.lower() in ("nan", "none"):
        return None
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}", texto):  # formato ISO (año primero)
            return date.fromisoformat(texto[:10])
        return parser_fechas.parse(texto, dayfirst=True).date()
    except (ValueError, OverflowError):
        return None


def detectar_signo(df, mapeo):
    """Con una sola columna de monto: si casi todo es positivo, lo positivo son gastos
    (así suelen venir los estados de tarjeta de crédito)."""
    if not mapeo.get("monto"):
        return "negativo"
    valores = [v for v in (convertir_monto(x) for x in df[mapeo["monto"]]) if v]
    positivos = sum(v > 0 for v in valores)
    return "positivo" if valores and positivos / len(valores) > 0.6 else "negativo"


def procesar(df, mapeo, signo="negativo"):
    """Convierte el DataFrame en una lista de movimientos. Devuelve (movimientos, filas_ignoradas)."""
    movimientos, ignoradas = [], 0
    for _, fila in df.iterrows():
        fecha = convertir_fecha(fila[mapeo["fecha"]]) if mapeo.get("fecha") else None
        descripcion = str(fila[mapeo["descripcion"]]).strip()[:200] if mapeo.get("descripcion") else ""

        tipo, monto = None, None
        if mapeo.get("cargo") or mapeo.get("abono"):
            cargo = convertir_monto(fila[mapeo["cargo"]]) if mapeo.get("cargo") else None
            abono = convertir_monto(fila[mapeo["abono"]]) if mapeo.get("abono") else None
            if cargo:
                tipo, monto = "gasto", abs(cargo)
            elif abono:
                tipo, monto = "ingreso", abs(abono)
        elif mapeo.get("monto"):
            valor = convertir_monto(fila[mapeo["monto"]])
            if valor:
                es_gasto = valor < 0 if signo == "negativo" else valor > 0
                tipo, monto = ("gasto" if es_gasto else "ingreso"), abs(valor)

        if fecha is None or tipo is None:
            ignoradas += 1
            continue
        movimientos.append({"fecha": fecha, "descripcion": descripcion or "(sin descripción)",
                            "monto": round(monto, 2), "tipo": tipo})
    return movimientos, ignoradas


def sugerir_categoria(descripcion, tipo, categorias):
    """Busca palabras clave en la descripción. categorias: lista de dicts de la BD."""
    texto = f" {normalizar(descripcion)} "  # con espacios a los lados para palabras como " dia "
    es_ingreso = tipo == "ingreso"
    propias = [c for c in categorias if bool(c["es_ingreso"]) == es_ingreso]
    por_nombre = {normalizar(c["nombre"]): c for c in propias}

    # 1) Si la descripción menciona el nombre de una categoría del usuario
    for nombre, categoria in por_nombre.items():
        if nombre and nombre in texto:
            return categoria
    # 2) Palabras clave conocidas
    for nombre_categoria, palabras in PALABRAS_CLAVE:
        if any(p in texto for p in palabras) and normalizar(nombre_categoria) in por_nombre:
            return por_nombre[normalizar(nombre_categoria)]
    # 3) "Otros gastos" / "Otros ingresos"
    return por_nombre.get("otros ingresos" if es_ingreso else "otros gastos")
