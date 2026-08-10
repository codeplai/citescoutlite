-- S3.7 + 3.8 Migration: CITE Taxonomy and anti-corruption layer
--
-- Purpose: Store known claims and ingredients for CITE validation
-- Protects against LLM hallucinations in Stage 4 (Formulation)
--
-- Run with: psql $DATABASE_URL -f migrations/005_create_taxonomia_cite.sql

BEGIN;

-- ============================================================
-- TAXONOMIA_CITE: Known claim categories for pilot crops
-- ============================================================

CREATE TABLE IF NOT EXISTS taxonomia_cite (
    categoria_id BIGSERIAL PRIMARY KEY,
    nombre_categoria VARCHAR(100) NOT NULL UNIQUE,  -- e.g., 'quinua'
    claims TEXT[] NOT NULL DEFAULT '{}',            -- array of known claims
    version VARCHAR(20) DEFAULT '0.1',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_taxonomia_nombre
    ON taxonomia_cite (nombre_categoria);

COMMENT ON TABLE taxonomia_cite IS 'Known claim categories for pilot crops (quinua, palto, etc.)';
COMMENT ON COLUMN taxonomia_cite.claims IS 'Array of canonical claims (fuzzy-match eligible)';
COMMENT ON COLUMN taxonomia_cite.version IS 'Taxonomy version for audit trail';


-- ============================================================
-- INGREDIENTES_CITE: Ingredient registry with claims
-- ============================================================

CREATE TABLE IF NOT EXISTS ingredientes_cite (
    ingrediente_id BIGSERIAL PRIMARY KEY,
    nombre VARCHAR(255) NOT NULL,
    insumo VARCHAR(100) NOT NULL,                   -- categoria_id reference
    ean VARCHAR(50),
    inacal_code VARCHAR(50),
    usda_id VARCHAR(50),
    off_id VARCHAR(50),
    es_alérgeno BOOLEAN DEFAULT FALSE,
    claims_aplicables TEXT[] DEFAULT '{}',         -- applicable claims from taxonomia
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT ingredientes_unique UNIQUE (ean, insumo)
);

CREATE INDEX IF NOT EXISTS idx_ingredientes_insumo
    ON ingredientes_cite (insumo);

CREATE INDEX IF NOT EXISTS idx_ingredientes_ean
    ON ingredientes_cite (ean);

COMMENT ON TABLE ingredientes_cite IS 'Ingredient registry linked to CITE taxonomy';
COMMENT ON COLUMN ingredientes_cite.insumo IS 'Crop category (foreign key to taxonomia_cite.nombre_categoria)';
COMMENT ON COLUMN ingredientes_cite.claims_aplicables IS 'Subset of claims valid for this ingredient';


-- ============================================================
-- AUDIT_CLAIMS: Record rejected claims (anti-corruption layer)
-- ============================================================

CREATE TABLE IF NOT EXISTS audit_claims (
    audit_id BIGSERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    etapa VARCHAR(50) NOT NULL,                    -- usually '4_formulacion'
    claim_propuesto TEXT NOT NULL,
    insumo_categoria VARCHAR(100),
    claim_canonico TEXT,                           -- matched claim, if any
    motivo_rechazo VARCHAR(255),                   -- "no en taxonomía", "similitud < 80%", etc
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_claims_run_id
    ON audit_claims (run_id);

CREATE INDEX IF NOT EXISTS idx_audit_claims_etapa
    ON audit_claims (etapa);

COMMENT ON TABLE audit_claims IS 'Log of rejected/corrected claims during validation';
COMMENT ON COLUMN audit_claims.claim_canonico IS 'Matched canonical claim (if similitud >= 80%)';

COMMIT;
