-- ============================================================
--  009 - Auditoria transversal del panel (S8.3)
--
--  8.3 pide poder responder "quien cambio esto, cuando, y que habia antes".
--  Hoy solo queda rastro de una de las seis acciones que enumera: la promocion
--  manual, en promotion_log (S7.4). Las otras cinco no dejan nada.
--
--  ## Por que una tabla nueva y no la que ya hay
--
--  En Postgres existe `public.audit_log`, huerfana del esquema S1
--  (scripts/create_schema_s1.sql). Tiene 0 filas y ningun codigo la escribe ni
--  la lee: sobrevivio a la limpieza del runner de migraciones porque no estaba
--  en su lista. Y su forma no sirve —(evento, tabla, fila_id, detalles)— porque
--  le falta justo lo que 8.3 pide al hacer clic en una fila: el antes y el
--  despues.
--
--  No se elimina aqui. Borrar una tabla es del dueno del esquema, no de una
--  migracion que viene a crear otra cosa; queda anotado al final.
--
--  Ojo con el nombre: `adaptadores/audit_log.py` es una TERCERA cosa distinta
--  —un log tecnico en SQLite (level, component, message) para el canario y los
--  conflictos de dedup— que no tiene que ver con esto. De ahi que la tabla se
--  llame `auditoria_panel` y no `audit_log` otra vez.
-- ============================================================

-- ============================================================
--  La tabla
--
--  `entidad_id` es text y no uuid a proposito: lo que se audita no comparte
--  tipo de clave. Una oferta es un uuid, una regla de promocion es un bigint y
--  el kill-switch es una cadena. Con una columna por tipo la tabla se llenaria
--  de nulos, y con uuid habria que dejar fuera la mitad de los eventos.
--
--  `antes` y `despues` son el corazon de 8.3 y van en jsonb porque cada evento
--  cambia campos distintos. Para un alta, `antes` es null; para una baja, lo es
--  `despues`. Esa asimetria es informacion, no un hueco.
-- ============================================================

create table if not exists public.auditoria_panel (
  audit_id      bigserial,
  ocurrido_en   timestamptz not null default now(),
  evento        text        not null,
  usuario_id    uuid,
  -- El correo se copia en el momento en vez de resolverlo por join al leer.
  -- Un registro de auditoria tiene que seguir siendo legible dentro de un ano,
  -- cuando esa persona puede haber cambiado de correo o no estar dada de alta:
  -- un informe que diga "usuario 6976d1cc..." no vale para nada.
  usuario_email text,
  entidad       text,
  entidad_id    text,
  antes         jsonb,
  despues       jsonb,
  detalles      jsonb       not null default '{}'::jsonb,
  -- La clave primaria incluye la fecha porque Postgres exige que la clave de
  -- particion forme parte de cualquier indice unico.
  primary key (audit_id, ocurrido_en)
) partition by range (ocurrido_en);

comment on table public.auditoria_panel is
  'S8.3 - Quien hizo que en el panel, con antes/despues. Solo insercion.';

-- ============================================================
--  Particion por mes
--
--  No es por volumen —CITE hara miles de filas al ano, no millones— sino por
--  la retencion de un ano que pide S8: con particiones, caducar un mes es
--  `drop table` (instantaneo, sin hinchar la tabla) en vez de un `delete` que
--  deja las paginas muertas y obliga a un vacuum. Ese es todo el motivo.
-- ============================================================

create or replace function public.crear_particion_auditoria(mes date)
returns text
language plpgsql
as $$
declare
  inicio date := date_trunc('month', mes)::date;
  fin    date := (date_trunc('month', mes) + interval '1 month')::date;
  nombre text := 'auditoria_panel_' || to_char(inicio, 'YYYY_MM');
begin
  if to_regclass('public.' || nombre) is not null then
    return nombre;
  end if;
  execute format(
    'create table public.%I partition of public.auditoria_panel
       for values from (%L) to (%L)', nombre, inicio, fin);
  return nombre;
end
$$;

comment on function public.crear_particion_auditoria(date) is
  'Crea la particion mensual que contiene esa fecha, si no existe. Idempotente.';

-- Doce meses por delante. Una particion vacia no cuesta nada y evita el fallo
-- clasico de este diseno: que el primer insert del mes que viene reviente
-- porque nadie creo la particion.
do $$
declare
  i int;
begin
  for i in 0..12 loop
    perform public.crear_particion_auditoria(
      (date_trunc('month', now()) + (i || ' month')::interval)::date);
  end loop;
end
$$;

-- La red de seguridad. Si algun dia se acaban las particiones creadas, el
-- insert cae aqui en vez de fallar: perder una escritura de auditoria es peor
-- que tenerla en el sitio equivocado.
--
-- Deberia estar siempre vacia. Si tiene filas, hay que moverlas antes de crear
-- la particion del mes que les toca: Postgres no deja crear un rango que
-- solape con filas que ya viven en la particion por defecto.
create table if not exists public.auditoria_panel_resto
  partition of public.auditoria_panel default;

comment on table public.auditoria_panel_resto is
  'Red de seguridad. Si tiene filas, falta crear la particion de ese mes.';

-- ============================================================
--  Indices
--
--  Los tres filtros que pide 8.3 (usuario, accion, fecha) y el orden en que se
--  lee siempre: lo ultimo primero.
-- ============================================================

create index if not exists ix_auditoria_panel_fecha
  on public.auditoria_panel (ocurrido_en desc);

create index if not exists ix_auditoria_panel_evento
  on public.auditoria_panel (evento, ocurrido_en desc);

create index if not exists ix_auditoria_panel_usuario
  on public.auditoria_panel (usuario_id, ocurrido_en desc);

create index if not exists ix_auditoria_panel_entidad
  on public.auditoria_panel (entidad, entidad_id);

-- ============================================================
--  Solo insercion
--
--  Un registro que se puede editar o borrar no es una auditoria: es un log. Y
--  la aplicacion se conecta como duena del esquema, asi que un `revoke` no la
--  detendria. El trigger si, y ademas deja el motivo por escrito para quien lo
--  intente.
--
--  No estorba a la retencion: caducar un mes es `drop table` sobre la
--  particion, que es DDL y no pasa por el trigger.
-- ============================================================

create or replace function public.auditoria_panel_solo_insercion()
returns trigger
language plpgsql
as $$
begin
  raise exception
    'auditoria_panel es de solo insercion (se intento %). Para caducar datos, '
    'elimina la particion del mes con drop table.', tg_op;
end
$$;

drop trigger if exists tg_auditoria_panel_inmutable on public.auditoria_panel;
create trigger tg_auditoria_panel_inmutable
  before update or delete on public.auditoria_panel
  for each row execute function public.auditoria_panel_solo_insercion();

-- ============================================================
--  Sin RLS, igual que las tablas de promocion de S7
--
--  Aqui no hay dato "de un usuario" que aislar: es un registro del sistema, y
--  quien puede leerlo lo decide `requiere_admin` en el endpoint. Ponerle RLS
--  daria una falsa sensacion de proteccion, porque la API entra con la
--  conexion de servicio y la saltaria igual.
-- ============================================================

-- ------------------------------------------------------------
--  Pendiente para el dueno del esquema:
--
--    drop table if exists public.audit_log;
--
--  0 filas y sin lectores. No se ejecuta aqui a proposito.
-- ------------------------------------------------------------
