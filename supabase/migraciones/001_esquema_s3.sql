-- ============================================================
--  AgroScout IA - Semana 3 - Esquema de estado de aplicacion
--  Aplicar con:  uv run python scripts/aplicar_migracion.py
--  o pegando el archivo en el SQL Editor de Supabase.
--
--  Es idempotente: se puede volver a aplicar sin romper nada.
--
--  Sin organizaciones: el MVP es de una sola institucion (PLAN-TIERS-S3 §1).
--  usuario_id queda desde el dia 1 para que anadir organizacion_id + RLS
--  por organizacion mas adelante sea una migracion de dos columnas.
-- ============================================================

-- Perfil de aplicacion colgado de auth.users.
create table if not exists public.perfiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text not null,
  plan        text not null default 'gratuito' check (plan in ('gratuito','premium')),
  creado_en   timestamptz not null default now()
);

create table if not exists public.ejecuciones (
  id                uuid primary key,
  usuario_id        uuid not null references auth.users(id),
  insumo_texto      text not null,
  snapshot_version  text not null,
  estado            text not null check (estado in ('ok','parcial','reformular','error')),
  -- La diferencia entre paywall, guard tecnico y kill-switch es una columna
  -- con check, no una cadena libre dentro del informe: es lo que P06 exige
  -- poder distinguir.
  motivo_parcial    text check (motivo_parcial in ('paywall','pocos_productos','presupuesto')),
  creado_en         timestamptz not null default now()
);

-- 'etapa' es TEXT y no INTEGER: cierra D6 antes de acumular historial.
-- '2a' = busqueda sobre el snapshot (lo que hoy hace buscar_productos).
-- '2b' = descubrimiento comercial, valor legal desde hoy aunque llegue en S4.
create table if not exists public.etapas_ejecucion (
  id                bigserial primary key,
  ejecucion_id      uuid not null references public.ejecuciones(id) on delete cascade,
  etapa             text not null check (etapa in ('1','2a','2b','3','4','5','6')),
  modelo            text,
  entrada_json      jsonb,
  salida_json       jsonb,
  duracion_ms       integer,
  costo_usd         numeric(12,6) not null default 0,
  tokens            integer not null default 0,
  tokens_entrada    integer not null default 0,
  tokens_salida     integer not null default 0,
  snapshot_version  text,
  creado_en         timestamptz not null default now()
);

create table if not exists public.cache_llm (
  clave_hash        text primary key,
  etapa             text,
  modelo            text,
  respuesta_json    jsonb not null,
  snapshot_version  text,
  creado_en         timestamptz not null default now()
);

create table if not exists public.informes (
  id            uuid primary key,
  ejecucion_id  uuid not null references public.ejecuciones(id) on delete cascade,
  usuario_id    uuid not null references auth.users(id),
  parcial       boolean not null,
  motivo        text,
  ruta_storage  text not null,
  creado_en     timestamptz not null default now()
);

create index if not exists ix_ejecuciones_usuario
  on public.ejecuciones (usuario_id, creado_en desc);
create index if not exists ix_etapas_ejecucion
  on public.etapas_ejecucion (ejecucion_id);
create index if not exists ix_informes_usuario
  on public.informes (usuario_id, creado_en desc);

-- Cost-meter por usuario y mes (P13).
create or replace view public.uso_mensual as
select e.usuario_id,
       date_trunc('month', e.creado_en) as mes,
       count(distinct e.id)             as runs,
       coalesce(sum(x.costo_usd), 0)    as costo_usd
from public.ejecuciones e
left join public.etapas_ejecucion x on x.ejecucion_id = e.id
group by 1, 2;

-- RLS activo en las 5 tablas. El backend entra con la clave de servicio y la
-- salta; esto es defensa en profundidad: si la clave publica se filtra, no lee
-- nada. Las politicas se recrean en cada aplicacion para que el archivo sea
-- la unica fuente de verdad.
alter table public.perfiles          enable row level security;
alter table public.ejecuciones       enable row level security;
alter table public.etapas_ejecucion  enable row level security;
alter table public.cache_llm         enable row level security;
alter table public.informes          enable row level security;

drop policy if exists p_perfil_propio on public.perfiles;
drop policy if exists p_ejec_propia   on public.ejecuciones;
drop policy if exists p_inf_propio    on public.informes;

create policy p_perfil_propio on public.perfiles    for select using (id = auth.uid());
create policy p_ejec_propia   on public.ejecuciones for select using (usuario_id = auth.uid());
create policy p_inf_propio    on public.informes    for select using (usuario_id = auth.uid());

-- etapas_ejecucion y cache_llm se quedan sin politicas a proposito:
-- sin politica y con RLS activo, anon y authenticated no leen ni una fila.
