"""FinanzApp para el celular (versión web).

Ejecutar desde la carpeta del proyecto con:  python src/main_web.py
Luego, en el celular (conectado al MISMO WiFi que esta computadora),
abre en el navegador la dirección que aparece en pantalla.
"""
import secrets
import socket

import uvicorn

from database.conexion import inicializar_bd
from utils.config import actualizar_config, cargar_config

PUERTO = 8000


def ip_local():
    """La IP de esta computadora dentro del WiFi (la que debe escribir el celular)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no envía nada: solo sirve para saber qué red se usaría
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


if __name__ == "__main__":
    # Clave para firmar las sesiones: se crea una sola vez y se guarda en data/config.json
    if not cargar_config()["clave_web"]:
        actualizar_config(clave_web=secrets.token_hex(32))
    inicializar_bd()

    from web.app import app  # después de crear la clave, porque app.py la lee al importarse

    print("\n  FinanzApp web está corriendo.")
    print(f"  En esta computadora:  http://localhost:{PUERTO}")
    print(f"  En tu celular:        http://{ip_local()}:{PUERTO}   (mismo WiFi)")
    print("  Si Windows pregunta por el firewall, permite el acceso en redes privadas.")
    print("  Para detenerla presiona Ctrl+C.\n")
    uvicorn.run(app, host="0.0.0.0", port=PUERTO, log_level="warning")
