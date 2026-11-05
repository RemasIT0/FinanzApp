"""El asistente en la app de escritorio:
- MascotaFlotante: el muñequito peludo que flota abajo a la derecha. Al tocarlo abre o cierra el chat.
- PanelAsistente: la ventana del chat. Las respuestas salen de utils/asistente.py;
  aquí solo se dibujan las burbujas, los atajos y los botones de acción.
"""
import math
import time
import tkinter as tk

import customtkinter as ctk
from PIL import Image, ImageTk

from ui.componentes import animaciones
from ui.componentes.boton_personalizado import Boton
from utils import asistente, mascota
from utils.temas import COLORES, NORMAL, NORMAL_NEGRITA, PEQUENO

ANCHO, ALTO = 380, 520
ANCHO_BURBUJA = 270
ALTO_MASCOTA = 78
MARGEN = 18                      # separación del muñeco con los bordes de la ventana
ESPACIO_MASCOTA = ALTO_MASCOTA + MARGEN + 10   # lo que ocupa abajo (el chat se abre encima)


COLOR_TRANSPARENTE = "#ff00ff"   # Windows hace "invisible" este color en la ventanita del muñeco


def _imagen_recortada(alto):
    """El muñeco listo para una ventana con color transparente.
    Ese truco de Windows solo entiende "visible / invisible" (no semitransparente), así que:
    los píxeles casi transparentes pasan a ser el color invisible y los bordes suaves se
    mezclan con marrón (como son pelos, no se nota)."""
    imagen = mascota.imagen(alto)
    fondo = Image.new("RGBA", imagen.size, mascota.MARRONES[1])
    mezcla = Image.alpha_composite(fondo, imagen)
    mascara = imagen.getchannel("A").point(lambda a: 255 if a >= 110 else 0)
    final = Image.new("RGB", imagen.size, COLOR_TRANSPARENTE)
    final.paste(mezcla.convert("RGB"), mask=mascara)
    return final


