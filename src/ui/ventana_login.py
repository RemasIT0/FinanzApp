"""Pantallas de inicio: conexión a MySQL (solo si falla) y login / registro."""
import customtkinter as ctk
import mysql.connector

from database import usuarios_dao
from database.conexion import inicializar_bd
from ui.componentes import animaciones
from ui.componentes.aviso import mostrar_aviso
from ui.componentes.boton_personalizado import Boton
from ui.ventana_config import DialogoRemitente, centrar_ventana
from utils import recuperacion
from utils.config import actualizar_config, cargar_config, guardar_config
from utils.temas import COLORES, NORMAL, PEQUENO, SUBTITULO, TITULO
from utils.validadores import email_valido, password_valida, texto_requerido


def _campo(master, etiqueta, ocultar=False, padx=40):
    ctk.CTkLabel(master, text=etiqueta, font=PEQUENO, text_color=COLORES["texto2"],
                 anchor="w").pack(fill="x", padx=padx, pady=(10, 2))
    entrada = ctk.CTkEntry(master, height=42, corner_radius=10, font=NORMAL, show="•" if ocultar else "",
                           fg_color=COLORES["entrada"], border_color=COLORES["borde"])
    entrada.pack(fill="x", padx=padx)
    return entrada


class PanelMarca(ctk.CTkFrame):
    """Panel izquierdo con el logo y el mensaje de bienvenida."""

    def __init__(self, master):
        super().__init__(master, corner_radius=0, fg_color="#2b2b31")
        contenido = ctk.CTkFrame(self, fg_color="transparent")
        # Entra subiendo suavemente hasta el centro
        animaciones.animar(contenido, 600, lambda a: contenido.place(relx=0.5, rely=0.56 - 0.06 * a, anchor="center"))
        ctk.CTkLabel(contenido, text="◈", font=("Segoe UI", 64), text_color=COLORES["destacado"]).pack(anchor="w")
        ctk.CTkLabel(contenido, text="FinanzApp", font=("Segoe UI", 40, "bold"),
                     text_color="#ffffff").pack(anchor="w")
        ctk.CTkLabel(contenido, text="Tus finanzas, claras y en orden.", font=SUBTITULO,
                     text_color="#c9d3ea").pack(anchor="w", pady=(4, 32))
        for punto in ("Importa tus estados de cuenta en segundos",
                      "Mira en qué se va tu dinero con gráficas",
                      "Pon presupuestos y recibe alertas"):
            ctk.CTkLabel(contenido, text=f"✓   {punto}", font=NORMAL, text_color="#ffffff").pack(anchor="w", pady=5)


