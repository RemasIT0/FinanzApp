"""Correo: conectar Gmail/Yahoo, elegir bancos y revisar los movimientos detectados en los avisos.

Leer el correo tarda unos segundos, así que se hace en un hilo aparte
para que la ventana no se congele mientras tanto.
"""
import imaplib
import re
import threading
from tkinter import messagebox, ttk

import customtkinter as ctk

from database import categorias_dao, correo_dao, cuentas_dao, plantillas_dao, transacciones_dao
from email_parser import lector_email
from ui.componentes.aviso import mostrar_aviso
from ui.componentes.boton_personalizado import Boton
from ui.componentes.tabla_transaccion import colores_encima, resaltar_al_pasar
from ui.componentes.tarjeta_resumen import Tarjeta
from ui.ventana_config import Dialogo
from utils import procesador_csv
from utils.calculos import formato_moneda
from utils.temas import COLORES, NORMAL, NORMAL_NEGRITA, PEQUENO, SUBTITULO, TITULO, color
from utils.validadores import email_valido, texto_requerido

PROVEEDORES = {"Gmail": "gmail", "Yahoo": "yahoo"}
AYUDA = {
    "gmail": "1. Activa la verificación en dos pasos en tu cuenta de Google.\n"
             "2. Entra a myaccount.google.com/apppasswords y crea una contraseña de aplicación.\n"
             "3. Pega aquí las 16 letras que te da Google (no tu contraseña normal).",
    "yahoo": "1. Activa la verificación en dos pasos en tu cuenta de Yahoo.\n"
             "2. En «Seguridad de la cuenta» elige «Generar contraseña de aplicación».\n"
             "3. Pega aquí la contraseña que te da Yahoo (no tu contraseña normal).",
}


def _menu(master, valores, comando=None, ancho=220):
    return ctk.CTkOptionMenu(master, values=valores, command=comando, width=ancho, height=36, font=NORMAL,
                             fg_color=COLORES["entrada"], button_color=COLORES["acento"],
                             button_hover_color=COLORES["acento_hover"], text_color=COLORES["texto"],
                             dynamic_resizing=False)


def _mensaje_error(error):
    if isinstance(error, imaplib.IMAP4.error):
        return "El correo rechazó la entrada. Revisa que uses una contraseña de aplicación."
    if isinstance(error, OSError):
        return "No hay conexión con el servidor de correo. Revisa tu internet."
    return str(error)


class DialogoCorreo(Dialogo):
    """Asistente para conectar el correo."""

    def __init__(self, master, usuario, al_guardar, cuenta=None):
        super().__init__(master, "Conectar correo", al_guardar, 600)
        self.usuario, self.cuenta = usuario, cuenta or {}
        self.etiqueta("Proveedor")
        self.proveedor = ctk.CTkSegmentedButton(self.cuerpo, values=list(PROVEEDORES), height=34, font=NORMAL,
                                                selected_color=COLORES["destacado"],
                                                selected_hover_color=COLORES["destacado_hover"],
                                                command=self._cambiar_proveedor)
        self.proveedor.set(next(k for k, v in PROVEEDORES.items() if v == self.cuenta.get("proveedor_email", "gmail")))
        self.proveedor.pack(fill="x")
        self.ayuda = ctk.CTkLabel(self.cuerpo, text="", font=PEQUENO, text_color=COLORES["texto2"],
                                  justify="left", anchor="w", wraplength=440)
        self.ayuda.pack(fill="x", pady=(10, 0))
        self.email = self.entrada("Correo", self.cuenta.get("email_conexion", ""))
        self.password = self.entrada("Contraseña de aplicación" + (" (déjala vacía para no cambiarla)"
                                                                  if self.cuenta else ""))
        self.password.configure(show="•")
        self.etiqueta("Revisar el correo automáticamente")
        self.intervalo = _menu(self.cuerpo, list(correo_dao.INTERVALOS), ancho=444)
        self.intervalo.set(next(k for k, v in correo_dao.INTERVALOS.items()
                                if v == self.cuenta.get("intervalo_horas", 6)))
        self.intervalo.pack(fill="x")
        self._cambiar_proveedor()
        self.email.focus()

    def _cambiar_proveedor(self, _=None):
        self.ayuda.configure(text=AYUDA[PROVEEDORES[self.proveedor.get()]])

    def guardar(self):
        proveedor = PROVEEDORES[self.proveedor.get()]
        email = self.email.get().strip().lower()
        password = self.password.get().replace(" ", "")  # Google la muestra en grupos de 4
        if not email_valido(email):
            return self.error.configure(text="Escribe un correo válido.")
        if not password:
            if self.cuenta.get("email_conexion") != email:
                return self.error.configure(text="Escribe la contraseña de aplicación.")
            password = lector_email.leer_password(email) or ""

        self.error.configure(text="Probando conexión…", text_color=COLORES["texto2"])
        self.update_idletasks()
        try:
            lector_email.probar_conexion(proveedor, email, password)
        except (imaplib.IMAP4.error, OSError) as e:
            return self.error.configure(text=_mensaje_error(e), text_color=COLORES["destacado"])

        anterior = self.cuenta.get("email_conexion")
        if anterior and anterior != email:
            lector_email.borrar_password(anterior)
        lector_email.guardar_password(email, password)
        correo_dao.guardar(self.usuario["id"], proveedor, email, correo_dao.INTERVALOS[self.intervalo.get()])
        return True


