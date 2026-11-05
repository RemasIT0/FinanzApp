"""Versión web de FinanzApp, pensada para usarse desde el celular.

Reutiliza la misma base de datos y la misma lógica que la app de escritorio
(database/*_dao.py y utils/). Aquí solo están las "pantallas" (rutas) y los
datos que cada una necesita; el HTML está en web/templates/.

Se arranca con:  python src/main_web.py
"""
import time
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from database import categorias_dao, cuentas_dao, presupuestos_dao, transacciones_dao, usuarios_dao
from utils import calculos, recuperacion
from utils.config import cargar_config
from utils.validadores import convertir_monto, email_valido, password_valida, texto_requerido

CARPETA = Path(__file__).parent
GASTO, INGRESO, NEUTRO, AHORRO = "#e94560", "#4ecca3", "#3498db", "#f9d923"

app = FastAPI(docs_url=None, redoc_url=None)
# La sesión va en una cookie firmada: nadie puede cambiar su "uid" sin la clave
app.add_middleware(SessionMiddleware, secret_key=cargar_config()["clave_web"] or "solo-pruebas",
                   max_age=30 * 24 * 3600, same_site="lax")
app.mount("/static", StaticFiles(directory=CARPETA / "static"), name="static")

plantillas = Jinja2Templates(directory=CARPETA / "templates")
plantillas.env.filters["dinero"] = calculos.formato_moneda
plantillas.env.filters["dinero_signo"] = lambda v: calculos.formato_moneda(v, con_signo=True)


# ---------- Ayudantes ----------

class SinSesion(Exception):
    """Se lanza cuando alguien entra a una página sin haber iniciado sesión."""


@app.exception_handler(SinSesion)
def _a_login(request, _):
    return RedirectResponse("/login", status_code=303)


def usuario_actual(request):
    uid = request.session.get("uid")
    usuario = usuarios_dao.obtener(uid) if uid else None
    if usuario is None:
        request.session.clear()
        raise SinSesion()
    return usuario


def avisar(request, texto, tipo="ok"):
    """Mensaje que se muestra una vez en la siguiente página (tipo "toast")."""
    request.session["aviso"] = [texto, tipo]


def mostrar(request, plantilla, **datos):
    datos["aviso"] = request.session.pop("aviso", None)
    return plantillas.TemplateResponse(request, plantilla, datos)


def entero(texto):
    """Los formularios mandan texto (a veces vacío): '12' -> 12, '' -> 0."""
    return int(texto) if str(texto).strip().isdigit() else 0


def ir(url):
    # 303 = después de un POST, el navegador abre la página con GET (así recargar no reenvía el formulario)
    return RedirectResponse(url, status_code=303)


def movimiento_para_vista(t):
    es_gasto = t["tipo"] == "gasto"
    return {**t, "monto": float(t["monto"]), "con_signo": float(t["monto"]) * (-1 if es_gasto else 1),
            "icono": t["icono"] or "❔", "color": t["color"] or "#7f8c8d",
            "categoria": t["categoria"] or "Sin categoría"}


def dona(por_categoria):
    """Tramos para dibujar la dona con CSS (conic-gradient), sin librerías de gráficas."""
    total = sum(c["total"] for c in por_categoria) or 1
    tramos, inicio = [], 0.0
    for c in por_categoria:
        fin = inicio + c["total"] / total * 100
        tramos.append(f"{c['color']} {inicio:.2f}% {fin:.2f}%")
        inicio = fin
    return {"gradiente": ", ".join(tramos),
            "leyenda": [{**c, "porcentaje": c["total"] / total * 100} for c in por_categoria]}


def barras_meses(usuario_id, meses):
    """Ingresos y gastos de cada mes, con su altura (%) para dibujar barras."""
    por_mes = transacciones_dao.totales_por_mes(usuario_id, calculos.rango_mes(*meses[0])[0],
                                                calculos.rango_mes(*meses[-1])[1])
    vacio = {"ingresos": 0, "gastos": 0}
    filas = [{"etiqueta": calculos.etiqueta_corta(*m), **por_mes.get(m, vacio)} for m in meses]
    maximo = max([max(f["ingresos"], f["gastos"]) for f in filas] + [1])
    for f in filas:
        f["alto_ingresos"] = f["ingresos"] / maximo * 100
        f["alto_gastos"] = f["gastos"] / maximo * 100
        f["ahorro"] = max(f["ingresos"] - f["gastos"], 0)
    return filas


