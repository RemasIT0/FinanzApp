"""Asistente (chatbot) de FinanzApp: respuestas rápidas sin internet ni inteligencia artificial.

Cómo funciona:
1. Se "normaliza" la pregunta: minúsculas y sin acentos ("¿Cuánto GASTÉ?" -> "¿cuanto gaste?").
2. Cada tema (INTENCIONES) tiene una lista de frases clave. Se suman puntos por cada frase
   encontrada; las frases más largas valen más ("estado de cuenta" gana a "cuenta").
3. Gana el tema con más puntos y su función arma la respuesta (algunas leen tus datos reales).

Cada respuesta es un diccionario:
    texto        -> lo que dice el asistente
    acciones     -> botones: [(texto del botón, acción)], por ejemplo ("Abrir Importar", ("ir", "importar"))
    sugerencias  -> preguntas que se ofrecen como atajos
No tiene nada de interfaz, así lo puede usar la app de escritorio y, más adelante, la web.
"""
import re
import unicodedata
from datetime import date

from database import cuentas_dao, presupuestos_dao, transacciones_dao
from utils import calculos

SUGERENCIAS_INICIO = ["¿Cuánto gasté este mes?", "Saldo de mis cuentas", "¿Cómo importo mi banco?",
                      "Conectar mi correo", "Ver el tutorial"]


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(texto.lower().replace("?", " ").replace("¿", " ").replace("!", " ").split())


def _respuesta(texto, acciones=None, sugerencias=None):
    return {"texto": texto, "acciones": acciones or [], "sugerencias": sugerencias or []}


def _mes_actual():
    hoy = date.today()
    return hoy, *calculos.rango_mes(hoy.year, hoy.month)


dinero = calculos.formato_moneda


# ---------- Respuestas con tus datos ----------

def _gastos_mes(usuario):
    hoy, desde, hasta = _mes_actual()
    totales = transacciones_dao.totales(usuario["id"], desde, hasta)
    categorias = transacciones_dao.gastos_por_categoria(usuario["id"], desde, hasta)
    if not totales["gastos"]:
        return _respuesta("Este mes todavía no registraste gastos.",
                          [("＋ Registrar un gasto", ("nuevo",))], ["¿Cómo registro un gasto?"])
    top = "\n".join(f"• {c['icono']} {c['nombre']}: {dinero(c['total'])}" for c in categorias[:3])
    texto = (f"En {calculos.nombre_mes(hoy.year, hoy.month).lower()} llevas gastado {dinero(totales['gastos'])}.\n\n"
             f"Donde más gastaste:\n{top}")
    return _respuesta(texto, [("Ver reportes", ("ir", "reportes"))], ["¿Cómo voy este mes?", "Mis presupuestos"])


def _ingresos_mes(usuario):
    hoy, desde, hasta = _mes_actual()
    ingresos = transacciones_dao.totales(usuario["id"], desde, hasta)["ingresos"]
    texto = (f"Este mes te entraron {dinero(ingresos)}." if ingresos else
             "Este mes todavía no registraste ingresos.")
    return _respuesta(texto, [("Ver historial", ("ir", "historial"))], ["¿Cuánto gasté este mes?", "¿Cómo voy este mes?"])


def _balance(usuario):
    hoy, desde, hasta = _mes_actual()
    t = transacciones_dao.totales(usuario["id"], desde, hasta)
    balance = t["ingresos"] - t["gastos"]
    ahorro = calculos.tasa_ahorro(t["ingresos"], t["gastos"])
    texto = (f"Resumen de {calculos.nombre_mes(hoy.year, hoy.month).lower()}:\n"
             f"• Ingresos: {dinero(t['ingresos'])}\n• Gastos: {dinero(t['gastos'])}\n"
             f"• Balance: {dinero(balance)}\n• Ahorro: {ahorro:.0f}% de tus ingresos\n\n")
    if t["gastos"]:
        p = calculos.proyeccion_fin_mes(t["gastos"], hoy)
        texto += f"A este ritmo terminarías el mes con {dinero(p['proyeccion'])} en gastos."
    return _respuesta(texto.strip(), [("Ver reportes", ("ir", "reportes"))], ["Mis presupuestos", "Saldo de mis cuentas"])


