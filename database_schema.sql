-- =============================================================
--  FinanzApp - Esquema de base de datos (MySQL 8)
--  La app ejecuta este script sola al iniciar, no hace falta
--  correrlo a mano (aunque se puede, desde MySQL Workbench).
-- =============================================================

CREATE DATABASE IF NOT EXISTS finanzapp
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE finanzapp;

-- Usuarios de la app
CREATE TABLE IF NOT EXISTS usuarios (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    nombre          VARCHAR(100) NOT NULL,
    email           VARCHAR(150) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    fecha_registro  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Cuentas, tarjetas y monederos de cada usuario
-- El saldo actual NO se guarda: se calcula como saldo_inicial + ingresos - gastos
CREATE TABLE IF NOT EXISTS cuentas (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id          INT NOT NULL,
    nombre              VARCHAR(100) NOT NULL,
    tipo                ENUM('banco', 'tarjeta_credito', 'tarjeta_debito', 'monedero') NOT NULL DEFAULT 'banco',
    banco               VARCHAR(100) NOT NULL DEFAULT '',
    ultimos_4_digitos   CHAR(4) NULL,
    saldo_inicial       DECIMAL(12,2) NOT NULL DEFAULT 0,
    color_icono         VARCHAR(7) NOT NULL DEFAULT '#3498db',
    activa              BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Categorías personalizables (cada usuario tiene las suyas)
CREATE TABLE IF NOT EXISTS categorias (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id  INT NOT NULL,
    nombre      VARCHAR(50) NOT NULL,
    icono       VARCHAR(50) NOT NULL DEFAULT '📦',
    color       VARCHAR(7) NOT NULL DEFAULT '#3498db',
    es_ingreso  BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Movimientos. El monto SIEMPRE es positivo: el campo "tipo" dice si es gasto, ingreso o transferencia.
-- En una transferencia el dinero sale de cuenta_id y entra a cuenta_destino_id
-- (no cuenta como gasto ni como ingreso: solo mueve saldo entre tus cuentas).
CREATE TABLE IF NOT EXISTS transacciones (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    cuenta_id           INT NOT NULL,
    cuenta_destino_id   INT NULL,
    categoria_id        INT NULL,
    descripcion     VARCHAR(200) NOT NULL DEFAULT '',
    monto           DECIMAL(12,2) NOT NULL,
    fecha           DATE NOT NULL,
    tipo            ENUM('gasto', 'ingreso', 'transferencia') NOT NULL,
    origen          ENUM('manual', 'csv', 'email') NOT NULL DEFAULT 'manual',
    fecha_creacion  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cuenta_id) REFERENCES cuentas(id) ON DELETE CASCADE,
    FOREIGN KEY (cuenta_destino_id) REFERENCES cuentas(id) ON DELETE CASCADE,
    FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE SET NULL,
    INDEX idx_fecha (fecha)
);

-- Preferencias de cada usuario (una fila por usuario)
CREATE TABLE IF NOT EXISTS preferencias (
    usuario_id                INT PRIMARY KEY,
    cuenta_predeterminada_id  INT NULL,   -- la del gasto rápido y la que aparece elegida en "Nuevo movimiento"
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (cuenta_predeterminada_id) REFERENCES cuentas(id) ON DELETE SET NULL
);

-- Presupuesto mensual por categoría (uno por categoría y mes)
CREATE TABLE IF NOT EXISTS presupuestos (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id      INT NOT NULL,
    categoria_id    INT NOT NULL,
    monto_limite    DECIMAL(12,2) NOT NULL,
    mes             TINYINT NOT NULL,
    anio            SMALLINT NOT NULL,
    UNIQUE KEY uq_presupuesto (usuario_id, categoria_id, mes, anio),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE,
    FOREIGN KEY (categoria_id) REFERENCES categorias(id) ON DELETE CASCADE
);

-- Correo conectado para leer avisos del banco (uno por usuario).
-- La contraseña de aplicación NO se guarda aquí: va en el llavero de Windows (keyring)
CREATE TABLE IF NOT EXISTS cuentas_email (
    id                      INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id              INT NOT NULL UNIQUE,
    proveedor_email         VARCHAR(50) NOT NULL,
    email_conexion          VARCHAR(150) NOT NULL,
    intervalo_horas         TINYINT NOT NULL DEFAULT 0,
    ultima_sincronizacion   DATETIME NULL,
    sincronizacion_activa   BOOLEAN NOT NULL DEFAULT TRUE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Patrones (expresiones regulares) para leer los avisos de cada banco
CREATE TABLE IF NOT EXISTS plantillas_email (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    banco            VARCHAR(100) NOT NULL UNIQUE,
    remitente        VARCHAR(150) NOT NULL DEFAULT '',
    patron_asunto    VARCHAR(200) NOT NULL,
    patron_monto     VARCHAR(200) NOT NULL,
    patron_fecha     VARCHAR(200) NOT NULL DEFAULT '',
    patron_comercio  VARCHAR(200) NOT NULL DEFAULT '',
    activo           BOOLEAN NOT NULL DEFAULT FALSE
);

-- Códigos para recuperar la contraseña (uno vigente por usuario).
-- El código se guarda cifrado con bcrypt, nunca en texto plano
CREATE TABLE IF NOT EXISTS recuperaciones (
    usuario_id   INT PRIMARY KEY,
    codigo_hash  VARCHAR(255) NOT NULL,
    expira       DATETIME NOT NULL,
    intentos     TINYINT NOT NULL DEFAULT 0,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Usuarios que ya vieron (o saltaron) el tutorial de bienvenida
CREATE TABLE IF NOT EXISTS tutoriales_vistos (
    usuario_id  INT PRIMARY KEY,
    fecha       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);

-- Correos ya guardados o descartados, para no mostrarlos dos veces
CREATE TABLE IF NOT EXISTS emails_procesados (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id       INT NOT NULL,
    message_id       VARCHAR(255) NOT NULL,
    fecha_procesado  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_email (usuario_id, message_id),
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
);
