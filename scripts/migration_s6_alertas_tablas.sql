-- S6.1 + S6.2: Crear tablas para alertas de retiro (openFDA + RASFF)
-- Ejecutar en Postgres contra CITE_MVP database

BEGIN;

-- ============================================================================
-- Tabla: openfda_alerts
-- Descripción: Alertas de enforcement actions de FDA (USA)
-- ============================================================================
CREATE TABLE IF NOT EXISTS openfda_alerts (
    alert_id VARCHAR(128) PRIMARY KEY,
    fecha_emitida DATE NOT NULL,
    empresa VARCHAR(255),
    producto_nombre VARCHAR(255) NOT NULL,
    razon_texto TEXT,
    razon_categoria VARCHAR(50) NOT NULL,  -- 'patogeno', 'alérgeno', 'residuo', 'otro'
    pais VARCHAR(10) NOT NULL,             -- 'US' por defecto
    url_oficial TEXT,
    titulo_enforcement VARCHAR(255),

    -- Auditoría
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_openfda_producto_fecha
    ON openfda_alerts(producto_nombre, razon_categoria, fecha_emitida);

CREATE INDEX IF NOT EXISTS idx_openfda_fecha_emitida
    ON openfda_alerts(fecha_emitida DESC);

CREATE INDEX IF NOT EXISTS idx_openfda_categoria
    ON openfda_alerts(razon_categoria);

-- ============================================================================
-- Tabla: rasff_alerts
-- Descripción: Alertas del sistema europeo RASFF (EU)
-- ============================================================================
CREATE TABLE IF NOT EXISTS rasff_alerts (
    rasff_id VARCHAR(128) PRIMARY KEY,
    fecha_emitida DATE NOT NULL,
    producto_nombre VARCHAR(255) NOT NULL,
    hazard_texto TEXT,
    hazard_categoria VARCHAR(50) NOT NULL, -- 'patogeno', 'alérgeno', 'residuo', 'otro'
    pais_origen VARCHAR(10),
    pais_destino VARCHAR(10) NOT NULL,     -- 'EU' o país específico
    accion VARCHAR(100),                   -- 'blocked', 'detained', 'border_rejection', etc
    url_oficial TEXT,
    reference_number VARCHAR(50),

    -- Auditoría
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rasff_producto_fecha
    ON rasff_alerts(producto_nombre, hazard_categoria, fecha_emitida);

CREATE INDEX IF NOT EXISTS idx_rasff_fecha_emitida
    ON rasff_alerts(fecha_emitida DESC);

CREATE INDEX IF NOT EXISTS idx_rasff_categoria
    ON rasff_alerts(hazard_categoria);

CREATE INDEX IF NOT EXISTS idx_rasff_pais_destino
    ON rasff_alerts(pais_destino);

-- ============================================================================
-- Tabla: alert_scores
-- Descripción: Scoring de riesgo para cada alerta (1-5 escala)
-- ============================================================================
CREATE TABLE IF NOT EXISTS alert_scores (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(128) NOT NULL,
    alert_tipo VARCHAR(20) NOT NULL,       -- 'openfda' o 'rasff'

    score DECIMAL(3,2) NOT NULL,           -- 1.0 - 5.0 escala
    severity_label VARCHAR(20) NOT NULL,   -- 'critical', 'high', 'medium', 'low'
    dias_desde_emitida INT NOT NULL,

    -- Auditoría
    created_at TIMESTAMP DEFAULT NOW(),

    -- Integridad
    CONSTRAINT fk_alert_tipo CHECK (alert_tipo IN ('openfda', 'rasff')),
    CONSTRAINT fk_severity CHECK (severity_label IN ('critical', 'high', 'medium', 'low')),
    CONSTRAINT fk_score CHECK (score >= 1.0 AND score <= 5.0)
);

CREATE INDEX IF NOT EXISTS idx_alert_scores_alert_id
    ON alert_scores(alert_id);

CREATE INDEX IF NOT EXISTS idx_alert_scores_severity
    ON alert_scores(severity_label);

CREATE INDEX IF NOT EXISTS idx_alert_scores_score
    ON alert_scores(score DESC);

-- ============================================================================
-- Tabla: alert_lookup_log
-- Descripción: Auditoría de búsquedas de alertas por ingrediente
-- ============================================================================
CREATE TABLE IF NOT EXISTS alert_lookup_log (
    id SERIAL PRIMARY KEY,
    ingrediente VARCHAR(255) NOT NULL,
    pais VARCHAR(10) NOT NULL,
    alertas_encontradas INT DEFAULT 0,
    fuentes_consultadas VARCHAR(255),      -- 'openfda,rasff' o similar

    -- Auditoría
    timestamp TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_lookup_ingrediente
    ON alert_lookup_log(ingrediente, pais, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_alert_lookup_timestamp
    ON alert_lookup_log(timestamp DESC);

-- ============================================================================
-- Tabla: alert_ingest_log
-- Descripción: Log de cada ejecución del job de ingesta
-- ============================================================================
CREATE TABLE IF NOT EXISTS alert_ingest_log (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(128),                   -- ID del job Procrastinate

    openfda_nuevos INT DEFAULT 0,
    openfda_duplicados INT DEFAULT 0,
    openfda_errores INT DEFAULT 0,

    rasff_nuevos INT DEFAULT 0,
    rasff_duplicados INT DEFAULT 0,
    rasff_errores INT DEFAULT 0,

    duracion_segundos DECIMAL(10,2),
    estado VARCHAR(20),                    -- 'success', 'partial', 'failed'
    error_mensaje TEXT,

    -- Auditoría
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_ingest_job_id
    ON alert_ingest_log(job_id);

CREATE INDEX IF NOT EXISTS idx_alert_ingest_created_at
    ON alert_ingest_log(created_at DESC);

-- ============================================================================
-- Tabla: alert_notification_history
-- Descripción: Historial de notificaciones enviadas (para no duplicar)
-- ============================================================================
CREATE TABLE IF NOT EXISTS alert_notification_history (
    id SERIAL PRIMARY KEY,
    alert_id VARCHAR(128) NOT NULL,
    alert_tipo VARCHAR(20) NOT NULL,
    severity_label VARCHAR(20) NOT NULL,

    recipient VARCHAR(255),                -- email o canal
    enviado_at TIMESTAMP DEFAULT NOW(),

    -- Integridad
    CONSTRAINT fk_notif_tipo CHECK (alert_tipo IN ('openfda', 'rasff')),
    CONSTRAINT fk_notif_severity CHECK (severity_label IN ('critical', 'high', 'medium', 'low'))
);

CREATE INDEX IF NOT EXISTS idx_alert_notif_alert_id
    ON alert_notification_history(alert_id, enviado_at DESC);

CREATE INDEX IF NOT EXISTS idx_alert_notif_severity
    ON alert_notification_history(severity_label);

-- ============================================================================
-- Vistas útiles para queries frecuentes
-- ============================================================================

-- Vista: Alertas críticas de las últimas 24h
CREATE OR REPLACE VIEW alertas_criticas_24h AS
SELECT
    COALESCE(o.alert_id, r.rasff_id) as alert_id,
    COALESCE(o.producto_nombre, r.producto_nombre) as producto_nombre,
    COALESCE(o.razon_categoria, r.hazard_categoria) as riesgo_tipo,
    COALESCE(o.fecha_emitida, r.fecha_emitida) as fecha_emitida,
    CASE
        WHEN o.alert_id IS NOT NULL THEN 'openfda'
        ELSE 'rasff'
    END as fuente,
    s.score,
    s.severity_label
FROM openfda_alerts o
-- fecha_emitida es DATE: en Postgres `date - date` ya da un integer de dias,
-- asi que EXTRACT(DAY FROM ...) sobra y ademas falla (no hay extract(unknown,
-- integer)). La resta directa expresa lo mismo: alertas del mismo dia.
FULL OUTER JOIN rasff_alerts r ON o.producto_nombre = r.producto_nombre
    AND ABS(o.fecha_emitida - r.fecha_emitida) < 1
LEFT JOIN alert_scores s ON (o.alert_id = s.alert_id AND s.alert_tipo = 'openfda')
    OR (r.rasff_id = s.alert_id AND s.alert_tipo = 'rasff')
WHERE COALESCE(o.fecha_emitida, r.fecha_emitida) >= CURRENT_DATE - 1
  AND COALESCE(s.severity_label, 'medium') IN ('critical', 'high')
ORDER BY COALESCE(o.fecha_emitida, r.fecha_emitida) DESC;

-- Vista: Alertas por ingrediente (útil para búsqueda fuzzy)
CREATE OR REPLACE VIEW alertas_por_ingrediente AS
SELECT
    producto_nombre,
    razon_categoria as riesgo_tipo,
    'openfda' as fuente,
    COUNT(*) as cantidad,
    MAX(fecha_emitida) as ultima_alerta
FROM openfda_alerts
GROUP BY producto_nombre, razon_categoria

UNION ALL

SELECT
    producto_nombre,
    hazard_categoria as riesgo_tipo,
    'rasff' as fuente,
    COUNT(*) as cantidad,
    MAX(fecha_emitida) as ultima_alerta
FROM rasff_alerts
GROUP BY producto_nombre, hazard_categoria;

COMMIT;

-- ============================================================================
-- Verificación post-creación
-- ============================================================================
-- Ejecutar estos queries para verificar:
/*
SELECT 'openfda_alerts' as tabla, COUNT(*) as registros FROM openfda_alerts
UNION ALL
SELECT 'rasff_alerts', COUNT(*) FROM rasff_alerts
UNION ALL
SELECT 'alert_scores', COUNT(*) FROM alert_scores
UNION ALL
SELECT 'alert_lookup_log', COUNT(*) FROM alert_lookup_log
UNION ALL
SELECT 'alert_ingest_log', COUNT(*) FROM alert_ingest_log
UNION ALL
SELECT 'alert_notification_history', COUNT(*) FROM alert_notification_history;

-- Ver vistas
SELECT * FROM alertas_criticas_24h;
SELECT * FROM alertas_por_ingrediente;
*/