def _saldos(usuario):
    cuentas = cuentas_dao.listar(usuario["id"], solo_activas=True)
    if not cuentas:
        return _respuesta("Todavía no tienes cuentas activas.", [("Crear una cuenta", ("ir", "config"))])
    lineas = "\n".join(f"• {c['nombre']}: {dinero(float(c['saldo_actual']))}" for c in cuentas)
    total = sum(float(c["saldo_actual"]) for c in cuentas)
    return _respuesta(f"Saldo de tus cuentas:\n{lineas}\n\nTotal: {dinero(total)}",
                      [("Administrar cuentas", ("ir", "config"))], ["¿Cómo agrego una cuenta?"])


def _presupuestos(usuario):
    hoy = date.today()
    lista = presupuestos_dao.listar(usuario["id"], hoy.year, hoy.month)
    if not lista:
        return _respuesta("No tienes presupuestos este mes.\n\nPara crear uno: Configuración → Presupuestos, "
                          "elige una categoría y un límite. Te aviso en Inicio al llegar al 80%.",
                          [("Crear presupuesto", ("ir", "config"))])
    lineas = []
    for p in lista:
        gastado, limite = float(p["gastado"]), float(p["monto_limite"])
        marca = "🔴" if gastado > limite else "🟡" if gastado >= limite * 0.8 else "🟢"
        lineas.append(f"{marca} {p['nombre']}: {dinero(gastado)} de {dinero(limite)}")
    return _respuesta("Tus presupuestos de este mes:\n" + "\n".join(lineas),
                      [("Editar presupuestos", ("ir", "config"))], ["¿Cuánto gasté este mes?"])


def _ultimos(usuario):
    ultimos = transacciones_dao.ultimas(usuario["id"], 5)
    if not ultimos:
        return _respuesta("Todavía no tienes movimientos.", [("＋ Registrar uno", ("nuevo",))])
    lineas = "\n".join(
        f"• {t['fecha']:%d/%m} {t['descripcion'][:28]}: "
        f"{dinero(float(t['monto']) * (-1 if t['tipo'] == 'gasto' else 1), con_signo=True)}" for t in ultimos)
    return _respuesta(f"Tus últimos movimientos:\n{lineas}", [("Ver historial", ("ir", "historial"))])


# ---------- Respuestas de "cómo se hace" ----------

def _fija(texto, acciones=None, sugerencias=None):
    """Para respuestas que no dependen de tus datos."""
    return lambda _usuario: _respuesta(texto, acciones, sugerencias)


