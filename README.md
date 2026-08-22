# AgroScout IA Lite MVP

Proyecto de demostración de evaluación de insumos agrícolas usando Modelos
Fundacionales y arquitecturas locales.

---

## Puesta en marcha

### 1. Entorno

```bash
uv sync
```

`./venv/` es un entorno aparte, solo para embeddings y búsqueda; **no tiene
fastapi**. Todo lo demás corre con `uv`.

### 2. Variables

Copiar [.env.example](.env.example) a `.env` y rellenarlo. Las cuatro claves de
Supabase están explicadas ahí una por una. Para comprobar que el entorno está
bien antes de arrancar nada:

```bash
uv run python scripts/verificar_supabase.py
```

Mide el RTT, decide cómo se verifican los JWT y avisa si `DATABASE_URL` apunta a
la conexión directa en vez de al pooler. No imprime el valor de ninguna clave.

### 3. Esquema y cuentas

```bash
uv run python scripts/aplicar_migracion.py supabase/migraciones/001_esquema_s3.sql
uv run python scripts/aplicar_migracion.py supabase/migraciones/002_cache_hit.sql
uv run python scripts/aplicar_migracion.py supabase/migraciones/003_perfiles_trigger.sql
uv run python scripts/crear_usuarios_demo.py --generar
```

### 4. Arrancar

En Windows, los dos scripts de la raiz lo hacen todo:

```bat
iniciar.bat    :: comprueba requisitos, abre API y SPA en su ventana, espera y abre el navegador
detener.bat    :: cierra esas ventanas y libera :8001 y :3000
```

`iniciar.bat worker` levanta ademas el worker de Procrastinate (los periodicos de
las 03:00 y 04:00); `iniciar.bat recarga` arranca la API con `--reload`.

A mano, una terminal por servicio:

```bash
uv run uvicorn api.main:app --host 0.0.0.0 --port 8001   # backend en :8001
cd frontend && npx vite --host 0.0.0.0 --port 3000       # SPA en :3000
```

`npm run dev` a secas sirve en :5173, el puerto por defecto de Vite. Los dos
puertos estan en la lista de CORS, pero la SPA solo se ve desde otra maquina si
se arranca con `--host`.

---

## Cuentas de acceso

Las credenciales **no se publican en el repositorio**.

| Cuenta | Plan | Qué ve |
|---|---|---|
| `demo-gratuita@cite.gob.pe` | gratuito | mapa comercial: etapas 1, 2a, 2b y 3 |
| `demo-premium@cite.gob.pe` | premium | además hipótesis de formulación y dossier regulatorio |

`crear_usuarios_demo.py --generar` deja las contraseñas en `.env.local`, que está
en `.gitignore`. Para fijarlas tú mismo, usa `--password-gratuita` y
`--password-premium`. Es idempotente: si se pierden, se vuelve a ejecutar.

---

## Los dos modos de ejecución

`APP_DB` decide dónde vive el estado de aplicación.

| | `APP_DB=supabase` | `APP_DB=sqlite` |
|---|---|---|
| Estado | Postgres gestionado | `agroscout.db` local |
| Auth | Supabase Auth (JWT ES256, verificado por JWKS) | JWT propio de S1 |
| Informes | Storage privado + URL firmada de 1 h | archivo en `informes/` |
| Necesita red | sí | **no** |

### Plan B de la demo

`APP_DB=sqlite` + `AGROSCOUT_OFFLINE=1` completa un run **sin conexión**. Para que
funcione hay que bajarse antes el cache de respuestas, con red:

```bash
uv run python scripts/sembrar_cache_local.py
```

Sin ese paso el plan B no puede terminar un run: sin red no hay modelo al que
llamar, así que las respuestas tienen que estar ya en el archivo local.

---

## Pruebas

```bash
uv run python -m pytest test/ -q          # suite completa
uv run python evals/runner_s2.py          # golden set de los 5 insumos piloto
```

`test/test_e2e_s3.py` y `test/test_sobrecoste_estado.py` se saltan solos si no hay
credenciales de Supabase o si `AGROSCOUT_OFFLINE=1`.

---

## Documentos

| Documento | Contenido |
|---|---|
| [PLAN-TIERS-S3.md](PLAN-TIERS-S3.md) | El plan de la semana, con las mediciones anotadas sobre cada tier |
| [TIER5-S3-COMPLETADO.md](TIER5-S3-COMPLETADO.md) | Separación de las etapas 4 y 5 |
| [TIER7-S3-COMPLETADO.md](TIER7-S3-COMPLETADO.md) | Cierre de la Semana 3 y deuda abierta |
| [ADR-001](ADR-001-nucleo-comercial-y-paywall.md) · [ADR-002](ADR-002-motor-inteligencia-mercado.md) · [ADR-003](ADR-003-escalado-multitenant.md) | Decisiones de arquitectura |
