-- S3.5 Migration: Create tendencias_insumo table for storing trend calculations
--
-- Purpose: Store deterministic trend metrics calculated by motor_tendencias_duckdb
-- Results are reusable across runs for reporting and analysis.
--
-- Run with: psql $DATABASE_URL -f migrations/004_create_tendencias_insumo.sql

BEGIN;

-- Main trends table
CREATE TABLE IF NOT EXISTS tendencias_insumo (
    tendencia_id BIGSERIAL PRIMARY KEY,
    insumo VARCHAR(100) NOT NULL,
    year_quarter VARCHAR(8) NOT NULL,  -- Format: '2026Q3'
    precio_trend DECIMAL(10, 2),  -- % change vs previous quarter
    precio_promedio DECIMAL(10, 2),
    marcas_nuevas INTEGER DEFAULT 0,
    marcas_salidas INTEGER DEFAULT 0,
    volatilidad DECIMAL(10, 4),  -- Coefficient of Variation (stddev/mean)
    promocion_pct DECIMAL(10, 2),  -- % of products with promotions
    total_products INTEGER DEFAULT 0,
    calculado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT tendencias_unique UNIQUE (insumo, year_quarter)
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_tendencias_insumo_quarter
    ON tendencias_insumo (insumo, year_quarter);

CREATE INDEX IF NOT EXISTS idx_tendencias_quarter
    ON tendencias_insumo (year_quarter);

-- Comments
COMMENT ON TABLE tendencias_insumo IS 'Deterministic price/brand trends by ingredient & quarter (no LLM)';
COMMENT ON COLUMN tendencias_insumo.insumo IS 'Crop/ingredient name (e.g., quinua, palto)';
COMMENT ON COLUMN tendencias_insumo.year_quarter IS 'Quarter in format 2026Q3';
COMMENT ON COLUMN tendencias_insumo.precio_trend IS 'Price change % vs previous quarter';
COMMENT ON COLUMN tendencias_insumo.volatilidad IS 'Stock volatility (coefficient of variation)';
COMMENT ON COLUMN tendencias_insumo.promocion_pct IS 'Percentage of products with active promotions';
COMMENT ON COLUMN tendencias_insumo.calculado_en IS 'When this row was computed';

COMMIT;
