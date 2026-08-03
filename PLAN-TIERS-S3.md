# Semana 3: Plan en TIERS — Supabase, paywall y presupuestos

**Fecha:** 2026-08-02 · **Proyecto:** AgroScout IA (CITEagroindustrial Chavimochic)
**Modelo:** el mismo de S1 y S2 — 7 tiers secuenciales, cada uno con gate numérico
**Calendario nominal:** Lun 3 – Vie 7 de agosto 2026 · **≈34 h de código**
**Estado previo:** S2 cerrada (7/7 tiers, 29.054 productos, P03 verde con p95 66 ms GPU / 176 ms CPU)

---

## 0. Antes de empezar: las claves que hay que poner en `.env`

Son **cuatro valores obligatorios** y vienen de dos sitios distintos del dashboard de
Supabase. La confusión más común es que la *clave de API* y la *contraseña de la base
de datos* son cosas diferentes: hacen falta las dos.

| # | Variable | Dónde está | Obligatoria |
|---|---|---|---|
| 1 | `SUPABASE_URL` | Project Settings → API → *Project URL* | ✅ |
| 2 | `SUPABASE_ANON_KEY` | Project Settings → API Keys → `sb_publishable_…` (proyectos nuevos) o `anon public` (proyectos anteriores) | ✅ |
| 3 | `SUPABASE_SERVICE_ROLE_KEY` | Misma página → `sb_secret_…` o `service_role secret` | ✅ |
| 4 | `DATABASE_URL` | Botón **Connect** (arriba) → pestaña *Transaction pooler*, puerto **6543** | ✅ |
| 5 | `SUPABASE_JWT_SECRET` | Project Settings → API → JWT Settings | ⚠️ solo si el proyecto usa firma heredada (se decide en T1.2) |
| 6 | `SUPABASE_BUCKET_INFORMES` | No es una clave: es el nombre del bucket que se crea en T1.3 | ✅ (valor `informes`) |

**Sobre el punto 4.** La cadena que da el dashboard trae un marcador
`[YOUR-PASSWORD]`. Esa contraseña es la de la base de datos, la que se fijó al crear
el proyecto (Project Settings → Database → *Reset database password* si se perdió).
Se copia la cadena **tal cual** y solo se reemplaza ese marcador; el host
(`aws-1-sa-east-1.pooler.supabase.com` o el que sea) cambia entre proyectos y no debe
escribirse a mano. Si la contraseña contiene `@ : / ? #`, hay que URL-encodearla.

**Por qué el pooler de transacciones y no la conexión directa:** la conexión directa
(`db.<ref>.supabase.co`) es **solo IPv6** salvo que se contrate el add-on de IPv4, y
desde una red doméstica peruana lo normal es que no resuelva. El pooler es IPv4 y es
el camino que funciona el primer día.

**Región recomendada:** `South America (São Paulo)`. Si el proyecto ya está creado en
otra región no se migra — se mide el RTT en T1.1 y se decide con el número delante
(ver el riesgo R1 en §9).

**Yo no necesito ver el valor de ninguna clave.** Se pegan en `.env` (que está en
`.gitignore`) y el trabajo arranca; lo único que necesito confirmar es que las cuatro
líneas existen y que `T1.1` pasa. La plantilla completa y comentada ya está en
[.env.example](.env.example).

### Qué NO hace falta

- **No hace falta la Supabase CLI** (arrastra Docker). Las migraciones son SQL plano
  que se aplica desde el SQL Editor o con `psql`.
- **No hace falta `supabase-py`.** Auth y Storage se usan por REST con `httpx`, que ya
  está en el árbol de dependencias vía `litellm`. Una dependencia menos que versionar.
- **No hacen falta claves en el frontend.** El login pasa por el backend (§T4.2), así
  que la SPA no necesita `VITE_SUPABASE_*` ni `@supabase/supabase-js`.

Dependencias nuevas en `pyproject.toml`: **solo `psycopg[binary,pool]>=3.2`**.

---

## 1. Alcance de la semana

**Entra:**

1. Estado de aplicación en Postgres gestionado (Supabase): `ejecuciones`,
   `etapas_ejecucion`, `cache_llm`, `informes`, `perfiles`.
2. Autenticación gestionada por Supabase Auth, en reemplazo del bcrypt + JWT propios.
3. **Separación de las etapas 4 y 5** del objeto `InsightDeMercado` — deuda de S1 que
   nunca se ejecutó y que es el prerrequisito estructural del paywall (§2).
4. Paywall como *early return* en la frontera de aplicación, distinguible del guard
   técnico `n_directos ≤ 2`.
5. Cost-meter por usuario, cuota por plan y kill-switch sobre las etapas LLM.
6. PDF en Storage privado con URL firmada, en vez de servir cualquier archivo por id.

**No entra (decisión del usuario: "es solo un MVP"):**

| Pieza | Por qué queda fuera |
|---|---|
| **Multi-tenant: organizaciones, RLS por `org_id`, rate-limit por plan en el borde** | Es el grueso de la S3 original y no aporta a un MVP de una sola institución |
| Cola `procrastinate` + workers | El PDF síncrono en <15 s alcanza para la demo (§8 de PLAN-MVP-v2) |
| Agente, mapa comercial 2b, MIM | S4 y roadmap del ADR |

### Consecuencia que hay que declarar

