"""Configuración: cuentas, categorías, presupuestos, apariencia y respaldos."""
from datetime import date
from tkinter import filedialog, messagebox

import customtkinter as ctk

from database import categorias_dao, cuentas_dao, presupuestos_dao
from ui.componentes import animaciones
from ui.componentes.aviso import mostrar_aviso
from ui.componentes.boton_personalizado import Boton
from ui.componentes.tarjeta_resumen import Tarjeta, tono_suave
from utils import calculos, enviar_correo, exportar
from utils.config import CARPETA_EXPORTS
from utils.temas import (COLORES, GRAFICAS, ICONO, NORMAL, NORMAL_NEGRITA, PALETA, PEQUENO, SUBTITULO,
                         TITULO)
from utils.validadores import convertir_monto, email_valido, texto_requerido, ultimos4_validos


def _menu(master, valores, comando=None, ancho=220):
    return ctk.CTkOptionMenu(master, values=valores, command=comando, width=ancho, height=36, font=NORMAL,
                             fg_color=COLORES["entrada"], button_color=COLORES["acento"],
                             button_hover_color=COLORES["acento_hover"], text_color=COLORES["texto"],
                             dynamic_resizing=False)


def _limpiar(marco):
    for hijo in marco.winfo_children():
        hijo.destroy()


def _fila(master, icono, color, titulo, detalle, derecha="", al_editar=None, al_eliminar=None):
    """Fila de lista: icono de color, título, detalle y botones de editar/eliminar."""
    fila = ctk.CTkFrame(master, fg_color=COLORES["fondo2"], corner_radius=12, border_width=1,
                        border_color=COLORES["borde"])
    fila.pack(fill="x", pady=4)
    ctk.CTkLabel(fila, text=icono, font=ICONO, width=40, height=40, corner_radius=12,
                 fg_color=tono_suave(color), text_color=color).pack(side="left", padx=12, pady=10)
    textos = ctk.CTkFrame(fila, fg_color="transparent")
    textos.pack(side="left")
    ctk.CTkLabel(textos, text=titulo, font=NORMAL_NEGRITA, anchor="w", height=20).pack(anchor="w")
    if detalle:
        ctk.CTkLabel(textos, text=detalle, font=PEQUENO, text_color=COLORES["texto2"], anchor="w",
                     height=18).pack(anchor="w")
    if al_eliminar:
        Boton(fila, "🗑", estilo="fantasma", width=40, command=al_eliminar).pack(side="right", padx=(0, 10))
    if al_editar:
        Boton(fila, "✎", estilo="fantasma", width=40, command=al_editar).pack(side="right")
    if derecha:
        ctk.CTkLabel(fila, text=derecha, font=NORMAL_NEGRITA).pack(side="right", padx=16)
    return fila


class SelectorColor(ctk.CTkFrame):
    """Fila de círculos de colores para elegir uno."""

    def __init__(self, master, inicial):
        super().__init__(master, fg_color="transparent")
        self.valor = inicial
        self.botones = {}
        for i, c in enumerate(PALETA):
            boton = ctk.CTkButton(self, text="", width=28, height=28, corner_radius=14, fg_color=c,
                                  hover_color=c, border_width=3, command=lambda c=c: self.elegir(c))
            boton.grid(row=0, column=i, padx=3)
            self.botones[c] = boton
        self.elegir(inicial)

    def elegir(self, valor):
        self.valor = valor
        for c, boton in self.botones.items():
            boton.configure(border_color=COLORES["texto"] if c == valor else c)


def centrar_ventana(ventana, master, ancho, alto):
    """Pone la ventana centrada sobre la principal (si no, Windows la pone donde quiere
    y puede quedar cortada) y la hace aparecer con un fundido."""
    principal = master.winfo_toplevel()
    escala = ventana._get_window_scaling()
    x = principal.winfo_rootx() + (principal.winfo_width() - round(ancho * escala)) // 2
    y = principal.winfo_rooty() + (principal.winfo_height() - round(alto * escala)) // 2
    ventana.geometry(f"{ancho}x{alto}+{max(x, 0)}+{max(y, 0)}")
    ventana.resizable(False, False)
    ventana.transient(principal)
    animaciones.aparecer_ventana(ventana)


