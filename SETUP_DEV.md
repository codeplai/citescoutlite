# 🚀 Setup de Desarrollo — AgroScout IA MVP

**Tiempo estimado:** 15 minutos · **Requisitos:** Python 3.11+, Git, cuenta Supabase

---

## 1️⃣ **Clonar el repositorio**

```bash
git clone <repo-url>
cd agroscout-mvp-v3
```

---

## 2️⃣ **Instalar dependencias**

```bash
# Con uv (recomendado, más rápido)
uv sync

# O con pip + venv tradicional
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -e .
```

---

## 3️⃣ **Configurar variables de entorno**

### Copiar template

```bash
cp .env.example .env
```

### Llenar credenciales en `.env`

Necesitas obtener valores de:

**Supabase:**
1. Ve a https://app.supabase.com
2. Abre tu proyecto (o crea uno nuevo: `agroscout-mvp-v3`)
3. Ve a **Settings > API** y copia:
   - `SUPABASE_URL` → "Project URL"
   - `SUPABASE_ANON_KEY` → "anon public" o "sb_publishable_..."
   - `SUPABASE_SECRET_KEY` → "service_role" o "sb_secret_..."

4. Ve a **Settings > Database > Session > Connection string** y copia:
   - `DATABASE_URL` → reemplaza `[YOUR-PASSWORD]` con tu contraseña

**APIs externas (opcionales para MVP):**
- `HUAWEI_MAAS_API_KEY` → Huawei ModelArts (LLM)
- `TAVILY_API_KEY` → Tavily (búsqueda web, S10+)
- `BRIGHT_DATA_KEY` → Bright Data (scraper, S3+)
- `USDA_API_KEY` → USDA FoodData (datos, S2+)

**Presupuestos (ya configurados, opcional cambiar):**
```env
PRESUPUESTO_RUN_USD=0.25           # Máximo por consulta
PRESUPUESTO_USUARIO_MES_USD=2      # Plan gratuito
PRESUPUESTO_PREMIUM_MES_USD=10     # Plan premium
PRESUPUESTO_GLOBAL_MES_USD=10      # Kill-switch global
```

---

## 4️⃣ **Verificar la conexión**

```bash
# Test todas las conexiones
python scripts/verify_s1.py

# O test manual a Supabase
python scripts/test_supabase_connection.py
```

Esperado:
```
✅ Connected to Supabase (7 tables)
✅ DuckDB ready
✅ FastAPI ready
```

---

## 5️⃣ **Levantar el servidor**

**Terminal 1: FastAPI**
```bash
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Abierto en: http://localhost:8000

**Ver health check:**
```bash
curl http://localhost:8000/health | jq
```

**Terminal 2 (opcional): Procrastinate worker**
```bash
# Próximamente en S3. Por ahora no necesario.
python scripts/start_worker.py
```

---

## 6️⃣ **Estructura de carpetas**

```
agroscout-mvp-v3/
├── .env                       # Credenciales (NO commitear)
├── .env.example               # Template (commitear)
├── pyproject.toml             # Dependencias
│
├── api/                        # FastAPI app
│   ├── main.py
│   ├── health.py              # Health check endpoint
│
├── adaptadores/               # Componentes técnicos
├── casos_de_uso/              # Lógica de negocio
├── dominio/                   # Modelos de datos
├── puertos/                   # Interfaces
│
├── data/                       # DuckDB local (analytics)
│   └── shelf_facts.duckdb
├── datasets/                  # Datos CSV/JSON
├── logs/                       # Logs de ejecución
├── informes/                  # PDFs generados
├── scripts/                   # Utilidades
│   ├── verify_s1.py           # Verificar setup
│   ├── init_duckdb.py         # Inicializar DuckDB
│   ├── deploy_schema.py       # Deploy schema Supabase
│   ├── test_job.py            # Encolar jobs (S3+)
│   ├── start_worker.py        # Worker (S3+)
│
├── tests/                     # Pruebas
│
└── SETUP_DEV.md              # Este archivo
```

---

## 🐛 **Troubleshooting**

### ❌ `DATABASE_URL not found`
Asegúrate de que `.env` tiene `DATABASE_URL` llenad o. Copia de nuevo desde Supabase.

### ❌ `psycopg: password authentication failed`
La contraseña no es válida. Verifica caracteres especiales:
- Si tiene `*`, `:`, `@`, `/`, `?`, `#` → URL-encódeala
- Ej: `Campeon*26041989` → `Campeon%2A26041989`

### ❌ `DuckDB file not found`
```bash
python scripts/init_duckdb.py
```

### ❌ FastAPI no levanta
```bash
# Verifica puerto
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Usa otro puerto
uvicorn api.main:app --port 8001
```

### ❌ Redis connection refused (optional)
Redis es opcional en MVP. Déjalo sin llenar si no quieres usarlo.

---

## 📚 **Documentación por semana**

| Semana | Documento | Estado |
|---|---|---|
| S1 | [SETUP_DEV.md](SETUP_DEV.md) | ✅ |
| S1 | [S1_PREPARACION_INFRA.md](TIERSV3/S1_PREPARACION_INFRA.md) | ✅ |
| S2 | [S2_AGENTE_CUARENTENA.md](TIERSV3/S2_AGENTE_CUARENTENA.md) | 📝 |
| S3+ | [Plan TIERS](./TIERSV3/) | 📋 |

---

## 🚀 **Próximos pasos**

1. ✅ **S1 completado** — Infraestructura lista
2. ⏳ **S2** — Auditoria de datos y ETL
3. ⏳ **S3-S10** — Features (agente, búsqueda, reportes, etc)

---

## 💬 **Preguntas frecuentes**

**¿Puedo usar SQLite en lugar de Supabase?**
Sí. En `.env` cambia `APP_DB=postgres` a `APP_DB=sqlite`. La app tiene modo offline.

**¿Necesito Redis?**
Opcional en MVP. Requerido en S10 para cache de búsquedas.

**¿A qué versión de Python apunta?**
Python 3.11+ (usa 3.11, 3.12 o 3.13).

**¿Dónde reporto bugs?**
Abre un issue en el repo o contacta al equipo de desarrollo.

---

**Última actualización:** 2026-08-09  
**Versión:** MVP v3  
**Autor:** Equipo AgroScout