class DialogoPlantilla(Dialogo):
    """Para ajustar cómo se leen los avisos de un banco."""

    CAMPOS = [("banco", "Banco", 100), ("remitente", "El remitente contiene (ej. bbva)", 150),
              ("patron_asunto", "Patrón del asunto", 200), ("patron_monto", "Patrón del monto", 200),
              ("patron_fecha", "Patrón de la fecha (opcional)", 200),
              ("patron_comercio", "Patrón del comercio (opcional)", 200)]

    def __init__(self, master, al_guardar, plantilla=None):
        super().__init__(master, "Editar banco" if plantilla else "Nuevo banco", al_guardar, 670)
        self.plantilla = plantilla or {}
        self.error.configure(wraplength=440)
        ctk.CTkLabel(self.cuerpo, text="Patrones: expresiones regulares (se toma el primer paréntesis).",
                     font=PEQUENO, text_color=COLORES["texto2"], anchor="w").pack(fill="x")
        self.campos = {}
        for clave, texto, _ in self.CAMPOS:
            self.campos[clave] = self.entrada(texto, self.plantilla.get(clave, ""))
            if clave.startswith("patron"):
                self.campos[clave].configure(font=("Consolas", 13))
        self.campos["banco"].focus()

    def guardar(self):
        valores = {clave: self.campos[clave].get().strip()[:maximo] for clave, _, maximo in self.CAMPOS}
        if not texto_requerido(valores["banco"], 100):
            return self.error.configure(text="Escribe el nombre del banco.")
        if not valores["patron_asunto"] or not valores["patron_monto"]:
            return self.error.configure(text="El patrón del asunto y el del monto son obligatorios.")
        for clave, texto, _ in self.CAMPOS[2:]:
            try:
                re.compile(valores[clave])
            except re.error as e:
                return self.error.configure(text=f"«{texto}» no es una expresión regular válida: {e}")
        datos = [valores[clave] for clave, _, _ in self.CAMPOS]
        if self.plantilla:
            plantillas_dao.actualizar(self.plantilla["id"], *datos)
        else:
            plantillas_dao.crear(*datos)
        return True


