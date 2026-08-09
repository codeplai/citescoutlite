-- ============================================================
--  AgroScout IA — SCHEMA SUPABASE (S1)
--  Ejecutar en: Supabase SQL Editor o via psql
-- ============================================================

-- 1. TABLA: consultas
CREATE TABLE IF NOT EXISTS consultas (
    id BIGSERIAL PRIMARY KEY,
    insumo VARCHAR(255) NOT NULL,
    pais VARCHAR(100) NOT NULL,
    usuario_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. TABLA: etapas_ejecucion
-- Etapas: '1', '2a', '2b', '3', '4', '5', '6'
CREATE TABLE IF NOT EXISTS etapas_ejecucion (
    id BIGSERIAL PRIMARY KEY,
    consulta_id BIGINT NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
    etapa TEXT NOT NULL CHECK (etapa IN ('1', '2a', '2b', '3', '4', '5', '6')),
    estado VARCHAR(50) DEFAULT 'pending',  -- pending, running, completed, failed
    resultado_json JSONB,
    duracion_ms INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. TABLA: cache_llm
-- Cache de respuestas LLM para evitar llamadas duplicadas
CREATE TABLE IF NOT EXISTS cache_llm (
    id BIGSERIAL PRIMARY KEY,
    clave_hash VARCHAR(64) UNIQUE NOT NULL,  -- hash de (insumo, país, etapa, modelo)
    etapa TEXT NOT NULL,
    modelo VARCHAR(100) NOT NULL,
    respuesta_json JSONB NOT NULL,
    tokens_in INT,
    tokens_out INT,
    costo_usd NUMERIC(10, 6),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ttl_days INT DEFAULT 30
);

-- 4. TABLA: informes
CREATE TABLE IF NOT EXISTS informes (
    id BIGSERIAL PRIMARY KEY,
    consulta_id BIGINT NOT NULL REFERENCES consultas(id) ON DELETE CASCADE,
    pdf_url VARCHAR(512),
    titulo VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. TABLA: usuarios (para multi-tenant)
CREATE TABLE IF NOT EXISTS usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    tenant_id UUID NOT NULL,
    rol VARCHAR(50) DEFAULT 'user',  -- user, admin, etc
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. TABLA: organizaciones
CREATE TABLE IF NOT EXISTS organizaciones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(255) NOT NULL,
    plan VARCHAR(50) DEFAULT 'free',  -- free, premium, enterprise
    nivel_maximo_costo INT DEFAULT 1,  -- 1, 2, 3 (cascada de N1, N2, N3)
    presupuesto_mes_usd NUMERIC(10, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 7. TABLA: audit_log
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    evento VARCHAR(255) NOT NULL,
    usuario_id UUID,
    tabla VARCHAR(100),
    fila_id BIGINT,
    detalles JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- ÍNDICES
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_consultas_usuario_id ON consultas(usuario_id);
CREATE INDEX IF NOT EXISTS idx_consultas_insumo_pais ON consultas(insumo, pais);
CREATE INDEX IF NOT EXISTS idx_etapas_consulta_id ON etapas_ejecucion(consulta_id);
CREATE INDEX IF NOT EXISTS idx_etapas_etapa ON etapas_ejecucion(etapa);
CREATE INDEX IF NOT EXISTS idx_cache_llm_hash ON cache_llm(clave_hash);
CREATE INDEX IF NOT EXISTS idx_cache_llm_modelo ON cache_llm(modelo);
CREATE INDEX IF NOT EXISTS idx_informes_consulta_id ON informes(consulta_id);
CREATE INDEX IF NOT EXISTS idx_usuarios_tenant_id ON usuarios(tenant_id);
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);
CREATE INDEX IF NOT EXISTS idx_audit_log_usuario_id ON audit_log(usuario_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);

-- ============================================================
-- ROW LEVEL SECURITY (RLS) — implementar en S3
-- Por ahora se deja deshabilitado, se configura después
-- ============================================================

-- TODO: Habilitar RLS y definir políticas en S3
-- ALTER TABLE consultas ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE etapas_ejecucion ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE informes ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- VERIFICACIÓN
-- ============================================================

-- Ver todas las tablas creadas
-- SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- Ver índices
-- SELECT indexname FROM pg_indexes WHERE schemaname = 'public';
