"""Historial de movimientos con filtros, edición, borrado y exportación."""
from datetime import date
from tkinter import filedialog, messagebox

import customtkinter as ctk
from tkcalendar import DateEntry

from database import categorias_dao, cuentas_dao, transacciones_dao
from ui.componentes.aviso import mostrar_aviso
from ui.componentes.boton_personalizado import Boton
from ui.componentes.tabla_transaccion import TablaTransacciones
from ui.componentes.tarjeta_resumen import Tarjeta
from ui.ventana_registro import VentanaRegistro
from utils import calculos, exportar
from utils.config import CARPETA_EXPORTS
from utils.temas import COLORES, NORMAL, PEQUENO, TITULO, opciones_calendario

TODAS = "Todas"
PERIODOS = ["Este mes", "Mes pasado", "Últimos 3 meses", "Este año", "Todo"]
TIPOS = {"Todos": None, "Gastos": "gasto", "Ingresos": "ingreso"}


def _menu(master, valores, comando, ancho=140):
    return ctk.CTkOptionMenu(master, values=valores, command=comando, width=ancho, height=36, font=NORMAL,
                             fg_color=COLORES["entrada"], button_color=COLORES["acento"],
                             button_hover_color=COLORES["acento_hover"], text_color=COLORES["texto"],
                             dynamic_resizing=False)


