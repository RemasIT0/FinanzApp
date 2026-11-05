"""Funciones de cálculo y formato (fechas, dinero, porcentajes)."""
import calendar
from datetime import date

MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]


def fecha_larga(fecha):
    """date(2026, 10, 29) -> 'Jueves 29 de octubre'"""
    return f"{DIAS[fecha.weekday()]} {fecha.day} de {MESES[fecha.month - 1].lower()}"


# ---------- Dinero (formato argentino: punto para miles, coma para decimales) ----------

def formato_numero(valor, decimales=2):
    """1234567.5 -> '1.234.567,50'"""
    texto = f"{valor:,.{decimales}f}"  # Python lo da al estilo inglés: '1,234,567.50'
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formato_moneda(valor, con_signo=False):
    """1234.5 -> '$ 1.234,50'  ·  -1234.5 -> '-$ 1.234,50'  ·  con_signo: '+$ 1.234,50'"""
    texto = "$ " + formato_numero(abs(valor))  # espacio que no se corta: "$" nunca queda solo en una línea
    if valor < 0:
        return "-" + texto
    return ("+" + texto) if con_signo and valor > 0 else texto


def monto_para_editar(valor):
    """Cómo se muestra un monto dentro de un campo para editarlo: 1250.5 -> '1250,50'"""
    return f"{float(valor):.2f}".replace(".", ",")


def leer_monto(valor):
    """Convierte lo que escribió el usuario (o lo que trae un archivo o correo) en número.

    Entiende el formato argentino y también el inglés/mexicano:
      '1.250,50' '1250,50' '$ 1.250' 'ARS 1.250,50'  -> formato argentino
      '1,250.50' '1250.50'                            -> formato inglés
      '-500' '(500)'                                  -> negativo
    Regla para un solo tipo de separador:
      - solo puntos:  '1.250' o '1.250.000' (grupos de 3) = miles;  '12.5' = decimal
      - solo comas:   '1,250' o '1,250,000' (grupos de 3) = miles;  '12,5' = decimal
    Devuelve None si no es un número.
    """
    texto = str(valor).strip()
    for quitar in ("ARS", "AR$", "MXN", "$", " ", "\xa0"):
        texto = texto.replace(quitar, "")
    if not texto or texto.lower() in ("nan", "none", "-"):
        return None
    negativo = texto.startswith("-") or (texto.startswith("(") and texto.endswith(")"))
    texto = texto.strip("()-+")

    if "," in texto and "." in texto:
        # El separador que aparece al final es el decimal
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")   # 1.250,50
        else:
            texto = texto.replace(",", "")                      # 1,250.50
    else:
        for separador in (",", "."):
            if separador in texto:
                partes = texto.split(separador)
                miles = len(partes) > 2 or len(partes[-1]) == 3
                texto = texto.replace(separador, "" if miles else ".")
    try:
        numero = float(texto)
    except ValueError:
        return None
    return -numero if negativo else numero


def nombre_mes(anio, mes):
    return f"{MESES[mes - 1]} {anio}"


def etiqueta_corta(anio, mes):
    return f"{MESES[mes - 1][:3]} {str(anio)[2:]}"


def rango_mes(anio, mes):
    """Primer y último día del mes."""
    return date(anio, mes, 1), date(anio, mes, calendar.monthrange(anio, mes)[1])


def mover_mes(anio, mes, cantidad):
    """Suma (o resta, si es negativo) meses a un (anio, mes)."""
    total = anio * 12 + (mes - 1) + cantidad
    return total // 12, total % 12 + 1


def ultimos_meses(cantidad, hoy=None):
    """Lista de (anio, mes) de los últimos N meses, del más viejo al actual."""
    hoy = hoy or date.today()
    return [mover_mes(hoy.year, hoy.month, -i) for i in range(cantidad - 1, -1, -1)]


def porcentaje(parte, total):
    return (parte / total * 100) if total else 0


def tasa_ahorro(ingresos, gastos):
    """Qué porcentaje de lo que entró no se gastó."""
    return max(porcentaje(ingresos - gastos, ingresos), 0)


def proyeccion_fin_mes(gasto_actual, hoy=None):
    """Estima el gasto total del mes según el promedio diario hasta hoy."""
    hoy = hoy or date.today()
    dias_mes = calendar.monthrange(hoy.year, hoy.month)[1]
    promedio_diario = gasto_actual / hoy.day
    return {"promedio_diario": promedio_diario,
            "proyeccion": promedio_diario * dias_mes,
            "dias_restantes": dias_mes - hoy.day}
