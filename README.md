# FinanzApp - Gestor Financiero Personal

Aplicación de escritorio en Python + MySQL (adaptada a Argentina) para organizar tus finanzas: importa
estados de cuenta (CSV/Excel), registra gastos a mano y mira reportes y gráficas.

## Requisitos

- Python 3.10 o más nuevo
- MySQL 8 corriendo en tu computadora

## Instalación

```bash
pip install -r requirements.txt
```

## Cómo ejecutarla

Desde la carpeta `finanzapp`:

```bash
python src/main.py
```

**La primera vez** la app intenta conectarse a MySQL. Si no puede, muestra una
pantalla para escribir servidor, puerto, usuario y contraseña. Al conectar, crea
sola la base de datos `finanzapp` y sus tablas (usa `database_schema.sql`).
Esos datos se guardan en `data/config.json`, que no se sube a git.

## Cómo se usa

1. **Crea tu cuenta** en la pantalla de inicio. Se crean categorías por defecto y una cuenta "Efectivo".
2. En **Configuración → Cuentas** agrega tus bancos y tarjetas.
3. Registra movimientos con **＋ Nuevo movimiento**, o desde el **Gasto rápido** del inicio
   (escribe el monto y toca una categoría).
4. En **Importar** sube el CSV/Excel de tu banco: revisa la vista previa y confirma.
   Hay archivos de prueba en `data/ejemplos/` (`ejemplo_galicia.csv` tiene formato argentino).
   Los montos se escriben como en Argentina: `1250,50` o `1.250,50`.
5. En **Configuración → Presupuestos** pon límites por categoría: el inicio te avisa al llegar al 80%.
6. En **Correo** conecta tu Gmail o Yahoo con una *contraseña de aplicación* (necesitas la
   verificación en dos pasos activada), enciende los bancos que usas y toca **Sincronizar ahora**.
   Revisa los movimientos detectados y guárdalos. Si eliges revisión automática, el correo se
   revisa cada X horas mientras la app esté abierta.
7. **¿Olvidaste tu contraseña?** (en la pantalla de inicio de sesión) manda un código de 6 dígitos
   al correo del usuario. Antes hay que configurar **una sola vez** el Gmail desde el que la app envía
   esos correos: *Configuración → Datos → Configurar correo de envío* (también con contraseña de aplicación).
8. **Asistente**: el muñequito peludo que flota abajo a la derecha (también en el celular). Tocalo y te
   responde cuánto gastaste, tus saldos, presupuestos y cómo usar la app. «🗑 Limpiar» borra la conversación.
   Funciona sin internet (respuestas programadas).
9. **Tutorial**: aparece solo la primera vez que entras. Para verlo otra vez, escríbele «tutorial» al asistente.
10. **Transferencias**: en «＋ Nuevo movimiento» elige «Transferencia» para pasar plata entre tus cuentas
    (no cuenta como gasto ni ingreso, solo cambia los saldos).
11. **Cuenta predeterminada**: en Configuración → Cuentas → ✎, marca «Usar para el gasto rápido y los
    movimientos nuevos». Se ve con una ★.

## Usarla desde el celular

```bash
python src/main_web.py
```

La consola muestra una dirección como `http://192.168.1.50:8000`. Ábrela en el navegador del
celular, que debe estar conectado **al mismo WiFi** que la computadora. La primera vez, Windows
pregunta por el firewall: permite el acceso en **redes privadas**.

- Funciona solo mientras la computadora esté encendida y `main_web.py` corriendo.
- Usa la misma base de datos: lo que registras en el celular aparece en la app de escritorio y al revés.
- En el celular puedes ver el inicio, registrar, editar y borrar movimientos, el historial, los reportes
  y recuperar la contraseña. Importar archivos, el correo bancario y la configuración siguen en la app de escritorio.
- Tip: en el navegador del celular elige «Agregar a pantalla de inicio» para abrirla como si fuera una app.

## Estructura

```
src/
├── main.py                 Punto de entrada (ventana y cambio de pantallas)
├── main_web.py             Punto de entrada de la versión web (celular)
├── web/
│   ├── app.py              Rutas/pantallas web (usa los mismos DAO y utils)
│   ├── templates/          HTML de cada pantalla (Jinja2)
│   └── static/estilo.css   Diseño para celular, modo claro/oscuro automático
├── database/               Todo lo que habla con MySQL
│   ├── conexion.py         Conexión + funciones consultar() / ejecutar()
│   └── *_dao.py            Una tabla por archivo
├── ui/                     Pantallas
│   ├── ventana_login.py        Login, registro y conexión a MySQL
│   ├── ventana_principal.py    Barra lateral + Dashboard
│   ├── ventana_registro.py     Formulario de nuevo movimiento / editar
│   ├── ventana_importar.py     Importar CSV/Excel
│   ├── ventana_correo.py       Conectar correo y revisar avisos del banco
│   ├── ventana_transacciones.py Historial
│   ├── ventana_reportes.py     Gráficas
│   ├── ventana_config.py       Cuentas, categorías, presupuestos, respaldo
│   ├── ventana_asistente.py    Muñequito flotante + panel del chat
│   ├── tutorial.py             Guía paso a paso de la primera vez
│   └── componentes/        Botones, tarjetas, tabla, gráficas, avisos, animaciones
├── email_parser/
│   └── lector_email.py     Lee los avisos del banco por IMAP y saca monto, fecha y comercio
└── utils/
    ├── procesador_csv.py   Lee archivos de bancos y sugiere categorías
    ├── calculos.py         Fechas, dinero, porcentajes, proyección
    ├── validadores.py      Validación de formularios
    ├── temas.py            Colores y fuentes (modo claro/oscuro)
    ├── exportar.py         CSV, PDF y respaldo JSON
    ├── enviar_correo.py    Envía correos (códigos) desde el Gmail de la app por SMTP
    ├── recuperacion.py     Pedir código para recuperar la contraseña (escritorio y web)
    ├── asistente.py        "Cerebro" del chatbot: entiende la pregunta y arma la respuesta
    ├── mascota.py          Dibuja el muñequito del asistente (Pillow), para escritorio y web
    └── config.py           Lee/guarda data/config.json
```

## Agregar un banco nuevo al importador

En `src/utils/procesador_csv.py`, agrega una entrada a `FORMATOS_BANCO` con los
nombres de columna que usa ese banco (en minúsculas y sin acentos):

```python
"Mi Banco": {"fecha": ["fecha"], "descripcion": ["concepto"], "cargo": ["debitos"], "abono": ["creditos"], "signo": "negativo"},
```
