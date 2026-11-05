"""Gráficas de matplotlib dentro de CustomTkinter, con los colores del tema.

Todas aparecen con una animación: las barras crecen, la dona gira hasta
completarse y las líneas suben desde cero. Primero se dibuja la gráfica
completa (para fijar los ejes) y luego se encoge a cero y se hace crecer.
"""
import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

from ui.componentes import animaciones
from utils.calculos import formato_numero
from utils.temas import FUENTE, GRAFICAS, color

# Ejes en formato argentino: "$ 250 mil", "$ 1,5 M"
_FORMATO_DINERO = FuncFormatter(lambda v, _: (f"$ {formato_numero(v / 1e6, 1).replace(',0', '')} M" if abs(v) >= 1e6 else
                                              f"$ {formato_numero(v / 1e3, 0)} mil" if abs(v) >= 1e3 else
                                              f"$ {formato_numero(v, 0)}"))
DURACION = 550  # ms que tarda en crecer cada gráfica


class Grafica(ctk.CTkFrame):
    def __init__(self, master, alto=3.2):
        super().__init__(master, fg_color="transparent")
        self.figura = Figure(figsize=(5, alto), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figura, master=self)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def nuevo_eje(self):
        """Limpia la figura y devuelve un eje ya pintado con los colores del tema."""
        animaciones.detener(self)  # si había una animación de la gráfica anterior, se cancela
        self.figura.clear()
        fondo = color("fondo2")
        self.figura.patch.set_facecolor(fondo)
        self.canvas.get_tk_widget().configure(bg=fondo, highlightthickness=0)
        ax = self.figura.add_subplot()
        ax.set_facecolor(fondo)
        for lado in ("top", "right", "left"):
            ax.spines[lado].set_visible(False)
        ax.spines["bottom"].set_color(color("borde"))
        ax.tick_params(colors=color("texto2"), labelsize=9, length=0)
        ax.grid(axis="y", color=color("borde"), linewidth=0.6)
        ax.set_axisbelow(True)
        return ax

    def mostrar(self, crecer=None):
        """Dibuja la gráfica. crecer(avance) pone cada elemento a su tamaño según el avance (0 a 1)."""
        self.figura.tight_layout(pad=1.2)
        if crecer is None:
            return self.canvas.draw_idle()

        def paso(a):
            crecer(a)
            self.canvas.draw_idle()

        animaciones.animar(self, DURACION, paso)

    def sin_datos(self, mensaje="Aún no hay datos para mostrar"):
        ax = self.nuevo_eje()
        ax.axis("off")
        ax.text(0.5, 0.5, mensaje, ha="center", va="center", color=color("texto2"),
                fontsize=11, family=FUENTE)
        self.mostrar()


def dona(grafica, etiquetas, valores, colores, texto_centro=""):
    if not valores or sum(valores) == 0:
        return grafica.sin_datos("Sin gastos en este periodo")
    ax = grafica.nuevo_eje()
    ax.grid(False)
    ax.spines["bottom"].set_visible(False)
    porciones, _ = ax.pie(valores, colors=colores, startangle=90, counterclock=False,
                          wedgeprops=dict(width=0.32, edgecolor=color("fondo2"), linewidth=2))
    ax.text(0, 0, texto_centro, ha="center", va="center", fontsize=12, fontweight="bold",
            color=color("texto"), family=FUENTE)
    total = sum(valores)
    leyenda = [f"{e}  {v / total:.0%}" for e, v in zip(etiquetas, valores)]
    ax.legend(porciones, leyenda, loc="center left", bbox_to_anchor=(1, 0.5), frameon=False,
              labelcolor=color("texto"), fontsize=9)
    ax.set_aspect("equal")

    # La dona "gira" hasta completarse: cada porción abre su ángulo desde las 12 en punto (90°)
    angulos = [(p.theta1, p.theta2) for p in porciones]

    def crecer(a):
        for porcion, (t1, t2) in zip(porciones, angulos):
            porcion.set_theta1(90 + (t1 - 90) * a)
            porcion.set_theta2(90 + (t2 - 90) * a)

    grafica.mostrar(crecer)


def barras_comparativas(grafica, etiquetas, ingresos, gastos):
    if not any(ingresos) and not any(gastos):
        return grafica.sin_datos()
    ax = grafica.nuevo_eje()
    posiciones = range(len(etiquetas))
    ancho = 0.36
    barras = list(ax.bar([p - ancho / 2 for p in posiciones], ingresos, ancho, label="Ingresos",
                         color=GRAFICAS["ingreso"]))
    barras += ax.bar([p + ancho / 2 for p in posiciones], gastos, ancho, label="Gastos", color=GRAFICAS["gasto"])
    ax.set_xticks(list(posiciones), etiquetas)
    ax.yaxis.set_major_formatter(_FORMATO_DINERO)
    ax.legend(frameon=False, labelcolor=color("texto"), fontsize=9, loc="lower left",
              bbox_to_anchor=(0, 1), ncol=3)
    ax.set_ylim(ax.get_ylim())  # los ejes se quedan fijos mientras las barras crecen
    alturas = [b.get_height() for b in barras]
    grafica.mostrar(lambda a: [b.set_height(h * a) for b, h in zip(barras, alturas)])


def lineas(grafica, etiquetas, series):
    """series: {"Ingresos": ([valores], color), ...}"""
    if not any(any(valores) for valores, _ in series.values()):
        return grafica.sin_datos()
    ax = grafica.nuevo_eje()
    trazos = []
    for nombre, (valores, color_linea) in series.items():
        linea, = ax.plot(etiquetas, valores, marker="o", markersize=5, linewidth=2.2, color=color_linea,
                         label=nombre)
        trazos.append([linea, valores, color_linea, ax.fill_between(etiquetas, valores, alpha=0.08,
                                                                    color=color_linea)])
    ax.yaxis.set_major_formatter(_FORMATO_DINERO)
    ax.legend(frameon=False, labelcolor=color("texto"), fontsize=9, loc="lower left",
              bbox_to_anchor=(0, 1), ncol=3)
    ax.set_ylim(ax.get_ylim())

    def crecer(a):
        # Las líneas suben desde cero; el relleno de abajo se vuelve a crear en cada cuadro
        for trazo in trazos:
            linea, valores, color_linea, relleno = trazo
            altura = [v * a for v in valores]
            linea.set_ydata(altura)
            relleno.remove()
            trazo[3] = ax.fill_between(etiquetas, altura, alpha=0.08, color=color_linea)

    grafica.mostrar(crecer)


def barras_horizontales(grafica, etiquetas, valores, colores):
    if not valores:
        return grafica.sin_datos("Sin gastos en este periodo")
    ax = grafica.nuevo_eje()
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=color("borde"), linewidth=0.6)
    barras = ax.barh(etiquetas[::-1], valores[::-1], color=colores[::-1], height=0.55)
    ax.xaxis.set_major_formatter(_FORMATO_DINERO)
    ax.tick_params(axis="y", labelcolor=color("texto"), labelsize=10)
    ax.set_xlim(ax.get_xlim())
    anchos = [b.get_width() for b in barras]
    grafica.mostrar(lambda a: [b.set_width(w * a) for b, w in zip(barras, anchos)])