Quitar el multi-tenant **desactiva la prueba P01 tal como está escrita** y con ella el
**bloque 5 del guion de demo** (`PLAN-MVP-v2.md` §9: *"RLS en vivo: consulta cruzada
entre organizaciones → 0 filas. El argumento del contrato multi-cooperativa"*).

Sustituto propuesto, sin inventar nada: el bloque 5 pasa a ser **aislamiento por
usuario** — `demo-gratuita` pide el informe de `demo-premium` por id y recibe 404 —
y el argumento multi-cooperativa se sostiene con el ADR-003 (*"RLS por organización
sobre estas mismas tablas; el modelo de datos ya lleva la columna"*), no con una
demostración en vivo. El coste real es que se cambia una demostración por una promesa
en un punto donde antes había demostración; si el CDR es una firma multi-organización
conviene saberlo con tres semanas de antelación, no el día del ensayo.

La columna `usuario_id` queda en las tablas desde el día 1, así que añadir
`organizacion_id` + políticas RLS después es una migración de dos columnas, no una
reescritura.

### Pruebas que cierra la semana

| Prueba | Estado al cerrar S3 |
|---|---|
| **P02** — cache hit con clave correcta (incluye modelo y snapshot) | ✅ |
| **P06** — paywall con informe parcial, distinto del guard técnico | ✅ |
| **P13** — costo en US$ por etapa y por usuario, visible | ✅ |
| **P12** — presupuestos y kill-switch | 🟡 parcial (sin agente no hay run de agente que topar) |
| **P01** — aislamiento | 🟡 degradado a por-usuario, sin RLS por organización |

---

## 2. La deuda que bloquea el paywall

Antes de planificar nada conviene mirar el código, porque el plan de 4 semanas asumía
algo que no ocurrió. `PLAN-MVP-v2.md` §7 pone en la **Semana 1**:

> *Separar etapas 4 y 5 de `InsightDeMercado` en etapas propias dentro de `etapa()`.
> Es el prerrequisito estructural del paywall.*

No se hizo. Hoy, en [dominio/insight_mercado.py](dominio/insight_mercado.py):

```python
class InsightDeMercado(BaseModel):
    cobertura: Literal["baja", "media", "alta"]
    resumen: str
    hipotesis_formulacion: str        # <- esto es la "etapa 4"
    verificacion_regulatoria: str     # <- esto es la "etapa 5"
    formatos_comunes: list[str]
    citas: list[str]
```

Los dos campos premium salen de **la misma llamada LLM** que el resumen gratuito, y el
contexto regulatorio se arma **fuera** del envoltorio `etapa()`
([evaluar_insumo.py:17-23](casos_de_uso/evaluar_insumo.py#L17)): no se audita, no se
cachea y no tiene costo propio. Con esta estructura el paywall no se puede
implementar honestamente: se pagaría el token de la formulación **siempre**, y
"ocultarla" sería recortar un string ya generado. Por eso **TIER 5 es de esta semana**
y no es opcional.

`casos_de_uso/etapas/` tiene hoy 4 archivos: `interpretar_insumo`, `buscar_productos`,
`generar_insight`, `ejecutor`. Faltan dos.

---

## 3. Estructura de TIERS

```
TIER 1: Preparación y contrato de entorno (Lun 3, mañana)      → 2-3 h
  ├─ T1.1 Proyecto Supabase + claves en .env + RTT medido
  ├─ T1.2 Decidir verificación de JWT: JWKS vs HS256 heredado
  ├─ T1.3 Bucket privado `informes`
  └─ T1.4 psycopg contra el pooler desde el entorno uv

TIER 2: Esquema y migración de datos (Lun 3, tarde)            → 4 h
  ├─ T2.1 001_esquema_s3.sql (5 tablas + vista + RLS deny-all)
  ├─ T2.2 Migrar 54 ejecuciones / 94 etapas / 47 cache de SQLite
  └─ T2.3 Saldar la deuda de esquema del .db vivo

TIER 3: Adaptadores Postgres + Storage (Mar 4)                 → 6 h
  ├─ T3.1 adaptadores/db.py (pool psycopg)
  ├─ T3.2 auditoria_postgres.py + cache_postgres.py
  ├─ T3.3 repositorio_informes_supabase.py (Storage + URL firmada)
  └─ T3.4 Conmutador APP_DB y medición de sobrecoste

TIER 5: Separación de etapas 4 y 5 (Mar 4 – Mié 5)             → 6 h
  ├─ T5.1 Partir InsightDeMercado en 3 contratos     ⚡ PARALELIZABLE
  ├─ T5.2 Etapa 4 formular_hipotesis                    con T3/T4
  ├─ T5.3 Etapa 5 verificar_regulacion (contexto adentro de etapa())
  └─ T5.4 Numeración TEXT '1','2a','2b','3','4','5','6' (D6)

TIER 4: Auth Supabase (Mié 5)                                  → 5 h
  ├─ T4.1 Verificador de JWT de Supabase
  ├─ T4.2 /token como proxy del password grant
  ├─ T4.3 perfiles + trigger + 2 usuarios demo
  └─ T4.4 Cerrar /informes/{id} por propiedad

TIER 6: Paywall, cuotas y kill-switch (Jue 6)                  → 6 h
  ├─ T6.1 PoliticaDeSuscripcion (entitlement guard)
  ├─ T6.2 Dos composiciones: mapa comercial / dossier
  ├─ T6.3 Presupuestos 3 niveles + degradación a "sin dato"
  └─ T6.4 GET /uso — costo por etapa, por run y por mes

TIER 7: Frontend, cierre y auditoría (Vie 7)                   → 5 h
  ├─ T7.1 SPA: tarjeta de paywall + barra de cuota
  ├─ T7.2 test/test_e2e_s3.py
  ├─ T7.3 README + TIER7-S3-COMPLETADO.md
  └─ T7.4 Ensayo del guion y verificación del plan B

TOTAL: ~34 h. T5 no depende de Supabase: es el tier que se adelanta
si las claves tardan o si el proyecto de Supabase no está listo.
```

---

## 🎯 TIER 1 · Preparación y contrato de entorno

**Duración:** 2-3 h · **Riesgo:** bajo · **Bloquea:** T2, T3, T4

### T1.1 · Claves y RTT (45 min)

Rellenar las 6 variables de §0 en `.env`. Después, medir — no suponer:

```python
# scripts/verificar_supabase.py
import os, time, statistics, psycopg
from dotenv import load_dotenv; load_dotenv()

with psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None) as c:
    lat = []
    for _ in range(20):
        t = time.perf_counter()
        c.execute("select 1").fetchone()
        lat.append((time.perf_counter() - t) * 1000)
    print(f"RTT p50 {statistics.median(lat):.0f} ms · p95 {sorted(lat)[18]:.0f} ms")
    print(c.execute("select current_user, version()").fetchone())
```

> `prepare_threshold=None` es obligatorio con el pooler de **transacciones**: psycopg3
> prepara sentencias por defecto y pgbouncer en modo transaction no las conserva entre
> checkouts. Sin esto aparecen errores intermitentes `prepared statement "_pg3_0"
> already exists` que cuesta horas diagnosticar.

**Gate T1.1:** `RTT p95 < 300 ms`. Por encima de 500 ms hay que rehacer la cuenta de
§9-R1 antes de seguir: cada run hace entre 8 y 12 viajes a la base.

### T1.2 · Cómo se verifica el JWT (30 min)

```bash
curl -s "$SUPABASE_URL/auth/v1/.well-known/jwks.json"
```

- Devuelve `keys` con contenido → **firma asimétrica**: se verifica por JWKS, no hace
  falta `SUPABASE_JWT_SECRET`, y la clave se puede rotar sin tocar el backend.
- Devuelve `{"keys":[]}` o 404 → **firma HS256 heredada**: hace falta el
  `SUPABASE_JWT_SECRET` del dashboard.

Anotar el resultado en el encabezado de `adaptadores/auth_supabase.py`. `python-jose`
—ya declarado en `pyproject.toml`— cubre los dos casos.

### T1.3 · Bucket de informes (20 min)

Storage → New bucket → nombre `informes`, **Public: OFF**. Privado no es un detalle:
es lo que convierte `/informes/{id}` de "sirve cualquier PDF por id" (punto 16 de la
auditoría) en "URL firmada de 1 hora para el dueño".

### T1.4 · Entorno (30 min)

```bash
uv add "psycopg[binary,pool]>=3.2"
uv sync
uv run python scripts/verificar_supabase.py
```

Recordatorio de [entornos](README.md): `./venv/` es el entorno de embeddings y no
tiene `fastapi`. Todo lo de S3 corre con `uv`.

### DoD de TIER 1

- [ ] 6 variables presentes en `.env`; `.env.example` actualizado y commiteado
- [ ] `verificar_supabase.py` conecta y reporta **RTT p95 < 300 ms**
- [ ] Modo de verificación de JWT decidido y anotado
- [ ] Bucket `informes` creado y **privado**
- [ ] `uv sync` limpio con `psycopg`

---

## 🗄️ TIER 2 · Esquema y migración de datos

**Duración:** 4 h · **Riesgo:** bajo · **Depende de:** T1

### T2.1 · `supabase/migraciones/001_esquema_s3.sql`

```sql
-- Perfil de aplicación colgado de auth.users. Sin organizaciones (MVP).
create table public.perfiles (
  id          uuid primary key references auth.users(id) on delete cascade,
  email       text not null,
  plan        text not null default 'gratuito' check (plan in ('gratuito','premium')),
  creado_en   timestamptz not null default now()
);

create table public.ejecuciones (
  id                uuid primary key,
  usuario_id        uuid not null references auth.users(id),
  insumo_texto      text not null,
  snapshot_version  text not null,
  estado            text not null check (estado in ('ok','parcial','reformular','error')),
  motivo_parcial    text check (motivo_parcial in ('paywall','pocos_productos','presupuesto')),
  creado_en         timestamptz not null default now()
);

create table public.etapas_ejecucion (
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

create table public.cache_llm (
  clave_hash        text primary key,
  etapa             text,
  modelo            text,
  respuesta_json    jsonb not null,
  snapshot_version  text,
  creado_en         timestamptz not null default now()
);

create table public.informes (
  id            uuid primary key,
  ejecucion_id  uuid not null references public.ejecuciones(id) on delete cascade,
  usuario_id    uuid not null references auth.users(id),
  parcial       boolean not null,
  motivo        text,
  ruta_storage  text not null,
  creado_en     timestamptz not null default now()
);

create index on public.ejecuciones (usuario_id, creado_en desc);
create index on public.etapas_ejecucion (ejecucion_id);
create index on public.informes (usuario_id, creado_en desc);

-- Cost-meter por usuario y mes (P13)
create view public.uso_mensual as
select e.usuario_id,
       date_trunc('month', e.creado_en) as mes,
       count(distinct e.id)             as runs,
       coalesce(sum(x.costo_usd), 0)    as costo_usd
from public.ejecuciones e
left join public.etapas_ejecucion x on x.ejecucion_id = e.id
group by 1, 2;

-- RLS activo en las 5 tablas. El backend usa service_role y la salta;
-- esto es defensa en profundidad: si la anon key se filtra, no lee nada.
alter table public.perfiles          enable row level security;
alter table public.ejecuciones       enable row level security;
alter table public.etapas_ejecucion  enable row level security;
alter table public.cache_llm         enable row level security;
alter table public.informes          enable row level security;

create policy p_perfil_propio  on public.perfiles    for select using (id = auth.uid());
create policy p_ejec_propia    on public.ejecuciones for select using (usuario_id = auth.uid());
create policy p_inf_propio     on public.informes    for select using (usuario_id = auth.uid());
-- etapas_ejecucion y cache_llm: sin políticas = deny-all para anon/authenticated.
```

Dos decisiones que quedan fijadas aquí:

- **`etapa` es `text`, no `integer`** — cierra D6 antes de acumular historial. `'2a'` y
  `'2b'` ya son valores legales aunque 2b no se implemente hasta S4.
- **`motivo_parcial` es una columna con `check`**, no un string libre. Es la diferencia
  entre paywall, guard técnico y kill-switch, y es exactamente lo que P06 exige poder
  distinguir. Un enum de tres valores en la base evita que la distinción se pierda en
  una cadena de texto del informe.

### T2.2 · `etl/migrar_sqlite_a_supabase.py`

Lee `agroscout.db` y sube: 54 `ejecuciones`, 94 `etapas_ejecucion`, 47 `cache_llm`. Sin
usuario asociado en el histórico → `usuario_id` del usuario `admin@cite.gob.pe`, que se
crea antes en T4.3; si T4 aún no corrió, se migra con un usuario `sistema` y se
reasigna. El histórico importa poco por su volumen, pero migrarlo prueba el camino de
escritura con datos reales antes de que dependan de él los tests.

### T2.3 · La deuda de esquema del `.db` vivo

Hallazgo al inspeccionar `agroscout.db`: **el archivo vivo está desincronizado del
código**. La tabla real es

```
etapas_ejecucion(ejecucion_id, etapa INTEGER, entrada_json, salida_json,
                 duracion_ms, costo_usd, tokens, tokens_entrada, tokens_salida)
```

y [auditoria_sqlite.py:58](adaptadores/auditoria_sqlite.py#L58) inserta además `modelo`
y `snapshot_version`, que **no existen en el archivo**. `CREATE TABLE IF NOT EXISTS` no
migra nada, así que ese INSERT falla contra la base actual. Lo mismo con
[main.py:101](api/main.py#L101): el login hace `SELECT id, password_hash, org_id FROM
usuarios` y la tabla real no tiene `org_id`.

No es un problema a arreglar en SQLite: la migración a Postgres lo resuelve creando el
esquema correcto de una vez. Pero **sí hay que verificarlo**, porque significa que hoy
el login y la auditoría están rotos contra la base que está en el repo, y eso no puede
descubrirse el viernes.

#### Verificado el 2026-08-02 — los dos fallos son reales

Ejecutados contra una copia de `agroscout.db`, ambos revientan al preparar la sentencia:

```
INSERT de auditoria_sqlite.py:58  -> OperationalError: table etapas_ejecucion
                                     has no column named modelo
SELECT del login de api/main.py   -> OperationalError: no such column: org_id
```

Esquema real del archivo, confirmado con `pragma table_info`:

| Tabla | Columnas reales | Filas |
|---|---|---|
| `ejecuciones` | id, insumo_texto, snapshot_version, estado, creado_en | 54 |
| `etapas_ejecucion` | ejecucion_id, etapa, entrada_json, salida_json, duracion_ms, costo_usd, tokens, tokens_entrada, tokens_salida | 94 |
| `cache_llm` | clave_hash, etapa, modelo, respuesta_json, snapshot_version, creado_en | 47 |
| `usuarios` | id, email, password_hash | 1 |

Tres cosas que la inspección añadió a lo que el plan ya sospechaba:

1. **`etapa` está guardada como entero, no como texto**, pese a que la columna se declara
   `TEXT` y `auditoria_sqlite.py` hace `str(etapa)`. Es la huella de que esas 94 filas
   las escribió una versión anterior del adaptador: otra confirmación de que el archivo
   del repo y el código llevan tiempo separados.
2. **`cache_llm` tiene `etapa`, `modelo` y `snapshot_version` en NULL en las 47 filas.**
   Es el punto 12 de la auditoría, y explica por qué **P02 no se puede probar hoy**: sin
   modelo ni snapshot en la clave, un cache hit no demuestra nada.
3. **`costo_usd` vale 0.0 en las 94 filas**, con 15.766 tokens registrados. No es un
   fallo de la migración — ver más abajo.

**Consecuencia sobre el plan B (R4).** El plan dice que la rama `APP_DB=sqlite` se
conserva funcionando y que es el plan B de la demo. Hoy no lo está: con este archivo, el
login y la auditoría fallan. Arreglarlo son tres `ALTER TABLE ADD COLUMN`, pero **hay que
hacerlo explícitamente en T3.4**, porque la migración a Postgres no lo toca.

#### Hallazgo colateral: el cost-meter mide 0 por un desajuste de claves

`costo_usd` es 0 en todo el histórico porque
[ejecutor.py:46](casos_de_uso/etapas/ejecutor.py#L46) busca la tarifa con la clave
equivocada:

```python
# adaptadores/redactor_glm.py:14 produce claves CON prefijo
modelo_por_etapa = {1: "openai/deepseek-v4-flash", 3: "openai/glm-5.0", ...}

# casos_de_uso/dependencias.py:25 las declara SIN prefijo
tarifas_modelos = {"deepseek-v4-flash": {...}, "glm-5.0": {...}}

tarifa = d.tarifas_modelos.get(modelo, {})   # -> siempre {}
costo_usd = tokens_entrada * tarifa.get("entrada_por_1k", 0) / 1000 + ...  # -> 0.0
```

El `.get(clave, 0)` convierte un modelo desconocido en tarifa cero sin avisar, así que el
sistema lleva desde S1 registrando tokens y cobrando 0 US$.

**Por qué importa aquí y no en T6:** el DoD de T6.4 es *"`costo_mes_usd` de `/uso` ==
`sum(costo_usd)` de las etapas del mes"*. Con el bug presente, esa igualdad se cumple
—`0 == 0`— y **P13 sale verde sin medir nada**. Lo mismo vale para los presupuestos de
T6.3: ningún tope se supera nunca si todo cuesta cero, de modo que **P12 también sería un
verde vacío**.

Sitio natural para arreglarlo: **T5.4**, que ya entra en `ejecutor.py` a cambiar
`num_etapa` de `int` a `str`. La corrección es normalizar la clave (quitar el prefijo
`openai/`) y, sobre todo, **dejar de tragarse el fallo**: un modelo sin tarifa debe
registrarse como tal, no como coste cero.

### DoD de TIER 2

- [ ] 5 tablas + 1 vista creadas; `select * from pg_policies` devuelve **3 políticas**
- [ ] `rowsecurity = true` en las **5** tablas (`pg_tables`)
- [ ] Conteos migrados **idénticos**: 54 / 94 / 47
- [ ] 0 filas con `costo_usd is null`; 0 filas con `etapa` fuera del `check`
- [ ] Documentado que el `agroscout.db` del repo tenía esquema viejo

---

## 🔌 TIER 3 · Adaptadores Postgres + Storage

**Duración:** 6 h · **Riesgo:** medio (latencia) · **Depende de:** T2

Los **puertos no se tocan**. `Auditoria`, `CacheLLM` y `RepositorioInformes` siguen
igual y entran adaptadores nuevos. Es la prueba de que la arquitectura hexagonal de S1
paga: cambiar el motor de estado no toca ni `dominio/` ni `casos_de_uso/`.

### T3.1 · `adaptadores/db.py`

```python
from psycopg_pool import ConnectionPool
_pool = ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=5,
                       kwargs={"prepare_threshold": None}, open=True)
```

Pool obligatorio: abrir conexión TLS por consulta contra São Paulo son ~200 ms de
handshake que se pagarían 10 veces por run.

### T3.2 · `auditoria_postgres.py` + `cache_postgres.py`

Traducción mecánica del SQL de los adaptadores SQLite, con tres cambios:

1. `registrar_etapa` recibe `usuario_id` (viaja en `Ejecucion`).
2. `iniciar` acepta `usuario_id`; `cerrar(estado, motivo_parcial)` nueva — hoy el estado
   se escribe `'ok'` al empezar y nunca se corrige.
3. `cache_llm` **llena de verdad** `etapa`, `modelo` y `snapshot_version` (punto 12 de
   la auditoría: hoy quedan siempre en NULL) → habilita **P02**.

### T3.3 · `repositorio_informes_supabase.py`

```
POST {URL}/storage/v1/object/informes/{ejecucion_id}.pdf     (service key)
POST {URL}/storage/v1/object/sign/informes/{...}  {"expiresIn": 3600}
```

El PDF se sigue generando con WeasyPrint en local y se sube; el endpoint devuelve la
URL firmada, no el archivo. Fila en `informes` con `usuario_id` y `ruta_storage`.

### T3.4 · Conmutador y medición

`APP_DB=supabase|sqlite` decide qué adaptadores arma `api/main.py`. La rama `sqlite` se
conserva **funcionando** — es el plan B de la demo (D5) y el modo en que corren los
tests que no deben depender de la red.

```python
# test/test_sobrecoste_estado.py
# Mide el tiempo de un run completo con APP_DB=sqlite vs APP_DB=supabase,
# con el cache LLM caliente para aislar el estado de la latencia del LLM.
```

**Gate T3.4: sobrecoste < 1 s por run.** Si se pasa, el orden de mitigación es:
(a) `cache_llm` se queda en SQLite local —es cache, no estado de negocio—;
(b) las escrituras de `etapas_ejecucion` se acumulan y se vuelcan en un solo
`executemany` al cerrar el run.

#### Medido el 2026-08-02 — **642 ms**, gate superado

El run completo no sirve para medirlo tal cual: lo dominan la carga del modelo de
embeddings y LanceDB, ~20 s idénticos en las dos ramas, donde un segundo de
diferencia se pierde en el ruido. Así que `test/test_sobrecoste_estado.py` envuelve los
tres puertos en un cronómetro y suma el tiempo pasado dentro de sus métodos:

| puerto | sqlite | supabase | delta |
|---|---|---|---|
| auditoría | 33 ms | 136 ms | +103 ms |
| cache | 7 ms | 228 ms | +221 ms |
| informes | 120 ms | 437 ms | +318 ms |
| **total** | **159 ms** | **801 ms** | **+642 ms** |

Llegar aquí costó tres correcciones, todas de viajes de ida y vuelta, no de código
lento. La primera medición dio **1,96 s**.

1. **`autocommit=True` en el pool.** Sin él, cada `with pool().connection()` abre
   transacción implícita y el `COMMIT` del cierre es un viaje más.
2. **Cliente `httpx` persistente en Storage.** `httpx.post` suelto abre conexión nueva
   y paga handshake TLS completo, dos veces por run. El puerto de informes bajó de
   1.310 ms a 318 ms. Los PDF pesan 13 KB: nunca fue ancho de banda.
3. **El run entero en una sentencia.** Aquí estaba el hallazgo menos obvio:
   `conexion.transaction()` fuerza un sync que **rompe el pipeline**, de modo que
   `BEGIN` y `COMMIT` se cobran cada uno su viaje. Medido con RTT de 112 ms:

   ```
   pipeline > transaction > insert + executemany ...... 450 ms  (4 viajes)
   pipeline > insert + executemany, sin transaction ... 113 ms  (1 viaje, NO atómico)
   una sentencia: CTE que inserta la cabecera +
                  unnest que expande las etapas ....... 114 ms  (1 viaje, atómico)
   ```

   Se eligió la tercera: una sentencia única es atómica por definición, así que no hace
   falta transacción explícita para que cabecera y etapas entren juntas.

**Consecuencia de orden.** Con la cabecera escribiéndose al cerrar, `informes` —que
tiene FK a `ejecuciones`— ya no se puede emitir dentro del `try`. `evaluar_insumo`
cierra en el `finally` y emite **después**, fuera del bloque.

**Margen para T5.** Dos etapas más son dos lecturas de cache más, ~220 ms, lo que deja
el sobrecoste en ~860 ms. Sigue bajo el gate, pero es el número a vigilar; la
mitigación (a) queda sin usar y vale 221 ms si hiciera falta.

### DoD de TIER 3

- [ ] Run completo escribe en Supabase; las filas se ven en el Table Editor
- [ ] Suite de S2 **18/18** verde con `APP_DB=sqlite` (sin regresión)
- [ ] Suite verde con `APP_DB=supabase`
- [ ] **Sobrecoste de estado < 1 s por run**, medido y anotado
- [ ] PDF en el bucket; URL firmada abre; la URL sin firmar da 400
- [ ] `cache_llm` con `etapa`, `modelo` y `snapshot_version` no nulos → **P02**

---

## ✂️ TIER 5 · Separación de las etapas 4 y 5

**Duración:** 6 h · **Riesgo:** medio · **⚡ No depende de Supabase**

Se ejecuta en paralelo con T3/T4 y es el tier que se adelanta al lunes si las claves
tardan. Cierra la deuda de §2.

### T5.1 · Tres contratos donde había uno

```python
# dominio/insight_mercado.py  (etapa 3, gratuito)
class InsightDeMercado(BaseModel):
    cobertura: Literal["baja","media","alta"]
    resumen: str
    formatos_comunes: list[str]
    citas: list[str]
    nota_regulatoria: str | None   # D4: párrafo básico, se queda en gratuito

# dominio/hipotesis_formulacion.py  (etapa 4, premium)
class HipotesisFormulacion(BaseModel):
    hipotesis: str
    ingredientes_probables: list[str]
    procesos_sugeridos: list[str]
    citas: list[str]

# dominio/dossier_regulatorio.py  (etapa 5, premium)
class DossierRegulatorio(BaseModel):
    restricciones: list[str]
    citas: list[CitaRegulatoria]   # texto + fuente + url + fecha, o null
    sin_dato: bool = False
```

Esto cierra **D4** por la vía recomendada en `PLAN-MVP-v2.md`: párrafo regulatorio
básico gratis (hoy ya funciona; quitarlo debilitaría la demo), dossier con citas
verificables en premium.

### T5.2 y T5.3 · Las etapas

`casos_de_uso/etapas/formular_hipotesis.py` y `verificar_regulacion.py`, ambas invocadas
por `etapa()` → cada una con su cache, su auditoría, su modelo y **su costo propio**.
El armado del contexto regulatorio de
[evaluar_insumo.py:17-23](casos_de_uso/evaluar_insumo.py#L17) se mueve **dentro** de la
etapa 5; deja de estar fuera del envoltorio.

`InformeScout`, la plantilla del PDF y `Result.vue` pasan a recibir tres objetos
opcionales en vez de uno. En el informe gratuito, formulación y dossier llegan como
`None` y la plantilla los sustituye por el bloque de paywall.

### T5.4 · Numeración

`num_etapa` pasa de `int` a `str` en `ejecutor.py` y en las llamadas. Regenerar
`contratos/` con `scripts/generar_contratos.py`.

### DoD de TIER 5

- [ ] Run **premium** → **5 filas** en `etapas_ejecucion`: `'1','2','3','4','5'`
- [ ] Las 5 con `modelo` distinto de null y **`costo_usd > 0` en las 4 filas LLM**
- [ ] Run **gratuito** → **3 filas**; ninguna llamada al modelo de etapa 4
- [ ] Segundo run idéntico → **0 llamadas LLM** (cache hit en las 5) → **P02**
- [ ] `contratos/` regenerado con los 3 esquemas nuevos
- [ ] Golden set de S2 sigue **5/5**

---

## 🔐 TIER 4 · Auth Supabase

**Duración:** 5 h · **Riesgo:** medio · **Depende de:** T1, T2

### T4.1 · `adaptadores/auth_supabase.py`

Verifica el JWT emitido por Supabase con el modo decidido en T1.2 (JWKS cacheado en
memoria, o HS256 con el secreto). Valida `exp`, `aud = "authenticated"` e `iss`.
Devuelve `sub` (uuid del usuario) y `email`. `get_current_user` en `api/main.py` pasa a
usarlo.

### T4.2 · `/token` como proxy

```python
POST {SUPABASE_URL}/auth/v1/token?grant_type=password
     headers: apikey: {ANON_KEY}
     body:    {"email": ..., "password": ...}
```

El endpoint conserva **la misma firma de request y response** que hoy, así que
[Login.vue](frontend/src/components/Login.vue) no cambia y la SPA no necesita ninguna
clave de Supabase. El token que devuelve ya es el de Supabase (vida ~1 h; suficiente
para una demo de 15 min). Se devuelve también `refresh_token` para no cerrar la puerta.

`adaptadores/autenticacion.py` (bcrypt + JWT propio) **se conserva** pero solo lo usa la
rama `APP_DB=sqlite`. `update_schema.py`, que inserta contraseñas demo en el repo, se
borra.

### T4.3 · `perfiles` y usuarios demo

Trigger que crea el perfil al alta:

```sql
create function public.crear_perfil() returns trigger language plpgsql security definer as $$
begin
  insert into public.perfiles (id, email) values (new.id, new.email);
  return new;
end $$;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.crear_perfil();
```

`scripts/crear_usuarios_demo.py` → `POST /auth/v1/admin/users` con la service key:

| Usuario | Plan |
|---|---|
| `demo-gratuita@cite.gob.pe` | `gratuito` |
| `demo-premium@cite.gob.pe` | `premium` |

Las contraseñas se pasan por argumento y **no se escriben en el repo** — es el punto 14
de la auditoría (`cite2026` en texto plano en `update_schema.py`).

### T4.4 · Cerrar `/informes/{id}`

`GET /informes/{id}` deja de leer del disco: consulta `informes` filtrando por
`usuario_id = sub` y devuelve la URL firmada. Si el informe es de otro usuario →
**404** (no 403: no confirma que el id existe).

### DoD de TIER 4

- [ ] Login de los 2 usuarios demo devuelve un JWT de Supabase válido
- [ ] Token manipulado, expirado o ausente → **401** en los **4** endpoints
- [ ] `demo-gratuita` pidiendo un informe de `demo-premium` → **404**
- [ ] `grep -rn "cite2026\|premium2026\|demo2026"` → **0 resultados**
- [ ] `perfiles` con 2 filas y el plan correcto

---

## 💰 TIER 6 · Paywall, cuotas y kill-switch

**Duración:** 6 h · **Riesgo:** bajo · **Depende de:** T4, T5

### T6.1 · `casos_de_uso/politica_suscripcion.py`

```python
@dataclass(frozen=True)
class Entitlement:
    plan: str
    etapas_permitidas: frozenset[str]   # gratuito: {'1','2','3'}
    tope_mes_usd: float                 # gratuito: 2.0 · premium: 10.0

def entitlement_de(perfil) -> Entitlement: ...
```

Vive en la **frontera de aplicación**, no en el dominio (ADR-001 §2.4: el paywall se
resuelve por composición de casos de uso, no filtrando filas).

### T6.2 · Dos composiciones

```python
async def generar_mapa_comercial(texto, d, usuario):   # 1 · 2 · 3
async def generar_dossier(texto, d, usuario):          # + 4 · 5
```

`POST /consultas` elige según el entitlement. El usuario gratuito recibe **200 con
informe parcial** y `motivo_parcial='paywall'` — no un 402, no un error. Distinto del
guard técnico `n_directos ≤ 2` → `motivo_parcial='pocos_productos'`, que sigue
existiendo tal cual en [evaluar_insumo.py:26](casos_de_uso/evaluar_insumo.py#L26). **Un
run puede tener los dos motivos y el informe debe decir cuál aplica**: es literalmente
lo que P06 comprueba.

### T6.3 · Presupuestos y kill-switch

`casos_de_uso/presupuesto.py`, consultado **antes de cada etapa LLM**:

| Nivel | Variable | Al superarse |
|---|---|---|
| Run | `PRESUPUESTO_RUN_USD` (0.25) | se saltan las etapas restantes |
| Usuario/mes | `PRESUPUESTO_USUARIO_MES_USD` (2) | idem, desde `uso_mensual` |
| Global/mes | `PRESUPUESTO_GLOBAL_MES_USD` (10) | kill-switch: nadie ejecuta LLM |

Al degradar: la etapa devuelve su contrato con `sin_dato=True`, el run cierra en
`parcial` con `motivo_parcial='presupuesto'`, y **la respuesta es 200**. Sin reintento
automático. El principio del ADR: *degrada a "sin dato", nunca error*.

### T6.4 · `GET /uso`

Reemplaza a `/ejecucion/{id}/tokens`, que además hoy **no filtra por usuario**:
cualquiera con un id ajeno ve su consumo.

```json
{"mes": "2026-08", "plan": "gratuito",
 "costo_mes_usd": 0.0143, "tope_usd": 2.0, "runs": 7,
 "ultimo_run": {"id": "...", "costo_usd": 0.0031,
   "etapas": [{"etapa":"1","modelo":"deepseek-v4-flash","costo_usd":0.0002}, ...]}}
```

### DoD de TIER 6

- [ ] **P06**: gratuito → parcial + `paywall`; premium mismo insumo → 5 etapas completas
- [ ] **P06**: insumo con `n_directos ≤ 2` en cuenta premium → `pocos_productos`, **no** paywall
- [ ] **P13**: `costo_mes_usd` de `/uso` == `sum(costo_usd)` de las etapas del mes
- [ ] **P12 parcial**: con `PRESUPUESTO_GLOBAL_MES_USD=0` → **HTTP 200**, run `parcial`,
      `motivo_parcial='presupuesto'`, **0 llamadas al LLM**
- [ ] `/uso` de un usuario nunca incluye runs de otro

---

## 🖥️ TIER 7 · Frontend, cierre y auditoría

**Duración:** 5 h · **Depende de:** todo

### T7.1 · SPA

- `Result.vue`: cuando `motivo_parcial === 'paywall'`, tarjeta con lo que falta
  (formulación + dossier) en vez de secciones vacías. Cuando es `'pocos_productos'`, el
  mensaje del guard técnico de siempre. Cuando es `'presupuesto'`, "sin dato".
- `TokenUsage.vue` → barra de cuota mensual (`costo_mes_usd / tope_usd`) + desglose por
  etapa con su modelo. Es el bloque 6 del guion: *"el gasto está acotado por diseño"*.
- Descarga del PDF por URL firmada.

### T7.2 · `test/test_e2e_s3.py`

| Test | Verifica |
|---|---|
| `test_esquema_supabase` | 5 tablas, RLS activo en las 5, 3 políticas |
| `test_auth_rechaza_token_invalido` | 401 en los 4 endpoints |
| `test_aislamiento_por_usuario` | informe ajeno → 404 |
| `test_paywall_gratuito` | 3 etapas, parcial, `paywall` |
| `test_premium_completo` | 5 etapas, no parcial |
| `test_guard_tecnico_no_es_paywall` | `pocos_productos` en cuenta premium |
| `test_cache_hit_sin_llm` | segundo run: 0 llamadas → **P02** |
| `test_costo_cuadra` | `/uso` == suma en base → **P13** |
| `test_killswitch_degrada_sin_error` | tope 0 → 200 parcial → **P12** |
| `test_plan_b_sqlite` | `APP_DB=sqlite` completa un run sin red |

### T7.3 y T7.4 · Cierre

`TIER7-S3-COMPLETADO.md` con el formato de S2 (gates obtenidos, deuda abierta), README
actualizado con el arranque contra Supabase, y **ensayo del guion de 15 min con el
bloque 5 en su versión nueva** (§1).

### DoD de TIER 7

- [ ] E2E de S3 verde (10/10) y suite de S2 sin regresión (18/18)
- [ ] Paywall visible en la SPA, distinguible del guard técnico
- [ ] Barra de cuota con datos reales
- [ ] Plan B verificado: `APP_DB=sqlite` + `AGROSCOUT_OFFLINE=1` completa un run
- [ ] Guion ensayado de punta a punta con las 2 cuentas

---

## 8. Matriz de cierre de la semana

| Gate | Número exacto | Tier |
|---|---|---|
| RTT a Supabase | p95 < 300 ms | T1 |
| Migración | 54 / 94 / 47 filas idénticas | T2 |
| RLS | 5 tablas con `rowsecurity=true` | T2 |
| Sobrecoste de estado | < 1 s por run | T3 |
| Etapas premium | 5 filas, 4 con costo > 0 | T5 |
| Etapas gratuitas | 3 filas | T5 |
| Cache hit | 0 llamadas LLM en el 2º run (**P02**) | T5 |
| Auth | 401 en 4 endpoints con token inválido | T4 |
| Aislamiento | informe ajeno → 404 | T4 |
| Paywall | `paywall` ≠ `pocos_productos` ≠ `presupuesto` (**P06**) | T6 |
| Cost-meter | `/uso` cuadra con la base (**P13**) | T6 |
| Kill-switch | tope 0 → 200 parcial, 0 llamadas (**P12** parcial) | T6 |
| Sin regresión | golden set 5/5, suite 18/18 | T7 |

---

## 9. Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| **R1** | **Latencia.** 8-12 viajes a Supabase por run desde Perú. A 150 ms son ~1,5 s añadidos a un run que hoy tarda ~10 s | Medir en T1.1 **antes** de escribir adaptadores. Pool de conexiones. Si el gate de T3.4 falla: cache en SQLite local y volcado por lotes de la auditoría |
| **R2** | **T5 es trabajo real de LLM, no fontanería.** Dos prompts nuevos que hay que ajustar hasta que devuelvan JSON válido contra el schema | Empezar T5 el lunes en paralelo con T2/T3: es el único tier con varianza de calidad, no solo de tiempo |
| **R3** | **Supabase Auth cambió de nomenclatura de claves** (`anon`/`service_role` → `sb_publishable_`/`sb_secret_`) y de firma (HS256 → JWKS) | T1.2 lo resuelve mirando el endpoint, no la documentación. El código soporta los dos modos |
| **R4** | **Nadie ha corrido la API contra el `agroscout.db` del repo últimamente**: su esquema no coincide con el código (§T2.3) | Verificarlo en T2.3. La rama sqlite es el plan B de la demo: si está rota, el plan B no existe |
| **R5** | **Se pierde el bloque 5 del guion** (RLS multi-organización en vivo) | Decidido y declarado en §1. Si el CDR gira sobre el contrato multi-cooperativa, reconsiderar: RLS por `org_id` sobre estas mismas tablas es ~1 día extra, no una semana |
| **R6** | El pooler de transacciones rompe las sentencias preparadas de psycopg3 | `prepare_threshold=None` desde la primera línea (T1.1) |

---

## 10. Calendario

| Día | Tiers | Horas |
|---|---|---|
| **Lun 3** | T1 (mañana) · T2 (tarde) · **arrancar T5.1** | 7 |
| **Mar 4** | T3 completo · T5.2 | 8 |
| **Mié 5** | T4 completo · T5.3-T5.4 | 8 |
| **Jue 6** | T6 completo | 6 |
| **Vie 7** | T7 completo | 5 |

**Orden de sacrificio si la semana se desborda** (declarándolo, como en S2):

1. Migración del histórico (T2.2) — 54 ejecuciones de prueba no valen medio día
2. Presupuesto por run (T6.3) — quedarse con usuario/mes + global
3. Barra de cuota en la SPA (T7.1) — mostrar el número, no el gráfico
4. **No se sacrifica T5**: sin separación de etapas no hay paywall, y sin paywall no hay
   Semana 3

---

## 11. Después de S3

**Semana 4** (`PLAN-MVP-v2.md` §7): entidad `ProductoEnMercado` + `catalogo_comercial`,
etapa **2b** sobre el snapshot (N1), puerto `DescubrimientoComercial` con N2/N3 como
stubs declarados, P04 y P05, panel mínimo, CI y ensayo final.

El esquema de T2 ya la contempla: `'2b'` es un valor legal de `etapa` desde hoy.
