"""Tutorial guiado: aparece la primera vez que el usuario entra y se puede repetir desde el asistente.

Cada paso:
- abre una sección (si tiene "seccion"),
- resalta con un borde rojo un botón de la barra lateral (si tiene "objetivo"),
- y muestra una tarjeta al lado con la explicación.
Teclado: → o Enter = siguiente, ← = anterior, Esc = saltar.
"""
import customtkinter as ctk

from database import usuarios_dao
from ui.componentes import animaciones
from ui.componentes.boton_personalizado import Boton
from utils.temas import COLORES, NORMAL, PEQUENO, SUBTITULO

ANCHO_TARJETA = 380

PASOS = [
    {"titulo": "¡Bienvenido a FinanzApp! 👋",
     "texto": "Te muestro en un minuto cómo funciona. Puedes saltarlo y volver a verlo cuando quieras "
              "desde el Asistente (abajo a la izquierda)."},
    {"seccion": "inicio", "objetivo": "inicio", "titulo": "Inicio",
     "texto": "Tu resumen del mes: ingresos, gastos, balance y ahorro, con gráficas y tus últimos movimientos.\n\n"
              "Usa «⚡ Gasto rápido»: escribe un monto y toca una categoría."},
    {"objetivo": "nuevo", "titulo": "Nuevo movimiento",
     "texto": "Registra un gasto o un ingreso: monto, categoría, cuenta y fecha. Es lo que más vas a usar."},
    {"seccion": "historial", "objetivo": "historial", "titulo": "Historial",
     "texto": "Todos tus movimientos con filtros por fecha, categoría y cuenta. Doble clic para editar. "
              "También puedes exportar a CSV o PDF."},
    {"seccion": "reportes", "objetivo": "reportes", "titulo": "Reportes",
     "texto": "Gráficas por categoría, evolución de 12 meses y cuánto gastarías a fin de mes si sigues a este ritmo."},
    {"seccion": "importar", "objetivo": "importar", "titulo": "Importar",
     "texto": "Sube el CSV o Excel de tu banco y la app crea los movimientos sola, sin repetir los que ya tienes."},
    {"seccion": "correo", "objetivo": "correo", "titulo": "Correo",
     "texto": "Conecta tu Gmail y la app lee los avisos de compra de tu banco para que no tengas que anotarlos."},
    {"seccion": "config", "objetivo": "config", "titulo": "Configuración",
     "texto": "Crea tus cuentas (banco, tarjetas, efectivo), categorías y presupuestos. "
              "En «Datos» configuras el correo para recuperar tu contraseña."},
    {"seccion": "inicio", "objetivo": "asistente", "titulo": "Asistente",
     "texto": "¿Dudas? Pregúntale cuánto gastaste, tus saldos o cómo hacer algo. "
              "Escríbele «tutorial» para ver esta guía otra vez."},
]


