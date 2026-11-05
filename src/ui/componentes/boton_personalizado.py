"""Botones con el estilo de la app (todos iguales en toda la interfaz).

Al pasar el mouse, el color cambia suavemente (animaciones.transicion_color)
en lugar del cambio instantáneo que trae CustomTkinter.
"""
import customtkinter as ctk

from ui.componentes import animaciones
from utils.temas import COLORES, NORMAL, NORMAL_NEGRITA

ESTILOS = {
    "primario": dict(fg_color=COLORES["destacado"], hover_color=COLORES["destacado_hover"],
                     text_color="#ffffff"),
    "secundario": dict(fg_color=COLORES["acento"], hover_color=COLORES["acento_hover"],
                       text_color=COLORES["texto"]),
    "peligro": dict(fg_color="transparent", hover_color=("#fde4e9", "#3d2328"), border_width=1,
                    border_color=COLORES["destacado"], text_color=COLORES["destacado"]),
    "fantasma": dict(fg_color="transparent", hover_color=COLORES["acento"], text_color=COLORES["texto2"]),
}


def hover_suave(boton, normal, encima):
    """El color de fondo pasa de `normal` a `encima` (y de regreso) con una transición."""
    boton.configure(hover=False)

    def entrar(_):
        if boton.cget("state") != "disabled":
            animaciones.transicion_color(boton, "fg_color", encima, normal)

    def salir(_):
        animaciones.transicion_color(boton, "fg_color", normal, encima)

    boton.bind("<Enter>", entrar)
    boton.bind("<Leave>", salir)


class Boton(ctk.CTkButton):
    def __init__(self, master, texto, icono="", estilo="primario", **opciones):
        configuracion = dict(corner_radius=10, height=38, font=NORMAL_NEGRITA, **ESTILOS[estilo])
        configuracion.update(opciones)
        super().__init__(master, text=f"{icono}  {texto}" if icono else texto, **configuracion)
        # Los transparentes no se pueden mezclar: usan el hover normal de CustomTkinter
        if configuracion["fg_color"] != "transparent":
            hover_suave(self, configuracion["fg_color"], configuracion["hover_color"])


class BotonMenu(ctk.CTkButton):
    """Botón de la barra lateral. Se resalta cuando su sección está abierta."""

    def __init__(self, master, texto, icono, comando):
        # Fondo del mismo color que la barra (no "transparent") para poder animarlo
        super().__init__(master, text=f"  {icono}    {texto}", anchor="w", height=44, corner_radius=10,
                         font=NORMAL, fg_color=COLORES["fondo2"], hover=False,
                         text_color=COLORES["texto2"], command=comando)
        self.activo = False
        self.bind("<Enter>", lambda _: self.activo or self._color(COLORES["acento"], COLORES["fondo2"]))
        self.bind("<Leave>", lambda _: self.activo or self._color(COLORES["fondo2"], COLORES["acento"]))

    def _color(self, hasta, desde):
        entrando = hasta == COLORES["acento"]
        animaciones.transicion_color(self, "fg_color", hasta, desde)
        animaciones.transicion_color(self, "text_color", COLORES["texto"] if entrando else COLORES["texto2"],
                                     COLORES["texto2"] if entrando else COLORES["texto"])

    def activar(self, activo):
        self.activo = activo
        animaciones.detener(self, "_anim_fg_color")
        animaciones.detener(self, "_anim_text_color")
        self.__dict__.get("_colores_actuales", {}).clear()
        if activo:
            self.configure(fg_color=COLORES["acento"], text_color=COLORES["texto"], font=NORMAL_NEGRITA)
        else:
            self.configure(fg_color=COLORES["fondo2"], text_color=COLORES["texto2"], font=NORMAL)
