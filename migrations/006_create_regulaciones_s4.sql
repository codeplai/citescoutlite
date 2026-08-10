-- S4: CORPUS REGULATORIO COMPLETO
-- Crear tablas para eCFR, EFSA, Codex, INACAL, DIGESA
-- Mapping entre regulaciones
-- Run with: psql $DATABASE_URL -f migrations/006_create_regulaciones_s4.sql

BEGIN;

-- ============================================================
-- ECFR_REGULATIONS: FDA Code of Federal Regulations (US)
-- ============================================================

CREATE TABLE IF NOT EXISTS ecfr_regulations (
    regulation_id BIGSERIAL PRIMARY KEY,
    title VARCHAR(10) NOT NULL,              -- 21 (Food & Drugs), 7 (Agriculture)
    part VARCHAR(50) NOT NULL,
    section VARCHAR(50) NOT NULL,
    subsection VARCHAR(50),
    texto_completo TEXT NOT NULL,
    url_oficial VARCHAR(500),
    fecha_efectiva DATE,
    last_update TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    content_hash VARCHAR(64),                -- SHA256 for change detection
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ecfr_title_part
    ON ecfr_regulations (title, part);

CREATE INDEX IF NOT EXISTS idx_ecfr_full_text
    ON ecfr_regulations USING GIN (
        to_tsvector('english', texto_completo)
    );

COMMENT ON TABLE ecfr_regulations IS 'FDA Electronic Code of Federal Regulations (all titles)';
COMMENT ON COLUMN ecfr_regulations.content_hash IS 'SHA256 hash for change detection in daily update job';


-- ============================================================
-- EFSA_REGULATIONS: European Food Safety Authority Additives
-- ============================================================

CREATE TABLE IF NOT EXISTS efsa_regulations (
    regulation_id BIGSERIAL PRIMARY KEY,
    e_number VARCHAR(20) NOT NULL UNIQUE,    -- E-number (e.g., E500, E621)
    ingredient_name VARCHAR(255) NOT NULL,
    authorized_uses TEXT[] DEFAULT '{}',     -- array of allowed uses
    max_levels_pct DECIMAL(10,4),            -- maximum level in %
    url_oficial VARCHAR(500),
    last_update TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    content_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_efsa_e_number
    ON efsa_regulations (e_number);

CREATE INDEX IF NOT EXISTS idx_efsa_ingredient
    ON efsa_regulations (ingredient_name);

COMMENT ON TABLE efsa_regulations IS 'EFSA authorized food additives (E-numbers)';
COMMENT ON COLUMN efsa_regulations.authorized_uses IS 'Array of allowed food categories';


-- ============================================================
-- CODEX_STANDARDS: International Food Standards (UN/FAO)
-- ============================================================

CREATE TABLE IF NOT EXISTS codex_standards (
    standard_id BIGSERIAL PRIMARY KEY,
    nombre_estandar VARCHAR(255) NOT NULL,
    codigo_cat VARCHAR(50) NOT NULL,         -- e.g., 'STAN 50-1991'
    version VARCHAR(50),
    anio_publicacion INTEGER,
    texto TEXT,
    url_oficial VARCHAR(500),
    last_update TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    content_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_codex_codigo
    ON codex_standards (codigo_cat);

CREATE INDEX IF NOT EXISTS idx_codex_nombre
    ON codex_standards (nombre_estandar);

COMMENT ON TABLE codex_standards IS 'Codex Alimentarius international standards (UN/FAO)';


-- ============================================================
-- INACAL_NTS: Peruvian Technical Standards
-- ============================================================

CREATE TABLE IF NOT EXISTS inacal_nts (
    nts_id BIGSERIAL PRIMARY KEY,
    nombre_nts VARCHAR(255) NOT NULL,
    codigo_nts VARCHAR(50) NOT NULL UNIQUE,  -- e.g., 'NTS 201.041'
    version VARCHAR(50),
    texto TEXT,
    url_oficial VARCHAR(500),
    last_update TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    content_hash VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_inacal_codigo
    ON inacal_nts (codigo_nts);

CREATE INDEX IF NOT EXISTS idx_inacal_nombre
    ON inacal_nts (nombre_nts);

COMMENT ON TABLE inacal_nts IS 'Peruvian technical standards for food (INACAL)';


-- ============================================================
-- DIGESA_DIRECTIVAS: Peruvian Health Authority Directives (OCR from PDF)
-- ============================================================

CREATE TABLE IF NOT EXISTS digesa_directivas (
    directiva_id BIGSERIAL PRIMARY KEY,
    asunto VARCHAR(255),
    ingrediente VARCHAR(255),
    accion VARCHAR(50),                      -- 'bloqueado', 'restringido', 'permitido'
    limite VARCHAR(100),                     -- e.g., '< 0.1%'
    justificacion TEXT,
    fecha_emitida DATE,
    archivo_pdf_url VARCHAR(500),
    ocr_accuracy DECIMAL(3,2),               -- 0.0-1.0 (confidence score)
    last_update TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_digesa_ingrediente
    ON digesa_directivas (ingrediente);

CREATE INDEX IF NOT EXISTS idx_digesa_accion
    ON digesa_directivas (accion);

COMMENT ON TABLE digesa_directivas IS 'DIGESA directives extracted from PDFs via OCR';
COMMENT ON COLUMN digesa_directivas.ocr_accuracy IS 'Confidence score from OCR (0.6+ = usable)';


-- ============================================================
-- MAPPING_REGULACIONES: Cross-reference between regulatory sources
-- ============================================================

CREATE TABLE IF NOT EXISTS mapping_regulaciones (
    mapping_id BIGSERIAL PRIMARY KEY,
    ingrediente_canonico VARCHAR(255) NOT NULL,
    ecfr_ref BIGINT REFERENCES ecfr_regulations(regulation_id) ON DELETE SET NULL,
    efsa_ref BIGINT REFERENCES efsa_regulations(regulation_id) ON DELETE SET NULL,
    codex_ref BIGINT REFERENCES codex_standards(standard_id) ON DELETE SET NULL,
    inacal_ref BIGINT REFERENCES inacal_nts(nts_id) ON DELETE SET NULL,
    digesa_ref BIGINT REFERENCES digesa_directivas(directiva_id) ON DELETE SET NULL,
    mapping_confidence DECIMAL(3,2) DEFAULT 1.0,  -- 0.0-1.0 (how sure are we?)
    notas TEXT,
    validated_by VARCHAR(100),               -- CITE specialist who validated
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mapping_ingrediente
    ON mapping_regulaciones (ingrediente_canonico);

CREATE INDEX IF NOT EXISTS idx_mapping_confidence
    ON mapping_regulaciones (mapping_confidence);

COMMENT ON TABLE mapping_regulaciones IS 'Unified mapping of ingredient regulations across all sources';
COMMENT ON COLUMN mapping_regulaciones.mapping_confidence IS '1.0 = validated by CITE, < 1.0 = fuzzy match or inference';


-- ============================================================
-- REGULACION_CITA: Unified citations table for Etapa 5
-- ============================================================

CREATE TABLE IF NOT EXISTS regulacion_cita (
    cita_id BIGSERIAL PRIMARY KEY,
    ingrediente VARCHAR(255) NOT NULL,
    tipo_regulacion VARCHAR(50) NOT NULL,   -- 'eCFR', 'EFSA', 'Codex', 'INACAL', 'DIGESA'
    regulation_id BIGINT,                   -- FK to specific table depending on tipo
    seccion_exacta VARCHAR(255),
    texto_cita TEXT,
    url_oficial VARCHAR(500),
    version_norma VARCHAR(100),
    fecha_acceso TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cita_ingrediente
    ON regulacion_cita (ingrediente);

CREATE INDEX IF NOT EXISTS idx_cita_tipo
    ON regulacion_cita (tipo_regulacion);

CREATE INDEX IF NOT EXISTS idx_cita_full_text
    ON regulacion_cita USING GIN (
        to_tsvector('spanish', texto_cita)
    );

COMMENT ON TABLE regulacion_cita IS 'Unified view of all regulatory citations for Etapa 5 (VerificacionRegulatoria)';
COMMENT ON COLUMN regulacion_cita.regulation_id IS 'References specific table based on tipo_regulacion';


-- ============================================================
-- AUDIT_REGULACIONES: Log changes in corpus (for job monitoring)
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_regulaciones (
    audit_id BIGSERIAL PRIMARY KEY,
    tipo_fuente VARCHAR(50),                 -- 'eCFR', 'EFSA', 'Codex', 'INACAL', 'DIGESA'
    accion VARCHAR(50),                      -- 'insert', 'update', 'delete'
    cantidad_cambios INTEGER,
    hash_anterior VARCHAR(64),
    hash_nuevo VARCHAR(64),
    detalles TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_regulaciones_timestamp
    ON audit_regulaciones (timestamp DESC);

COMMENT ON TABLE audit_regulaciones IS 'Audit trail for daily corpus update job (job_corpus_ingest)';


-- ============================================================
-- CONSTRAINT: Asegurar que regulacion_cita tiene reference válida
-- ============================================================

-- Note: Cannot do direct FK because regulation_id points to different tables
-- Validation done in application layer instead


COMMIT;