class PanelTransacciones(ctk.CTkFrame):
    def __init__(self, master, usuario):
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario
        self._espera = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        ctk.CTkLabel(cabecera, text="Historial", font=TITULO).pack(side="left")
        Boton(cabecera, "PDF", icono="⇩", estilo="secundario", width=90,
              command=lambda: self._exportar("pdf")).pack(side="right")
        Boton(cabecera, "CSV", icono="⇩", estilo="secundario", width=90,
              command=lambda: self._exportar("csv")).pack(side="right", padx=8)

        # Filtros
        filtros = Tarjeta(self)
        filtros.grid(row=1, column=0, sticky="ew")
        self.busqueda = ctk.CTkEntry(filtros, height=36, corner_radius=10, font=NORMAL, width=180,
                                     placeholder_text="🔍  Buscar descripción…",
                                     fg_color=COLORES["entrada"], border_color=COLORES["borde"])
        self.busqueda.grid(row=1, column=0, padx=(16, 6), pady=(0, 14))
        self.busqueda.bind("<KeyRelease>", self._buscar_con_pausa)

        self.periodo = _menu(filtros, PERIODOS, self._cambiar_periodo, ancho=150)
        self.desde = DateEntry(filtros, width=11, **opciones_calendario())
        self.hasta = DateEntry(filtros, width=11, **opciones_calendario())
        self.categoria = _menu(filtros, [TODAS], lambda _: self.refrescar())
        self.cuenta = _menu(filtros, [TODAS], lambda _: self.refrescar())
        self.tipo = _menu(filtros, list(TIPOS), lambda _: self.refrescar(), ancho=110)
        for columna, (titulo, widget) in enumerate([("Periodo", self.periodo), ("Desde", self.desde),
                                                    ("Hasta", self.hasta), ("Categoría", self.categoria),
                                                    ("Cuenta", self.cuenta), ("Tipo", self.tipo)], start=1):
            ctk.CTkLabel(filtros, text=titulo, font=PEQUENO, text_color=COLORES["texto2"]).grid(
                row=0, column=columna, sticky="w", padx=4, pady=(12, 2))
            widget.grid(row=1, column=columna, padx=4, pady=(0, 14), ipady=3 if isinstance(widget, DateEntry) else 0)
        ctk.CTkLabel(filtros, text="Buscar", font=PEQUENO, text_color=COLORES["texto2"]).grid(
            row=0, column=0, sticky="w", padx=(16, 6), pady=(12, 2))
        Boton(filtros, "Limpiar", estilo="fantasma", width=80, command=self._limpiar).grid(
            row=1, column=7, padx=(6, 16), pady=(0, 14))
        for fecha in (self.desde, self.hasta):
            fecha.bind("<<DateEntrySelected>>", lambda _: self.refrescar())

        # Resumen + acciones
        barra = ctk.CTkFrame(self, fg_color="transparent")
        barra.grid(row=2, column=0, sticky="ew", pady=(16, 8))
        self.resumen = ctk.CTkLabel(barra, text="", font=NORMAL, text_color=COLORES["texto2"])
        self.resumen.pack(side="left")
        Boton(barra, "Eliminar", icono="🗑", estilo="peligro", width=110, height=34,
              command=self._eliminar).pack(side="right")
        Boton(barra, "Editar", icono="✎", estilo="secundario", width=100, height=34,
              command=self._editar).pack(side="right", padx=8)

        self.tabla = TablaTransacciones(self, al_doble_clic=self._editar)
        self.tabla.grid(row=3, column=0, sticky="nsew")

        self.periodo.set("Este mes")
        self._cambiar_periodo("Este mes", refrescar=False)

    def aplicar_tema(self):
        self.tabla.aplicar_colores()
        for fecha in (self.desde, self.hasta):
            fecha.configure(**{k: v for k, v in opciones_calendario().items()
                               if k not in ("locale", "date_pattern", "firstweekday", "showweeknumbers")})

    def _cambiar_periodo(self, periodo, refrescar=True):
        hoy = date.today()
        if periodo == "Este mes":
            desde, hasta = calculos.rango_mes(hoy.year, hoy.month)
        elif periodo == "Mes pasado":
            desde, hasta = calculos.rango_mes(*calculos.mover_mes(hoy.year, hoy.month, -1))
        elif periodo == "Últimos 3 meses":
            desde = calculos.rango_mes(*calculos.mover_mes(hoy.year, hoy.month, -2))[0]
            hasta = calculos.rango_mes(hoy.year, hoy.month)[1]
        elif periodo == "Este año":
            desde, hasta = date(hoy.year, 1, 1), date(hoy.year, 12, 31)
        else:  # Todo
            desde, hasta = date(2000, 1, 1), date(hoy.year + 1, 12, 31)
        self.desde.set_date(desde)
        self.hasta.set_date(hasta)
        if refrescar:
            self.refrescar()

    def _buscar_con_pausa(self, _):
        """Espera a que el usuario deje de escribir para no consultar en cada tecla."""
        if self._espera:
            self.after_cancel(self._espera)
        self._espera = self.after(300, self.refrescar)

    def _limpiar(self):
        self.busqueda.delete(0, "end")
        for menu in (self.categoria, self.cuenta):
            menu.set(TODAS)
        self.tipo.set("Todos")
        self.periodo.set("Este mes")
        self._cambiar_periodo("Este mes")

    def _actualizar_opciones(self):
        uid = self.usuario["id"]
        self.categorias = {f"{c['icono']} {c['nombre']}": c["id"] for c in categorias_dao.listar(uid)}
        self.cuentas = {c["nombre"]: c["id"] for c in cuentas_dao.listar(uid)}
        for menu, opciones in ((self.categoria, self.categorias), (self.cuenta, self.cuentas)):
            valores = [TODAS] + list(opciones)
            menu.configure(values=valores)
            if menu.get() not in valores:
                menu.set(TODAS)

    def _filtrados(self):
        return transacciones_dao.buscar(
            self.usuario["id"], desde=self.desde.get_date(), hasta=self.hasta.get_date(),
            categoria_id=self.categorias.get(self.categoria.get()), cuenta_id=self.cuentas.get(self.cuenta.get()),
            tipo=TIPOS[self.tipo.get()], texto=self.busqueda.get().strip())

    def refrescar(self):
        self._actualizar_opciones()
        self.transacciones = self._filtrados()
        self.tabla.cargar(self.transacciones)
        ingresos = sum(float(t["monto"]) for t in self.transacciones if t["tipo"] == "ingreso")
        gastos = sum(float(t["monto"]) for t in self.transacciones if t["tipo"] == "gasto")
        self.resumen.configure(text=f"{len(self.transacciones)} movimientos   ·   "
                                    f"Ingresos {calculos.formato_moneda(ingresos)}   ·   "
                                    f"Gastos {calculos.formato_moneda(gastos)}")

    def _editar(self, transaccion=None):
        transaccion = transaccion or self.tabla.seleccionada()
        if not transaccion:
            return mostrar_aviso(self, "Selecciona un movimiento de la tabla", tipo="info")
        VentanaRegistro(self, self.usuario, transaccion=transaccion,
                        al_guardar=lambda: (self.refrescar(), mostrar_aviso(self, "✓ Cambios guardados")))

    def _eliminar(self):
        transaccion = self.tabla.seleccionada()
        if not transaccion:
            return mostrar_aviso(self, "Selecciona un movimiento de la tabla", tipo="info")
        if messagebox.askyesno("Eliminar movimiento",
                               f"¿Eliminar “{transaccion['descripcion']}” por "
                               f"{calculos.formato_moneda(float(transaccion['monto']))}?\nEsto no se puede deshacer."):
            transacciones_dao.eliminar(transaccion["id"], self.usuario["id"])
            self.refrescar()
            mostrar_aviso(self, "Movimiento eliminado")

    def _exportar(self, formato):
        if not self.transacciones:
            return mostrar_aviso(self, "No hay movimientos para exportar", tipo="info")
        CARPETA_EXPORTS.mkdir(exist_ok=True)
        ruta = filedialog.asksaveasfilename(
            initialdir=CARPETA_EXPORTS, defaultextension=f".{formato}",
            initialfile=f"movimientos_{date.today():%Y-%m-%d}.{formato}",
            filetypes=[(formato.upper(), f"*.{formato}")])
        if not ruta:
            return
        periodo = f"{self.desde.get_date():%d/%m/%Y} al {self.hasta.get_date():%d/%m/%Y}"
        if formato == "csv":
            exportar.a_csv(self.transacciones, ruta)
        else:
            exportar.a_pdf(self.transacciones, ruta, titulo=f"Movimientos del {periodo}")
        mostrar_aviso(self, f"✓ Exportado a {formato.upper()}")
