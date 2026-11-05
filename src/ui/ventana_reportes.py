"""Reportes: gráficas por categoría, evolución, comparativa, top 5 y proyección."""
from datetime import date

import customtkinter as ctk

from database import transacciones_dao
from ui.componentes import animaciones, graficas
from ui.componentes.tarjeta_resumen import Tarjeta
from utils import calculos
from utils.temas import COLORES, GRAFICAS, NORMAL, NORMAL_NEGRITA, NUMERO, PEQUENO, SUBTITULO, TITULO


class PanelReportes(ctk.CTkScrollableFrame):
    def __init__(self, master, usuario):
        super().__init__(master, fg_color="transparent", scrollbar_button_color=COLORES["acento"])
        self.usuario = usuario
        self.grid_columnconfigure((0, 1), weight=1, uniform="col")

        cabecera = ctk.CTkFrame(self, fg_color="transparent")
        cabecera.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16))
        ctk.CTkLabel(cabecera, text="Reportes", font=TITULO).pack(side="left")
        hoy = date.today()
        self.meses = calculos.ultimos_meses(12, hoy)[::-1]  # del actual hacia atrás
        self.selector_mes = ctk.CTkOptionMenu(
            cabecera, values=[calculos.nombre_mes(*m) for m in self.meses], command=lambda _: self.refrescar(),
            width=200, height=36, font=NORMAL, fg_color=COLORES["fondo2"], button_color=COLORES["acento"],
            button_hover_color=COLORES["acento_hover"], text_color=COLORES["texto"], dynamic_resizing=False)
        self.selector_mes.pack(side="right")
        ctk.CTkLabel(cabecera, text="Mes:", font=NORMAL, text_color=COLORES["texto2"]).pack(side="right", padx=8)

        self.dona = self._grafica(1, 0, "Gastos por categoría")
        self.top = self._grafica(1, 1, "Top 5 categorías con más gasto")
        self.lineas = self._grafica(2, 0, "Evolución de los últimos 12 meses", columnas=2)
        self.barras = self._grafica(3, 0, "Comparativa de los últimos 6 meses")

        # Proyección de fin de mes
        self.proyeccion = Tarjeta(self, brillo=True)
        self.proyeccion.grid(row=3, column=1, sticky="nsew", pady=8, padx=(8, 0))
        ctk.CTkLabel(self.proyeccion, text="Proyección de fin de mes", font=SUBTITULO,
                     anchor="w").pack(fill="x", padx=20, pady=(16, 8))
        self.contenido_proyeccion = ctk.CTkFrame(self.proyeccion, fg_color="transparent")
        self.contenido_proyeccion.pack(fill="both", expand=True, padx=20, pady=(0, 16))

    def _grafica(self, fila, columna, titulo, columnas=1):
        tarjeta = Tarjeta(self, brillo=True)
        izquierda = columna == 0
        tarjeta.grid(row=fila, column=columna, columnspan=columnas, sticky="nsew", pady=8,
                     padx=0 if columnas == 2 else ((0, 8) if izquierda else (8, 0)))
        ctk.CTkLabel(tarjeta, text=titulo, font=SUBTITULO, anchor="w").pack(fill="x", padx=20, pady=(16, 0))
        grafica = graficas.Grafica(tarjeta, alto=3.0)
        grafica.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        return grafica

    def aplicar_tema(self):
        pass  # todo se redibuja en refrescar()

    def refrescar(self):
        uid = self.usuario["id"]
        anio, mes = self.meses[[calculos.nombre_mes(*m) for m in self.meses].index(self.selector_mes.get())]
        inicio, fin = calculos.rango_mes(anio, mes)

        por_categoria = transacciones_dao.gastos_por_categoria(uid, inicio, fin)
        total_gastos = sum(c["total"] for c in por_categoria)
        graficas.dona(self.dona, [c["nombre"] for c in por_categoria], [c["total"] for c in por_categoria],
                      [c["color"] for c in por_categoria], calculos.formato_moneda(total_gastos))
        top5 = por_categoria[:5]
        graficas.barras_horizontales(self.top, [c["nombre"] for c in top5], [c["total"] for c in top5],
                                     [c["color"] for c in top5])

        # Evolución y comparativa (siempre terminan en el mes elegido)
        doce = calculos.ultimos_meses(12, date(anio, mes, 1))
        por_mes = transacciones_dao.totales_por_mes(uid, calculos.rango_mes(*doce[0])[0], fin)
        vacio = {"ingresos": 0, "gastos": 0}
        ingresos = [por_mes.get(m, vacio)["ingresos"] for m in doce]
        gastos = [por_mes.get(m, vacio)["gastos"] for m in doce]
        ahorro = [max(i - g, 0) for i, g in zip(ingresos, gastos)]
        etiquetas = [calculos.etiqueta_corta(*m) for m in doce]
        graficas.lineas(self.lineas, etiquetas, {"Ingresos": (ingresos, GRAFICAS["ingreso"]),
                                                 "Gastos": (gastos, GRAFICAS["gasto"]),
                                                 "Ahorro": (ahorro, GRAFICAS["ahorro"])})
        graficas.barras_comparativas(self.barras, etiquetas[-6:], ingresos[-6:], gastos[-6:])

        self._proyeccion(anio, mes, total_gastos, ingresos[-1])

    def _proyeccion(self, anio, mes, gastado, ingresos):
        for hijo in self.contenido_proyeccion.winfo_children():
            hijo.destroy()
        hoy = date.today()

        def dato(titulo, valor, color_valor=None):
            ctk.CTkLabel(self.contenido_proyeccion, text=titulo, font=PEQUENO, text_color=COLORES["texto2"],
                         anchor="w").pack(fill="x", pady=(10, 0))
            ctk.CTkLabel(self.contenido_proyeccion, text=valor, font=NORMAL_NEGRITA, anchor="w",
                         text_color=color_valor or COLORES["texto"]).pack(fill="x")

        if (anio, mes) != (hoy.year, hoy.month):
            ctk.CTkLabel(self.contenido_proyeccion, text="Este mes ya terminó.", font=NORMAL,
                         text_color=COLORES["texto2"], anchor="w").pack(fill="x")
            dato("Gasto total", calculos.formato_moneda(gastado), GRAFICAS["gasto"])
            dato("Ingresos", calculos.formato_moneda(ingresos), GRAFICAS["ingreso"])
            dato("Balance final", calculos.formato_moneda(ingresos - gastado))
            return

        p = calculos.proyeccion_fin_mes(gastado, hoy)
        ctk.CTkLabel(self.contenido_proyeccion, text="Si sigues gastando a este ritmo, terminarás el mes con:",
                     font=NORMAL, text_color=COLORES["texto2"], anchor="w", wraplength=380,
                     justify="left").pack(fill="x")
        numero = ctk.CTkLabel(self.contenido_proyeccion, text="$ 0,00", font=NUMERO, text_color=GRAFICAS["gasto"],
                              anchor="w")
        numero.pack(fill="x", pady=(4, 0))
        animaciones.contar(numero, p["proyeccion"], calculos.formato_moneda, duracion=900)
        ctk.CTkLabel(self.contenido_proyeccion, text="en gastos", font=PEQUENO,
                     text_color=COLORES["texto2"], anchor="w").pack(fill="x")
        dato("Gasto promedio por día", calculos.formato_moneda(p["promedio_diario"]))
        dato("Llevas gastado", f"{calculos.formato_moneda(gastado)}  ·  faltan {p['dias_restantes']} días")
        if ingresos:
            sobrante = ingresos - p["proyeccion"]
            dato("Te sobraría" if sobrante >= 0 else "Te faltaría", calculos.formato_moneda(abs(sobrante)),
                 GRAFICAS["ingreso"] if sobrante >= 0 else GRAFICAS["gasto"])
