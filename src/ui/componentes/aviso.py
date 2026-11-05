"""Aviso flotante que aparece abajo a la derecha y desaparece solo (tipo "toast")."""
import customtkinter as ctk

from ui.componentes import animaciones
from utils.temas import COLORES, NORMAL_NEGRITA


def mostrar_aviso(ventana, texto, tipo="ok", duracion=2500):
    fondo = {"ok": "#2e9c7c", "error": COLORES["destacado"], "info": "#3498db"}[tipo]
    aviso = ctk.CTkLabel(ventana.winfo_toplevel(), text=f"  {texto}  ", font=NORMAL_NEGRITA,
                         fg_color=fondo, text_color="#ffffff", corner_radius=12, height=44)
    lugar = dict(relx=0.98, rely=1.0, anchor="se")

    # Entra subiendo desde abajo y, al terminar, baja y desaparece
    animaciones.animar(aviso, 240, lambda a: aviso.place(y=round(-24 + 60 * (1 - a)), **lugar))
    aviso.after(duracion, lambda: animaciones.animar(
        aviso, 200, lambda a: aviso.place(y=round(-24 + 70 * a), **lugar), al_terminar=aviso.destroy))