class Dialogo(ctk.CTkToplevel):
    """Ventana modal base para los formularios de cuenta y categoría."""

    def __init__(self, master, titulo, al_guardar, alto):
        super().__init__(master, fg_color=COLORES["fondo"])
        self.title(titulo)
        centrar_ventana(self, master, 500, alto)
        self.al_guardar = al_guardar
        ctk.CTkLabel(self, text=titulo, font=SUBTITULO, anchor="w").pack(fill="x", padx=28, pady=(24, 4))
        self.cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self.cuerpo.pack(fill="both", expand=True, padx=28)
        self.error = ctk.CTkLabel(self, text="", font=PEQUENO, text_color=COLORES["destacado"])
        self.error.pack()
        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(fill="x", padx=28, pady=(0, 24))
        Boton(botones, "Guardar", command=self._guardar).pack(side="right")
        Boton(botones, "Cancelar", estilo="fantasma", command=self.destroy).pack(side="right", padx=8)
        self.bind("<Escape>", lambda _: self.destroy())
        self.after(150, lambda: (self.lift(), self.focus_force(), self.grab_set()))

    def etiqueta(self, texto):
        ctk.CTkLabel(self.cuerpo, text=texto, font=PEQUENO, text_color=COLORES["texto2"],
                     anchor="w").pack(fill="x", pady=(12, 4))

    def entrada(self, texto, valor=""):
        self.etiqueta(texto)
        campo = ctk.CTkEntry(self.cuerpo, height=40, corner_radius=10, font=NORMAL,
                             fg_color=COLORES["fondo2"], border_color=COLORES["borde"])
        campo.insert(0, valor)
        campo.pack(fill="x")
        return campo

    def _guardar(self):
        if self.guardar():
            self.destroy()
            self.al_guardar()


class DialogoCuenta(Dialogo):
    def __init__(self, master, usuario, al_guardar, cuenta=None):
        super().__init__(master, "Editar cuenta" if cuenta else "Nueva cuenta", al_guardar, 640)
        self.usuario, self.cuenta = usuario, cuenta or {}
        self.nombre = self.entrada("Nombre (ej. BBVA Nómina)", self.cuenta.get("nombre", ""))
        self.etiqueta("Tipo")
        self.tipo = _menu(self.cuerpo, list(cuentas_dao.TIPOS.values()), ancho=444)
        self.tipo.set(cuentas_dao.TIPOS[self.cuenta.get("tipo", "banco")])
        self.tipo.pack(fill="x")
        self.banco = self.entrada("Banco", self.cuenta.get("banco", ""))
        self.digitos = self.entrada("Últimos 4 dígitos (opcional)", self.cuenta.get("ultimos_4_digitos") or "")
        self.saldo = self.entrada("Saldo inicial", calculos.monto_para_editar(self.cuenta.get("saldo_inicial", 0)))
        self.etiqueta("Color")
        self.color = SelectorColor(self.cuerpo, self.cuenta.get("color_icono", "#3498db"))
        self.color.pack(anchor="w")
        self.nombre.focus()

    def guardar(self):
        nombre = texto_requerido(self.nombre.get(), 100)
        saldo = convertir_monto(self.saldo.get().lstrip("-"), permitir_cero=True)
        digitos = self.digitos.get().strip()
        if not nombre:
            return self.error.configure(text="Escribe un nombre para la cuenta.")
        if saldo is None:
            return self.error.configure(text="El saldo inicial debe ser un número.")
        if not ultimos4_validos(digitos):
            return self.error.configure(text="Los últimos dígitos deben ser 4 números.")
        if self.saldo.get().strip().startswith("-"):
            saldo = -saldo  # p. ej. deuda inicial en una tarjeta de crédito
        tipo = next(k for k, v in cuentas_dao.TIPOS.items() if v == self.tipo.get())
        datos = (nombre, tipo, self.banco.get().strip()[:100], digitos, saldo, self.color.valor)
        if self.cuenta:
            cuentas_dao.actualizar(self.cuenta["id"], self.usuario["id"], *datos)
        else:
            cuentas_dao.crear(self.usuario["id"], *datos)
        return True


