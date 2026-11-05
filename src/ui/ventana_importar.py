"""Importar estados de cuenta en CSV o Excel.

Pasos: 1) elegir archivo, banco y cuenta  2) revisar columnas y vista previa  3) confirmar.
"""
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk

from database import categorias_dao, cuentas_dao, transacciones_dao
from ui.componentes.aviso import mostrar_aviso
from ui.componentes.boton_personalizado import Boton
from ui.componentes.tabla_transaccion import colores_encima, resaltar_al_pasar
from ui.componentes.tarjeta_resumen import Tarjeta
from utils import procesador_csv
from utils.calculos import formato_moneda
from utils.temas import COLORES, NORMAL, NORMAL_NEGRITA, PEQUENO, SUBTITULO, TITULO, color

NINGUNA = "— Ninguna —"
SIGNOS = {"Gastos con signo −": "negativo", "Gastos en positivo": "positivo"}


def _menu(master, valores, comando=None, ancho=220):
    return ctk.CTkOptionMenu(master, values=valores, command=comando, width=ancho, height=36, font=NORMAL,
                             fg_color=COLORES["entrada"], button_color=COLORES["acento"],
                             button_hover_color=COLORES["acento_hover"], text_color=COLORES["texto"],
                             dynamic_resizing=False)


class PanelImportar(ctk.CTkFrame):
    def __init__(self, master, usuario):
        super().__init__(master, fg_color="transparent")
        self.usuario = usuario
        self.df = None
        self.movimientos = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(self, text="Importar estado de cuenta", font=TITULO, anchor="w").grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(self, text="Descarga el CSV o Excel desde la app o página de tu banco y súbelo aquí.",
                     font=NORMAL, text_color=COLORES["texto2"], anchor="w").grid(row=1, column=0, sticky="w", pady=(0, 16))

        # Paso 1: archivo, banco y cuenta
        paso1 = Tarjeta(self)
        paso1.grid(row=2, column=0, sticky="ew")
        ctk.CTkLabel(paso1, text="1. Elige el archivo", font=SUBTITULO).grid(row=0, column=0, columnspan=4,
                                                                            sticky="w", padx=20, pady=(16, 8))
        Boton(paso1, "Seleccionar archivo", icono="📂", command=self._elegir_archivo).grid(row=1, column=0, padx=(20, 12), pady=(0, 18))
        self.nombre_archivo = ctk.CTkLabel(paso1, text="Ningún archivo seleccionado", font=NORMAL,
                                           text_color=COLORES["texto2"], anchor="w", width=240)
        self.nombre_archivo.grid(row=1, column=1, sticky="w", pady=(0, 18))

        ctk.CTkLabel(paso1, text="Banco", font=PEQUENO, text_color=COLORES["texto2"]).grid(row=0, column=2, sticky="sw", padx=12)
        self.banco = _menu(paso1, list(procesador_csv.FORMATOS_BANCO), self._cambiar_banco)
        self.banco.grid(row=1, column=2, padx=12, pady=(0, 18))
        ctk.CTkLabel(paso1, text="Guardar en la cuenta", font=PEQUENO, text_color=COLORES["texto2"]).grid(row=0, column=3, sticky="sw", padx=(12, 20))
        # Al cambiar de cuenta se recalculan los duplicados
        self.cuenta = _menu(paso1, ["(sin cuentas)"], lambda _: self.df is not None and self._previsualizar())
        self.cuenta.grid(row=1, column=3, padx=(12, 20), pady=(0, 18))
        paso1.grid_columnconfigure(1, weight=1)

        # Paso 2: columnas + vista previa (aparece después de elegir archivo)
        self.paso2 = Tarjeta(self)
        self.paso2.grid_columnconfigure(0, weight=1)
        self.paso2.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(self.paso2, text="2. Revisa que todo se vea bien", font=SUBTITULO).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))

        mapeo = ctk.CTkFrame(self.paso2, fg_color="transparent")
        mapeo.grid(row=1, column=0, sticky="ew", padx=20)
        self.menus_columna = {}
        etiquetas = {"fecha": "Fecha", "descripcion": "Descripción", "monto": "Monto",
                     "cargo": "Cargo (gasto)", "abono": "Abono (ingreso)"}
        for i, (campo, texto) in enumerate(etiquetas.items()):
            ctk.CTkLabel(mapeo, text=texto, font=PEQUENO, text_color=COLORES["texto2"]).grid(row=0, column=i, sticky="w", padx=4)
            self.menus_columna[campo] = _menu(mapeo, [NINGUNA], lambda _: self._previsualizar(), ancho=150)
            self.menus_columna[campo].grid(row=1, column=i, padx=4, pady=(0, 8))
        ctk.CTkLabel(mapeo, text="Signo del monto", font=PEQUENO, text_color=COLORES["texto2"]).grid(row=0, column=5, sticky="w", padx=4)
        self.signo = _menu(mapeo, list(SIGNOS), lambda _: self._previsualizar(), ancho=190)
        self.signo.grid(row=1, column=5, padx=4, pady=(0, 8))

        contenedor = ctk.CTkFrame(self.paso2, fg_color="transparent")
        contenedor.grid(row=2, column=0, sticky="nsew", padx=12)
        contenedor.grid_rowconfigure(0, weight=1)
        contenedor.grid_columnconfigure(0, weight=1)
        self.vista = ttk.Treeview(contenedor, columns=("fecha", "descripcion", "categoria", "tipo", "monto"),
                                  show="headings", height=8)
        for clave, titulo, ancho, alin in (("fecha", "Fecha", 100, "w"), ("descripcion", "Descripción", 340, "w"),
                                           ("categoria", "Categoría sugerida", 180, "w"),
                                           ("tipo", "Tipo", 90, "w"), ("monto", "Monto", 120, "e")):
            self.vista.heading(clave, text=titulo, anchor=alin)
            self.vista.column(clave, width=ancho, anchor=alin, stretch=clave == "descripcion")
        self.vista.grid(row=0, column=0, sticky="nsew")
        barra = ctk.CTkScrollbar(contenedor, command=self.vista.yview)
        barra.grid(row=0, column=1, sticky="ns")
        self.vista.configure(yscrollcommand=barra.set)
        resaltar_al_pasar(self.vista)

        pie = ctk.CTkFrame(self.paso2, fg_color="transparent")
        pie.grid(row=3, column=0, sticky="ew", padx=20, pady=16)
        self.resumen = ctk.CTkLabel(pie, text="", font=NORMAL, text_color=COLORES["texto2"], anchor="w")
        self.resumen.pack(side="left")
        self.boton_importar = Boton(pie, "Importar", icono="✓", command=self._importar)
        self.boton_importar.pack(side="right")
        Boton(pie, "Cancelar", estilo="fantasma", command=self._reiniciar).pack(side="right", padx=8)

        # Mensaje mientras no hay archivo
        self.ayuda = ctk.CTkLabel(self, text="⇩\n\nElige un archivo para ver la vista previa aquí.\n"
                                             "Formatos: .csv, .xlsx, .xls",
                                  font=NORMAL, text_color=COLORES["texto2"])
        self.ayuda.grid(row=3, column=0, sticky="nsew", pady=16)

    def aplicar_tema(self):
        self._colores_vista()

    def _colores_vista(self):
        self.vista.tag_configure("duplicado", foreground=color("texto2"))
        self.vista.tag_configure("gasto", foreground=color("texto"))
        self.vista.tag_configure("ingreso", foreground="#2e9c7c")
        colores_encima(self.vista)

    def refrescar(self):
        self.cuentas = cuentas_dao.listar(self.usuario["id"], solo_activas=True)
        self.categorias = categorias_dao.listar(self.usuario["id"])
        nombres = [c["nombre"] for c in self.cuentas] or ["(sin cuentas)"]
        actual = self.cuenta.get()
        self.cuenta.configure(values=nombres)
        self.cuenta.set(actual if actual in nombres else nombres[0])
        self._colores_vista()

    def _reiniciar(self):
        self.df = None
        self.movimientos = []
        self.nombre_archivo.configure(text="Ningún archivo seleccionado")
        self.paso2.grid_forget()
        self.ayuda.grid(row=3, column=0, sticky="nsew", pady=16)

    def _elegir_archivo(self):
        ruta = filedialog.askopenfilename(title="Selecciona tu estado de cuenta",
                                          filetypes=[("CSV o Excel", "*.csv *.xlsx *.xls"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            self.df = procesador_csv.leer_archivo(ruta)
        except Exception as e:  # archivo dañado, protegido, formato raro...
            return messagebox.showerror("No se pudo leer", f"No pudimos leer el archivo:\n{e}")
        if self.df.empty:
            return messagebox.showwarning("Archivo vacío", "El archivo no tiene filas con datos.")

        self.nombre_archivo.configure(text=f"{Path(ruta).name}  ·  {len(self.df)} filas", text_color=COLORES["texto"])
        opciones = [NINGUNA] + list(self.df.columns)
        for menu in self.menus_columna.values():
            menu.configure(values=opciones)
        self.ayuda.grid_forget()
        self.paso2.grid(row=3, column=0, sticky="nsew", pady=(16, 0))
        self._cambiar_banco()

    def _cambiar_banco(self, _=None):
        """Mapeo automático de columnas según el banco elegido."""
        if self.df is None:
            return
        banco = self.banco.get()
        mapeo = procesador_csv.detectar_columnas(self.df, banco)
        for campo, columna in mapeo.items():
            self.menus_columna[campo].set(columna or NINGUNA)
        if banco == "Detectar automáticamente":
            signo = procesador_csv.detectar_signo(self.df, mapeo)
        else:
            signo = procesador_csv.FORMATOS_BANCO[banco]["signo"]
        self.signo.set(next(k for k, v in SIGNOS.items() if v == signo))
        self._previsualizar()

    def _previsualizar(self):
        mapeo = {campo: (None if m.get() == NINGUNA else m.get()) for campo, m in self.menus_columna.items()}
        self.movimientos, ignoradas = procesador_csv.procesar(self.df, mapeo, SIGNOS[self.signo.get()])

        cuenta = self._cuenta_elegida()
        existentes = transacciones_dao.firmas_existentes(cuenta["id"]) if cuenta else set()
        self.vista.delete(*self.vista.get_children())
        duplicados = 0
        for i, mov in enumerate(self.movimientos):
            categoria = procesador_csv.sugerir_categoria(mov["descripcion"], mov["tipo"], self.categorias)
            mov["categoria_id"] = categoria["id"] if categoria else None
            mov["duplicado"] = (mov["fecha"], mov["monto"], mov["descripcion"]) in existentes
            duplicados += mov["duplicado"]
            etiqueta_categoria = f"{categoria['icono']}  {categoria['nombre']}" if categoria else "Sin categoría"
            self.vista.insert("", "end", iid=str(i), tags=("duplicado" if mov["duplicado"] else mov["tipo"],), values=(
                mov["fecha"].strftime("%d/%m/%Y"), mov["descripcion"],
                "Ya importado" if mov["duplicado"] else etiqueta_categoria, mov["tipo"].capitalize(),
                formato_moneda(mov["monto"] * (-1 if mov["tipo"] == "gasto" else 1))))

        nuevos = len(self.movimientos) - duplicados
        partes = [f"{nuevos} movimientos listos"]
        if duplicados:
            partes.append(f"{duplicados} ya estaban importados (se omiten)")
        if ignoradas:
            partes.append(f"{ignoradas} filas sin fecha o monto (se omiten)")
        if not self.movimientos:
            partes = ["No encontramos movimientos: revisa qué columna es la fecha y cuál el monto"]
        self.resumen.configure(text="  ·  ".join(partes))
        self.boton_importar.configure(text=f"✓  Importar {nuevos}", state="normal" if nuevos else "disabled")

    def _cuenta_elegida(self):
        return next((c for c in self.cuentas if c["nombre"] == self.cuenta.get()), None)

    def _importar(self):
        cuenta = self._cuenta_elegida()
        if cuenta is None:
            return messagebox.showwarning("Sin cuenta", "Primero crea una cuenta en Configuración.")
        nuevos = [m for m in self.movimientos if not m["duplicado"]]
        gastos = sum(m["monto"] for m in nuevos if m["tipo"] == "gasto")
        ingresos = sum(m["monto"] for m in nuevos if m["tipo"] == "ingreso")
        if not messagebox.askyesno("Confirmar importación",
                                   f"Se van a guardar {len(nuevos)} movimientos en “{cuenta['nombre']}”.\n\n"
                                   f"Gastos: {formato_moneda(gastos)}\nIngresos: {formato_moneda(ingresos)}\n\n¿Continuar?"):
            return
        transacciones_dao.crear_varias([(cuenta["id"], m["categoria_id"], m["descripcion"], m["monto"],
                                         m["fecha"], m["tipo"], "csv") for m in nuevos])
        self._reiniciar()
        mostrar_aviso(self, f"✓ {len(nuevos)} movimientos importados")