def lineas_svg(filas, ancho=320, alto=120):
    """Puntos de cada línea (ingresos, gastos, ahorro) para un <polyline> de SVG."""
    maximo = max([max(f["ingresos"], f["gastos"]) for f in filas] + [1])
    paso = ancho / max(len(filas) - 1, 1)

    def puntos(clave):
        return " ".join(f"{i * paso:.1f},{alto - f[clave] / maximo * (alto - 6) - 3:.1f}" for i, f in enumerate(filas))
    return {"ancho": ancho, "alto": alto, "series": [
        {"nombre": "Ingresos", "color": INGRESO, "puntos": puntos("ingresos")},
        {"nombre": "Gastos", "color": GASTO, "puntos": puntos("gastos")},
        {"nombre": "Ahorro", "color": AHORRO, "puntos": puntos("ahorro")}]}


# ---------- Entrar, crear cuenta y salir ----------

_fallos = {}  # email -> (fallos, hora del último): frena a quien prueba contraseñas sin parar


@app.get("/login")
def login(request: Request):
    if request.session.get("uid"):
        return ir("/")
    return mostrar(request, "login.html", email=cargar_config()["ultimo_email"], modo="entrar")


@app.post("/login")
def login_enviar(request: Request, email: str = Form(""), password: str = Form("")):
    email = email.strip().lower()
    fallos, ultimo = _fallos.get(email, (0, 0))
    if fallos >= 5 and time.time() - ultimo < 60:
        return mostrar(request, "login.html", email=email, modo="entrar",
                       error="Demasiados intentos. Espera un minuto.")
    usuario = usuarios_dao.iniciar_sesion(email, password) if email_valido(email) else None
    if usuario is None:
        _fallos[email] = (fallos + 1, time.time())
        return mostrar(request, "login.html", email=email, modo="entrar", error="Correo o contraseña incorrectos.")
    _fallos.pop(email, None)
    request.session.clear()
    request.session["uid"] = usuario["id"]
    return ir("/")


@app.get("/registro")
def registro(request: Request):
    return mostrar(request, "login.html", modo="registro", email="", nombre="")


@app.post("/registro")
def registro_enviar(request: Request, nombre: str = Form(""), email: str = Form(""), password: str = Form("")):
    email = email.strip().lower()
    nombre_ok = texto_requerido(nombre, 100)

    def error(texto):
        return mostrar(request, "login.html", modo="registro", email=email, nombre=nombre, error=texto)
    if not nombre_ok:
        return error("Escribe tu nombre.")
    if not email_valido(email):
        return error("Escribe un correo válido.")
    if not password_valida(password):
        return error("La contraseña debe tener al menos 6 caracteres.")
    if usuarios_dao.existe_email(email):
        return error("Ese correo ya está registrado. Inicia sesión.")
    request.session.clear()
    request.session["uid"] = usuarios_dao.registrar(nombre_ok, email, password)
    avisar(request, "✓ Cuenta creada. ¡Bienvenido!")
    return ir("/")


@app.get("/salir")
def salir(request: Request):
    request.session.clear()
    return ir("/login")


# ---------- Recuperar contraseña ----------

@app.get("/recuperar")
def recuperar(request: Request, paso: str = ""):
    email = request.session.get("recuperar_email", "")
    if paso == "codigo" and email:
        return mostrar(request, "recuperar.html", paso="codigo", email=email,
                       mensaje=recuperacion.MENSAJE_ENVIADO)
    return mostrar(request, "recuperar.html", paso="correo", email=email,
                   disponible=recuperacion.disponible())


