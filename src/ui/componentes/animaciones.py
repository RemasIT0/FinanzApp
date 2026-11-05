"""Animaciones de la interfaz.

Todas usan la misma idea: cambiar algo un poquito cada 15 ms con after().
- animar(): el motor. Llama a una función con el avance (de 0 a 1) en cada cuadro.
- deslizar_entrada() / ocultar(): pantallas que entran deslizándose.
- transicion_color(): un color cambia suavemente a otro (botones, bordes).
- contar(): un número sube hasta su valor, como un contador.
- llenar(): una barra de progreso se llena poco a poco.
- sacudir(): mueve un widget a los lados, como diciendo «no».
- aparecer_ventana(): una ventana aparece con un fundido.
"""
import math
import time

import customtkinter as ctk

CUADRO = 15  # milisegundos entre cuadros (unos 60 por segundo)


def suavizar(t):
    """Rápido al inicio y suave al final ("ease-out"), se ve más natural que una velocidad fija."""
    return 1 - (1 - t) ** 3


def animar(widget, duracion, al_paso, al_terminar=None, clave="_animacion"):
    """Llama a al_paso(avance) durante `duracion` ms; el avance va de 0 a 1 ya suavizado.
    El avance se calcula con el reloj: si la computadora va lenta se saltan cuadros, pero la
    animación siempre termina a tiempo. Si el mismo widget se vuelve a animar con la misma
    clave, la animación anterior se cancela."""
    detener(widget, clave)
    inicio = time.perf_counter()

    def paso():
        if not widget.winfo_exists():
            return
        t = min((time.perf_counter() - inicio) * 1000 / duracion, 1)
        al_paso(suavizar(t))
        if t < 1:
            setattr(widget, clave, widget.after(CUADRO, paso))
        else:
            setattr(widget, clave, None)
            if al_terminar:
                al_terminar()

    paso()


def detener(widget, clave="_animacion"):
    pendiente = getattr(widget, clave, None)
    if pendiente:
        widget.after_cancel(pendiente)
        setattr(widget, clave, None)


# ---------- Movimiento ----------

def deslizar_entrada(widget, contenedor=None, desde_x=0, desde_y=0, duracion=180):
    """Coloca el widget ocupando todo el contenedor y lo desliza desde (desde_x, desde_y) hasta (0, 0).
    Se usa place() porque mueve el widget sin cambiar su tamaño (las gráficas no se redibujan)."""
    opciones = dict(relwidth=1, relheight=1)
    if contenedor is not None:
        opciones["in_"] = contenedor
    detener(widget)
    # Dibujar la primera vez es lo más lento: se hace antes de moverlo, así se ve todo el deslizamiento
    widget.place(x=desde_x, y=desde_y, **opciones)
    widget.update_idletasks()
    animar(widget, duracion, lambda a: widget.place(x=round(desde_x * (1 - a)), y=round(desde_y * (1 - a)),
                                                    **opciones))


def ocultar(widget):
    """Quita el widget de la vista, cancelando su animación si todavía estaba en curso."""
    detener(widget)
    widget.place_forget()


def sacudir(widget, lugar, distancia=14, duracion=420):
    """Mueve a los lados un widget colocado con place(**lugar) y lo regresa a su sitio."""
    animar(widget, duracion, lambda a: widget.place(x=round(distancia * math.sin(a * math.pi * 6) * (1 - a)),
                                                    **lugar), clave="_anim_sacudir")


def aparecer_ventana(ventana, duracion=220):
    """La ventana pasa de transparente a visible."""
    ventana.attributes("-alpha", 0.0)
    animar(ventana, duracion, lambda a: ventana.attributes("-alpha", a), clave="_anim_alpha")


# ---------- Colores ----------

def resolver(color):
    """'#rrggbb' o (claro, oscuro) → el '#rrggbb' del modo actual."""
    if isinstance(color, (tuple, list)):
        return color[1] if ctk.get_appearance_mode() == "Dark" else color[0]
    return color


def mezclar(color1, color2, t):
    """Color intermedio entre dos: t=0 da color1, t=1 da color2."""
    a, b = resolver(color1), resolver(color2)
    canales = [round(int(a[i:i + 2], 16) * (1 - t) + int(b[i:i + 2], 16) * t) for i in (1, 3, 5)]
    return "#{:02x}{:02x}{:02x}".format(*canales)


def transicion_color(widget, propiedad, hasta, desde, duracion=160):
    """Cambia un color del widget suavemente. Si otra transición estaba a la mitad, sigue desde ahí.
    Al final deja el valor original (aunque sea una pareja claro/oscuro) para que el cambio de tema funcione."""
    actuales = widget.__dict__.setdefault("_colores_actuales", {})
    inicio = actuales.get(propiedad) or resolver(desde)

    def paso(a):
        actuales[propiedad] = mezclar(inicio, hasta, a)
        widget.configure(**{propiedad: actuales[propiedad]})

    def terminar():
        actuales[propiedad] = None
        widget.configure(**{propiedad: hasta})

    animar(widget, duracion, paso, terminar, clave=f"_anim_{propiedad}")


# ---------- Números y barras ----------

def contar(etiqueta, valor, formato, duracion=700):
    """El número sube (o baja) desde el valor que tenía hasta el nuevo."""
    inicio = getattr(etiqueta, "_valor_contado", 0)
    etiqueta._valor_contado = valor
    animar(etiqueta, duracion, lambda a: etiqueta.configure(text=formato(inicio + (valor - inicio) * a)),
           clave="_anim_contar")


def llenar(barra, valor, duracion=600):
    """La barra de progreso se llena desde 0 hasta `valor` (entre 0 y 1)."""
    animar(barra, duracion, lambda a: barra.set(valor * a), clave="_anim_llenar")