class PanelLogin(ctk.CTkFrame):
    def __init__(self, master, al_entrar):
        super().__init__(master, corner_radius=0, fg_color=COLORES["fondo"])
        self.al_entrar = al_entrar
        self.grid_columnconfigure((0, 1), weight=1, uniform="mitad")
        self.grid_rowconfigure(0, weight=1)
        PanelMarca(self).grid(row=0, column=0, sticky="nsew")

        derecha = ctk.CTkFrame(self, fg_color="transparent")
        derecha.grid(row=0, column=1, sticky="nsew")
        tarjeta = ctk.CTkFrame(self, corner_radius=20, fg_color=COLORES["fondo2"], width=440, border_width=1,
                               border_color=COLORES["borde"])
        # Con place() se puede sacudir la tarjeta cuando hay un error
        self.tarjeta, self.lugar_tarjeta = tarjeta, dict(in_=derecha, relx=0.5, rely=0.5, anchor="center")
        tarjeta.place(**self.lugar_tarjeta)

        self.titulo = ctk.CTkLabel(tarjeta, text="Bienvenido de nuevo", font=TITULO)
        self.titulo.pack(padx=40, pady=(36, 4), anchor="w")
        self.subtitulo = ctk.CTkLabel(tarjeta, text="Inicia sesión para ver tu resumen",
                                      font=NORMAL, text_color=COLORES["texto2"])
        self.subtitulo.pack(padx=40, anchor="w")

        self.selector = ctk.CTkSegmentedButton(
            tarjeta, values=["Iniciar sesión", "Crear cuenta"], command=self._cambiar_modo, height=36,
            font=NORMAL, selected_color=COLORES["destacado"], selected_hover_color=COLORES["destacado_hover"],
            unselected_color=COLORES["entrada"], fg_color=COLORES["entrada"])
        self.selector.set("Iniciar sesión")
        self.selector.pack(fill="x", padx=40, pady=(20, 6))

        # El campo "nombre" solo se muestra al crear cuenta
        self.marco_nombre = ctk.CTkFrame(tarjeta, fg_color="transparent")
        self.nombre = _campo(self.marco_nombre, "Nombre")
        self.marco_campos = ctk.CTkFrame(tarjeta, fg_color="transparent")
        self.marco_campos.pack(fill="x")
        self.email = _campo(self.marco_campos, "Correo electrónico")
        self.password = _campo(self.marco_campos, "Contraseña", ocultar=True)
        # Solo se ve en "Iniciar sesión"
        self.olvide = ctk.CTkButton(self.marco_campos, text="¿Olvidaste tu contraseña?", font=PEQUENO,
                                    fg_color="transparent", hover=False, text_color=COLORES["destacado"],
                                    height=24, width=10, command=self._recuperar)
        self.olvide.pack(anchor="e", padx=36, pady=(6, 0))

        self.error = ctk.CTkLabel(tarjeta, text="", font=PEQUENO, text_color=COLORES["destacado"], wraplength=360)
        self.error.pack(padx=40, pady=(10, 0))
        self.boton = Boton(tarjeta, "Entrar", height=46, command=self._enviar)
        self.boton.pack(fill="x", padx=40, pady=(6, 36))

        ultimo = cargar_config()["ultimo_email"]
        if ultimo:
            self.email.insert(0, ultimo)
        for entrada in (self.nombre, self.email, self.password):
            entrada.bind("<Return>", lambda _: self._enviar())
        self.after(100, lambda: (self.password if ultimo else self.email).focus())

    def _creando_cuenta(self):
        return self.selector.get() == "Crear cuenta"

    def _cambiar_modo(self, _=None):
        self.error.configure(text="")
        if self._creando_cuenta():
            self.titulo.configure(text="Crea tu cuenta")
            self.subtitulo.configure(text="Solo toma un minuto")
            self.marco_nombre.pack(fill="x", before=self.marco_campos)
            self.boton.configure(text="Crear cuenta")
            self.olvide.pack_forget()
            self.nombre.focus()
        else:
            self.titulo.configure(text="Bienvenido de nuevo")
            self.subtitulo.configure(text="Inicia sesión para ver tu resumen")
            self.marco_nombre.pack_forget()
            self.boton.configure(text="Entrar")
            self.olvide.pack(anchor="e", padx=36, pady=(6, 0))

    def _recuperar(self):
        DialogoRecuperar(self, self.email.get().strip().lower(), al_terminar=self._password_cambiada)

    def _password_cambiada(self, email):
        self.email.delete(0, "end")
        self.email.insert(0, email)
        self.password.delete(0, "end")
        self.password.focus()
        self.error.configure(text="")
        mostrar_aviso(self, "✓ Contraseña cambiada. Ya puedes entrar")

    def _mostrar_error(self, texto):
        self.error.configure(text=texto)
        animaciones.sacudir(self.tarjeta, self.lugar_tarjeta)

    def _enviar(self):
        email = self.email.get().strip().lower()
        password = self.password.get()
        if not email_valido(email):
            return self._mostrar_error("Escribe un correo válido.")
        if not password_valida(password):
            return self._mostrar_error("La contraseña debe tener al menos 6 caracteres.")

        if self._creando_cuenta():
            nombre = texto_requerido(self.nombre.get(), 100)
            if not nombre:
                return self._mostrar_error("Escribe tu nombre.")
            if usuarios_dao.existe_email(email):
                return self._mostrar_error("Ese correo ya está registrado. Inicia sesión.")
            usuarios_dao.registrar(nombre, email, password)

        usuario = usuarios_dao.iniciar_sesion(email, password)
        if not usuario:
            return self._mostrar_error("Correo o contraseña incorrectos.")
        actualizar_config(ultimo_email=email)
        self.al_entrar(usuario)