class Tutorial:
    def __init__(self, ventana, al_terminar=None):
        """ventana: la VentanaPrincipal (de ahí se sacan los botones a resaltar y mostrar())."""
        self.ventana = ventana
        self.al_terminar = al_terminar
        self.indice = 0
        self.resaltado = None
        self.tarjeta = None
        self.flecha = ctk.CTkLabel(ventana, text="◀", font=("Segoe UI", 22), text_color=COLORES["destacado"],
                                   fg_color=COLORES["fondo"])
        raiz = ventana.winfo_toplevel()
        self._teclas = [(t, raiz.bind(t, f, add="+")) for t, f in
                        (("<Right>", lambda _: self.siguiente()), ("<Return>", lambda _: self.siguiente()),
                         ("<Left>", lambda _: self.anterior()), ("<Escape>", lambda _: self.terminar()))]
        self._mostrar()

    def _widget(self, objetivo):
        if objetivo in ("nuevo", "asistente"):
            return getattr(self.ventana, f"boton_{objetivo}")
        return self.ventana.botones_menu.get(objetivo)

    def _quitar_resaltado(self):
        if self.resaltado is not None and self.resaltado.winfo_exists():
            self.resaltado.configure(border_width=0)
        self.resaltado = None

    def _mostrar(self):
        paso = PASOS[self.indice]
        if paso.get("seccion"):
            self.ventana.mostrar(paso["seccion"])
        self._quitar_resaltado()
        if self.tarjeta is not None:
            self.tarjeta.destroy()
        self.tarjeta = self._construir_tarjeta(paso)
        # Se espera un instante a que la sección termine de acomodarse para medir posiciones
        self.ventana.after(80, lambda: self._colocar(paso))

    def _construir_tarjeta(self, paso):
        tarjeta = ctk.CTkFrame(self.ventana, width=ANCHO_TARJETA, corner_radius=16, fg_color=COLORES["fondo2"],
                               border_width=2, border_color=COLORES["destacado"])
        ctk.CTkLabel(tarjeta, text=f"Paso {self.indice + 1} de {len(PASOS)}", font=PEQUENO,
                     text_color=COLORES["destacado"], anchor="w").pack(fill="x", padx=20, pady=(16, 0))
        ctk.CTkLabel(tarjeta, text=paso["titulo"], font=SUBTITULO, anchor="w").pack(fill="x", padx=20)
        ctk.CTkLabel(tarjeta, text=paso["texto"], font=NORMAL, text_color=COLORES["texto2"], anchor="w",
                     justify="left", wraplength=ANCHO_TARJETA - 44).pack(fill="x", padx=20, pady=(6, 0))

        # Puntitos de progreso
        puntos = ctk.CTkFrame(tarjeta, fg_color="transparent")
        puntos.pack(anchor="w", padx=20, pady=(12, 0))
        for i in range(len(PASOS)):
            ctk.CTkFrame(puntos, width=18 if i == self.indice else 8, height=8, corner_radius=4,
                         fg_color=COLORES["destacado"] if i <= self.indice else COLORES["acento"]
                         ).pack(side="left", padx=2)

        botones = ctk.CTkFrame(tarjeta, fg_color="transparent")
        botones.pack(fill="x", padx=16, pady=(12, 16))
        ultimo = self.indice == len(PASOS) - 1
        Boton(botones, "¡Listo!" if ultimo else "Siguiente →", width=120, height=36,
              command=self.siguiente).pack(side="right")
        if self.indice > 0:
            Boton(botones, "← Atrás", estilo="secundario", width=90, height=36,
                  command=self.anterior).pack(side="right", padx=8)
        if not ultimo:
            Boton(botones, "Saltar", estilo="fantasma", width=70, height=36, command=self.terminar).pack(side="left")
        return tarjeta

    def _colocar(self, paso):
        if self.tarjeta is None or not self.tarjeta.winfo_exists():
            return
        v = self.ventana
        escala = v._get_widget_scaling()  # winfo_* da píxeles reales; place() espera medidas sin escalar
        v.update_idletasks()
        alto_ventana = v.winfo_height() / escala
        alto_tarjeta = self.tarjeta.winfo_reqheight() / escala
        objetivo = self._widget(paso.get("objetivo")) if paso.get("objetivo") else None

        if objetivo is None:  # paso sin botón: tarjeta en el centro
            self.flecha.place_forget()
            self.tarjeta.place(relx=0.5, rely=0.5, anchor="center")
        else:
            objetivo.configure(border_width=2, border_color=COLORES["destacado"])
            self.resaltado = objetivo
            centro = (objetivo.winfo_rooty() - v.winfo_rooty() + objetivo.winfo_height() / 2) / escala
            # Todos los objetivos están en la barra lateral: la flecha va justo a su borde derecho
            borde = (v.barra.winfo_rootx() - v.winfo_rootx() + v.barra.winfo_width()) / escala
            y = min(max(centro - alto_tarjeta / 2, 16), alto_ventana - alto_tarjeta - 16)
            self.flecha.place(x=borde + 2, y=centro, anchor="w")
            self.flecha.lift()
            animaciones.animar(self.tarjeta, 200, lambda a: self.tarjeta.place(x=borde + 28 + round(16 * (1 - a)), y=y))
        self.tarjeta.lift()

    # ---------- Navegación ----------

    def siguiente(self):
        if self.indice == len(PASOS) - 1:
            return self.terminar()
        self.indice += 1
        self._mostrar()

    def anterior(self):
        if self.indice > 0:
            self.indice -= 1
            self._mostrar()

    def terminar(self):
        """Fin normal (Listo o Saltar): se recuerda para no mostrarlo otra vez al entrar."""
        self.cancelar()
        usuarios_dao.marcar_tutorial_visto(self.ventana.usuario["id"])
        if self.al_terminar:
            self.al_terminar()

    def cancelar(self):
        """Quita la tarjeta, el resaltado y las teclas (también se usa al cerrar sesión a mitad)."""
        self._quitar_resaltado()
        for widget in (self.tarjeta, self.flecha):
            if widget is not None and widget.winfo_exists():
                widget.destroy()
        raiz = self.ventana.winfo_toplevel()
        for tecla, identificador in self._teclas:
            raiz.unbind(tecla, identificador)
        self._teclas = []