@app.post("/recuperar")
def recuperar_enviar(request: Request, email: str = Form("")):
    email = email.strip().lower()
    if not email_valido(email):
        return mostrar(request, "recuperar.html", paso="correo", email=email, disponible=True,
                       error="Escribe un correo válido.")
    try:
        recuperacion.solicitar(email)
    except ValueError as e:
        return mostrar(request, "recuperar.html", paso="correo", email=email,
                       disponible=recuperacion.disponible(), error=str(e))
    request.session["recuperar_email"] = email
    return ir("/recuperar?paso=codigo")


@app.post("/recuperar/cambiar")
def recuperar_cambiar(request: Request, codigo: str = Form(""), nueva: str = Form(""), repetir: str = Form("")):
    email = request.session.get("recuperar_email")
    if not email:
        return ir("/recuperar")

    def error(texto):
        return mostrar(request, "recuperar.html", paso="codigo", email=email, error=texto)
    codigo = codigo.strip()
    if not (codigo.isdigit() and len(codigo) == 6):
        return error("El código tiene 6 números.")
    if not password_valida(nueva):
        return error("La contraseña debe tener al menos 6 caracteres.")
    if nueva != repetir:
        return error("Las contraseñas no coinciden.")
    problema = usuarios_dao.cambiar_password_con_codigo(email, codigo, nueva)
    if problema:
        return error(problema)
    request.session.pop("recuperar_email", None)
    avisar(request, "✓ Contraseña cambiada. Ya puedes entrar")
    return ir("/login")


# ---------- Inicio ----------

@app.get("/")
def inicio(request: Request):
    usuario = usuario_actual(request)
    uid, hoy = usuario["id"], date.today()
    desde, hasta = calculos.rango_mes(hoy.year, hoy.month)
    totales = transacciones_dao.totales(uid, desde, hasta)
    anterior = transacciones_dao.totales(uid, *calculos.rango_mes(*calculos.mover_mes(hoy.year, hoy.month, -1)))
    ingresos, gastos = totales["ingresos"], totales["gastos"]

    def comparar(actual, previo, subir_es_bueno):
        if not previo:
            return {"texto": "Sin datos del mes pasado", "clase": ""}
        cambio = calculos.porcentaje(actual - previo, previo)
        bueno = (cambio >= 0) == subir_es_bueno
        return {"texto": f"{'▲' if cambio >= 0 else '▼'} {abs(cambio):.0f}% vs. mes pasado",
                "clase": "buena" if bueno else "mala"}

    alertas = []
    for p in presupuestos_dao.alertas(uid, hoy.year, hoy.month):
        gastado, limite = float(p["gastado"]), float(p["monto_limite"])
        alertas.append({**p, "excedido": gastado > limite, "diferencia": abs(limite - gastado),
                        "porcentaje": calculos.porcentaje(gastado, limite)})

    return mostrar(
        request, "inicio.html", usuario=usuario, seccion="inicio",
        nombre=usuario["nombre"].split()[0], mes=calculos.nombre_mes(hoy.year, hoy.month).lower(),
        fecha=calculos.fecha_larga(hoy), ingresos=ingresos, gastos=gastos, balance=ingresos - gastos,
        ahorro=calculos.tasa_ahorro(ingresos, gastos),
        cmp_ingresos=comparar(ingresos, anterior["ingresos"], True),
        cmp_gastos=comparar(gastos, anterior["gastos"], False),
        alertas=alertas, rapidas=categorias_dao.mas_usadas(uid, 4),
        dona=dona(transacciones_dao.gastos_por_categoria(uid, desde, hasta)),
        meses=barras_meses(uid, calculos.ultimos_meses(6, hoy)),
        ultimos=[movimiento_para_vista(t) for t in transacciones_dao.ultimas(uid, 5)])


@app.post("/rapido")
def gasto_rapido(request: Request, monto: str = Form(""), categoria_id: str = Form("")):
    """Igual que en escritorio: se guarda en la primera cuenta activa con fecha de hoy."""
    usuario = usuario_actual(request)
    valor = convertir_monto(monto)
    categoria_id = entero(categoria_id)
    categoria = next((c for c in categorias_dao.listar(usuario["id"]) if c["id"] == categoria_id), None)
    cuentas = cuentas_dao.listar(usuario["id"], solo_activas=True)
    if valor is None:
        avisar(request, "Escribe primero el monto", "error")
    elif not cuentas:
        avisar(request, "Primero crea una cuenta (en la app de escritorio)", "error")
    elif categoria:
        transacciones_dao.crear(cuentas[0]["id"], categoria["id"], categoria["nombre"], valor, date.today(), "gasto")
        avisar(request, f"✓ {calculos.formato_moneda(valor)} en {categoria['nombre']}")
    return ir("/")


