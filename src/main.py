"""FinanzApp - Gestor financiero personal.

Ejecutar desde la carpeta del proyecto con:  python src/main.py
"""
import customtkinter as ctk
import mysql.connector

from database.conexion import inicializar_bd
from ui.componentes.animaciones import deslizar_entrada
from ui.ventana_login import PanelConexion, PanelLogin
from ui.ventana_principal import VentanaPrincipal
from utils.config import cargar_config
from utils.temas import COLORES, estilo_tablas


class App(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=COLORES["fondo"])
        self.title("FinanzApp")
        self.minsize(1100, 700)
        # Que quepa en pantallas pequeñas sin quedar debajo de la barra de tareas
        ancho, alto = min(1320, self.winfo_screenwidth() - 40), min(820, self.winfo_screenheight() - 100)
        x = (self.winfo_screenwidth() - ancho) // 2
        y = (self.winfo_screenheight() - alto) // 3
        self.geometry(f"{ancho}x{alto}+{max(x, 0)}+{max(y, 0)}")
        estilo_tablas()

        self.pantalla = None
        self.iniciar()
        self._aparecer()

    def _aparecer(self, opacidad=0.0):
        """Animación de entrada: la ventana aparece con un fundido suave."""
        self.attributes("-alpha", opacidad)
        if opacidad < 1:
            self.after(12, self._aparecer, round(opacidad + 0.08, 2))

    def _cambiar_pantalla(self, nueva):
        if self.pantalla is not None:
            self.pantalla.destroy()
        self.pantalla = nueva
        deslizar_entrada(nueva, desde_y=40)  # La pantalla nueva sube suavemente

    def iniciar(self):
        try:
            inicializar_bd()
        except mysql.connector.Error as e:
            return self._cambiar_pantalla(PanelConexion(self, f"No se pudo conectar: {e.msg}", self.iniciar))
        self.mostrar_login()

    def mostrar_login(self):
        self._cambiar_pantalla(PanelLogin(self, al_entrar=self.entrar))

    def entrar(self, usuario):
        self._cambiar_pantalla(VentanaPrincipal(self, usuario, al_salir=self.mostrar_login))


if __name__ == "__main__":
    ctk.set_appearance_mode("dark" if cargar_config()["tema"] == "dark" else "light")
    App().mainloop()
