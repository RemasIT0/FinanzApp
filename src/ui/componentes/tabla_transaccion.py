"""Tabla de movimientos (ttk.Treeview con los colores del tema)."""
import customtkinter as ctk
from tkinter import ttk

from utils.calculos import texto_categoria, texto_cuenta, texto_monto
from utils.temas import COLORES, color


def resaltar_al_pasar(tabla):
    """La fila bajo el mouse se ilumina. Se le pone la etiqueta "encima" y se le devuelven
    sus etiquetas originales (colores alternados, ingreso/gasto...) cuando el mouse se va."""
    estado = {"fila": None, "etiquetas": ()}

    def apagar():
        if estado["fila"] and tabla.exists(estado["fila"]):
            tabla.item(estado["fila"], tags=estado["etiquetas"])
        estado["fila"] = None

    def mover(evento):
        fila = tabla.identify_row(evento.y)
        if fila == estado["fila"]:
            return
        apagar()
        if fila and fila not in tabla.selection():  # la seleccionada conserva su color
            estado["fila"], estado["etiquetas"] = fila, tabla.item(fila, "tags")
            tabla.item(fila, tags=("encima",))

    tabla.bind("<Motion>", mover, add="+")
    tabla.bind("<Leave>", lambda _: apagar(), add="+")
    tabla.bind("<<TreeviewSelect>>", lambda _: apagar(), add="+")
    colores_encima(tabla)


def colores_encima(tabla):
    """Color de la fila resaltada (se vuelve a llamar al cambiar de tema)."""
    tabla.tag_configure("encima", background=color("acento"), foreground=color("texto"))


class TablaTransacciones(ctk.CTkFrame):
    COLUMNAS = {
        "fecha": ("Fecha", 100, "w"),
        "descripcion": ("Descripción", 300, "w"),
        "categoria": ("Categoría", 170, "w"),
        "cuenta": ("Cuenta", 150, "w"),
        "monto": ("Monto", 130, "e"),
    }

    def __init__(self, master, al_doble_clic=None, **opciones):
        super().__init__(master, fg_color=COLORES["fondo2"], corner_radius=16, border_width=1,
                         border_color=COLORES["borde"], **opciones)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.tabla = ttk.Treeview(self, columns=list(self.COLUMNAS), show="headings", selectmode="browse")
        for clave, (titulo, ancho, alineacion) in self.COLUMNAS.items():
            self.tabla.heading(clave, text=titulo, anchor=alineacion)
            self.tabla.column(clave, width=ancho, anchor=alineacion, stretch=clave == "descripcion")
        self.tabla.grid(row=0, column=0, sticky="nsew", padx=(12, 0), pady=12)

        barra = ctk.CTkScrollbar(self, command=self.tabla.yview)
        barra.grid(row=0, column=1, sticky="ns", padx=4, pady=12)
        self.tabla.configure(yscrollcommand=barra.set)

        if al_doble_clic:
            self.tabla.bind("<Double-1>", lambda _: self.seleccionada() and al_doble_clic(self.seleccionada()))
        resaltar_al_pasar(self.tabla)
        self.aplicar_colores()

    def aplicar_colores(self):
        """Filas alternadas; se vuelve a llamar al cambiar de modo claro/oscuro."""
        self.tabla.tag_configure("par", background=color("fondo2"))
        self.tabla.tag_configure("impar", background=color("fondo"))
        colores_encima(self.tabla)

    def cargar(self, transacciones):
        self._datos = {str(t["id"]): t for t in transacciones}
        self.tabla.delete(*self.tabla.get_children())
        for i, t in enumerate(transacciones):
            self.tabla.insert("", "end", iid=str(t["id"]), tags=("par" if i % 2 == 0 else "impar",), values=(
                t["fecha"].strftime("%d/%m/%Y"), t["descripcion"], texto_categoria(t), texto_cuenta(t),
                texto_monto(t)))

    def seleccionada(self):
        """Devuelve el movimiento seleccionado (dict) o None."""
        seleccion = self.tabla.selection()
        return self._datos.get(seleccion[0]) if seleccion else None
