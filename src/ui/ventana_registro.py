"""Ventana para registrar (o editar) un gasto, un ingreso o una transferencia entre tus cuentas."""
from datetime import date

import customtkinter as ctk
from tkcalendar import DateEntry

from database import categorias_dao, cuentas_dao, transacciones_dao
from ui.componentes.boton_personalizado import Boton
from ui.ventana_config import centrar_ventana
from utils.calculos import monto_para_editar
from utils.temas import COLORES, GRAFICAS, NORMAL, PEQUENO, SUBTITULO, opciones_calendario
from utils.validadores import convertir_monto


class VentanaRegistro(ctk.CTkToplevel):
    def __init__(self, master, usuario, al_guardar, transaccion=None):
        super().__init__(master, fg_color=COLORES["fondo"])
        self.usuario = usuario
        self.al_guardar = al_guardar
        self.transaccion = transaccion  # si viene, estamos editando
        self.title("Editar movimiento" if transaccion else "Nuevo movimiento")
        centrar_ventana(self, master, 520, 690)

        self.cuentas = cuentas_dao.listar(usuario["id"], solo_activas=True)
        self.categorias = categorias_dao.listar(usuario["id"])
        self.categoria_id = None
        self._construir()
        if transaccion:
            self._rellenar()
        else:
            predeterminada = cuentas_dao.predeterminada(self.cuentas)
            if predeterminada:
                self.cuenta.set(predeterminada["nombre"])
            self._cambiar_tipo()

        # En Windows hay que esperar un instante para poder poner la ventana al frente
        self.after(150, self._al_frente)

    def _al_frente(self):
        self.lift()
        self.focus_force()
        self.grab_set()
        self.monto.focus()

    def _etiqueta(self, texto):
        ctk.CTkLabel(self, text=texto, font=PEQUENO, text_color=COLORES["texto2"],
                     anchor="w").pack(fill="x", padx=28, pady=(14, 4))

    def _construir(self):
        ctk.CTkLabel(self, text=self.title(), font=SUBTITULO, anchor="w").pack(fill="x", padx=28, pady=(24, 8))

        self.tipo = ctk.CTkSegmentedButton(self, values=["Gasto", "Ingreso", "Transferencia"], command=self._cambiar_tipo,
                                           height=38, font=NORMAL, fg_color=COLORES["fondo2"],
                                           unselected_color=COLORES["fondo2"],
                                           selected_color=GRAFICAS["gasto"], selected_hover_color=GRAFICAS["gasto"])
        self.tipo.set("Gasto")
        self.tipo.pack(fill="x", padx=28)

        self._etiqueta("Monto")
        self.monto = ctk.CTkEntry(self, height=56, corner_radius=12, font=("Segoe UI", 26, "bold"),
                                  placeholder_text="$ 0,00", fg_color=COLORES["fondo2"], border_color=COLORES["borde"])
        self.monto.pack(fill="x", padx=28)

        # Gasto / Ingreso: botones de categoría.  Transferencia: elegir la cuenta a la que va el dinero.
        # Se muestra uno u otro (ver _cambiar_tipo).
        self.zona_variable = ctk.CTkFrame(self, fg_color="transparent")
        self.zona_variable.pack(fill="x")
        self.bloque_categorias = ctk.CTkFrame(self.zona_variable, fg_color="transparent")
        ctk.CTkLabel(self.bloque_categorias, text="Categoría", font=PEQUENO, text_color=COLORES["texto2"],
                     anchor="w").pack(fill="x", padx=28, pady=(14, 4))
        self.marco_categorias = ctk.CTkFrame(self.bloque_categorias, fg_color="transparent")
        self.marco_categorias.pack(fill="x", padx=24)
        self.bloque_destino = ctk.CTkFrame(self, fg_color="transparent")  # va debajo de "Desde la cuenta"
        ctk.CTkLabel(self.bloque_destino, text="Hacia la cuenta", font=PEQUENO, text_color=COLORES["texto2"],
                     anchor="w").pack(fill="x", padx=28, pady=(14, 4))
        self.destino = self._menu_cuentas(self.bloque_destino)
        self.destino.pack(fill="x", padx=28)
        ctk.CTkLabel(self.bloque_destino, text="Una transferencia mueve dinero entre tus cuentas: no cuenta como "
                                               "gasto ni como ingreso.", font=PEQUENO, text_color=COLORES["texto2"],
                     anchor="w", justify="left", wraplength=440).pack(fill="x", padx=28, pady=(6, 0))

        fila = self.fila_cuenta = ctk.CTkFrame(self, fg_color="transparent")
        fila.pack(fill="x", padx=28, pady=(14, 0))
        fila.grid_columnconfigure((0, 1), weight=1, uniform="col")
        self.etiqueta_cuenta = ctk.CTkLabel(fila, text="Cuenta", font=PEQUENO, text_color=COLORES["texto2"])
        self.etiqueta_cuenta.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(fila, text="Fecha", font=PEQUENO, text_color=COLORES["texto2"]).grid(row=0, column=1, sticky="w", padx=(12, 0))
        self.cuenta = self._menu_cuentas(fila)
        self.cuenta.grid(row=1, column=0, sticky="ew")
        self.fecha = DateEntry(fila, **opciones_calendario())
        self.fecha.set_date(date.today())
        self.fecha.grid(row=1, column=1, sticky="ew", padx=(12, 0), ipady=4)

        self._etiqueta("Descripción (opcional)")
        self.descripcion = ctk.CTkEntry(self, height=40, corner_radius=10, font=NORMAL,
                                        placeholder_text="Ej. Comida con amigos",
                                        fg_color=COLORES["fondo2"], border_color=COLORES["borde"])
        self.descripcion.pack(fill="x", padx=28)

        self.error = ctk.CTkLabel(self, text="", font=PEQUENO, text_color=COLORES["destacado"])
        self.error.pack(pady=(8, 0))

        botones = ctk.CTkFrame(self, fg_color="transparent")
        botones.pack(fill="x", padx=28, pady=(0, 24), side="bottom")
        Boton(botones, "Guardar", height=44, command=self._guardar).pack(side="right")
        Boton(botones, "Cancelar", estilo="fantasma", height=44, command=self.destroy).pack(side="right", padx=8)

        self.bind("<Return>", lambda _: self._guardar())
        self.bind("<Escape>", lambda _: self.destroy())

    def _menu_cuentas(self, master):
        return ctk.CTkOptionMenu(master, values=[c["nombre"] for c in self.cuentas] or ["(sin cuentas)"],
                                 height=38, font=NORMAL, fg_color=COLORES["fondo2"],
                                 button_color=COLORES["acento"], button_hover_color=COLORES["acento_hover"],
                                 text_color=COLORES["texto"], dynamic_resizing=False)

    def _cambiar_tipo(self, _=None):
        """Muestra las categorías (gasto/ingreso) o la cuenta de destino (transferencia)."""
        tipo = self.tipo.get()
        color_tipo = {"Gasto": GRAFICAS["gasto"], "Ingreso": GRAFICAS["ingreso"]}.get(tipo, GRAFICAS["neutro"])
        self.tipo.configure(selected_color=color_tipo, selected_hover_color=color_tipo)
        if tipo == "Transferencia":
            # Se oculta el marco entero: un marco vacío en Tkinter conserva su alto y dejaría un hueco
            self.zona_variable.pack_forget()
            self.bloque_destino.pack(fill="x", after=self.fila_cuenta)
            self.etiqueta_cuenta.configure(text="Desde la cuenta")
            # Proponer como destino una cuenta distinta a la de origen
            if self.destino.get() == self.cuenta.get():
                otra = next((c["nombre"] for c in self.cuentas if c["nombre"] != self.cuenta.get()), None)
                if otra:
                    self.destino.set(otra)
        else:
            self.bloque_destino.pack_forget()
            self.zona_variable.pack(fill="x", before=self.fila_cuenta)
            self.bloque_categorias.pack(fill="x")
            self.etiqueta_cuenta.configure(text="Cuenta")
            self._mostrar_categorias()

    def _mostrar_categorias(self):
        """Dibuja los botones de categoría según sea gasto o ingreso."""
        es_ingreso = self.tipo.get() == "Ingreso"

        for hijo in self.marco_categorias.winfo_children():
            hijo.destroy()
        self.botones_categoria = {}
        visibles = [c for c in self.categorias if bool(c["es_ingreso"]) == es_ingreso]
        if self.categoria_id not in [c["id"] for c in visibles]:
            self.categoria_id = visibles[0]["id"] if visibles else None
        for i, cat in enumerate(visibles):
            boton = ctk.CTkButton(self.marco_categorias, text=f"{cat['icono']}  {cat['nombre']}", height=34,
                                  corner_radius=17, font=PEQUENO, border_width=2, border_color=COLORES["fondo2"],
                                  fg_color=COLORES["fondo2"], hover_color=COLORES["acento"],
                                  text_color=COLORES["texto"], width=110,
                                  command=lambda c=cat["id"]: self._elegir_categoria(c))
            boton.grid(row=i // 3, column=i % 3, padx=4, pady=4, sticky="ew")
            self.botones_categoria[cat["id"]] = (boton, cat["color"])
        self.marco_categorias.grid_columnconfigure((0, 1, 2), weight=1, uniform="cat")
        self._elegir_categoria(self.categoria_id)

    def _elegir_categoria(self, categoria_id):
        self.categoria_id = categoria_id
        for cid, (boton, color_cat) in self.botones_categoria.items():
            boton.configure(border_color=color_cat if cid == categoria_id else COLORES["fondo2"])

    def _rellenar(self):
        t = self.transaccion
        self.tipo.set({"ingreso": "Ingreso", "transferencia": "Transferencia"}.get(t["tipo"], "Gasto"))
        self.categoria_id = t["categoria_id"]
        self.cuenta.set(t["cuenta"])
        if t.get("cuenta_destino"):
            self.destino.set(t["cuenta_destino"])
        self._cambiar_tipo()
        self.monto.insert(0, monto_para_editar(t["monto"]))
        self.fecha.set_date(t["fecha"])
        self.descripcion.insert(0, t["descripcion"])

    def _guardar(self):
        monto = convertir_monto(self.monto.get())
        if monto is None:
            return self.error.configure(text="Escribe un monto válido mayor a cero.")
        cuenta = next((c for c in self.cuentas if c["nombre"] == self.cuenta.get()), None)
        if cuenta is None:
            return self.error.configure(text="Primero crea una cuenta en Configuración.")

        tipo = {"Ingreso": "ingreso", "Transferencia": "transferencia"}.get(self.tipo.get(), "gasto")
        descripcion = self.descripcion.get().strip()[:200]
        categoria_id, destino_id = self.categoria_id, None
        if tipo == "transferencia":
            destino = next((c for c in self.cuentas if c["nombre"] == self.destino.get()), None)
            if len(self.cuentas) < 2:
                return self.error.configure(text="Para transferir necesitas al menos dos cuentas.")
            if destino is None or destino["id"] == cuenta["id"]:
                return self.error.configure(text="Elige una cuenta de destino distinta a la de origen.")
            categoria_id, destino_id = None, destino["id"]
            descripcion = descripcion or f"Transferencia a {destino['nombre']}"
        if not descripcion:
            nombre_cat = next((c["nombre"] for c in self.categorias if c["id"] == categoria_id), "")
            descripcion = nombre_cat or tipo.capitalize()

        if self.transaccion:
            transacciones_dao.actualizar(self.transaccion["id"], self.usuario["id"], cuenta["id"], categoria_id,
                                         descripcion, monto, self.fecha.get_date(), tipo, cuenta_destino_id=destino_id)
        else:
            transacciones_dao.crear(cuenta["id"], categoria_id, descripcion, monto, self.fecha.get_date(), tipo,
                                    cuenta_destino_id=destino_id)
        self.destroy()
        self.al_guardar()