class DialogoRecuperar(ctk.CTkToplevel):
    """Dos pasos: 1) escribir el correo y recibir el código  2) código + contraseña nueva."""

    def __init__(self, master, email, al_terminar):
        super().__init__(master, fg_color=COLORES["fondo"])
        self.al_terminar = al_terminar
        self.title("Recuperar contraseña")
        centrar_ventana(self, master, 480, 520)
        self.email_enviado = ""

        ctk.CTkLabel(self, text="Recuperar contraseña", font=SUBTITULO, anchor="w").pack(fill="x", padx=28, pady=(24, 4))
        self.explicacion = ctk.CTkLabel(self, text="", font=NORMAL, text_color=COLORES["texto2"], anchor="w",
                                        justify="left", wraplength=420)
        self.explicacion.pack(fill="x", padx=28)
        self.cuerpo = ctk.CTkFrame(self, fg_color="transparent")
        self.cuerpo.pack(fill="both", expand=True)
        self.error = ctk.CTkLabel(self, text="", font=PEQUENO, text_color=COLORES["destacado"], wraplength=420)
        self.error.pack(padx=28)
        self.botones = ctk.CTkFrame(self, fg_color="transparent")
        self.botones.pack(fill="x", padx=28, pady=(8, 24))
        self.bind("<Escape>", lambda _: self.destroy())

        self._paso_correo(email)
        self.after(150, lambda: (self.lift(), self.focus_force(), self.grab_set()))

    def _limpiar(self):
        for marco in (self.cuerpo, self.botones):
            for hijo in marco.winfo_children():
                hijo.destroy()
        self.error.configure(text="", text_color=COLORES["destacado"])

    def _mensaje(self, texto, es_error=True):
        self.error.configure(text=texto, text_color=COLORES["destacado"] if es_error else COLORES["texto2"])
        self.update_idletasks()

    # ---------- Paso 1 ----------

    def _paso_correo(self, email=""):
        self._limpiar()
        if not recuperacion.disponible():
            self.explicacion.configure(text="Para mandarte un código, antes hay que configurar la cuenta Gmail "
                                            "desde la que la app envía los correos (solo se hace una vez).")
            Boton(self.botones, "Configurar correo de envío", icono="✉",
                  # Al cerrar el diálogo hijo, esta ventana recupera el foco y pasa al paso del correo
                  command=lambda: DialogoRemitente(self, lambda: (self.grab_set(), self._paso_correo()))
                  ).pack(side="right")
            Boton(self.botones, "Cancelar", estilo="fantasma", command=self.destroy).pack(side="right", padx=8)
            return
        self.explicacion.configure(text="Escribe el correo con el que te registraste y te mandaremos "
                                        "un código de 6 dígitos.")
        self.email = _campo(self.cuerpo, "Correo electrónico", padx=28)
        self.email.insert(0, email or self.email_enviado)
        self.email.bind("<Return>", lambda _: self._enviar_codigo())
        Boton(self.botones, "Enviar código", command=self._enviar_codigo).pack(side="right")
        Boton(self.botones, "Cancelar", estilo="fantasma", command=self.destroy).pack(side="right", padx=8)
        self.email.focus()

    def _enviar_codigo(self, email=None):
        email = email or self.email.get().strip().lower()
        if not email_valido(email):
            return self._mensaje("Escribe un correo válido.")
        self._mensaje("Enviando código…", es_error=False)
        try:
            aviso = recuperacion.solicitar(email)
        except ValueError as e:
            return self._mensaje(str(e))
        self.email_enviado = email
        self._paso_codigo(aviso)

    # ---------- Paso 2 ----------

    def _paso_codigo(self, aviso):
        self._limpiar()
        self.explicacion.configure(text=f"{aviso}\n\nCorreo: {self.email_enviado}")
        self.codigo = _campo(self.cuerpo, "Código de 6 dígitos", padx=28)
        self.nueva = _campo(self.cuerpo, "Contraseña nueva (mínimo 6 caracteres)", ocultar=True, padx=28)
        self.repetir = _campo(self.cuerpo, "Repite la contraseña nueva", ocultar=True, padx=28)
        for campo in (self.codigo, self.nueva, self.repetir):
            campo.bind("<Return>", lambda _: self._cambiar())
        Boton(self.botones, "Cambiar contraseña", command=self._cambiar).pack(side="right")
        Boton(self.botones, "Reenviar código", estilo="fantasma",
              command=lambda: self._enviar_codigo(self.email_enviado)).pack(side="right", padx=8)
        Boton(self.botones, "← Volver", estilo="fantasma", width=90,
              command=self._paso_correo).pack(side="left")
        self.codigo.focus()

    def _cambiar(self):
        codigo = self.codigo.get().strip()
        nueva = self.nueva.get()
        if not (codigo.isdigit() and len(codigo) == 6):
            return self._mensaje("El código tiene 6 números.")
        if not password_valida(nueva):
            return self._mensaje("La contraseña debe tener al menos 6 caracteres.")
        if nueva != self.repetir.get():
            return self._mensaje("Las contraseñas no coinciden.")
        error = usuarios_dao.cambiar_password_con_codigo(self.email_enviado, codigo, nueva)
        if error:
            return self._mensaje(error)
        self.destroy()
        self.al_terminar(self.email_enviado)