# (clave, frases clave, función que responde). El orden decide los empates.
INTENCIONES = [
    ("tutorial", ["tutorial", "guia", "recorrido", "como se usa", "como funciona la app", "empezar", "ensename"],
     _fija("¡Claro! Te muestro la app paso a paso.", [("▶ Empezar tutorial", ("tutorial",))])),
    ("gastos_mes", ["cuanto gaste", "gaste", "gastos del mes", "en que gasto", "en que se va", "cuanto llevo",
                    "mis gastos", "en que gaste"], _gastos_mes),
    ("ingresos_mes", ["ingresos", "ingreso", "cuanto gane", "cuanto me entro", "cuanto cobre", "sueldo"], _ingresos_mes),
    ("balance", ["balance", "resumen", "como voy", "como van mis finanzas", "ahorro", "ahorre", "proyeccion"], _balance),
    ("saldos", ["saldo", "cuanto tengo", "mis cuentas", "dinero tengo", "cuanto dinero"], _saldos),
    ("presupuestos", ["presupuesto", "presupuestos", "limite"], _presupuestos),
    ("ultimos", ["ultimos movimientos", "ultimo movimiento", "movimientos recientes", "que registre"], _ultimos),
    ("registrar", ["registrar", "registro", "agregar gasto", "agrego un gasto", "nuevo movimiento", "anotar",
                   "cargar un gasto", "cargar gasto", "agregar ingreso", "nuevo gasto"],
     _fija("Para registrar un movimiento:\n1. Toca «＋ Nuevo movimiento» en la barra lateral.\n"
           "2. Elige Gasto o Ingreso, escribe el monto y toca una categoría.\n3. Elige cuenta y fecha, y Guardar.\n\n"
           "Más rápido: en Inicio usa «⚡ Gasto rápido»: escribe el monto y toca la categoría.",
           [("＋ Nuevo movimiento", ("nuevo",))], ["¿Cómo edito un movimiento?"])),
    ("editar", ["editar", "edito", "borrar", "borro", "eliminar", "corregir", "modificar", "me equivoque"],
     _fija("Para editar o borrar un movimiento: ve a Historial, búscalo con los filtros y "
           "haz doble clic (o selecciónalo y toca Editar / Eliminar).",
           [("Abrir Historial", ("ir", "historial"))])),
    ("importar", ["importar", "importo", "csv", "excel", "estado de cuenta", "extracto", "archivo del banco", "resumen del banco"],
     _fija("Para importar movimientos de tu banco:\n1. Descarga el estado de cuenta en CSV o Excel desde tu banco.\n"
           "2. Ve a Importar → Seleccionar archivo.\n3. Elige banco y cuenta, revisa la vista previa.\n"
           "4. Toca Importar. Los repetidos se saltan solos.",
           [("Abrir Importar", ("ir", "importar"))], ["¿Puedo leer los avisos de mi correo?"])),
    ("correo", ["correo", "email", "mail", "gmail", "yahoo", "conectar", "sincroniz", "aviso",
                "contrasena de aplicacion", "apppasswords", "leer los avisos"],
     _fija("Para conectar tu correo:\n1. Activa la verificación en dos pasos en tu cuenta de Google.\n"
           "2. Crea una contraseña de aplicación en myaccount.google.com/apppasswords.\n"
           "3. En la app: Correo → Conectar correo, y pega las 16 letras.\n"
           "4. Enciende tu banco en «Bancos que se leen» y toca Sincronizar ahora.",
           [("Abrir Correo", ("ir", "correo"))], ["No me detecta los correos", "¿Cómo agrego un banco?"])),
    ("patrones", ["patron", "regex", "sin monto", "no se cargo", "no aparece", "no detecta", "no me detecta",
                  "no lee", "agregar banco", "agrego un banco", "banco nuevo", "no parecian avisos"],
     _fija("Si un correo del banco no aparece:\n• «No parecían avisos»: el asunto no coincide. Edita el banco (✎) "
           "y agrega esa palabra al Patrón del asunto, separada con |.\n"
           "• «Sin monto reconocible»: el monto viene en otro formato; hay que ajustar el Patrón del monto.\n"
           "• Nada: revisa que el banco esté encendido y que «El remitente contiene» esté en la dirección del correo.\n\n"
           "Para un banco nuevo: «＋ Agregar banco», copia los patrones de otro banco y cambia nombre y remitente.",
           [("Abrir Correo", ("ir", "correo"))])),
    ("recuperar", ["olvide", "recuperar", "cambiar contrasena", "cambiar mi contrasena", "codigo", "contrasena"],
     _fija("Para recuperar tu contraseña: cierra sesión, toca «¿Olvidaste tu contraseña?», escribe tu correo y "
           "usa el código de 6 dígitos que te llega (vence en 15 minutos).\n\n"
           "Antes, una sola vez: Configuración → Datos → Configurar correo de envío.",
           [("Abrir Configuración", ("ir", "config"))])),
    ("cuentas", ["agregar cuenta", "agrego una cuenta", "nueva cuenta", "tarjeta", "banco", "efectivo", "cuenta"],
     _fija("Para agregar una cuenta (banco, tarjeta o efectivo): Configuración → Cuentas → «＋ Nueva cuenta». "
           "Pon el saldo inicial: la app calcula el saldo actual sola con tus movimientos.",
           [("Abrir Configuración", ("ir", "config"))], ["Saldo de mis cuentas"])),
    ("categorias", ["categoria", "categorias", "icono"],
     _fija("Para crear o editar categorías: Configuración → Categorías. Elige nombre, icono, color y si es de gasto "
           "o de ingreso. Si borras una, sus movimientos quedan «Sin categoría».",
           [("Abrir Configuración", ("ir", "config"))])),
    ("exportar", ["exportar", "pdf", "descargar", "imprimir"],
     _fija("Para exportar: en Historial filtra lo que quieras y toca CSV o PDF arriba a la derecha.",
           [("Abrir Historial", ("ir", "historial"))], ["¿Cómo hago un respaldo?"])),
    ("respaldo", ["respaldo", "backup", "copia de seguridad", "otra computadora"],
     _fija("Para respaldar todo: Configuración → Datos → Exportar respaldo (un archivo .json). "
           "Con «Importar respaldo» lo cargas en esta u otra computadora.",
           [("Abrir Configuración", ("ir", "config"))])),
    ("tema", ["modo oscuro", "modo claro", "oscuro", "claro", "tema", "colores"],
     _fija("Cambia entre modo claro y oscuro con el interruptor «Modo oscuro» abajo en la barra lateral.")),
    ("celular", ["celular", "movil", "telefono", "android", "iphone", "version web"],
     _fija("Para usarla en el celular: en la computadora corre «python src/main_web.py» y abre en el celular "
           "la dirección que aparece (mismo WiFi). Usa los mismos datos que esta app.")),
    ("ayuda", ["ayuda", "que puedes", "que sabes", "opciones", "que haces", "menu"],
     _fija("Puedo:\n• Decirte cuánto gastaste, tus ingresos, tu balance y tus saldos.\n• Mostrar tus presupuestos "
           "y últimos movimientos.\n• Explicarte cómo registrar, importar, conectar el correo, exportar y más.\n"
           "• Mostrarte el tutorial otra vez.", sugerencias=SUGERENCIAS_INICIO)),
    ("gracias", ["gracias", "genial", "perfecto", "excelente"], _fija("¡De nada! Si necesitas algo más, pregúntame. 😊")),
    ("saludo", ["hola", "buenas", "buen dia", "buenos dias", "buenas tardes", "hey"],
     _fija("¡Hola! ¿En qué te ayudo?", sugerencias=SUGERENCIAS_INICIO)),
]


def bienvenida(usuario):
    nombre = usuario["nombre"].split()[0]
    return _respuesta(f"¡Hola, {nombre}! Soy el asistente de FinanzApp. Pregúntame por tus gastos, tus cuentas "
                      "o cómo usar la app.", sugerencias=SUGERENCIAS_INICIO)


def responder(pregunta, usuario):
    """Elige el tema con más puntos y devuelve su respuesta."""
    texto = normalizar(pregunta)
    mejor, puntos_mejor = None, 0
    for clave, frases, funcion in INTENCIONES:
        # Cada frase encontrada suma tantos puntos como palabras tiene.
        # \b = la frase empieza al inicio de una palabra ("tema" no cuenta dentro de "sistema"),
        # pero puede seguir ("correo" sí cuenta dentro de "correos").
        puntos = sum(len(f.split()) for f in frases if re.search(r"\b" + re.escape(f), texto))
        if puntos > puntos_mejor:
            mejor, puntos_mejor = funcion, puntos
    if mejor is None:
        return _respuesta("No entendí bien 🤔. Prueba con otras palabras o toca una de estas opciones:",
                          sugerencias=SUGERENCIAS_INICIO)
    return mejor(usuario)
