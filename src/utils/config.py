"""Lectura y guardado de la configuración local (data/config.json)."""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
RUTA_CONFIG = RAIZ / "data" / "config.json"
CARPETA_EXPORTS = RAIZ / "exports"

DEFECTO = {
    "mysql": {"host": "localhost", "puerto": 3306, "usuario": "root", "password": ""},
    "tema": "dark",
    "ultimo_email": "",
    "correo_app": "",       # Gmail desde el que se mandan los códigos de recuperación
    "clave_web": "",        # Firma de las sesiones de la versión web (se genera sola)
}


def cargar_config():
    config = json.loads(json.dumps(DEFECTO))  # copia profunda de los valores por defecto
    if RUTA_CONFIG.exists():
        guardada = json.loads(RUTA_CONFIG.read_text(encoding="utf-8"))
        config["mysql"].update(guardada.get("mysql", {}))
        for clave in ("tema", "ultimo_email", "correo_app", "clave_web"):
            config[clave] = guardada.get(clave, config[clave])
    return config


def guardar_config(config):
    RUTA_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    RUTA_CONFIG.write_text(json.dumps(config, indent=4, ensure_ascii=False), encoding="utf-8")


def actualizar_config(**cambios):
    config = cargar_config()
    config.update(cambios)
    guardar_config(config)