# ---------- Historial ----------

PERIODOS = ["Este mes", "Mes pasado", "Últimos 3 meses", "Este año", "Todo"]


def rango_periodo(periodo):
    hoy = date.today()
    if periodo == "Mes pasado":
        return calculos.rango_mes(*calculos.mover_mes(hoy.year, hoy.month, -1))
    if periodo == "Últimos 3 meses":
        return (calculos.rango_mes(*calculos.mover_mes(hoy.year, hoy.month, -2))[0],
                calculos.rango_mes(hoy.year, hoy.month)[1])
    if periodo == "Este año":
        return date(hoy.year, 1, 1), date(hoy.year, 12, 31)
    if periodo == "Todo":
        return None, None
    return calculos.rango_mes(hoy.year, hoy.month)


@app.get("/historial")
def historial(request: Request, periodo: str = "Este mes", tipo: str = "", categoria: str = "", q: str = ""):
    usuario = usuario_actual(request)
    categoria = entero(categoria)
    periodo = periodo if periodo in PERIODOS else "Este mes"
    desde, hasta = rango_periodo(periodo)
    movimientos = [movimiento_para_vista(t) for t in transacciones_dao.buscar(
        usuario["id"], desde=desde, hasta=hasta, categoria_id=categoria or None,
        tipo=tipo if tipo in ("gasto", "ingreso") else None, texto=q.strip())]

    # Agrupados por día, como en las apps de banco
    dias = []
    for m in movimientos:
        if not dias or dias[-1]["fecha"] != m["fecha"]:
            dias.append({"fecha": m["fecha"], "titulo": calculos.fecha_larga(m["fecha"]), "movimientos": []})
        dias[-1]["movimientos"].append(m)

    return mostrar(request, "historial.html", usuario=usuario, seccion="historial", dias=dias,
                   periodos=PERIODOS, filtro={"periodo": periodo, "tipo": tipo, "categoria": categoria, "q": q},
                   categorias=categorias_dao.listar(usuario["id"]), cantidad=len(movimientos),
                   ingresos=sum(m["monto"] for m in movimientos if m["tipo"] == "ingreso"),
                   gastos=sum(m["monto"] for m in movimientos if m["tipo"] == "gasto"))


# ---------- Nuevo / editar movimiento ----------

def formulario(request, usuario, mov, error=None):
    return mostrar(request, "movimiento.html", usuario=usuario, seccion="nuevo", mov=mov, error=error,
                   cuentas=cuentas_dao.listar(usuario["id"], solo_activas=True),
                   categorias=categorias_dao.listar(usuario["id"]))


@app.get("/movimiento/nuevo")
def movimiento_nuevo(request: Request, tipo: str = "gasto"):
    usuario = usuario_actual(request)
    return formulario(request, usuario, {"id": None, "tipo": "ingreso" if tipo == "ingreso" else "gasto",
                                         "monto": "", "fecha": date.today(), "descripcion": "",
                                         "categoria_id": None, "cuenta_id": None})


@app.get("/movimiento/{transaccion_id}")
def movimiento_editar(request: Request, transaccion_id: int):
    usuario = usuario_actual(request)
    t = transacciones_dao.obtener(transaccion_id, usuario["id"])
    if t is None:
        avisar(request, "Ese movimiento ya no existe", "error")
        return ir("/historial")
    return formulario(request, usuario, {**t, "monto": calculos.monto_para_editar(t["monto"])})


