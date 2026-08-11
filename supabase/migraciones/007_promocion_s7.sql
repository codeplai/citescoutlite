-- ============================================================
--  007 - Promocion automatica por muestreo (S7.1, S7.2, S7.3, S7.4)
--
--  Cuatro tablas:
--    promotion_rules            reglas que decide CITE, sin tocar codigo
--    promotion_watermark_log    que salio por la via automatica y cual manual
--    promotion_validation_log   por que se rechazo cada oferta
--    promotion_log              registro de cada promocion (auditoria)
--
--  Recordatorio de D1: promover NO mueve la fila a catalogo_comercial, que no
--  existe. Marca staging_agente.promoted_at + promotion_source (migracion 006).
--  Por eso todo lo de aqui apunta a staging_id.
-- ============================================================

-- ============================================================
--  promotion_rules (7.2)
--
--  La expresion va en JSONB y no en columnas: el DSL de S7 tiene formas
--  distintas por regla (rangos, minimos, listas de exclusion) y CITE debe
--  poder ajustarlo desde el panel sin una migracion por cada matiz.
-- ============================================================

create table if not exists public.promotion_rules (
  rule_id      bigserial primary key,
  nombre_regla text not null unique,
  descripcion  text,
  expresion    jsonb not null,
  -- Arrancan apagadas las que no tienen de donde leer el dato todavia; ver el
  -- seed de mas abajo.
  activo       boolean not null default false,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);

create index if not exists ix_promotion_rules_activas
  on public.promotion_rules (nombre_regla) where activo;

-- ============================================================
--  promotion_watermark_log (7.1)
--
--  Deja por escrito de que lado cayo cada oferta y con que semilla. El
--  watermark es determinista, asi que esto se puede recalcular; se guarda
--  igual porque es lo que permite responder "por que esta se promovio sola"
--  meses despues, aunque para entonces el umbral haya cambiado.
-- ============================================================

create table if not exists public.promotion_watermark_log (
  id           bigserial primary key,
  staging_id   uuid not null references public.staging_agente(staging_id) on delete cascade,
  semilla      text not null,          -- '2026-W33'
  lunes_semana date not null,          -- lunes de esa semana ISO, para filtrar por fecha
  cubo         smallint not null check (cubo between 0 and 99),
  porcentaje   smallint not null check (porcentaje between 0 and 100),
  automatica   boolean not null,       -- cubo < porcentaje
  created_at   timestamptz not null default now(),
  -- Una decision por oferta y semana. Si el job se repite, actualiza en vez de
  -- duplicar: dos filas distintas para la misma oferta y semana significarian
  -- que el watermark no es determinista, que es justo lo que promete.
  constraint uq_watermark_oferta_semana unique (staging_id, semilla)
);

create index if not exists ix_watermark_semana
  on public.promotion_watermark_log (semilla, automatica);

-- ============================================================
--  promotion_validation_log (7.3)
--
--  Por que se rechazo una oferta. Es lo que contesta el riesgo de S7 de
--  "reglas demasiado estrictas, 100 % rechazado": sin esto solo se ve que no
--  entro nada, no que regla lo impidio.
-- ============================================================

create table if not exists public.promotion_validation_log (
  id          bigserial primary key,
  staging_id  uuid not null references public.staging_agente(staging_id) on delete cascade,
  passed      boolean not null,
  errores     jsonb not null default '[]'::jsonb,  -- [{regla, motivo, valor}]
  reglas_evaluadas text[] not null default '{}',
  created_at  timestamptz not null default now()
);

create index if not exists ix_validation_staging
  on public.promotion_validation_log (staging_id, created_at desc);
create index if not exists ix_validation_fallidas
  on public.promotion_validation_log (created_at desc) where not passed;

-- ============================================================
--  promotion_log (7.4)
--
--  Registro inmutable de promociones. Sin unique sobre staging_id: una oferta
--  puede ser rechazada por el job y promovida a mano despues, y las dos cosas
--  tienen que quedar.
-- ============================================================

