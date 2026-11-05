# FinanzApp - Especificación

Aplicación de escritorio (Python + CustomTkinter + MySQL) para organizar las
finanzas personales: importar estados de cuenta, registrar gastos y ver
reportes. Filosofía: **"Simple por dentro, profesional por fuera"**.

## Estilo

| Uso | Color |
|---|---|
| Fondo principal | `#1c1c1f` (gris oscuro) |
| Fondo secundario (tarjetas) | `#26262b` |
| Acento | `#34343b` |
| Destacado (botones importantes) | `#e94560` |
| Texto / texto secundario | `#ffffff` / `#a0a0a0` |
| Gráficas: gastos / ingresos / ahorro / neutro | `#e94560` / `#4ecca3` / `#f9d923` / `#3498db` |

Modo oscuro por defecto, modo claro opcional. Fuente Segoe UI (24 / 18 / 14 / 12 px).
Todos los colores están en `src/utils/temas.py`.

## Módulos

1. **Dashboard**: ingresos, gastos, balance y ahorro del mes; dona por categoría;
   barras de 6 meses; últimos 5 movimientos; alertas de presupuesto; gasto rápido.
2. **Importación**: CSV/Excel, selector de banco, mapeo automático de columnas
   (editable), vista previa con categoría sugerida, detección de duplicados, confirmación.
3. **Registro manual**: monto, categoría con iconos, cuenta, fecha (hoy por defecto), descripción.
4. **Historial**: tabla con filtros (periodo, fechas, categoría, cuenta, tipo, búsqueda),
   edición, eliminación, exportar a CSV/PDF.
5. **Reportes**: dona por categoría, evolución de 12 meses, comparativa de 6 meses,
   top 5 categorías, proyección de fin de mes.
6. **Configuración**: cuentas, categorías, presupuestos, respaldo JSON. Modo claro/oscuro en la barra lateral.
7. **Correo bancario**: conecta Gmail o Yahoo por IMAP, lee los avisos de los bancos activos,
   extrae monto, fecha y comercio con plantillas de regex por banco, sugiere categoría, muestra
   vista previa antes de guardar y recuerda los correos ya procesados. Sincronización manual o
   cada X horas.

## Cambios respecto a la especificación original

| Cambio | Por qué |
|---|---|
| `transacciones.monto` siempre positivo; el `tipo` dice si es gasto o ingreso | Antes el signo y el tipo decían lo mismo y podían contradecirse |
| `cuentas.saldo_actual` → `saldo_inicial`; el saldo actual se calcula | Así nunca se desincroniza al editar o borrar movimientos |
| Tabla `presupuestos` con `UNIQUE (usuario, categoría, mes, año)` | Evita presupuestos duplicados |
| FKs con `ON DELETE CASCADE` / `SET NULL` | Borrar una categoría deja sus movimientos como "Sin categoría" |
| Iconos con emoji/Unicode en lugar de Font Awesome | Tkinter no carga fuentes de iconos fácilmente; así no hay archivos extra |
| "Ahorro del mes" = % de los ingresos que no se gastó | La especificación no lo definía |
| Se agregó `ventana_registro.py`, `presupuestos_dao.py`, `utils/exportar.py`, `utils/config.py`, `componentes/graficas.py` y `componentes/aviso.py` | Faltaban en la estructura para cubrir los módulos |
| Las transferencias existen en la BD pero no en la interfaz | Para mantenerlo simple; no cuentan en los totales |
| Correo con contraseña de aplicación guardada en el llavero de Windows (`keyring`) en vez de token OAuth; `cuentas_email` no tiene `token_acceso` | OAuth exige registrar la app con Google/Microsoft. La contraseña nunca queda en la base de datos |
| Solo Gmail y Yahoo, no Outlook | Outlook ya no permite IMAP con contraseña en cuentas personales |
| `cuentas_email` agrega `intervalo_horas` y es una por usuario | Para la sincronización cada X horas |
| `plantillas_email` agrega `remitente` | El servidor filtra por remitente y así solo se descargan correos de bancos |
| Tabla nueva `emails_procesados` | Para el historial de correos ya leídos (evita duplicados) |
| La sincronización automática solo corre con la app abierta | Una app de escritorio no puede trabajar cerrada sin instalar un servicio |
| No se usa `cryptography` | `keyring` ya guarda la contraseña cifrada por Windows |
| Recuperar contraseña con código de 6 dígitos por correo (tabla `recuperaciones`) | El código se guarda con bcrypt, vence en 15 min, máximo 5 intentos y 1 envío por minuto. Se envía desde un Gmail de la app (SMTP), cuya contraseña de aplicación va en el llavero |
| Adaptada a **Argentina** | Montos `$ 1.250,50`; se pueden escribir `1250,50`, `1.250,50` o `1250.50` (`calculos.leer_monto`, una sola función para toda la app). Bancos argentinos en importar y correo, comercios argentinos para las categorías, calendario `es_AR`, CSV exportado con `;` y coma decimal para el Excel argentino. Las plantillas de correo con los patrones viejos (México) se actualizan solas |
| Asistente con respuestas programadas (palabras clave), no con IA | Funciona sin internet, sin costo y responde al instante; lee datos reales del usuario (gastos, saldos, presupuestos). La lógica está en `utils/asistente.py`, separada de la interfaz |
| Tutorial de bienvenida (tabla `tutoriales_vistos`) | Se muestra la primera vez; se repite desde el asistente. Si se cierra sesión a mitad, vuelve a salir la próxima vez |
| La sincronización de correo avisa los correos del banco cuyo asunto no coincidió | Antes se descartaban en silencio y parecía que la app no funcionaba |
| Versión web para el celular (`main_web.py`, FastAPI + Jinja2) | Una app de escritorio no corre en el teléfono. La web reutiliza los DAO y utils; solo funciona en el mismo WiFi y con la PC encendida. Las gráficas son CSS/SVG para no depender de internet |