@app.post("/movimiento")
def movimiento_guardar(request: Request, id: str = Form(""), tipo: str = Form("gasto"), monto: str = Form(""),
                       categoria_id: str = Form(""), cuenta_id: str = Form(""), fecha: str = Form(""),
                       descripcion: str = Form("")):
    usuario = usuario_actual(request)
    id, categoria_id, cuenta_id = entero(id), entero(categoria_id), entero(cuenta_id)
    uid = usuario["id"]
    tipo = "ingreso" if tipo == "ingreso" else "gasto"
    mov = {"id": id or None, "tipo": tipo, "monto": monto, "categoria_id": categoria_id or None,
           "cuenta_id": cuenta_id, "fecha": fecha, "descripcion": descripcion}

    # La cuenta y la categoría tienen que ser del usuario (no confiamos en lo que manda el navegador)
    cuenta = next((c for c in cuentas_dao.listar(uid, solo_activas=True) if c["id"] == cuenta_id), None)
    categoria = next((c for c in categorias_dao.listar(uid)
                      if c["id"] == categoria_id and bool(c["es_ingreso"]) == (tipo == "ingreso")), None)
    valor = convertir_monto(monto)
    try:
        dia = date.fromisoformat(fecha)
    except ValueError:
        dia = None
    if valor is None:
        return formulario(request, usuario, mov, "Escribe un monto válido mayor a cero.")
    if cuenta is None:
        return formulario(request, usuario, mov, "Elige una cuenta (si no tienes, créala en la app de escritorio).")
    if dia is None:
        return formulario(request, usuario, mov, "Elige una fecha válida.")

    texto = descripcion.strip()[:200] or (categoria["nombre"] if categoria else tipo.capitalize())
    categoria_id = categoria["id"] if categoria else None
    if id:
        if transacciones_dao.obtener(id, uid) is None:
            avisar(request, "Ese movimiento ya no existe", "error")
            return ir("/historial")
        transacciones_dao.actualizar(id, uid, cuenta["id"], categoria_id, texto, valor, dia, tipo)
        avisar(request, "✓ Cambios guardados")
        return ir("/historial")
    transacciones_dao.crear(cuenta["id"], categoria_id, texto, valor, dia, tipo)
    avisar(request, "✓ Movimiento guardado")
    return ir("/")


@app.post("/movimiento/{transaccion_id}/eliminar")
def movimiento_eliminar(request: Request, transaccion_id: int):
    usuario = usuario_actual(request)
    transacciones_dao.eliminar(transaccion_id, usuario["id"])  # solo borra si es suyo
    avisar(request, "Movimiento eliminado", "info")
    return ir("/historial")


# ---------- Reportes ----------

@app.get("/reportes")
def reportes(request: Request, mes: str = ""):
    usuario = usuario_actual(request)
    uid, hoy = usuario["id"], date.today()
    opciones = calculos.ultimos_meses(12, hoy)[::-1]
    elegido = next((m for m in opciones if f"{m[0]}-{m[1]:02d}" == mes), opciones[0])
    desde, hasta = calculos.rango_mes(*elegido)

    por_categoria = transacciones_dao.gastos_por_categoria(uid, desde, hasta)
    gastado = sum(c["total"] for c in por_categoria)
    doce = barras_meses(uid, calculos.ultimos_meses(12, date(elegido[0], elegido[1], 1)))
    ingresos = doce[-1]["ingresos"]

    proyeccion = None
    if elegido == (hoy.year, hoy.month):
        proyeccion = calculos.proyeccion_fin_mes(gastado, hoy)
        proyeccion["sobrante"] = ingresos - proyeccion["proyeccion"] if ingresos else None

    maximo_top = max([c["total"] for c in por_categoria[:5]] + [1])
    return mostrar(request, "reportes.html", usuario=usuario, seccion="reportes",
                   meses=[{"valor": f"{a}-{m:02d}", "nombre": calculos.nombre_mes(a, m), "elegido": (a, m) == elegido}
                          for a, m in opciones],
                   gastado=gastado, ingresos=ingresos, dona=dona(por_categoria),
                   top=[{**c, "ancho": c["total"] / maximo_top * 100} for c in por_categoria[:5]],
                   lineas=lineas_svg(doce), etiquetas=[f["etiqueta"] for f in doce],
                   comparativa=barras_meses(uid, calculos.ultimos_meses(6, date(elegido[0], elegido[1], 1))),
                   proyeccion=proyeccion)
