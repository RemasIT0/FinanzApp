"""El muñequito del asistente: una bola peluda con cara de sorpresa.

Se dibuja con código (Pillow), así no hace falta ningún archivo de imagen y la app de
escritorio y la web usan exactamente el mismo muñeco.

Se dibuja grande (4 veces el tamaño final) y después se achica: así los bordes y los pelos
quedan suaves. El pelo usa siempre la misma "semilla" al azar, para que salga igual cada vez.
"""
import io
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

# Colores del muñeco
MARRONES = ["#3b2414", "#4a2e1a", "#56361f", "#5f3c22", "#6b4428", "#7a5032"]
REFLEJO = "#8f6440"
CREMA = "#f4ecdc"
CREMA_SOMBRA = "#e2d6bf"
ROJO = "#d7262f"
ROJO_OSCURO = "#a81b22"
NEGRO = "#151515"

LIENZO = (400, 440)            # tamaño de trabajo (se achica al final)
CENTRO = (200, 236)            # centro del cuerpo
RADIO_X, RADIO_Y = 148, 146    # tamaño del cuerpo


def _punto_borde(angulo, escala=1.0):
    """Un punto en el borde del cuerpo (una elipse) en ese ángulo."""
    return (CENTRO[0] + math.cos(angulo) * RADIO_X * escala,
            CENTRO[1] + math.sin(angulo) * RADIO_Y * escala)


def _pelo(dibujo, azar, cantidad, desde, hasta, largo_extra=0.0, ancho=(3, 6)):
    """Mechones que salen del cuerpo hacia afuera, con una pequeña curva."""
    for _ in range(cantidad):
        angulo = azar.uniform(0, 2 * math.pi)
        inicio = _punto_borde(angulo, azar.uniform(*desde))
        # Arriba el pelo es más largo y alborotado (como un copete)
        arriba = max(0.0, -math.sin(angulo))
        fin_escala = azar.uniform(*hasta) + largo_extra * arriba ** 2
        curva = azar.uniform(-0.18, 0.18)
        medio = _punto_borde(angulo + curva / 2, (desde[1] + fin_escala) / 2)
        fin = _punto_borde(angulo + curva, fin_escala)
        color = REFLEJO if azar.random() < 0.08 else azar.choice(MARRONES)
        dibujo.line([inicio, medio, fin], fill=color, width=azar.randint(*ancho), joint="curve")


def _pata(dibujo, x, y, espejo):
    """Pata crema con tres deditos redondos."""
    dibujo.ellipse([x - 38, y - 26, x + 38, y + 24], fill=CREMA, outline=CREMA_SOMBRA, width=3)
    for i in range(3):
        dx = (i - 1) * 22 + (6 if espejo else -6)
        dibujo.ellipse([x + dx - 13, y + 4, x + dx + 13, y + 30], fill=CREMA, outline=CREMA_SOMBRA, width=3)


@lru_cache(maxsize=None)
def _dibujo_grande():
    azar = random.Random(7)  # misma semilla = mismo muñeco siempre
    imagen = Image.new("RGBA", LIENZO, (0, 0, 0, 0))
    d = ImageDraw.Draw(imagen)

    # 1. Patas (asoman por abajo, a los costados)
    _pata(d, 98, 394, espejo=False)
    _pata(d, 302, 394, espejo=True)

    # 2. Cuerpo: relleno oscuro + capas de pelo de adentro hacia afuera
    d.ellipse([CENTRO[0] - RADIO_X, CENTRO[1] - RADIO_Y, CENTRO[0] + RADIO_X, CENTRO[1] + RADIO_Y], fill=MARRONES[1])
    _pelo(d, azar, 900, desde=(0.25, 0.85), hasta=(0.7, 1.0), ancho=(3, 5))        # textura interior
    _pelo(d, azar, 750, desde=(0.75, 0.95), hasta=(1.02, 1.16), largo_extra=0.28)  # borde peludo

    # 3. Cara: óvalo crema con una sombra suave abajo
    cara = [CENTRO[0] - 98, CENTRO[1] - 78, CENTRO[0] + 98, CENTRO[1] + 30]
    d.ellipse([cara[0], cara[1] + 6, cara[2], cara[3] + 6], fill=CREMA_SOMBRA)
    d.ellipse(cara, fill=CREMA)

    # 4. Flequillo: mechones que caen un poco sobre el borde de arriba de la cara
    for _ in range(70):
        x = azar.uniform(cara[0] + 15, cara[2] - 15)
        y = cara[1] + azar.uniform(-14, 4)
        d.line([(x, y - 22), (x + azar.uniform(-6, 6), y + azar.uniform(4, 14))],
               fill=azar.choice(MARRONES), width=azar.randint(3, 5))

    # 5. Ojos negros con brillo
    for ex in (CENTRO[0] - 55, CENTRO[0] + 55):
        ey = CENTRO[1] - 34
        d.ellipse([ex - 15, ey - 15, ex + 15, ey + 15], fill=NEGRO)
        d.ellipse([ex - 8, ey - 9, ex - 1, ey - 2], fill="#ffffff")

    # 6. Boca grande abierta (media elipse) con un dientito
    boca = [CENTRO[0] - 70, CENTRO[1] - 48, CENTRO[0] + 70, CENTRO[1] + 22]
    d.chord(boca, 0, 180, fill=ROJO, outline=ROJO_OSCURO, width=3)
    d.rounded_rectangle([CENTRO[0] + 4, CENTRO[1] - 14, CENTRO[0] + 28, CENTRO[1] + 10], radius=5, fill="#ffffff")

    return imagen.filter(ImageFilter.SMOOTH)


@lru_cache(maxsize=None)
def imagen(alto):
    """El muñeco con fondo transparente, de `alto` píxeles de alto."""
    grande = _dibujo_grande()
    ancho = round(grande.width * alto / grande.height)
    return grande.resize((ancho, alto), Image.LANCZOS)


@lru_cache(maxsize=None)
def png(alto):
    """Los bytes del PNG (para servirlo en la versión web)."""
    salida = io.BytesIO()
    imagen(alto).save(salida, format="PNG", optimize=True)
    return salida.getvalue()