create table if not exists public.promotion_log (
  log_id           bigserial primary key,
  staging_id       uuid not null references public.staging_agente(staging_id) on delete cascade,
  promotion_type   text not null check (promotion_type in ('auto', 'manual')),
  -- uuid del admin que promovio, o null si fue el job. Sin FK a auth.users:
  -- el log es auditoria y debe sobrevivir a que se borre la cuenta.
  promoted_by      uuid,
  rules_applied    text[] not null default '{}',
  validation_errors jsonb not null default '[]'::jsonb,
  result           text not null check (result in ('promoted', 'rejected')),
  created_at       timestamptz not null default now(),
  -- 'system' es quien promueve en automatico; a mano tiene que haber usuario.
  constraint promocion_manual_con_autor check (
    (promotion_type = 'auto' and promoted_by is null)
    or (promotion_type = 'manual' and promoted_by is not null)
  )
);

create index if not exists ix_promotion_log_staging
  on public.promotion_log (staging_id);
create index if not exists ix_promotion_log_autor
  on public.promotion_log (promoted_by, created_at desc);
create index if not exists ix_promotion_log_dia
  on public.promotion_log (created_at desc, result);

-- ============================================================
--  Reglas base (7.2)
--
--  `activo` refleja si HOY hay de donde leer el dato, no si la regla es
--  deseable. Tres de las cinco arrancan apagadas porque el sistema todavia no
--  tiene ese dato, y dejarlas encendidas rechazaria el 100 % de las ofertas:
--
--    precio_vs_historico  no hay serie de precios por producto; tendencias_insumo
--                         es por insumo y trimestre, no por oferta.
--    stock_minimo         ProductoSchema tiene stock, pero la pagina rara vez da
--                         una cifra y el extractor deja null si no la ve.
--    tienda_no_marketplace no hay clasificacion de tienda; habria que derivarla
--                         del dominio de fuente_url.
--
--  Las dos que quedan encendidas se sirven con lo que ya hay en staging_agente.
-- ============================================================

insert into public.promotion_rules (nombre_regla, descripcion, expresion, activo)
values
  ('dato_fresco',
   'Rechaza ofertas capturadas hace mas de N dias.',
   '{"tipo": "date_freshness", "max_dias": 7}'::jsonb,
   true),

  ('url_presente',
   'Rechaza ofertas sin URL de origen: sin ella la procedencia no se puede comprobar.',
   '{"tipo": "url_presente"}'::jsonb,
   true),

  ('grounding_ok',
   'Rechaza ofertas cuyo grounding check no paso: el valor no estaba en el HTML.',
   '{"tipo": "grounding_ok"}'::jsonb,
   true),

  ('precio_vs_historico',
   'Precio dentro de un porcentaje del historico. APAGADA: no hay serie de precios por producto.',
   '{"tipo": "price_range", "min_pct_historico": 80, "max_pct_historico": 120}'::jsonb,
   false),

  ('stock_minimo',
   'Exige unidades disponibles. APAGADA: la mayoria de fichas no dan cifra de stock.',
   '{"tipo": "stock", "min_unidades": 1}'::jsonb,
   false),

  ('tienda_no_marketplace',
   'Excluye marketplaces. APAGADA: no hay clasificacion de tienda.',
   '{"tipo": "tienda_class", "excluir": ["marketplace"]}'::jsonb,
   false)
on conflict (nombre_regla) do nothing;

comment on table public.promotion_rules is 'Reglas de promocion, editables por CITE. activo=false = escrita pero sin dato que la alimente.';
comment on table public.promotion_watermark_log is 'S7.1: de que lado cayo cada oferta (80/20) y con que semilla semanal.';
comment on table public.promotion_validation_log is 'S7.3: por que se rechazo cada oferta.';
comment on table public.promotion_log is 'S7.4: registro de promociones. Auditoria.';
