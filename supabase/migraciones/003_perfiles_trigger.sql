-- ============================================================
--  003 - Perfil automatico al dar de alta un usuario
--
--  `perfiles` cuelga de auth.users y guarda lo que Supabase Auth no sabe: el
--  plan de suscripcion. Sin trigger habria que acordarse de insertarlo en cada
--  alta, y un usuario sin perfil no tendria entitlement en T6.
--
--  security definer es necesario: el trigger corre en el contexto de quien
--  inserta en auth.users (el servicio de Auth), que no tiene permiso sobre
--  public.perfiles. `set search_path` va explicito para que la funcion no
--  dependa del search_path de quien la dispare.
--
--  Dispara solo para altas POSTERIORES. La cuenta tecnica admin@cite.gob.pe,
--  creada en T2.2 como duena del historico, se queda deliberadamente sin
--  perfil: no participa del paywall y asi `perfiles` termina con exactamente
--  las 2 cuentas demo que verifica el DoD de este tier.
-- ============================================================

create or replace function public.crear_perfil()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.perfiles (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end
$$;

drop trigger if exists on_auth_user_created on auth.users;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.crear_perfil();
