"""Colores, fuentes y estilos de toda la app.

Los colores van como (modo_claro, modo_oscuro): CustomTkinter elige solo
el que corresponde. Para matplotlib y las tablas (que no son de
CustomTkinter) usamos color("nombre"), que devuelve el del modo actual.
"""
import customtkinter as ctk
from tkinter import ttk

COLORES = {
    "fondo": ("#eef0f7", "#1c1c1f"),
    "fondo2": ("#ffffff", "#26262b"),
    "acento": ("#dde3f0", "#34343b"),
    "acento_hover": ("#cbd4e8", "#44444d"),
    "borde": ("#d9deea", "#3a3a42"),
    "entrada": ("#f6f7fb", "#2e2e34"),
    "destacado": "#e94560",
    "destacado_hover": "#c9364f",
    "texto": ("#1a1a2e", "#ffffff"),
    "texto2": ("#5f6577", "#a0a0a0"),
}

GRAFICAS = {
    "gasto": "#e94560",
    "ingreso": "#4ecca3",
    "ahorro": "#f9d923",
    "neutro": "#3498db",
}

# Paleta para elegir color de cuentas y categorías
PALETA = ["#e94560", "#ff7f50", "#f39c12", "#f9d923", "#4ecca3", "#1abc9c",
          "#27ae60", "#3498db", "#2980b9", "#9b59b6", "#e67e22", "#7f8c8d"]

FUENTE = "Segoe UI"
TITULO = (FUENTE, 24, "bold")
SUBTITULO = (FUENTE, 18, "bold")
NORMAL = (FUENTE, 14)
NORMAL_NEGRITA = (FUENTE, 14, "bold")
PEQUENO = (FUENTE, 12)
NUMERO = (FUENTE, 26, "bold")
ICONO = ("Segoe UI Emoji", 16)


def modo_oscuro():
    return ctk.get_appearance_mode() == "Dark"


def color(nombre):
    valor = COLORES[nombre]
    if isinstance(valor, tuple):
        return valor[1] if modo_oscuro() else valor[0]
    return valor


def estilo_tablas():
    """Aplica los colores del tema a las tablas ttk.Treeview y al calendario."""
    estilo = ttk.Style()
    estilo.theme_use("clam")
    estilo.configure("Treeview", background=color("fondo2"), fieldbackground=color("fondo2"),
                     foreground=color("texto"), rowheight=36, borderwidth=0, font=(FUENTE, 11))
    estilo.configure("Treeview.Heading", background=color("acento"), foreground=color("texto"),
                     relief="flat", font=(FUENTE, 11, "bold"), padding=8)
    estilo.map("Treeview.Heading", background=[("active", color("acento_hover"))])
    estilo.map("Treeview", background=[("selected", COLORES["destacado"])],
               foreground=[("selected", "#ffffff")])
    estilo.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])  # sin borde
    estilo.configure("DateEntry", fieldbackground=color("entrada"), background=color("acento"),
                     foreground=color("texto"), arrowcolor=color("texto"), bordercolor=color("borde"),
                     lightcolor=color("entrada"), darkcolor=color("entrada"), padding=6)


def opciones_calendario():
    """Colores para el desplegable de tkcalendar.DateEntry."""
    return dict(background=color("acento"), foreground=color("texto"),
                headersbackground=color("fondo2"), headersforeground=color("texto2"),
                normalbackground=color("fondo2"), normalforeground=color("texto"),
                weekendbackground=color("fondo2"), weekendforeground=color("texto"),
                othermonthbackground=color("fondo"), othermonthwebackground=color("fondo"),
                othermonthforeground=color("texto2"), othermonthweforeground=color("texto2"),
                selectbackground=COLORES["destacado"], selectforeground="#ffffff",
                bordercolor=color("borde"), font=(FUENTE, 10), date_pattern="dd/mm/yyyy",
                locale="es_AR", firstweekday="monday", showweeknumbers=False)
