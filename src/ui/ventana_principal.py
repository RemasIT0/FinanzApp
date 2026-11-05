"""Ventana principal: barra lateral de navegación + Dashboard."""
from datetime import date, datetime

import customtkinter as ctk

from database import categorias_dao, correo_dao, cuentas_dao, presupuestos_dao, transacciones_dao, usuarios_dao
from ui.componentes import animaciones, graficas
from ui.componentes.aviso import mostrar_aviso
from ui.componentes.boton_personalizado import Boton, BotonMenu, hover_suave
from ui.componentes.tarjeta_resumen import Tarjeta, TarjetaResumen, tono_suave
from ui.tutorial import Tutorial
from ui.ventana_asistente import PanelAsistente
from ui.ventana_config import PanelConfig
from ui.ventana_correo import PanelCorreo
from ui.ventana_importar import PanelImportar
from ui.ventana_registro import VentanaRegistro
from ui.ventana_reportes import PanelReportes
from ui.ventana_transacciones import PanelTransacciones
from utils import calculos
from utils.config import actualizar_config
from utils.temas import (COLORES, GRAFICAS, NORMAL, NORMAL_NEGRITA, PEQUENO, SUBTITULO, TITULO,
                         estilo_tablas, modo_oscuro)
from utils.validadores import convertir_monto