class PanelCorreo(ctk.CTkFrame):
    def __init__(self, master, usuario):
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario
        self.principal = master
        self.movimientos = []
        self.ignorados = []  # correos del banco con asunto que no coincidió (última sincronización)
        self._hilo = None
        self._id_revision = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(self, text="Correo bancario", font=TITULO, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(self, text="Lee los avisos de compra que te manda tu banco y conviértelos en movimientos.",
                     font=NORMAL, text_color=COLORES["texto2"], anchor="w").grid(row=1, column=0, sticky="w",
                                                                                 pady=(0, 16))
        # Conexión (se rellena en refrescar)
        self.tarjeta_conexion = Tarjeta(self)
        self.tarjeta_conexion.grid(row=2, column=0, sticky="ew")

        # Bancos
        bancos = Tarjeta(self)
        bancos.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        cabecera = ctk.CTkFrame(bancos, fg_color="transparent")
        cabecera.pack(fill="x", padx=20, pady=(14, 4))
        ctk.CTkLabel(cabecera, text="Bancos que se leen", font=SUBTITULO).pack(side="left")
        ctk.CTkLabel(cabecera, text="  Solo se revisan los correos de los bancos encendidos", font=PEQUENO,
                     text_color=COLORES["texto2"]).pack(side="left")
        Boton(cabecera, "Agregar banco", icono="＋", estilo="secundario", width=140, height=32,
              command=lambda: DialogoPlantilla(self, self.refrescar)).pack(side="right")
        self.lista_bancos = ctk.CTkFrame(bancos, fg_color="transparent")
        self.lista_bancos.pack(fill="x", padx=14, pady=(0, 12))

        # Vista previa
        previa = Tarjeta(self)
        previa.grid(row=4, column=0, sticky="nsew", pady=(16, 0))
        previa.grid_columnconfigure(0, weight=1)
        previa.grid_rowconfigure(1, weight=1)
        cabecera = ctk.CTkFrame(previa, fg_color="transparent")
        cabecera.grid(row=0, column=0, sticky="ew", padx=20, pady=(14, 6))
        ctk.CTkLabel(cabecera, text="Movimientos detectados", font=SUBTITULO).pack(side="left")
        self.cuenta = _menu(cabecera, ["(sin cuentas)"])
        self.cuenta.pack(side="right")
        ctk.CTkLabel(cabecera, text="Guardar en", font=PEQUENO, text_color=COLORES["texto2"]).pack(side="right",
                                                                                                    padx=8)
        contenedor = ctk.CTkFrame(previa, fg_color="transparent")
        contenedor.grid(row=1, column=0, sticky="nsew", padx=12)
        contenedor.grid_rowconfigure(0, weight=1)
        contenedor.grid_columnconfigure(0, weight=1)
        self.vista = ttk.Treeview(contenedor, columns=("fecha", "banco", "descripcion", "categoria", "monto"),
                                  show="headings", height=6, selectmode="browse")
        for clave, titulo, ancho, alin in (("fecha", "Fecha", 100, "w"), ("banco", "Banco", 120, "w"),
                                           ("descripcion", "Comercio / descripción", 320, "w"),
                                           ("categoria", "Categoría sugerida", 180, "w"),
                                           ("monto", "Monto", 120, "e")):
            self.vista.heading(clave, text=titulo, anchor=alin)
            self.vista.column(clave, width=ancho, anchor=alin, stretch=clave == "descripcion")
        self.vista.grid(row=0, column=0, sticky="nsew")
        barra = ctk.CTkScrollbar(contenedor, command=self.vista.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.vista.configure(yscrollcommand=barra.set)
        resaltar_al_pasar(self.vista)

        pie = ctk.CTkFrame(previa, fg_color="transparent")
        pie.grid(row=2, column=0, sticky="ew", padx=20, pady=14)
        self.resumen = ctk.CTkLabel(pie, text="", font=NORMAL, text_color=COLORES["texto2"], anchor="w",
                                    justify="left", wraplength=620)
        self.resumen.pack(side="left", fill="x", expand=True)
        self.boton_guardar = Boton(pie, "Guardar", icono="✓", command=self._guardar)
        self.boton_guardar.pack(side="right")
        Boton(pie, "Descartar seleccionado", estilo="fantasma",
              command=self._descartar).pack(side="right", padx=8)
        self._mostrar_previa()

    def aplicar_tema(self):
        self.vista.tag_configure("ingreso", foreground="#2e9c7c")
        self.vista.tag_configure("gasto", foreground=color("texto"))
        colores_encima(self.vista)

    def destroy(self):
        if self._id_revision:
            self.after_cancel(self._id_revision)
        super().destroy()

    def refrescar(self):
        plantillas_dao.crear_por_defecto()
        self.cuenta_email = correo_dao.obtener(self.usuario["id"])
        self.cuentas = cuentas_dao.listar(self.usuario["id"], solo_activas=True)
        nombres = [c["nombre"] for c in self.cuentas] or ["(sin cuentas)"]
        actual = self.cuenta.get()
        self.cuenta.configure(values=nombres)
        self.cuenta.set(actual if actual in nombres else nombres[0])
        self._dibujar_conexion()
        self._dibujar_bancos()
        self.aplicar_tema()

    # ---------- Conexión ----------

    def _dibujar_conexion(self):
        for hijo in self.tarjeta_conexion.winfo_children():
            hijo.destroy()
        c = self.cuenta_email
        ctk.CTkLabel(self.tarjeta_conexion, text="✉", font=("Segoe UI Emoji", 18), width=44, height=44,
                     corner_radius=12, fg_color=COLORES["destacado"] if c else COLORES["acento"],
                     text_color="#ffffff").pack(side="left", padx=(20, 12), pady=16)
        textos = ctk.CTkFrame(self.tarjeta_conexion, fg_color="transparent")
        textos.pack(side="left")
        if not c:
            ctk.CTkLabel(textos, text="Tu correo no está conectado", font=NORMAL_NEGRITA, anchor="w").pack(anchor="w")
            ctk.CTkLabel(textos, text="Funciona con Gmail y Yahoo usando una contraseña de aplicación.",
                         font=PEQUENO, text_color=COLORES["texto2"], anchor="w").pack(anchor="w")
            Boton(self.tarjeta_conexion, "Conectar correo", icono="＋",
                  command=self._configurar).pack(side="right", padx=20)
            return

        ultima = f"{c['ultima_sincronizacion']:%d/%m/%Y %H:%M}" if c["ultima_sincronizacion"] else "nunca"
        automatico = next(k for k, v in correo_dao.INTERVALOS.items() if v == c["intervalo_horas"])
        ctk.CTkLabel(textos, text=f"{c['email_conexion']}  ·  {c['proveedor_email'].capitalize()}",
                     font=NORMAL_NEGRITA, anchor="w").pack(anchor="w")
        self.estado = ctk.CTkLabel(textos, text=f"Última revisión: {ultima}  ·  Automático: {automatico.lower()}",
                                   font=PEQUENO, text_color=COLORES["texto2"], anchor="w")
        self.estado.pack(anchor="w")
        Boton(self.tarjeta_conexion, "Desconectar", estilo="peligro", width=110,
              command=self._desconectar).pack(side="right", padx=(0, 20))
        Boton(self.tarjeta_conexion, "Configurar", estilo="secundario", width=110,
              command=self._configurar).pack(side="right", padx=8)
        self.boton_sincronizar = Boton(self.tarjeta_conexion, "Sincronizar ahora", icono="↻",
                                       command=self.sincronizar)
        self.boton_sincronizar.pack(side="right")
        if self._hilo:
            self._estado_buscando()

    def _configurar(self):
        DialogoCorreo(self, self.usuario, self._conexion_guardada, cuenta=self.cuenta_email)

    def _conexion_guardada(self):
        self.refrescar()
        self.principal.programar_correo()
        mostrar_aviso(self, "✓ Correo conectado")

    def _desconectar(self):
        if not messagebox.askyesno("Desconectar correo", "¿Desconectar tu correo?\n\n"
                                   "Los movimientos que ya guardaste no se borran."):
            return
        lector_email.borrar_password(self.cuenta_email["email_conexion"])
        correo_dao.eliminar(self.usuario["id"])
        self.refrescar()
        self.principal.programar_correo()

    # ---------- Bancos ----------

    def _dibujar_bancos(self):
        for hijo in self.lista_bancos.winfo_children():
            hijo.destroy()
        for i, plantilla in enumerate(plantillas_dao.listar()):
            celda = ctk.CTkFrame(self.lista_bancos, fg_color=COLORES["entrada"], corner_radius=10)
            celda.grid(row=i // 4, column=i % 4, padx=6, pady=4, sticky="ew")
            interruptor = ctk.CTkSwitch(celda, text=plantilla["banco"], font=NORMAL, width=40,
                                        progress_color=COLORES["destacado"], text_color=COLORES["texto"])
            interruptor.configure(command=lambda p=plantilla, s=interruptor:
                                  plantillas_dao.cambiar_activo(p["id"], s.get() == 1))
            if plantilla["activo"]:
                interruptor.select()
            interruptor.pack(side="left", padx=(12, 4), pady=8)
            Boton(celda, "✎", estilo="fantasma", width=34, height=30,
                  command=lambda p=plantilla: DialogoPlantilla(self, self.refrescar, p)).pack(side="right", padx=4)
        self.lista_bancos.grid_columnconfigure((0, 1, 2, 3), weight=1, uniform="banco")

    # ---------- Sincronizar (en un hilo) ----------

    def sincronizar(self, automatico=False):
        if self._hilo:
            return
        if correo_dao.obtener(self.usuario["id"]) is None:
            return None if automatico else mostrar_aviso(self, "Primero conecta tu correo", tipo="error")
        self._automatico = automatico
        self._resultado = None
        self._hilo = threading.Thread(target=self._trabajo, daemon=True)
        self._hilo.start()
        self._estado_buscando()
        self._id_revision = self.after(200, self._revisar_hilo)

    def _trabajo(self):
        """Corre en el hilo aparte: aquí no se toca la ventana, solo se guarda el resultado."""
        try:
            self._resultado = lector_email.sincronizar(self.usuario["id"])
        except Exception as e:  # sin internet, contraseña revocada, plantilla con error...
            self._resultado = e

    def _estado_buscando(self, puntos=3):
        boton = getattr(self, "boton_sincronizar", None)  # no existe si el panel aún no se dibujó
        if boton is not None and boton.winfo_exists():
            # Los puntos se mueven ("Buscando", "Buscando.", "Buscando.."...) mientras espera
            boton.configure(state="disabled", text="Buscando" + "." * puntos + " " * (3 - puntos))

    def _revisar_hilo(self):
        """Revisa cada 200 ms si el hilo ya terminó (Tkinter solo se puede tocar desde aquí)."""
        if self._hilo.is_alive():
            self._puntos = (getattr(self, "_puntos", 0) + 1) % 4
            self._estado_buscando(self._puntos)
            self._id_revision = self.after(200, self._revisar_hilo)
            return
        self._hilo = self._id_revision = None
        resultado = self._resultado
        self.refrescar()
        self.principal.programar_correo()
        if isinstance(resultado, Exception):
            return mostrar_aviso(self, _mensaje_error(resultado), tipo="error", duracion=5000)

        nuevos, sin_monto, self.ignorados = resultado
        ya_listados = {m["message_id"] for m in self.movimientos}
        self.movimientos += [m for m in nuevos if m["message_id"] not in ya_listados]
        self._mostrar_previa(sin_monto)
        if self._automatico and not nuevos:
            return
        if nuevos:
            texto = f"✓ {len(nuevos)} movimientos nuevos en tu correo"
        elif self.ignorados:
            texto = f"{len(self.ignorados)} correos del banco no parecían avisos (mira el detalle abajo)"
        else:
            texto = "No hay avisos nuevos"
        if self._automatico:
            texto += ". Revísalos en Correo"
        mostrar_aviso(self.principal, texto, tipo="ok" if nuevos else "info", duracion=4000)

    # ---------- Vista previa ----------

    def _mostrar_previa(self, sin_monto=0):
        categorias = categorias_dao.listar(self.usuario["id"])
        self.vista.delete(*self.vista.get_children())
        for i, mov in enumerate(self.movimientos):
            categoria = procesador_csv.sugerir_categoria(mov["descripcion"], mov["tipo"], categorias)
            mov["categoria_id"] = categoria["id"] if categoria else None
            self.vista.insert("", "end", iid=str(i), tags=(mov["tipo"],), values=(
                mov["fecha"].strftime("%d/%m/%Y"), mov["banco"], mov["descripcion"],
                f"{categoria['icono']}  {categoria['nombre']}" if categoria else "Sin categoría",
                formato_moneda(mov["monto"] * (-1 if mov["tipo"] == "gasto" else 1))))
        partes = [f"{len(self.movimientos)} movimientos por revisar" if self.movimientos
                  else "Toca «Sincronizar ahora» para buscar avisos nuevos"]
        if sin_monto:
            partes.append(f"Avisos sin monto reconocible: {sin_monto} (ajusta el patrón del banco)")
        texto = "  ·  ".join(partes)
        if self.ignorados:
            # Correos del remitente del banco cuyo asunto no coincidió: se listan para poder corregir el patrón
            ejemplos = ", ".join(f"«{i['asunto'][:40]}» ({i['banco']})" for i in self.ignorados[:3])
            extra = f" y {len(self.ignorados) - 3} más" if len(self.ignorados) > 3 else ""
            texto += (f"\n⚠ {len(self.ignorados)} correos del banco no parecían avisos: {ejemplos}{extra}. "
                      "Si eran movimientos, agrega esa palabra al «Patrón del asunto» del banco (✎).")
        self.resumen.configure(text=texto)
        self.boton_guardar.configure(text=f"✓  Guardar {len(self.movimientos)}",
                                     state="normal" if self.movimientos else "disabled")

    def _descartar(self):
        seleccion = self.vista.selection()
        if not seleccion:
            return mostrar_aviso(self, "Selecciona un movimiento de la tabla", tipo="info")
        mov = self.movimientos.pop(int(seleccion[0]))
        correo_dao.marcar_procesados(self.usuario["id"], [mov["message_id"]])  # no vuelve a aparecer
        self._mostrar_previa()

    def _guardar(self):
        cuenta = next((c for c in self.cuentas if c["nombre"] == self.cuenta.get()), None)
        if cuenta is None:
            return messagebox.showwarning("Sin cuenta", "Primero crea una cuenta en Configuración.")
        transacciones_dao.crear_varias([(cuenta["id"], m["categoria_id"], m["descripcion"], m["monto"],
                                         m["fecha"], m["tipo"], "email") for m in self.movimientos])
        correo_dao.marcar_procesados(self.usuario["id"], [m["message_id"] for m in self.movimientos])
        cantidad = len(self.movimientos)
        self.movimientos = []
        self._mostrar_previa()
        mostrar_aviso(self, f"✓ {cantidad} movimientos guardados en “{cuenta['nombre']}”")
