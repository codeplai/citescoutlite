-- ============================================================
--  006 - Procedencia de la promocion (S7.7, decision D1)
--
--  D1: "promover" es marcar la fila en staging_agente, NO moverla a una tabla
--  catalogo_comercial. Esa tabla se corto del MVP a proposito (ver el docstring
--  de dominio/mapa_comercial.py: la evidencia de procedencia es la fila de
--  etapas_ejecucion.salida_json) y S7 la daba por existente sin estarlo.
--
--  Con lo cual la promocion queda como un cambio de estado sobre la cuarentena:
--
--      update public.staging_agente
--         set promoted_at = now(),
--             no_verificado = false,
--             promotion_source = 'auto_watermark'
--       where staging_id = ...;
--
--  y el mapa comercial lee las filas con promoted_at not null.
--
--  Solo dos valores. S7.7 listaba ademas 'n1_direct' y 'n2_direct', pero por
--  staging_agente solo pasa N3: un producto del snapshot (N1) o de Bright Data
--  (N2) no entra en cuarentena, asi que esos dos serian estados imposibles.
--  Cuando N1/N2 escriban aqui se amplia el check.
-- ============================================================

alter table public.staging_agente
  add column if not exists promotion_source text;

do $$
begin
  -- Postgres no tiene ADD CONSTRAINT IF NOT EXISTS.
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.staging_agente'::regclass
       and conname = 'staging_promotion_source_valido'
  ) then
    alter table public.staging_agente
      add constraint staging_promotion_source_valido check (
        promotion_source is null
        or promotion_source in ('auto_watermark', 'manual_human')
      );
  end if;

  -- Coherencia con promoted_at: una fila en cuarentena no tiene procedencia de
  -- promocion, y una promovida no puede no tenerla. Sin esto, el "que % de
  -- datos son auto-promovidos" de S7.7 se calcularia sobre un campo que puede
  -- quedar a null por descuido.
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.staging_agente'::regclass
       and conname = 'staging_promocion_coherente'
  ) then
    alter table public.staging_agente
      add constraint staging_promocion_coherente check (
        (promoted_at is null and promotion_source is null)
        or (promoted_at is not null and promotion_source is not null)
      );
  end if;
end
$$;

create index if not exists ix_staging_promovidos
  on public.staging_agente (promotion_source, promoted_at desc)
  where promoted_at is not null;

comment on column public.staging_agente.promotion_source is
  'Como se promovio: auto_watermark (job nocturno) o manual_human (panel CITE). NULL = aun en cuarentena.';

-- La vista de S2 solo mira la cuarentena; esta es su contraparte, y es de
-- donde el mapa comercial debe leer lo ya promovido.
create or replace view public.staging_promovido as
select staging_id,
       usuario_id,
       insumo,
       pais,
       mes,
       producto_json,
       fuente_url,
       provenance,
       promotion_source,
       promoted_at
from public.staging_agente
where promoted_at is not null
order by promoted_at desc;
