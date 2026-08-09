-- ============================================================
--  004 - Tabla de cuarentena STAGING_AGENTE (Semana 2, S2.3)
--
--  Almacén temporal de datos recolectados por el agente investigador comercial,
--  antes de validación manual y promoción a catalogo_comercial.
--
--  TTL: 24h. Los datos sin revisar se borran automáticamente.
--  RLS: Los usuarios ven solo sus propios stagings.
--  Constraint: promoted_at IS NULL indica "aún en cuarentena".
--
--  Campos clave:
--    - producto_json: JSONB con nombre, precio, marca, stock, etc. (schema ProductoSchema)
--    - grounding_check_status: resultado de validación (passed/failed + detalles)
--    - validation_errors: array de errores detectados
--    - promoted_at: timestamp cuando se promovió a catálogo (NULL = aún en staging)
-- ============================================================

create table if not exists public.staging_agente (
  staging_id          uuid primary key default gen_random_uuid(),
  usuario_id          uuid not null references auth.users(id) on delete cascade,
  insumo              text not null,
  pais                text not null,
  mes                 text,  -- YYYY-MM para búsquedas mensuales
  producto_json       jsonb not null,
  fuente_url          text not null,
  html_capturado      text,
  provenance          text not null default 'agente' check (provenance in ('agente', 'manual')),
  no_verificado       boolean not null default true,
  grounding_check_status jsonb,  -- {passed: bool, errors: [...], timestamp: ...}
  validation_errors   text[],
  creado_en           timestamptz not null default now(),
  promoted_at         timestamptz,  -- NULL = aún en staging; lleno = ya promovido
  constraint staging_no_promovido check (
    (promoted_at is null and no_verificado = true) or
    (promoted_at is not null and no_verificado = false)
  )
);

-- Índices para búsquedas frecuentes en staging
create index if not exists ix_staging_usuario
  on public.staging_agente (usuario_id, creado_en desc);
create index if not exists ix_staging_lookup
  on public.staging_agente (insumo, pais, mes)
  where promoted_at is null;  -- Solo los en cuarentena
create index if not exists ix_staging_ttl
  on public.staging_agente (creado_en)
  where promoted_at is null;  -- Para trigger TTL

-- ============================================================
--  TTL Trigger: borrar automáticamente después de 24 horas
--  sin promoción manual.
-- ============================================================

create or replace function public.limpiar_staging_agente()
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  delete from public.staging_agente
  where promoted_at is null
    and creado_en < now() - interval '24 hours';

  raise notice 'staging_agente: limpieza completada';
end
$$;

-- Trigger de limpieza TTL (ejecutarse cada 2 horas)
-- En producción, esto debería ser un pg_cron job. Por ahora, se puede llamar manualmente.
-- TODO(s2): Configurar pg_cron si Supabase lo permite

-- ============================================================
--  RLS: Cada usuario ve solo sus propios stagings
-- ============================================================

alter table public.staging_agente enable row level security;

drop policy if exists staging_usuario_propio on public.staging_agente;
create policy staging_usuario_propio
  on public.staging_agente
  as permissive
  for all
  using (auth.uid() = usuario_id);

-- Service role (backend) ve todo sin restricción RLS
drop policy if exists staging_admin on public.staging_agente;
create policy staging_admin
  on public.staging_agente
  as permissive
  for all
  using (auth.role() = 'service_role');

-- ============================================================
--  Vista: Staging pendiente de promoción (helper queries)
-- ============================================================

create or replace view public.staging_pendiente as
select staging_id,
       usuario_id,
       insumo,
       pais,
       producto_json ->> 'nombre' as producto_nombre,
       producto_json ->> 'precio' as producto_precio,
       grounding_check_status ->> 'passed' as grounding_passed,
       validation_errors,
       creado_en,
       extract(epoch from (now() - creado_en)) / 3600 as horas_en_staging
from public.staging_agente
where promoted_at is null
order by creado_en desc;

-- ============================================================
--  Comentarios para documentación
-- ============================================================

comment on table public.staging_agente is 'Cuarentena: datos del agente sin validar. TTL 24h. Requiere promoción manual a catalogo_comercial.';
comment on column public.staging_agente.producto_json is 'JSONB schema: {nombre, precio, marca, stock, ...}';
comment on column public.staging_agente.grounding_check_status is 'JSONB: {passed: bool, errors: [string], timestamp: ISO8601}';
comment on column public.staging_agente.promoted_at is 'NULL=en cuarentena; timestamp=promovido a catálogo_comercial';
