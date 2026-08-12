-- ============================================================
--  010 - Configuracion del sistema (S8.5)
--
--  8.5 pide un kill-switch: un interruptor con estado verde/naranja que un
--  administrador pueda accionar. Lo que habia era un **umbral calculado**:
--
--      gasto_global_mes >= PRESUPUESTO_GLOBAL_MES_USD
--
--  Eso no es un interruptor. No hay estado persistido, no hay forma de
--  activarlo a mano y, por tanto, no hay nada que auditar (B5).
--
--  ## Por que una tabla y no una variable de entorno mas
--
--  Los topes viven en el entorno y esta bien: son politica, cambian cuando
--  cambia el presupuesto del proyecto y tocarlos es un despliegue. El
--  kill-switch es lo contrario: se acciona **durante** un incidente, por una
--  persona que no tiene acceso al servidor, y hay que poder responder despues
--  quien lo apago y cuando. Nada de eso cabe en una variable de entorno.
--
--  ## Clave-valor y no una columna por ajuste
--
--  Las fases 3 y 4 de S8 van a necesitar mas ajustes de sistema. Una tabla de
--  una sola fila con una columna por ajuste obliga a una migracion por cada
--  uno; clave-valor con jsonb no. El precio es que el esquema del valor no lo
--  valida Postgres, y por eso lo valida el adaptador que la lee.
-- ============================================================

create table if not exists public.sistema_config (
  clave            text primary key,
  valor            jsonb       not null,
  descripcion      text,
  actualizado_por  uuid,
  actualizado_en   timestamptz not null default now()
);

comment on table public.sistema_config is
  'S8.5 - Ajustes que se accionan en caliente desde el panel, no por despliegue.';

comment on column public.sistema_config.actualizado_por is
  'Quien lo toco por ultima vez. El historico completo esta en auditoria_panel (S8.3).';

-- ============================================================
--  El kill-switch
--
--  Arranca APAGADO. Una migracion que dejara el sistema parado al aplicarse
--  seria una caida provocada por un despliegue.
--
--  `motivo` va dentro del valor y no en una columna aparte porque solo tiene
--  sentido mientras el switch esta activo: es lo que el panel enseña al lado
--  del estado naranja para que quien lo vea sepa por que esta parado y no
--  tenga que ir a buscar a quien lo acciono.
-- ============================================================

insert into public.sistema_config (clave, valor, descripcion)
values (
  'kill_switch',
  '{"activo": false, "motivo": null}'::jsonb,
  'Para en seco el gasto en LLM de todos los usuarios. Degrada a sin_dato: los runs siguen respondiendo 200 en parcial, no fallan.'
)
on conflict (clave) do nothing;

-- ============================================================
--  Sin RLS, igual que las tablas de promocion y de auditoria
--
--  No hay dato "de un usuario" que aislar: es configuracion del sistema. Quien
--  puede escribirla lo decide `requiere_admin` en el endpoint, y la API entra
--  con la conexion de servicio, que saltaria la politica igual.
-- ============================================================
