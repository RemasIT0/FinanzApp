"""Panel flotante del asistente (chatbot). Las respuestas salen de utils/asistente.py;
aquí solo se dibujan las burbujas, los atajos y los botones de acción."""
import customtkinter as ctk

from ui.componentes import animaciones
from ui.componentes.boton_personalizado import Boton
from utils import asistente
from utils.temas import COLORES, NORMAL, NORMAL_NEGRITA, PEQUENO

ANCHO, ALTO = 380, 560
ANCHO_BURBUJA = 270


class PanelAsistente(ctk.CTkFrame):
    def __init__(self, master, usuario, al_accion):
        """al_accion(accion): la ventana principal sabe qué hacer con ("ir", seccion), ("nuevo",) o ("tutorial",)."""
        super().__init__(master, width=ANCHO, height=ALTO, corner_radius=16, fg_color=COLORES["fondo2"],
                         border_width=1, border_color=COLORES["borde"])
        self.pack_propagate(False)
        self.usuario = usuario
        self.al_accion = al_accion
        self.abierto = False

        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(cabecera, text="💬", font=("Segoe UI Emoji", 20), width=40, height=40, corner_radius=12,
                     fg_color=COLORES["destacado"], text_color="#ffffff").pack(side="left")
        textos = ctk.CTkFrame(cabecera, fg_color="transparent")
        textos.pack(side="left", padx=10)
        ctk.CTkLabel(textos, text="Asistente", font=NORMAL_NEGRITA, anchor="w", height=20).pack(anchor="w")
        ctk.CTkLabel(textos, text="Respuestas rápidas sobre tu dinero y la app", font=PEQUENO,
                     text_color=COLORES["texto2"], anchor="w", height=16).pack(anchor="w")
        Boton(cabecera, "✕", estilo="fantasma", width=34, height=34, command=self.cerrar).pack(side="right")

        # Escribir (abajo) y atajos (encima): se empaquetan antes que la conversación para que nunca se tapen
        fila = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(side="bottom", fill="x", padx=12, pady=(4, 14))
        self.entrada = ctk.CTkEntry(fila, height=40, corner_radius=12, font=NORMAL,
                                    placeholder_text="Escribe tu pregunta…", fg_color=COLORES["entrada"],
                                    border_color=COLORES["borde"])
        self.entrada.pack(side="left", fill="x", expand=True)
        self.entrada.bind("<Return>", lambda _: self.enviar())
        self.entrada.bind("<Escape>", lambda _: self.cerrar())
        Boton(fila, "➤", width=44, height=40, command=self.enviar).pack(side="left", padx=(8, 0))
        self.atajos = ctk.CTkFrame(self, fg_color="transparent")
        self.atajos.pack(side="bottom", fill="x", padx=12)

        self.conversacion = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                                   scrollbar_button_color=COLORES["acento"])
        self.conversacion.pack(fill="both", expand=True, padx=4)

        self._mostrar_respuesta(asistente.bienvenida(usuario))

    # ---------- Abrir / cerrar ----------

    def abrir(self):
        self.abierto = True
        self.lift()
        # Entra subiendo un poco desde abajo a la derecha. Queda 70 px arriba del borde para que
        # los avisos flotantes (que salen abajo a la derecha) no tapen la caja de escribir.
        animaciones.animar(self, 220, lambda a: self.place(relx=1, rely=1, x=-24, y=-70 + round(30 * (1 - a)),
                                                           anchor="se"))
        self.after(50, self.entrada.focus)

    def cerrar(self):
        self.abierto = False
        self.place_forget()

    def alternar(self):
        self.cerrar() if self.abierto else self.abrir()

    # ---------- Conversación ----------

    def enviar(self, texto=None):
        texto = (texto or self.entrada.get()).strip()
        if not texto:
            return
        self.entrada.delete(0, "end")
        self._burbuja(texto, propia=True)
        self._mostrar_respuesta(asistente.responder(texto, self.usuario))

    def _burbuja(self, texto, propia=False):
        fila = ctk.CTkFrame(self.conversacion, fg_color="transparent")
        fila.pack(fill="x", pady=4, padx=6)
        ctk.CTkLabel(fila, text=texto, font=NORMAL, wraplength=ANCHO_BURBUJA, justify="left", anchor="w",
                     corner_radius=14, fg_color=COLORES["destacado"] if propia else COLORES["acento"],
                     text_color="#ffffff" if propia else COLORES["texto"]).pack(
            side="right" if propia else "left", ipadx=10, ipady=6)
        return fila

    def _mostrar_respuesta(self, respuesta):
        self._burbuja(respuesta["texto"])
        for texto, accion in respuesta["acciones"]:
            Boton(self.conversacion, texto, estilo="secundario", height=32, font=PEQUENO,
                  command=lambda a=accion: self._ejecutar(a)).pack(anchor="w", padx=10, pady=(0, 4))
        self._mostrar_atajos(respuesta["sugerencias"] or asistente.SUGERENCIAS_INICIO[:3])
        self.after(60, lambda: self.conversacion._parent_canvas.yview_moveto(1.0))  # bajar al último mensaje

    def _mostrar_atajos(self, sugerencias):
        for hijo in self.atajos.winfo_children():
            hijo.destroy()
        for i, texto in enumerate(sugerencias[:4]):
            boton = ctk.CTkButton(self.atajos, text=texto, font=PEQUENO, height=28, corner_radius=14,
                                  fg_color=COLORES["entrada"], hover_color=COLORES["acento"],
                                  text_color=COLORES["texto"], border_width=1, border_color=COLORES["borde"],
                                  command=lambda t=texto: self.enviar(t))
            boton.grid(row=i // 2, column=i % 2, sticky="ew", padx=3, pady=3)
        self.atajos.grid_columnconfigure((0, 1), weight=1, uniform="atajo")

    def _ejecutar(self, accion):
        if accion[0] in ("ir", "tutorial"):
            self.cerrar()  # que no tape la sección ni el tutorial
        self.al_accion(accion)