class PanelConexion(ctk.CTkFrame):
    """Se muestra solo si no se pudo conectar a MySQL (por ejemplo, la primera vez)."""

    def __init__(self, master, mensaje_error, al_conectar):
        super().__init__(master, corner_radius=0, fg_color=COLORES["fondo"])
        self.al_conectar = al_conectar
        tarjeta = ctk.CTkFrame(self, corner_radius=20, fg_color=COLORES["fondo2"])
        tarjeta.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(tarjeta, text="Conectar con MySQL", font=TITULO).pack(padx=40, pady=(32, 4), anchor="w")
        ctk.CTkLabel(tarjeta, text="Escribe los datos de tu servidor MySQL.\n"
                                   "La base de datos y las tablas se crean solas.",
                     font=NORMAL, text_color=COLORES["texto2"], justify="left").pack(padx=40, anchor="w")

        datos = cargar_config()["mysql"]
        self.host = _campo(tarjeta, "Servidor")
        self.puerto = _campo(tarjeta, "Puerto")
        self.usuario = _campo(tarjeta, "Usuario")
        self.password = _campo(tarjeta, "Contraseña", ocultar=True)
        for entrada, valor in ((self.host, datos["host"]), (self.puerto, datos["puerto"]),
                               (self.usuario, datos["usuario"]), (self.password, datos["password"])):
            entrada.insert(0, str(valor))
        self.password.bind("<Return>", lambda _: self._probar())

        self.error = ctk.CTkLabel(tarjeta, text=mensaje_error, font=PEQUENO, wraplength=380,
                                  text_color=COLORES["destacado"], justify="left")
        self.error.pack(padx=40, pady=(12, 0), anchor="w")
        Boton(tarjeta, "Probar y guardar", height=46, command=self._probar).pack(fill="x", padx=40, pady=(8, 32))

    def _probar(self):
        config = cargar_config()
        config["mysql"] = {"host": self.host.get().strip(), "puerto": self.puerto.get().strip() or "3306",
                           "usuario": self.usuario.get().strip(), "password": self.password.get()}
        guardar_config(config)
        try:
            inicializar_bd()
        except mysql.connector.Error as e:
            return self.error.configure(text=f"No se pudo conectar: {e.msg}")
        except ValueError:
            return self.error.configure(text="El puerto debe ser un número (normalmente 3306).")
        self.al_conectar()
