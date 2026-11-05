"""Tarjetas: el contenedor base de todas las pantallas y la tarjeta con un número grande."""
import customtkinter as ctk

from ui.componentes import animaciones
from utils.temas import COLORES, GRAFICAS, ICONO, NORMAL, NUMERO, PEQUENO


class Tarjeta(ctk.CTkFrame):
    """Contenedor redondeado con un borde fino. Con brillo=True el borde se ilumina al pasar el mouse."""

    def __init__(self, master, brillo=False, **opciones):
        super().__init__(master, corner_radius=16, fg_color=COLORES["fondo2"], border_width=1,
                         border_color=COLORES["borde"], **opciones)
        self._iluminada = False
        if brillo:
            self.bind("<Enter>", lambda _: self._encender())

    def _encender(self):
        if self._iluminada:
            return
        self._iluminada = True
        animaciones.transicion_color(self, "border_color", COLORES["texto2"], COLORES["borde"], 220)
        self.after(120, self._vigilar)

    def _vigilar(self):
        """Mientras brilla, revisa si el mouse sigue dentro. (Si sale pasando por un texto de adentro,
        Tkinter no avisa a la tarjeta, por eso se revisa la posición en lugar de esperar un evento.)"""
        if not self.winfo_exists():
            return
        x, y = self.winfo_pointerxy()
        dentro = (self.winfo_rootx() <= x < self.winfo_rootx() + self.winfo_width()
                  and self.winfo_rooty() <= y < self.winfo_rooty() + self.winfo_height())
        if dentro and self.winfo_ismapped():
            self.after(120, self._vigilar)
            return
        self._iluminada = False
        animaciones.transicion_color(self, "border_color", COLORES["borde"], COLORES["texto2"], 220)


def tono_suave(color):
    """El color mezclado con el fondo de las tarjetas: un fondo tenue para iconos (claro, oscuro)."""
    claro, oscuro = COLORES["fondo2"]
    return animaciones.mezclar(color, claro, 0.85), animaciones.mezclar(color, oscuro, 0.78)


class TarjetaResumen(Tarjeta):
    def __init__(self, master, titulo, icono, color):
        super().__init__(master, brillo=True)
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text=icono, font=ICONO, width=40, height=40, corner_radius=12,
                     fg_color=tono_suave(color), text_color=color).grid(row=0, column=0, padx=(20, 12), pady=(20, 8))
        ctk.CTkLabel(self, text=titulo, font=NORMAL, text_color=COLORES["texto2"],
                     anchor="w").grid(row=0, column=1, sticky="w", pady=(20, 8))

        self.valor = ctk.CTkLabel(self, text="$ 0,00", font=NUMERO, anchor="w", text_color=COLORES["texto"])
        self.valor.grid(row=1, column=0, columnspan=2, sticky="w", padx=20)
        self.detalle = ctk.CTkLabel(self, text="", font=PEQUENO, anchor="w", text_color=COLORES["texto2"])
        self.detalle.grid(row=2, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 18))

    def actualizar(self, numero, formato, detalle="", color_valor=None, tendencia=None):
        """El número sube como contador. tendencia: "buena" (verde), "mala" (rojo) o None (gris)."""
        # Los montos grandes ("$ 1.250.000,00") se achican un poco para que entren en la tarjeta
        largo = len(formato(numero))
        tamano = NUMERO[1] if largo <= 10 else 22 if largo <= 13 else 19
        self.valor.configure(text_color=color_valor or COLORES["texto"], font=(NUMERO[0], tamano, "bold"))
        animaciones.contar(self.valor, numero, formato)
        colores = {"buena": GRAFICAS["ingreso"], "mala": GRAFICAS["gasto"]}
        self.detalle.configure(text=detalle, text_color=colores.get(tendencia, COLORES["texto2"]))
