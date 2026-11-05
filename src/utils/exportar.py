"""Exportar movimientos a CSV/PDF y hacer respaldos completos en JSON."""
import json
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure

from database import categorias_dao, cuentas_dao, presupuestos_dao, transacciones_dao
from database.conexion import consultar
from utils.calculos import formato_moneda, monto_con_signo, texto_cuenta


def _tabla(transacciones):
    return pd.DataFrame([{
        "Fecha": t["fecha"].strftime("%d/%m/%Y"),
        "Descripción": t["descripcion"],
        "Categoría": "Transferencia" if t["tipo"] == "transferencia" else t["categoria"] or "Sin categoría",
        "Cuenta": texto_cuenta(t),
        "Tipo": t["tipo"].capitalize(),
        "Monto": monto_con_signo(t),
    } for t in transacciones])


def a_csv(transacciones, ruta):
    # utf-8-sig para que Excel muestre bien los acentos.
    # Formato del Excel en Argentina: columnas separadas con ";" y coma decimal
    _tabla(transacciones).to_csv(ruta, index=False, encoding="utf-8-sig", sep=";", decimal=",")


def a_pdf(transacciones, ruta, titulo="Movimientos"):
    tabla = _tabla(transacciones)
    tabla["Monto"] = tabla["Monto"].apply(formato_moneda)
    tabla["Descripción"] = tabla["Descripción"].str.slice(0, 45)
    filas_por_pagina = 28
    with PdfPages(ruta) as pdf:
        for inicio in range(0, max(len(tabla), 1), filas_por_pagina):
            pagina = tabla.iloc[inicio:inicio + filas_por_pagina]
            figura = Figure(figsize=(11, 8.5))  # carta horizontal
            ax = figura.add_subplot()
            ax.axis("off")
            ax.set_title(f"FinanzApp · {titulo}", loc="left", fontsize=16, fontweight="bold", color="#1a1a2e")
            if len(pagina):
                celdas = ax.table(cellText=pagina.values, colLabels=pagina.columns, loc="upper center",
                                  cellLoc="left", colWidths=[0.1, 0.38, 0.16, 0.16, 0.08, 0.12])
                celdas.auto_set_font_size(False)
                celdas.set_fontsize(9)
                celdas.scale(1, 1.45)
                for (fila, _), celda in celdas.get_celld().items():
                    celda.set_edgecolor("#dddddd")
                    if fila == 0:
                        celda.set_facecolor("#0f3460")
                        celda.set_text_props(color="white", fontweight="bold")
            figura.text(0.5, 0.02, f"Generado el {date.today():%d/%m/%Y}", ha="center", fontsize=8, color="gray")
            pdf.savefig(figura)


# ---------- Respaldo completo ----------

def _serializable(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, (date, datetime)):
        return valor.isoformat()
    return valor


def exportar_respaldo(usuario_id, ruta):
    datos = {
        "version": 1,
        "cuentas": cuentas_dao.listar(usuario_id),
        "categorias": categorias_dao.listar(usuario_id),
        "transacciones": transacciones_dao.buscar(usuario_id),
        "presupuestos": consultar("SELECT * FROM presupuestos WHERE usuario_id = %s", (usuario_id,)),
    }
    limpio = {clave: [{k: _serializable(v) for k, v in fila.items()} for fila in filas]
              if isinstance(filas, list) else filas for clave, filas in datos.items()}
    with open(ruta, "w", encoding="utf-8") as archivo:
        json.dump(limpio, archivo, ensure_ascii=False, indent=2)


def importar_respaldo(usuario_id, ruta):
    """Agrega al usuario actual todo lo que hay en el respaldo. Devuelve cuántos movimientos importó."""
    with open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)

    # Los ids cambian al insertar, así que guardamos la equivalencia viejo -> nuevo
    nuevas_cuentas, nuevas_categorias = {}, {}
    for c in datos.get("cuentas", []):
        nuevas_cuentas[c["id"]] = cuentas_dao.crear(usuario_id, c["nombre"], c["tipo"], c["banco"],
                                                    c["ultimos_4_digitos"], c["saldo_inicial"], c["color_icono"])
    for c in datos.get("categorias", []):
        nuevas_categorias[c["id"]] = categorias_dao.crear(usuario_id, c["nombre"], c["icono"],
                                                          c["color"], bool(c["es_ingreso"]))
    movimientos = [t for t in datos.get("transacciones", []) if t["cuenta_id"] in nuevas_cuentas]
    filas = [(nuevas_cuentas[t["cuenta_id"]], nuevas_categorias.get(t["categoria_id"]), t["descripcion"],
              t["monto"], t["fecha"], t["tipo"], t["origen"])
             for t in movimientos if t["tipo"] != "transferencia"]
    transacciones_dao.crear_varias(filas)
    # Las transferencias llevan además la cuenta de destino (con su id nuevo)
    for t in movimientos:
        if t["tipo"] == "transferencia" and t.get("cuenta_destino_id") in nuevas_cuentas:
            transacciones_dao.crear(nuevas_cuentas[t["cuenta_id"]], None, t["descripcion"], t["monto"], t["fecha"],
                                    "transferencia", t["origen"], cuenta_destino_id=nuevas_cuentas[t["cuenta_destino_id"]])
            filas.append(t)
    for p in datos.get("presupuestos", []):
        if p["categoria_id"] in nuevas_categorias:
            presupuestos_dao.guardar(usuario_id, nuevas_categorias[p["categoria_id"]],
                                     p["monto_limite"], p["anio"], p["mes"])
    return len(filas)
