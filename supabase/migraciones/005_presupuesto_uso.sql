-- ============================================================
--  005 - Tracking de presupuestos en tiempo real (S2.6)
--
--  Registra cada etapa ejecutada, su costo, tokens consumidos,
--  y el status (ok, parcial si alcanzó tope, error).
--
--  Usado por INTEG.2 (presupuestos) y INTEG.3 (cost-meter).
-- ============================================================

create table if not exists public.presupuesto_uso (
  id                bigserial primary key,
  ejecucion_id      uuid not null references public.ejecuciones(id) on delete cascade,
  usuario_id        uuid not null references auth.users(id) on delete cascade,
  etapa             text,  -- '1', '2a', '2b', '3', etc.
  timestamp         timestamptz not null default now(),
  costo_usd         numeric(12,6) not null default 0,
  token_entrada     integer default 0,
  token_salida      integer default 0,
  status            text check (status in ('ok', 'parcial', 'error')) default 'ok',
  motivo_parcial    text check (motivo_parcial in ('paywall', 'presupuesto', 'pocos_productos')) -- si status='parcial'
);

-- Índices para búsquedas frecuentes
create index if not exists ix_presupuesto_usuario
  on public.presupuesto_uso (usuario_id, timestamp desc);
create index if not exists ix_presupuesto_ejecucion
  on public.presupuesto_uso (ejecucion_id);
create index if not exists ix_presupuesto_etapa
  on public.presupuesto_uso (etapa, timestamp desc);

-- Vista: resumen de gasto por usuario y mes
create or replace view public.gasto_usuario_mes as
select usuario_id,
       date_trunc('month', timestamp) as mes,
       count(distinct ejecucion_id) as runs,
       coalesce(sum(costo_usd), 0) as costo_total_usd
from public.presupuesto_uso
where status != 'error'  -- No contar errores
group by 1, 2
order by 2 desc;

-- Vista: resumen de gasto global por día
create or replace view public.gasto_global_dia as
select date_trunc('day', timestamp) as dia,
       count(distinct ejecucion_id) as runs,
       count(distinct usuario_id) as usuarios,
       coalesce(sum(costo_usd), 0) as costo_total_usd,
       coalesce(sum(token_entrada), 0) as tokens_entrada_total,
       coalesce(sum(token_salida), 0) as tokens_salida_total
from public.presupuesto_uso
where status != 'error'
group by 1
order by 1 desc;

-- RLS: Los usuarios ven solo su propio gasto
alter table public.presupuesto_uso enable row level security;

drop policy if exists presupuesto_usuario_propio on public.presupuesto_uso;
create policy presupuesto_usuario_propio
  on public.presupuesto_uso
  as permissive
  for all
  using (auth.uid() = usuario_id);

-- Service role (backend) ve todo
drop policy if exists presupuesto_admin on public.presupuesto_uso;
create policy presupuesto_admin
  on public.presupuesto_uso
  as permissive
  for all
  using (auth.role() = 'service_role');

-- ============================================================
--  Config de presupuestos por tier (OPCIONAL, para futuro)
-- ============================================================

create table if not exists public.presupuesto_config (
  id                serial primary key,
  tier_id           text unique not null,  -- 'gratuito', 'premium', etc.
  run_limit_usd     numeric(10,2) default 0.25,
  month_limit_usd   numeric(10,2) default 2.0,
  daily_limit_usd   numeric(10,2) default 10.0,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

-- Seed inicial (opcional)
insert into public.presupuesto_config (tier_id, run_limit_usd, month_limit_usd, daily_limit_usd)
values
  ('gratuito', 0.25, 2.0, 10.0),
  ('premium', 1.0, 50.0, 100.0)
on conflict (tier_id) do nothing;

comment on table public.presupuesto_uso is 'Tracking de gasto en tiempo real: etapas, tokens, costos, status.';
comment on table public.presupuesto_config is 'Configuración de límites por tier de suscripción (futuro).';