class VentanaPrincipal(ctk.CTkFrame):
    def __init__(self, master, usuario, al_salir):
        super().__init__(master, corner_radius=0, fg_color=COLORES["fondo"])
        self.usuario = usuario
        self.al_salir = al_salir
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # (icono, texto, clase del panel)
        self.secciones = {
            "inicio": ("⌂", "Inicio", PanelDashboard),
            "historial": ("☰", "Historial", PanelTransacciones),
            "reportes": ("◔", "Reportes", PanelReportes),
            "importar": ("⇩", "Importar", PanelImportar),
            "correo": ("✉", "Correo", PanelCorreo),
            "config": ("⚙", "Configuración", PanelConfig),
        }
        # Título de grupo que va antes de cada una de estas secciones en la barra lateral
        self.grupos = {"inicio": "GENERAL", "importar": "AGREGAR DATOS", "config": "AJUSTES"}
        self.paneles = {}
        self.actual = None
        self._id_correo = None
        self._barra_lateral()
        # Espacio donde se colocan los paneles (con place, para poder animarlos)
        self.contenido = ctk.CTkFrame(self, fg_color="transparent")
        self.contenido.grid(row=0, column=1, sticky="nsew", padx=28, pady=24)
        self.mostrar("inicio")
        self.programar_correo()

        self.asistente = None   # el panel del chat se crea la primera vez que se abre
        self.tutorial = None
        if not usuarios_dao.vio_tutorial(usuario["id"]):
            self.after(700, self.iniciar_tutorial)  # primera vez: guía de bienvenida

    def _barra_lateral(self):
        barra = self.barra = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=COLORES["fondo2"])
        barra.grid(row=0, column=0, sticky="nsw")
        barra.grid_propagate(False)
        barra.pack_propagate(False)

        logo = ctk.CTkFrame(barra, fg_color="transparent")
        logo.pack(fill="x", padx=24, pady=(28, 22))
        ctk.CTkLabel(logo, text="◈", font=("Segoe UI", 26), text_color=COLORES["destacado"]).pack(side="left")
        ctk.CTkLabel(logo, text=" FinanzApp", font=SUBTITULO).pack(side="left")

        self.boton_nuevo = Boton(barra, "Nuevo movimiento", icono="＋", height=44, command=self.nuevo_movimiento)
        self.boton_nuevo.pack(fill="x", padx=16, pady=(0, 8))

        self.botones_menu = {}
        for clave, (icono, texto, _) in self.secciones.items():
            if clave in self.grupos:
                ctk.CTkLabel(barra, text=self.grupos[clave], font=(PEQUENO[0], 10, "bold"),
                             text_color=COLORES["texto2"], anchor="w").pack(fill="x", padx=28, pady=(14, 2))
            boton = BotonMenu(barra, texto, icono, comando=lambda c=clave: self.mostrar(c))
            boton.pack(fill="x", padx=16, pady=1)
            self.botones_menu[clave] = boton
        # Barrita roja que se desliza hasta la sección abierta
        self.indicador = ctk.CTkFrame(barra, width=4, height=22, corner_radius=2, fg_color=COLORES["destacado"])

        inferior = ctk.CTkFrame(barra, fg_color="transparent")
        inferior.pack(side="bottom", fill="x", padx=16, pady=18)
        self._tarjeta_usuario(inferior)
        self.interruptor = ctk.CTkSwitch(inferior, text="Modo oscuro", font=PEQUENO, command=self.cambiar_tema,
                                         progress_color=COLORES["destacado"], text_color=COLORES["texto2"])
        if modo_oscuro():
            self.interruptor.select()
        self.interruptor.pack(anchor="w", padx=10, pady=(12, 8))
        # Asistente y Salir en la misma fila, para que la barra quepa en pantallas bajas (notebooks)
        fila = ctk.CTkFrame(inferior, fg_color="transparent")
        fila.pack(fill="x")
        self.boton_asistente = Boton(fila, "Asistente", icono="💬", estilo="secundario", height=38,
                                     command=self.alternar_asistente)
        self.boton_asistente.pack(side="left", fill="x", expand=True)
        Boton(fila, "Salir", estilo="fantasma", width=72, height=38,
              command=self.al_salir).pack(side="left", padx=(6, 0))

    def _tarjeta_usuario(self, master):
        """Círculo con las iniciales del usuario, su nombre y su correo."""
        tarjeta = ctk.CTkFrame(master, fg_color=COLORES["entrada"], corner_radius=12)
        tarjeta.pack(fill="x")
        iniciales = "".join(p[0] for p in self.usuario["nombre"].split()[:2]).upper()
        ctk.CTkLabel(tarjeta, text=iniciales, width=38, height=38, corner_radius=19, font=NORMAL_NEGRITA,
                     fg_color=COLORES["destacado"], text_color="#ffffff").pack(side="left", padx=10, pady=10)
        textos = ctk.CTkFrame(tarjeta, fg_color="transparent")
        textos.pack(side="left", fill="x", expand=True)
        correo = self.usuario["email"]
        ctk.CTkLabel(textos, text=self.usuario["nombre"][:20], font=(PEQUENO[0], 13, "bold"), anchor="w",
                     height=18).pack(fill="x")
        ctk.CTkLabel(textos, text=correo if len(correo) <= 22 else correo[:21] + "…", font=(PEQUENO[0], 11),
                     text_color=COLORES["texto2"], anchor="w", height=16).pack(fill="x")

    def _mover_indicador(self, clave):
        """Desliza la barrita roja hasta el botón de la sección (con animación si ya estaba visible)."""
        boton = self.botones_menu[clave]
        if boton.winfo_height() <= 1:  # la ventana aún no se acomoda en pantalla: se intenta en un momento
            return self.after(60, self._mover_indicador, clave)
        escala = self._get_widget_scaling()  # winfo_* da píxeles reales; place() espera medidas sin escalar
        x = boton.winfo_x() / escala + 4
        destino = (boton.winfo_y() + boton.winfo_height() / 2) / escala - 11
        inicio = getattr(self, "_y_indicador", None)
        self._y_indicador = destino
        self.indicador.lift()
        if inicio is None:
            return self.indicador.place(x=x, y=destino)
        animaciones.animar(self.indicador, 260, lambda a: self.indicador.place(x=x, y=inicio + (destino - inicio) * a))

    def mostrar(self, clave):
        """Cambia de sección. Los paneles se crean una vez y se refrescan al mostrarlos."""
        if clave == self.actual:
            return
        if self.actual:
            animaciones.ocultar(self.paneles[self.actual])
        for c, boton in self.botones_menu.items():
            boton.activar(c == clave)
        self.actual = clave
        panel = self._panel(clave)
        panel.refrescar()  # Primero los datos, para que la animación no se trabe
        animaciones.deslizar_entrada(panel, self.contenido, desde_x=60)
        self._mover_indicador(clave)  # deslizar_entrada ya calculó las posiciones de todo

    def _panel(self, clave):
        """Devuelve el panel de la sección, creándolo la primera vez (sin mostrarlo)."""
        if clave not in self.paneles:
            self.paneles[clave] = self.secciones[clave][2](self, self.usuario)
        return self.paneles[clave]

    def refrescar(self):
        self.paneles[self.actual].refrescar()

    def programar_correo(self):
        """Agenda la próxima revisión automática del correo (solo mientras la app está abierta)."""
        if self._id_correo:
            self.after_cancel(self._id_correo)
            self._id_correo = None
        cuenta = correo_dao.obtener(self.usuario["id"])
        if not cuenta or not cuenta["intervalo_horas"]:
            return
        espera = cuenta["intervalo_horas"] * 3600
        if cuenta["ultima_sincronizacion"]:
            espera -= (datetime.now() - cuenta["ultima_sincronizacion"]).total_seconds()
        # Si ya tocaba, se revisa a los 5 segundos para no hacer más lento el inicio
        self._id_correo = self.after(int(max(espera, 5) * 1000), self._revisar_correo)

    def _revisar_correo(self):
        self._id_correo = None
        self._panel("correo").sincronizar(automatico=True)  # al terminar vuelve a llamar a programar_correo

    def destroy(self):
        if self._id_correo:
            self.after_cancel(self._id_correo)
        if getattr(self, "tutorial", None) is not None:
            self.tutorial.cancelar()  # cerró sesión a mitad del tutorial: se verá la próxima vez
        super().destroy()

    # ---------- Asistente y tutorial ----------

    def alternar_asistente(self):
        if self.asistente is None:
            self.asistente = PanelAsistente(self, self.usuario, al_accion=self._accion_asistente)
        self.asistente.alternar()

    def _accion_asistente(self, accion):
        """Lo que pasa al tocar un botón dentro de una respuesta del asistente."""
        if accion[0] == "ir":
            self.mostrar(accion[1])
        elif accion[0] == "nuevo":
            self.nuevo_movimiento()
        elif accion[0] == "tutorial":
            self.iniciar_tutorial()

    def iniciar_tutorial(self):
        if self.tutorial is not None or not self.winfo_exists():
            return  # ya hay uno abierto
        if self.asistente is not None:
            self.asistente.cerrar()
        self.tutorial = Tutorial(self, al_terminar=self._fin_tutorial)

    def _fin_tutorial(self):
        self.tutorial = None
        self.mostrar("inicio")
        mostrar_aviso(self, "¿Dudas? Toca «💬 Asistente» cuando quieras", tipo="info", duracion=3500)

    def nuevo_movimiento(self):
        VentanaRegistro(self, self.usuario, al_guardar=self._movimiento_guardado)

    def _movimiento_guardado(self):
        self.refrescar()
        mostrar_aviso(self, "✓ Movimiento guardado")

    def cambiar_tema(self):
        oscuro = self.interruptor.get() == 1
        ctk.set_appearance_mode("dark" if oscuro else "light")
        actualizar_config(tema="dark" if oscuro else "light")
        estilo_tablas()
        # Las gráficas y tablas no son de CustomTkinter: hay que volver a dibujarlas
        for panel in self.paneles.values():
            if hasattr(panel, "aplicar_tema"):
                panel.aplicar_tema()
        self.refrescar()