class MascotaFlotante:
    """El muñequito: vive en su propia ventanita sin bordes (con fondo invisible) que flota
    sobre la esquina de abajo a la derecha de la ventana principal. Sube y baja suave y al
    tocarlo llama a al_tocar().

    ¿Por qué una ventanita aparte? Dentro de una ventana de Tkinter las imágenes no pueden
    tener fondo transparente: se vería un recuadro detrás del muñeco al pasar sobre una tarjeta.
    """

    def __init__(self, ventana, al_tocar):
        self.ventana = ventana          # la VentanaPrincipal (el globo de diálogo se dibuja ahí)
        self.al_tocar = al_tocar
        self.escala = ventana._get_widget_scaling()  # zoom de Windows (ej. 1.25 = 125 %)
        alto = round(ALTO_MASCOTA * self.escala)   # en píxeles reales
        self.foto = ImageTk.PhotoImage(_imagen_recortada(alto))
        self.ancho_px, self.alto_px = self.foto.width(), self.foto.height()
        self.ancho = round(self.ancho_px / self.escala)   # en medidas de la app (sin escalar)

        self.ventanita = tk.Toplevel(ventana)
        self.ventanita.overrideredirect(True)                       # sin bordes ni barra de título
        self.ventanita.transient(ventana.winfo_toplevel())          # siempre encima de la app (y se minimiza con ella)
        self.ventanita.configure(bg=COLOR_TRANSPARENTE)
        self.ventanita.attributes("-transparentcolor", COLOR_TRANSPARENTE)
        etiqueta = tk.Label(self.ventanita, image=self.foto, bg=COLOR_TRANSPARENTE, bd=0, highlightthickness=0,
                            cursor="hand2")
        etiqueta.pack()
        etiqueta.bind("<Button-1>", lambda _: self.al_tocar())

        # Si se minimiza la app, el muñeco se esconde; al volver, reaparece.
        # (Ojo: estos eventos también llegan cuando se oculta cualquier parte de la app, por
        #  eso se revisa que sea la ventana principal: e.widget is raiz.)
        raiz = ventana.winfo_toplevel()
        self._eventos = [
            (raiz, "<Unmap>", raiz.bind("<Unmap>", lambda e: e.widget is raiz and self.ventanita.withdraw(), add="+")),
            (raiz, "<Map>", raiz.bind("<Map>", lambda e: e.widget is raiz and self.ventanita.deiconify(), add="+"))]
        self.inicio = time.perf_counter()
        self.salto = 0.0       # altura extra de un salto (para llamar la atención)
        self.globo = None
        self._flotar()

    def _flotar(self):
        """Sigue a la ventana principal y sube y baja 4 px. Se reprograma solo cada 40 ms."""
        if not self.ventanita.winfo_exists():
            return
        raiz = self.ventana.winfo_toplevel()
        t = time.perf_counter() - self.inicio
        margen = round(MARGEN * self.escala)
        x = raiz.winfo_rootx() + raiz.winfo_width() - margen - self.ancho_px
        y = (raiz.winfo_rooty() + raiz.winfo_height() - margen - self.alto_px
             - round((4 * math.sin(t * 2.6) + self.salto) * self.escala))
        # (Sin lift(): como es "transient" ya queda encima de la app, y lift() la traería
        #  al frente sobre otros programas abiertos.)
        self.ventanita.geometry(f"+{x}+{y}")
        self.ventanita.after(40, self._flotar)

    def destruir(self):
        for widget, evento, identificador in self._eventos:
            if widget.winfo_exists():
                widget.unbind(evento, identificador)
        if self.ventanita.winfo_exists():
            self.ventanita.destroy()

    def saltar(self):
        """Da un saltito (se usa en el tutorial para señalarlo)."""
        animaciones.animar(self.ventanita, 500, lambda a: setattr(self, "salto", 26 * math.sin(a * math.pi)),
                           clave="_anim_salto")

    def decir(self, texto, duracion=4500):
        """Un globito de diálogo a la izquierda del muñeco que desaparece solo."""
        self.callar()
        self.globo = ctk.CTkLabel(self.ventana, text=texto, font=NORMAL_NEGRITA, corner_radius=14, height=38,
                                  fg_color=COLORES["fondo2"], text_color=COLORES["texto"], cursor="hand2")
        self.globo.bind("<Button-1>", lambda _: self.al_tocar())
        self.globo.place(relx=1, rely=1, x=-(MARGEN + self.ancho + 8), y=-(MARGEN + 40), anchor="se")
        self.globo.lift()
        self.globo.after(duracion, self.callar)

    def callar(self):
        if self.globo is not None and self.globo.winfo_exists():
            self.globo.destroy()
        self.globo = None


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
        cabecera.pack(fill="x", padx=14, pady=(12, 6))
        imagen = mascota.imagen(84)
        self.cara = ctk.CTkImage(imagen, size=(round(imagen.width * 42 / imagen.height), 42))
        ctk.CTkLabel(cabecera, text="", image=self.cara).pack(side="left")
        textos = ctk.CTkFrame(cabecera, fg_color="transparent")
        textos.pack(side="left", padx=10)
        ctk.CTkLabel(textos, text="Asistente", font=NORMAL_NEGRITA, anchor="w", height=20).pack(anchor="w")
        ctk.CTkLabel(textos, text="Tu dinero y la app, rápido", font=PEQUENO,
                     text_color=COLORES["texto2"], anchor="w", height=16).pack(anchor="w")
        Boton(cabecera, "✕", estilo="fantasma", width=34, height=34, command=self.cerrar).pack(side="right")
        Boton(cabecera, "Limpiar", icono="🗑", estilo="fantasma", width=90, height=34, font=PEQUENO,
              command=self.limpiar).pack(side="right")

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

    # ---------- Abrir / cerrar / limpiar ----------

    def abrir(self):
        self.abierto = True
        self.lift()
        # Entra subiendo un poco, justo encima del muñeco
        animaciones.animar(self, 220, lambda a: self.place(relx=1, rely=1, x=-MARGEN,
                                                           y=-ESPACIO_MASCOTA + round(30 * (1 - a)), anchor="se"))
        self.after(50, self.entrada.focus)

    def cerrar(self):
        self.abierto = False
        self.place_forget()

    def alternar(self):
        self.cerrar() if self.abierto else self.abrir()

    def limpiar(self):
        """Borra toda la conversación y vuelve a saludar."""
        for hijo in self.conversacion.winfo_children():
            hijo.destroy()
        self._mostrar_respuesta(asistente.bienvenida(self.usuario))
        # Volver arriba: si no, queda desplazado donde estaban los mensajes viejos y se ve vacío
        self.after(120, lambda: self.conversacion._parent_canvas.yview_moveto(0.0))
        self.entrada.focus()

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
