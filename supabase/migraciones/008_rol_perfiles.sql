-- ============================================================
--  008 - Rol de usuario (S7.6)
--
--  7.6 pide que "Promover" sea solo para administradores, y hasta ahora no
--  habia ningun concepto de rol: cualquier usuario con token podia llamar a
--  cualquier endpoint. Promover cambia lo que ve todo el mundo, asi que no
--  basta con estar autenticado.
--
--  Va en `perfiles` y no en el JWT porque ahi ya vive el plan del usuario, y
--  asi dar o quitar permisos es un UPDATE, sin tocar Supabase Auth ni esperar
--  a que caduque un token.
--
--  Por defecto 'operador': un alta nueva no promueve nada. El trigger de la
--  migracion 003 crea el perfil sin tocar este campo, con lo que hereda el
--  default.
-- ============================================================

alter table public.perfiles
  add column if not exists rol text not null default 'operador';

do $$
begin
  if not exists (
    select 1 from pg_constraint
     where conrelid = 'public.perfiles'::regclass
       and conname = 'perfiles_rol_valido'
  ) then
    alter table public.perfiles
      add constraint perfiles_rol_valido check (rol in ('operador', 'admin'));
  end if;
end
$$;

create index if not exists ix_perfiles_admin
  on public.perfiles (rol) where rol = 'admin';

comment on column public.perfiles.rol is
  'operador (por defecto) o admin. Solo admin puede promover o rechazar ofertas (S7.6).';

-- Para nombrar al primer administrador:
--   update public.perfiles set rol = 'admin' where email = 'quien@cite.gob.pe';