class PanelDashboard(ctk.CTkScrollableFrame):
    def __init__(self, master, usuario):
        super().__init__(master, fg_color="transparent", scrollbar_button_color=COLORES["acento"])
        self.usuario = usuario
        self.principal = master
        self.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="tarjetas")

        # Encabezado
        self.titulo = ctk.CTkLabel(self, text="", font=TITULO, anchor="w")
        self.titulo.grid(row=0, column=0, columnspan=3, sticky="w")
        self.subtitulo = ctk.CTkLabel(self, text="", font=NORMAL, text_color=COLORES["texto2"], anchor="w")
        self.subtitulo.grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 16))
        self.fecha = ctk.CTkLabel(self, text="", font=PEQUENO, height=32, corner_radius=16,
                                  fg_color=COLORES["fondo2"], text_color=COLORES["texto2"])
        self.fecha.grid(row=0, column=3, sticky="e")

        # Alertas de presupuesto (se muestran solo si hay)
        self.marco_alertas = ctk.CTkFrame(self, fg_color="transparent")

        # Tarjetas de resumen
        self.tarjetas = {
            "ingresos": TarjetaResumen(self, "Ingresos del mes", "↗", GRAFICAS["ingreso"]),
            "gastos": TarjetaResumen(self, "Gastos del mes", "↘", GRAFICAS["gasto"]),
            "balance": TarjetaResumen(self, "Balance", "⚖", GRAFICAS["neutro"]),
            "ahorro": TarjetaResumen(self, "Ahorro del mes", "★", "#d4b106"),
        }
        for i, tarjeta in enumerate(self.tarjetas.values()):
            tarjeta.grid(row=3, column=i, sticky="nsew", padx=(0 if i == 0 else 8, 0 if i == 3 else 8))

        self._gasto_rapido()

        # Gráficas
        self.tarjeta_dona = self._tarjeta_grafica(5, 0, "Gastos por categoría")
        self.dona = graficas.Grafica(self.tarjeta_dona)
        self.dona.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tarjeta_barras = self._tarjeta_grafica(5, 2, "Últimos 6 meses")
        self.barras = graficas.Grafica(self.tarjeta_barras)
        self.barras.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        # Últimos movimientos
        ultimos = Tarjeta(self, brillo=True)
        ultimos.grid(row=6, column=0, columnspan=4, sticky="nsew", pady=(16, 8))
        cabecera = ctk.CTkFrame(ultimos, fg_color="transparent")
        cabecera.pack(fill="x", padx=20, pady=(16, 4))
        ctk.CTkLabel(cabecera, text="Últimos movimientos", font=SUBTITULO).pack(side="left")
        Boton(cabecera, "Ver todo  →", estilo="fantasma", width=100, height=32,
              command=lambda: master.mostrar("historial")).pack(side="right")
        self.lista_ultimos = ctk.CTkFrame(ultimos, fg_color="transparent")
        self.lista_ultimos.pack(fill="x", padx=20, pady=(0, 16))

    def _tarjeta_grafica(self, fila, columna, titulo):
        tarjeta = Tarjeta(self, brillo=True, height=340)
        tarjeta.grid(row=fila, column=columna, columnspan=2, sticky="nsew", pady=(16, 0),
                     padx=(0, 8) if columna == 0 else (8, 0))
        ctk.CTkLabel(tarjeta, text=titulo, font=SUBTITULO, anchor="w").pack(fill="x", padx=20, pady=(16, 0))
        return tarjeta

    def _gasto_rapido(self):
        """Escribe un monto y toca una categoría: listo, gasto registrado."""
        barra = Tarjeta(self)
        barra.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(16, 0))
        ctk.CTkLabel(barra, text="⚡ Gasto rápido", font=NORMAL_NEGRITA).pack(side="left", padx=(20, 12), pady=14)
        self.monto_rapido = ctk.CTkEntry(barra, width=130, height=38, corner_radius=10, font=NORMAL,
                                         placeholder_text="$ Monto", fg_color=COLORES["entrada"],
                                         border_color=COLORES["borde"])
        self.monto_rapido.pack(side="left", padx=(0, 12))
        self.botones_rapidos = ctk.CTkFrame(barra, fg_color="transparent")
        self.botones_rapidos.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(barra, text="Se guarda con fecha de hoy", font=PEQUENO,
                     text_color=COLORES["texto2"]).pack(side="right", padx=20)

    def _guardar_rapido(self, categoria):
        monto = convertir_monto(self.monto_rapido.get())
        if monto is None:
            self.monto_rapido.focus()
            return mostrar_aviso(self, "Escribe primero el monto", tipo="error")
        cuentas = cuentas_dao.listar(self.usuario["id"], solo_activas=True)
        if not cuentas:
            return mostrar_aviso(self, "Primero crea una cuenta en Configuración", tipo="error")
        transacciones_dao.crear(cuentas[0]["id"], categoria["id"], categoria["nombre"], monto, date.today(), "gasto")
        self.monto_rapido.delete(0, "end")
        self.refrescar()
        mostrar_aviso(self, f"✓ {calculos.formato_moneda(monto)} en {categoria['nombre']}")

    def aplicar_tema(self):
        pass  # las gráficas se redibujan en refrescar()

    def refrescar(self):
        uid = self.usuario["id"]
        hoy = date.today()
        inicio, fin = calculos.rango_mes(hoy.year, hoy.month)

        self.titulo.configure(text=f"Hola, {self.usuario['nombre'].split()[0]} 👋")
        self.subtitulo.configure(text=f"Así van tus finanzas en {calculos.nombre_mes(hoy.year, hoy.month).lower()}")
        self.fecha.configure(text=f"   {calculos.fecha_larga(hoy)}   ")

        # Tarjetas (los números suben como contador)
        totales = transacciones_dao.totales(uid, inicio, fin)
        anterior = transacciones_dao.totales(uid, *calculos.rango_mes(*calculos.mover_mes(hoy.year, hoy.month, -1)))
        ingresos, gastos = totales["ingresos"], totales["gastos"]
        balance = ingresos - gastos

        def comparar(actual, previo, subir_es_bueno):
            """Devuelve (texto, tendencia): si subir es bueno (ingresos), una subida se pinta de verde."""
            if not previo:
                return "Sin datos del mes pasado", None
            cambio = calculos.porcentaje(actual - previo, previo)
            bueno = (cambio >= 0) == subir_es_bueno
            return f"{'▲' if cambio >= 0 else '▼'} {abs(cambio):.0f}% vs. mes pasado", "buena" if bueno else "mala"

        dinero = calculos.formato_moneda
        texto, tendencia = comparar(ingresos, anterior["ingresos"], True)
        self.tarjetas["ingresos"].actualizar(ingresos, dinero, texto, tendencia=tendencia)
        texto, tendencia = comparar(gastos, anterior["gastos"], False)
        self.tarjetas["gastos"].actualizar(gastos, dinero, texto, tendencia=tendencia)
        self.tarjetas["balance"].actualizar(balance, dinero,
                                            "Te queda dinero" if balance >= 0 else "Gastaste más de lo que entró",
                                            GRAFICAS["ingreso"] if balance >= 0 else GRAFICAS["gasto"])
        self.tarjetas["ahorro"].actualizar(calculos.tasa_ahorro(ingresos, gastos), lambda v: f"{v:.0f}%",
                                           f"de tus ingresos ({dinero(max(balance, 0))})")

        self._alertas(uid, hoy)

        # Botones de gasto rápido con las categorías más usadas
        for hijo in self.botones_rapidos.winfo_children():
            hijo.destroy()
        for categoria in categorias_dao.mas_usadas(uid, 4):
            boton = ctk.CTkButton(self.botones_rapidos, text=f"{categoria['icono']}  {categoria['nombre']}",
                                  height=36, corner_radius=18, font=PEQUENO, fg_color=COLORES["acento"],
                                  text_color=COLORES["texto"], width=100,
                                  command=lambda c=categoria: self._guardar_rapido(c))
            hover_suave(boton, COLORES["acento"], tono_suave(categoria["color"]))
            boton.pack(side="left", padx=4)

        # Gráfica de dona
        por_categoria = transacciones_dao.gastos_por_categoria(uid, inicio, fin)
        graficas.dona(self.dona, [c["nombre"] for c in por_categoria], [c["total"] for c in por_categoria],
                      [c["color"] for c in por_categoria], calculos.formato_moneda(gastos))

        # Barras de los últimos 6 meses
        meses = calculos.ultimos_meses(6, hoy)
        por_mes = transacciones_dao.totales_por_mes(uid, calculos.rango_mes(*meses[0])[0], fin)
        vacio = {"ingresos": 0, "gastos": 0}
        graficas.barras_comparativas(self.barras, [calculos.etiqueta_corta(*m) for m in meses],
                                     [por_mes.get(m, vacio)["ingresos"] for m in meses],
                                     [por_mes.get(m, vacio)["gastos"] for m in meses])

        self._ultimos(uid)

    def _alertas(self, uid, hoy):
        for hijo in self.marco_alertas.winfo_children():
            hijo.destroy()
        alertas = presupuestos_dao.alertas(uid, hoy.year, hoy.month)
        if not alertas:
            self.marco_alertas.grid_forget()
            return
        self.marco_alertas.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(0, 16))
        for p in alertas:
            gastado, limite = float(p["gastado"]), float(p["monto_limite"])
            excedido = gastado > limite
            texto = (f"{p['icono']}  {p['nombre']}: te pasaste del presupuesto por "
                     f"{calculos.formato_moneda(gastado - limite)}" if excedido else
                     f"{p['icono']}  {p['nombre']}: ya usaste el {calculos.porcentaje(gastado, limite):.0f}% "
                     f"de tu presupuesto ({calculos.formato_moneda(limite - gastado)} disponibles)")
            alerta = ctk.CTkLabel(self.marco_alertas, text=f"⚠  {texto}", font=NORMAL, anchor="w",
                                  corner_radius=12, height=42, text_color="#ffffff", fg_color=COLORES["fondo"])
            alerta.pack(fill="x", pady=3)
            # Aparece "encendiéndose" desde el color del fondo
            animaciones.transicion_color(alerta, "fg_color", COLORES["destacado"] if excedido else "#c58b00",
                                         COLORES["fondo"], 450)

    def _ultimos(self, uid):
        for hijo in self.lista_ultimos.winfo_children():
            hijo.destroy()
        ultimos = transacciones_dao.ultimas(uid, 5)
        if not ultimos:
            ctk.CTkLabel(self.lista_ultimos, text="Todavía no tienes movimientos. Registra uno con "
                                                  "“＋ Nuevo movimiento” o importa tu estado de cuenta.",
                         font=NORMAL, text_color=COLORES["texto2"]).pack(pady=20)
            return
        for t in ultimos:
            fila = ctk.CTkFrame(self.lista_ultimos, fg_color="transparent")
            fila.pack(fill="x", pady=4)
            ctk.CTkLabel(fila, text=t["icono"] or "❔", width=40, height=40, corner_radius=12,
                         font=("Segoe UI Emoji", 16), fg_color=tono_suave(t["color"] or "#7f8c8d")).pack(side="left")
            textos = ctk.CTkFrame(fila, fg_color="transparent")
            textos.pack(side="left", padx=12)
            ctk.CTkLabel(textos, text=t["descripcion"], font=NORMAL_NEGRITA, anchor="w", height=20).pack(anchor="w")
            ctk.CTkLabel(textos, text=f"{t['categoria'] or 'Sin categoría'} · {t['cuenta']} · "
                                      f"{t['fecha']:%d/%m/%Y}", font=PEQUENO, text_color=COLORES["texto2"],
                         anchor="w", height=18).pack(anchor="w")
            es_gasto = t["tipo"] == "gasto"
            ctk.CTkLabel(fila, text=calculos.formato_moneda(float(t["monto"]) * (-1 if es_gasto else 1), con_signo=True),
                         font=NORMAL_NEGRITA,
                         text_color=GRAFICAS["gasto"] if es_gasto else GRAFICAS["ingreso"]).pack(side="right")
