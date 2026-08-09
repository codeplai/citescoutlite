# Semana 1 · PREPARACIÓN Y SETUP SUPABASE (MVP)

**Objetivo:** Stack operativo con Supabase: Postgres manejado, auth, observabilidad básica.

**Duración:** 2-3 días · **Equipo:** Backend (1) + DevOps (1)

---

## ITEMS SEMANA 1

### 1.1 CREAR PROYECTO SUPABASE
- **Descripción:** Instancia de Postgres manejada en Supabase (gratis tier ok para MVP)
- **Tareas:**
  - [ ] Ir a https://supabase.com → Create new project
  - [ ] Nombre: `agroscout-mvp-v3`
  - [ ] Región: sa-east-1 (São Paulo, cerca de Perú) o us-east-1
  - [ ] Password: guardar seguro (acceso directo a DB)
  - [ ] Esperar deployment (~2 min)
  - [ ] Copiar credenciales:
    - [ ] `SUPABASE_URL` (ej: https://xxx.supabase.co)
    - [ ] `SUPABASE_KEY` (anon key público)
    - [ ] `SUPABASE_DB_URL` (postgres://user:pass@db.xxx.supabase.co:5432/postgres)
  - [ ] Test: `psql $SUPABASE_DB_URL -c "SELECT version();"`
- **Duración:** 0.5 días
- **Dependencias:** Ninguna
- **DoD:** Proyecto creado, credenciales funcionales, psql conecta

---

### 1.2 CREAR SCHEMA Y TABLAS EN SUPABASE
- **Descripción:** Estructura de datos v3 en Postgres Supabase
- **Tareas:**
  - [ ] En Supabase SQL editor (o via `psql`), crear tablas:
    - [ ] `consultas` (hereda de v2: id, insumo, país, usuario, created_at)
    - [ ] `etapas_ejecucion` (ahora etapa es TEXT, no INT: '1','2a','2b','3','4','5','6')
    - [ ] `cache_llm` (clave_hash, etapa, modelo, respuesta_json, tokens_in/out)
    - [ ] `informes` (hereda: consulta_id, pdf_url, created_at)
    - [ ] `usuarios` (id, email, tenant_id, rol, created_at)
    - [ ] `organizaciones` (id, nombre, plan, nivel_maximo_costo)
    - [ ] `audit_log` (evento, usuario, tabla, timestamp, detalles)
  - [ ] Índices: (consulta_id), (usuario_id), (etapa), (modelo)
  - [ ] RLS: políticas básicas (anyone can select own tenant)
  - [ ] Test: `SELECT COUNT(*) FROM consultas`
- **Duración:** 1 día
- **Dependencias:** Supabase (1.1)
- **DoD:** Schema creado, tablas visibles en Supabase studio, RLS básico

---

### 1.3 MIGRAR DATOS V2 A SUPABASE
- **Descripción:** Traer dump de v2 (SQLite) a Postgres Supabase
- **Tareas:**
  - [ ] Exportar de v2 SQLite: `sqlite3 agroscout.db ".dump" > v2_dump.sql`
  - [ ] Convertir SQL syntax (SQLite → Postgres):
    - [ ] Opción A: manual (replace AUTOINCREMENT, etc.)
    - [ ] Opción B: usar herramienta pgloader o Python script
  - [ ] Restaurar en Supabase:
    - [ ] Opción A: pegar SQL en Supabase editor (si pequeño)
    - [ ] Opción B: `psql $SUPABASE_DB_URL < v2_dump_converted.sql`
  - [ ] Validar: row counts por tabla (consultas, etapas_ejecucion, informes)
  - [ ] Copiar `datasets/2026-07/` a carpeta local `./datasets/` (para desarrollo)
  - [ ] Test: query en Supabase: `SELECT COUNT(*) FROM consultas`
- **Duración:** 0.75 días
- **Dependencias:** Supabase schema (1.2)
- **DoD:** Datos v2 en Supabase, row counts verificados

---

### 1.4 SETUP OBSERVABILIDAD (SUPABASE DASHBOARD + PROMETHEUS LOCAL OPCIONAL)
- **Descripción:** Métricas de aplicación + logs Supabase
- **Tareas:**
  - [ ] Supabase nativo:
    - [ ] Ir a Supabase studio → "Database" → ver tamaño, conexiones, queries lentas
    - [ ] Habilitar "Postgres logs" si needed (Settings → Logs)
  - [ ] Prometheus local (optional, para metrics de app):
    - [ ] Docker: `docker run -d -p 9090:9090 prom/prometheus`
    - [ ] Config: `/prometheus.yml` que scrape FastAPI (`:8000/metrics`)
  - [ ] Grafana local (optional):
    - [ ] Docker: `docker run -d -p 3000:3000 grafana/grafana`
    - [ ] Conectar a Prometheus datasource
    - [ ] Crear 2 dashboards básicos: API metrics, aplicación health
  - [ ] Test: acceder a Supabase studio, ver stats
- **Duración:** 0.75 días
- **Dependencias:** Supabase (1.1), Docker (opcional)
- **DoD:** Supabase studio visible, Prometheus/Grafana opcional pero funcional

---

### 1.5 CONFIGURAR .ENV.LOCAL Y PYPROJECT.TOML
- **Descripción:** Variables de entorno y dependencias para v3
- **Tareas:**
  - [ ] Crear `.env.local` (NO commitear):
    ```
    SUPABASE_URL=https://xxx.supabase.co
    SUPABASE_KEY=<anon-key-from-supabase>
    SUPABASE_DB_URL=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres
    HUAWEI_MAAS_API_KEY=<token>
    TAVILY_API_KEY=<token>
    BRIGHT_DATA_KEY=<token>
    REDIS_URL=redis://localhost:6379
    DEBUG=true
    ```
  - [ ] Actualizar `pyproject.toml` con dependencias:
    ```toml
    [dependencies]
    supabase-py = "^0.3"
    procrastinate = "^2.0"
    duckdb = "^0.8"
    pydantic-ai = "^0.1"
    trafilatura = "^1.6"
    beautifulsoup4 = "^4.12"
    ```
  - [ ] Crear `.env.example` (SIN keys reales) en git
  - [ ] `uv sync` para instalar
- **Duración:** 0.5 días
- **Dependencias:** Supabase (1.1)
- **DoD:** `.env.local` funciona, `uv sync` sin errores

---

### 1.6 SETUP PROCRASTINATE WORKER (SOBRE SUPABASE)
- **Descripción:** Queue de jobs async sobre Postgres Supabase
- **Tareas:**
  - [ ] Instalar procrastinate SDK: ya en `pyproject.toml` (1.5)
  - [ ] Configurar connector en `config.py`:
    ```python
    import procrastinate
    app = procrastinate.AiopgConnector(SUPABASE_DB_URL)
    ```
  - [ ] Crear scripts en `scripts/`:
    - [ ] `start_worker.py`: inicia worker (conecta a Supabase, listen forever)
    - [ ] `test_job.py`: enqueue job de prueba
  - [ ] Test: 
    - [ ] `python scripts/test_job.py` → encola job
    - [ ] Verificar en Supabase SQL: `SELECT * FROM procrastinate_jobs` (debe haber 1 fila)
  - [ ] Iniciar worker: `python scripts/start_worker.py` (en tmux/screen/otra terminal)
- **Duración:** 0.5 días
- **Dependencias:** Supabase (1.1), .env.local (1.5)
- **DoD:** Worker corriendo, jobs enqueueable en Supabase

---

### 1.7 SETUP DUCKDB LOCAL (PARA TENDENCIAS)
- **Descripción:** Archivo local .duckdb para analytics de tendencias (no Supabase)
- **Tareas:**
  - [ ] Crear archivo: `./data/shelf_facts.duckdb`
  - [ ] Schema inicial (vacío, poblado en S3):
    ```python
    import duckdb
    db = duckdb.connect('data/shelf_facts.duckdb')
    db.execute('''
      CREATE TABLE IF NOT EXISTS shelf_facts_quarterly (
        year_quarter VARCHAR, insumo VARCHAR, tienda_id VARCHAR, 
        producto_ean VARCHAR, precio_promedio FLOAT
      )
    ''')
    ```
  - [ ] Test: insert dummy data, query rápida
- **Duración:** 0.25 días
- **Dependencias:** DuckDB en pyproject.toml (1.5)
- **DoD:** DuckDB file existe, queries funcionan

---

### 1.8 SETUP REDIS LOCAL (CACHÉ OPCIONAL)
- **Descripción:** Cache en memoria para búsquedas (opcional para MVP, requerido S10)
- **Tareas:**
  - [ ] Docker: `docker run -d -p 6379:6379 redis:latest`
  - [ ] Test: `redis-cli ping` → PONG
  - [ ] Conectar en FastAPI después (S10)
- **Duración:** 0.25 días
- **Dependencias:** Docker (opcional)
- **DoD:** Redis corriendo si quieres

---

### 1.9 CREAR ESTRUCTURA DE CARPETAS Y .GITIGNORE
- **Descripción:** Organizar carpetas locales
- **Tareas:**
  - [ ] Crear:
    ```
    ./data/          # DuckDB local
    ./datasets/      # copia local de datasets/2026-07/ (del v2)
    ./logs/          # logs de FastAPI, worker
    ./informes/      # PDFs generados
    ./scripts/       # start_worker.py, test_job.py
    ./tests/fixtures # golden set, test data
    ```
  - [ ] Actualizar `.gitignore`:
    ```
    .env.local
    .env.*.local
    ./data/
    ./logs/
    ./informes/
    __pycache__/
    .venv/
    *.db
    ```
- **Duración:** 0.25 días
- **Dependencias:** Proyecto clonado
- **DoD:** Carpetas existen, .gitignore updated

---

### 1.10 HEALTHCHECK ENDPOINT
- **Descripción:** `/health` que valida Supabase, worker, redis
- **Tareas:**
  - [ ] Endpoint en FastAPI (api/main.py o health.py):
    ```python
    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "supabase": test_supabase_connection(),
            "worker": check_worker_alive(),
            "redis": test_redis() if REDIS_ENABLED else "skipped",
            "timestamp": datetime.now().isoformat()
        }
    ```
  - [ ] Test: `curl http://localhost:8000/health` → 200 con status ok
- **Duración:** 0.25 días
- **Dependencias:** FastAPI app, Supabase (1.1)
- **DoD:** `/health` devuelve OK, conecta a Supabase

---

### 1.11 DOCUMENTACIÓN: SETUP DEV CON SUPABASE
- **Descripción:** Cómo un nuevo dev se monta el stack
- **Tareas:**
  - [ ] Documento: `SETUP_DEV.md`
  - [ ] Secciones:
    - [ ] Prerequisites: Python 3.11+, Docker, Git, Supabase account
    - [ ] Clone: `git clone <repo>`
    - [ ] Setup:
      1. `uv sync`
      2. `cp .env.example .env.local`
      3. Llenar `SUPABASE_*` y `*_API_KEY` (lead dev provee credenciales)
      4. `python scripts/test_supabase_connection.py`
      5. `uvicorn api.main:app --reload`
      6. En otra terminal: `python scripts/start_worker.py`
    - [ ] Verificar: curl http://localhost:8000/health
    - [ ] Links: Supabase studio (https://app.supabase.com), FastAPI (localhost:8000)
  - [ ] Troubleshooting: qué hacer si Supabase conexión falla
- **Duración:** 0.5 días
- **Dependencias:** Todos (1.1-1.10)
- **DoD:** Documento claro, nuevo dev setup en 15 min sin preguntas

---

## DEFINITION OF DONE (S1 SUPABASE)

- [ ] Proyecto Supabase creado, credenciales funcionales
- [ ] Schema creado, tablas visibles en Supabase studio
- [ ] Datos v2 migrados, row counts verificados
- [ ] Observabilidad: Supabase dashboard + Prometheus/Grafana (opcional)
- [ ] .env.local configurado, `uv sync` sin errores
- [ ] Procrastinate worker corriendo, jobs enqueueable
- [ ] DuckDB local file creado, schema básico
- [ ] Redis corriendo (si decidiste hacerlo)
- [ ] Carpetas organizadas, .gitignore updated
- [ ] `/health` endpoint funciona, conecta a Supabase
- [ ] SETUP_DEV.md escrito y testado
- [ ] Todos en equipo pueden reproducir en 15 min

---

## RIESGOS S1

| Riesgo | Mitigación |
|---|---|
| Supabase gratis tiene limitaciones (conexiones, storage) | MVP es pequeño, gratis alcanza; upgrade si necesario |
| Credenciales en `.env.local` no están protegidas | Usar `.gitignore`, .env.example sin keys reales |
| Migración SQLite → Postgres tiene errores de tipo | Test conversión en pequeño subset primero |
| Procrastinate no conecta a Supabase | Verificar DNS, network, SUPABASE_DB_URL syntax |
| Nuevo dev no entiende cómo llenar .env.local | Documento claro + video 2 min demo |

---

## NOTAS

- **Supabase tier:** Gratis funciona para MVP (100 MB storage, 2GB bandwidth/mes). Upgrade a Pro ($25/mes) si necesario
- **Duración:** 2-3 días (mucho más rápido que setup manual de Postgres + backups)
- **Equipo:** 1 backend dev + 1 infra (pueden paralelizar tareas)
- **Decisión clave:** ¿Manejo de DB en Supabase o local? Supabase = menos pain, local = más control. Elegimos Supabase para MVP