class DialogoCategoria(Dialogo):
    def __init__(self, master, usuario, al_guardar, categoria=None, es_ingreso=False):
        super().__init__(master, "Editar categoría" if categoria else "Nueva categoría", al_guardar, 560)
        self.usuario, self.categoria = usuario, categoria or {}
        self.nombre = self.entrada("Nombre", self.categoria.get("nombre", ""))
        self.etiqueta("Tipo")
        self.tipo = ctk.CTkSegmentedButton(self.cuerpo, values=["Gasto", "Ingreso"], height=34, font=NORMAL,
                                           selected_color=COLORES["destacado"],
                                           selected_hover_color=COLORES["destacado_hover"])
        self.tipo.set("Ingreso" if self.categoria.get("es_ingreso", es_ingreso) else "Gasto")
        self.tipo.pack(fill="x")

        self.etiqueta("Icono")
        self.icono = self.categoria.get("icono", categorias_dao.ICONOS_DISPONIBLES[0])
        rejilla = ctk.CTkFrame(self.cuerpo, fg_color="transparent")
        rejilla.pack(anchor="w")
        self.botones_icono = {}
        for i, icono in enumerate(categorias_dao.ICONOS_DISPONIBLES):
            boton = ctk.CTkButton(rejilla, text=icono, font=ICONO, width=44, height=40, corner_radius=10,
                                  fg_color=COLORES["fondo2"], hover_color=COLORES["acento"],
                                  text_color=COLORES["texto"], command=lambda ic=icono: self._elegir_icono(ic))
            boton.grid(row=i // 10, column=i % 10, padx=1, pady=1)
            self.botones_icono[icono] = boton
        self._elegir_icono(self.icono)

        self.etiqueta("Color")
        self.color = SelectorColor(self.cuerpo, self.categoria.get("color", PALETA[7]))
        self.color.pack(anchor="w")
        self.nombre.focus()

    def _elegir_icono(self, icono):
        self.icono = icono
        for ic, boton in self.botones_icono.items():
            boton.configure(fg_color=COLORES["destacado"] if ic == icono else COLORES["fondo2"])

    def guardar(self):
        nombre = texto_requerido(self.nombre.get(), 50)
        if not nombre:
            return self.error.configure(text="Escribe un nombre (máximo 50 letras).")
        datos = (nombre, self.icono, self.color.valor, self.tipo.get() == "Ingreso")
        if self.categoria:
            categorias_dao.actualizar(self.categoria["id"], self.usuario["id"], *datos)
        else:
            categorias_dao.crear(self.usuario["id"], *datos)
        return True


class DialogoRemitente(Dialogo):
    """Gmail de la app desde el que se mandan los códigos para recuperar la contraseña."""

    def __init__(self, master, al_guardar):
        super().__init__(master, "Correo de envío de la app", al_guardar, 520)
        self.error.configure(wraplength=440)
        ctk.CTkLabel(self.cuerpo, text="Desde esta cuenta Gmail se mandan los códigos para recuperar la "
                                       "contraseña. Puede ser una cuenta creada solo para FinanzApp.\n\n"
                                       "1. Activa la verificación en dos pasos en esa cuenta.\n"
                                       "2. Crea una contraseña de aplicación en myaccount.google.com/apppasswords.\n"
                                       "3. Pega aquí las 16 letras (no tu contraseña normal).",
                     font=PEQUENO, text_color=COLORES["texto2"], justify="left", anchor="w",
                     wraplength=440).pack(fill="x")
        self.correo = self.entrada("Correo Gmail", enviar_correo.remitente())
        self.password = self.entrada("Contraseña de aplicación")
        self.password.configure(show="•")
        self.correo.focus()

    def guardar(self):
        correo = self.correo.get().strip().lower()
        password = self.password.get().replace(" ", "")
        if not email_valido(correo):
            return self.error.configure(text="Escribe un correo válido.")
        if not password:
            return self.error.configure(text="Escribe la contraseña de aplicación.")
        self.error.configure(text="Probando conexión con Gmail…", text_color=COLORES["texto2"])
        self.update_idletasks()
        try:
            enviar_correo.configurar_remitente(correo, password)
        except Exception as e:
            return self.error.configure(text=enviar_correo.mensaje_error(e), text_color=COLORES["destacado"])
        return True


class PanelConfig(ctk.CTkFrame):
    def __init__(self, master, usuario):
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario
        self.principal = master
        ctk.CTkLabel(self, text="Configuración", font=TITULO, anchor="w").pack(fill="x")

        self.pestanas = ctk.CTkTabview(self, fg_color="transparent", corner_radius=12,
                                       segmented_button_selected_color=COLORES["destacado"],
                                       segmented_button_selected_hover_color=COLORES["destacado_hover"],
                                       segmented_button_fg_color=COLORES["fondo2"],
                                       segmented_button_unselected_color=COLORES["fondo2"],
                                       text_color=COLORES["texto"], anchor="w")
        self.pestanas.pack(fill="both", expand=True)
        for nombre in ("Cuentas", "Categorías", "Presupuestos", "Datos"):
            self.pestanas.add(nombre)
        self.pestanas._segmented_button.configure(font=NORMAL, height=36)

        self._pestana_cuentas(self.pestanas.tab("Cuentas"))
        self._pestana_categorias(self.pestanas.tab("Categorías"))
        self._pestana_presupuestos(self.pestanas.tab("Presupuestos"))
        self._pestana_datos(self.pestanas.tab("Datos"))

    def refrescar(self):
        self._cargar_cuentas()
        self._cargar_categorias()
        self._cargar_presupuestos()

    # ---------- Cuentas ----------

    def _pestana_cuentas(self, pestana):
        barra = ctk.CTkFrame(pestana, fg_color="transparent")
        barra.pack(fill="x", pady=(4, 8))
        ctk.CTkLabel(barra, text="Tus bancos, tarjetas y efectivo", font=NORMAL,
                     text_color=COLORES["texto2"]).pack(side="left")
        Boton(barra, "Agregar cuenta", icono="＋",
              command=lambda: DialogoCuenta(self, self.usuario, self._cambio)).pack(side="right")
        self.lista_cuentas = ctk.CTkScrollableFrame(pestana, fg_color="transparent")
        self.lista_cuentas.pack(fill="both", expand=True)

    def _cargar_cuentas(self):
        _limpiar(self.lista_cuentas)
        for c in cuentas_dao.listar(self.usuario["id"]):
            detalle = cuentas_dao.TIPOS[c["tipo"]]
            if c["banco"]:
                detalle += f" · {c['banco']}"
            if c["ultimos_4_digitos"]:
                detalle += f" · •••• {c['ultimos_4_digitos']}"
            saldo = float(c["saldo_actual"])
            _fila(self.lista_cuentas, "💳" if "tarjeta" in c["tipo"] else "🏦" if c["tipo"] == "banco" else "👛",
                  c["color_icono"], c["nombre"], detalle, calculos.formato_moneda(saldo),
                  al_editar=lambda c=c: DialogoCuenta(self, self.usuario, self._cambio, cuenta=c),
                  al_eliminar=lambda c=c: self._eliminar_cuenta(c))

    def _eliminar_cuenta(self, cuenta):
        if messagebox.askyesno("Eliminar cuenta", f"¿Eliminar “{cuenta['nombre']}”?\n\n"
                                                  "También se borrarán TODOS sus movimientos."):
            cuentas_dao.eliminar(cuenta["id"], self.usuario["id"])
            self._cambio()

    # ---------- Categorías ----------

    def _pestana_categorias(self, pestana):
        pestana.grid_columnconfigure((0, 1), weight=1, uniform="col")
        pestana.grid_rowconfigure(1, weight=1)
        self.listas_categorias = {}
        for columna, (titulo, es_ingreso) in enumerate((("Gastos", False), ("Ingresos", True))):
            barra = ctk.CTkFrame(pestana, fg_color="transparent")
            barra.grid(row=0, column=columna, sticky="ew", padx=8, pady=(4, 8))
            ctk.CTkLabel(barra, text=titulo, font=SUBTITULO).pack(side="left")
            Boton(barra, "Agregar", icono="＋", estilo="secundario", width=110,
                  command=lambda e=es_ingreso: DialogoCategoria(self, self.usuario, self._cambio,
                                                                es_ingreso=e)).pack(side="right")
            lista = ctk.CTkScrollableFrame(pestana, fg_color="transparent")
            lista.grid(row=1, column=columna, sticky="nsew", padx=8)
            self.listas_categorias[es_ingreso] = lista

    def _cargar_categorias(self):
        for es_ingreso, lista in self.listas_categorias.items():
            _limpiar(lista)
            for c in categorias_dao.listar(self.usuario["id"], es_ingreso):
                _fila(lista, c["icono"], c["color"], c["nombre"], "",
                      al_editar=lambda c=c: DialogoCategoria(self, self.usuario, self._cambio, categoria=c),
                      al_eliminar=lambda c=c: self._eliminar_categoria(c))

    def _eliminar_categoria(self, categoria):
        if messagebox.askyesno("Eliminar categoría", f"¿Eliminar “{categoria['nombre']}”?\n\n"
                                                     "Sus movimientos quedarán como “Sin categoría”."):
            categorias_dao.eliminar(categoria["id"], self.usuario["id"])
            self._cambio()

    # ---------- Presupuestos ----------

    def _pestana_presupuestos(self, pestana):
        hoy = date.today()
        self.meses_presupuesto = [calculos.mover_mes(hoy.year, hoy.month, i) for i in (-1, 0, 1)]
        nuevo = Tarjeta(pestana)
        nuevo.pack(fill="x", pady=(4, 8))
        ctk.CTkLabel(nuevo, text="Mes", font=PEQUENO, text_color=COLORES["texto2"]).grid(row=0, column=0, sticky="w", padx=(16, 6), pady=(12, 2))
        self.mes_presupuesto = _menu(nuevo, [calculos.nombre_mes(*m) for m in self.meses_presupuesto],
                                     lambda _: self._cargar_presupuestos(), ancho=180)
        self.mes_presupuesto.set(calculos.nombre_mes(hoy.year, hoy.month))
        self.mes_presupuesto.grid(row=1, column=0, padx=(16, 6), pady=(0, 14))
        ctk.CTkLabel(nuevo, text="Categoría", font=PEQUENO, text_color=COLORES["texto2"]).grid(row=0, column=1, sticky="w", padx=6, pady=(12, 2))
        self.categoria_presupuesto = _menu(nuevo, ["—"])
        self.categoria_presupuesto.grid(row=1, column=1, padx=6, pady=(0, 14))
        ctk.CTkLabel(nuevo, text="Límite mensual", font=PEQUENO, text_color=COLORES["texto2"]).grid(row=0, column=2, sticky="w", padx=6, pady=(12, 2))
        self.limite = ctk.CTkEntry(nuevo, width=140, height=36, corner_radius=10, font=NORMAL, placeholder_text="$ 0,00",
                                   fg_color=COLORES["entrada"], border_color=COLORES["borde"])
        self.limite.grid(row=1, column=2, padx=6, pady=(0, 14))
        self.limite.bind("<Return>", lambda _: self._guardar_presupuesto())
        Boton(nuevo, "Guardar", command=self._guardar_presupuesto).grid(row=1, column=3, padx=6, pady=(0, 14))
        Boton(nuevo, "Copiar del mes anterior", estilo="fantasma",
              command=self._copiar_presupuestos).grid(row=1, column=4, padx=(6, 16), pady=(0, 14))
        self.lista_presupuestos = ctk.CTkScrollableFrame(pestana, fg_color="transparent")
        self.lista_presupuestos.pack(fill="both", expand=True)

    def _mes_elegido(self):
        nombres = [calculos.nombre_mes(*m) for m in self.meses_presupuesto]
        return self.meses_presupuesto[nombres.index(self.mes_presupuesto.get())]

    def _cargar_presupuestos(self):
        self.categorias_gasto = {f"{c['icono']} {c['nombre']}": c["id"]
                                 for c in categorias_dao.listar(self.usuario["id"], es_ingreso=False)}
        nombres = list(self.categorias_gasto) or ["—"]
        self.categoria_presupuesto.configure(values=nombres)
        if self.categoria_presupuesto.get() not in nombres:
            self.categoria_presupuesto.set(nombres[0])

        _limpiar(self.lista_presupuestos)
        anio, mes = self._mes_elegido()
        presupuestos = presupuestos_dao.listar(self.usuario["id"], anio, mes)
        if not presupuestos:
            ctk.CTkLabel(self.lista_presupuestos, text="No hay presupuestos para este mes.\n"
                                                       "Agrega uno arriba: elige categoría y límite.",
                         font=NORMAL, text_color=COLORES["texto2"]).pack(pady=30)
        for p in presupuestos:
            gastado, limite = float(p["gastado"]), float(p["monto_limite"])
            avance = gastado / limite if limite else 0
            color_barra = GRAFICAS["ingreso"] if avance < 0.8 else "#f0a500" if avance <= 1 else GRAFICAS["gasto"]
            fila = _fila(self.lista_presupuestos, p["icono"], p["color"], p["nombre"],
                         f"{calculos.formato_moneda(gastado)} de {calculos.formato_moneda(limite)}",
                         f"{avance:.0%}", al_eliminar=lambda p=p: self._eliminar_presupuesto(p))
            barra = ctk.CTkProgressBar(fila, height=10, corner_radius=5, progress_color=color_barra,
                                       fg_color=COLORES["acento"])
            barra.set(0)
            barra.pack(side="right", fill="x", expand=True, padx=16)
            animaciones.llenar(barra, min(avance, 1))

    def _guardar_presupuesto(self):
        categoria_id = self.categorias_gasto.get(self.categoria_presupuesto.get())
        limite = convertir_monto(self.limite.get())
        if not categoria_id or limite is None:
            return mostrar_aviso(self, "Elige una categoría y escribe un límite válido", tipo="error")
        presupuestos_dao.guardar(self.usuario["id"], categoria_id, limite, *self._mes_elegido())
        self.limite.delete(0, "end")
        self._cargar_presupuestos()
        mostrar_aviso(self, "✓ Presupuesto guardado")

    def _copiar_presupuestos(self):
        anio, mes = self._mes_elegido()
        presupuestos_dao.copiar_de_mes(self.usuario["id"], *calculos.mover_mes(anio, mes, -1), anio, mes)
        self._cargar_presupuestos()

    def _eliminar_presupuesto(self, presupuesto):
        presupuestos_dao.eliminar(presupuesto["id"], self.usuario["id"])
        self._cargar_presupuestos()

    # ---------- Datos (respaldo) ----------

    def _pestana_datos(self, pestana):
        tarjeta = Tarjeta(pestana)
        tarjeta.pack(fill="x", pady=(4, 8))
        ctk.CTkLabel(tarjeta, text="Respaldo de datos", font=SUBTITULO, anchor="w").pack(fill="x", padx=20, pady=(16, 2))
        ctk.CTkLabel(tarjeta, text="Guarda todas tus cuentas, categorías, movimientos y presupuestos en un "
                                   "archivo .json. Puedes cargarlo después en esta u otra computadora.",
                     font=NORMAL, text_color=COLORES["texto2"], anchor="w", justify="left",
                     wraplength=700).pack(fill="x", padx=20)
        botones = ctk.CTkFrame(tarjeta, fg_color="transparent")
        botones.pack(fill="x", padx=20, pady=16)
        Boton(botones, "Exportar respaldo", icono="⇩", command=self._exportar_respaldo).pack(side="left")
        Boton(botones, "Importar respaldo", icono="⇧", estilo="secundario",
              command=self._importar_respaldo).pack(side="left", padx=8)

        envio = Tarjeta(pestana)
        envio.pack(fill="x", pady=8)
        ctk.CTkLabel(envio, text="Recuperar contraseña", font=SUBTITULO, anchor="w").pack(fill="x", padx=20, pady=(16, 2))
        self.texto_envio = ctk.CTkLabel(envio, text="", font=NORMAL, text_color=COLORES["texto2"], anchor="w",
                                        justify="left", wraplength=700)
        self.texto_envio.pack(fill="x", padx=20)
        Boton(envio, "Configurar correo de envío", icono="✉", estilo="secundario",
              command=lambda: DialogoRemitente(self, self._remitente_guardado)).pack(anchor="w", padx=20, pady=16)
        self._mostrar_remitente()

        tema = Tarjeta(pestana)
        tema.pack(fill="x", pady=8)
        ctk.CTkLabel(tema, text="Apariencia", font=SUBTITULO, anchor="w").pack(fill="x", padx=20, pady=(16, 2))
        ctk.CTkLabel(tema, text="Cambia entre modo claro y oscuro con el interruptor de la barra lateral.",
                     font=NORMAL, text_color=COLORES["texto2"], anchor="w").pack(fill="x", padx=20, pady=(0, 16))

    def _mostrar_remitente(self):
        correo = enviar_correo.remitente()
        self.texto_envio.configure(
            text=f"Los códigos para recuperar la contraseña se envían desde {correo}." if correo else
            "Todavía no hay un correo de envío: sin él, nadie podrá recuperar su contraseña "
            "con «¿Olvidaste tu contraseña?».")

    def _remitente_guardado(self):
        self._mostrar_remitente()
        mostrar_aviso(self, "✓ Correo de envío guardado")

    def _exportar_respaldo(self):
        CARPETA_EXPORTS.mkdir(exist_ok=True)
        ruta = filedialog.asksaveasfilename(initialdir=CARPETA_EXPORTS, defaultextension=".json",
                                            initialfile=f"respaldo_finanzapp_{date.today():%Y-%m-%d}.json",
                                            filetypes=[("Respaldo JSON", "*.json")])
        if ruta:
            exportar.exportar_respaldo(self.usuario["id"], ruta)
            mostrar_aviso(self, "✓ Respaldo guardado")

    def _importar_respaldo(self):
        ruta = filedialog.askopenfilename(filetypes=[("Respaldo JSON", "*.json")])
        if not ruta or not messagebox.askyesno(
                "Importar respaldo", "Los datos del respaldo se AGREGARÁN a los que ya tienes.\n¿Continuar?"):
            return
        try:
            cantidad = exportar.importar_respaldo(self.usuario["id"], ruta)
        except (KeyError, ValueError) as e:
            return messagebox.showerror("Respaldo inválido", f"El archivo no es un respaldo válido.\n{e}")
        self._cambio()
        mostrar_aviso(self, f"✓ Respaldo importado ({cantidad} movimientos)")

    def _cambio(self):
        self.refrescar()
