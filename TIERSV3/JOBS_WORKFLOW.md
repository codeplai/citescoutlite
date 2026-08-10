# S3.11 Jobs Workflow: Complete Flow Diagram

**Purpose:** Visualize job lifecycle, event streaming, retry strategy, and fallback paths.

---

## 📊 COMPLETE WORKFLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────┐
│ CLIENT (Vue3 Frontend)                                              │
│  - User submits query: POST /consultas                              │
│  - Opens WebSocket: ws://localhost:8000/ws/run/{run_id}             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                           │ HTTP POST
                           ▼
        ┌──────────────────────────────────┐
        │ API (FastAPI) /consultas         │
        │  - Validate request              │
        │  - Create run record             │
        │  - Enqueue job_agente_run        │
        │  - Return run_id to client       │
        └──────────────────┬───────────────┘
                           │
                           │ defer(run_id, insumo, país, nivel_costo)
                           ▼
        ┌──────────────────────────────────────────┐
        │ PROCRASTINATE QUEUE (PostgreSQL)         │
        │  procrastinate_jobs table                │
        │  - job_id: BIGSERIAL                     │
        │  - task_name: 'job_agente_run'           │
        │  - args: {run_id, insumo, país, ...}     │
        │  - scheduled_at: NOW()                   │
        │  - status: 'queued'                      │
        └──────────────────┬───────────────────────┘
                           │
                ┌──────────┴──────────┐
                │                     │
                ▼                     ▼
        ┌─────────────────┐  ┌─────────────────┐
        │ WORKER 1        │  │ WORKER 2        │  ... (concurrency=4)
        │ (Procrastinate) │  │ (Procrastinate) │
        └────┬────────────┘  └────┬────────────┘
             │                    │
             │ Dequeue job        │ Dequeue job
             │                    │
             ▼                    ▼
    ┌─────────────────────────────────────┐
    │ STEP 1: JOB STARTED                 │
    │ ────────────────────────────────    │
    │ emit_event(run_id, 'started')       │
    │  ↓ INSERT INTO eventos_job          │
    │  ↓ event_id=123, evento='started'   │
    │  ↓ WebSocket broadcasts to all      │
    │    connected clients for this run   │
    └────────────────┬────────────────────┘
                     │
                     │ Execute task
                     ▼
    ┌─────────────────────────────────────────────────────┐
    │ STEP 2: JOB EXECUTION (5 min timeout)              │
    │ ────────────────────────────────────────────────    │
    │ Execute job_agente_run():                           │
    │  1. Fetch insumo details                            │
    │  2. Call agent (stage 1-5)                          │
    │  3. Generate formulation claims                     │
    │  4. Validate claims vs taxonomía_cite              │
    │     (fuzzy match, 80% similarity)                   │
    │  5. Update run status to 'success'                  │
    │  6. Enqueue next job (job_informe_pdf) [S4]        │
    │                                                      │
    │ ⏱️ TIMEOUT: If > 5 min → kill task, mark failed     │
    └────────────────┬────────────────────────────────────┘
                     │
            ┌────────┴─────────┬──────────────┐
            │                  │              │
       SUCCESS           EXCEPTION         TIMEOUT
            │                  │              │
            ▼                  ▼              ▼
    ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
    │ JOB OK      │  │ RETRY LOGIC  │  │ FINAL FAIL   │
    │ evento:     │  │              │  │              │
    │ completed   │  │ attempt: 1/4 │  │ max_attempts │
    │             │  │ wait: 1s     │  │ exceeded     │
    │             │  │              │  │              │
    │             │  │ attempt: 2/4 │  │ evento:      │
    │             │  │ wait: 2s     │  │ failed       │
    │             │  │              │  │ reason: ...  │
    │             │  │ attempt: 3/4 │  │              │
    │             │  │ wait: 4s     │  │ Fallback:    │
    │             │  │              │  │ run status = │
    │             │  │ attempt: 4/4 │  │ 'parcial'    │
    │             │  │ wait: 8s     │  │              │
    │             │  │ [FINAL]      │  │ Send email   │
    │             │  │              │  │ to user:     │
    │             │  │ If all fail→ │  │ "partial    │
    │             │  │ emit 'failed'│  │  results    │
    │             │  └──────────────┘  │ available"  │
    └─────────────┘                     └──────────────┘
            │
            │ (SUCCESS PATH)
            ▼
    ┌─────────────────────────────────────┐
    │ STEP 3: COMPLETION EVENT            │
    │ ────────────────────────────────    │
    │ emit_event(run_id, 'completed')     │
    │  ↓ INSERT INTO eventos_job          │
    │  ↓ data_json = {result, duration}   │
    │  ↓ WebSocket broadcasts             │
    │  ↓ Frontend updates progress: 100%  │
    └────────────────┬────────────────────┘
                     │
                     │ Auto-enqueue (S4)
                     ▼
    ┌──────────────────────────┐
    │ Enqueue job_informe_pdf  │
    │ (Stage 6 - PDF report)   │
    │ timeout: 5 min           │
    │ retry: exponential       │
    └──────────────────────────┘


┌─────────────────────────────────────────────────────────────┐
│ FRONTEND (Vue 3) WEBSOCKET UPDATES IN REAL-TIME             │
│                                                             │
│ ws.onmessage = (event) => {                                │
│   const msg = JSON.parse(event.data);                      │
│   switch(msg.evento) {                                     │
│     case 'created':   → "Enqueued..."                      │
│     case 'started':   → "Processing..."                    │
│     case 'progress':  → Progress bar: msg.data.percent     │
│     case 'completed': → "Done! ✅"                         │
│     case 'failed':    → "Error: " + msg.data.error         │
│   }                                                         │
│ }                                                           │
└─────────────────────────────────────────────────────────────┘
```

---

## ⏰ NIGHTLY JOBS SCHEDULER (S3.10)

```
┌─────────────────────────────────────────────────────────────┐
│ SUPERVISOR / SYSTEMD (Worker Process)                      │
│  - Auto-restart if crash                                   │
│  - Running 24/7                                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────────┐
        │ Procrastinate Worker         │
        │ (scripts/start_worker.py)    │
        │  - Concurrency: 4            │
        │  - Retry: exponential        │
        │  - SLA monitor: on           │
        └──────────────┬───────────────┘
                       │
                       │ Check schedule
                       ▼
    ┌─────────────────────────────────────┐
    │ NIGHTLY JOB SCHEDULE                │
    │ ════════════════════════════════    │
    │                                     │
    │  00:00 UTC: job_mim_etl             │
    │  ┌─────────────────────────────┐    │
    │  │ Nightly MIM ETL Pipeline:   │    │
    │  │ 1. Download OFF/USDA        │    │
    │  │ 2. Update shelf_facts       │    │
    │  │ 3. Calculate tendencias     │    │
    │  │ 4. Save to PostgreSQL       │    │
    │  │ SLA: < 30 min               │    │
    │  │ Timeout: auto-fail if > 30m │    │
    │  │ Status → eventos_job        │    │
    │  └─────────────────────────────┘    │
    │                                     │
    │  02:00 UTC: job_corpus_ingest       │
    │  ┌─────────────────────────────┐    │
    │  │ Corpus Preparation (S4):    │    │
    │  │ 1. Download documents       │    │
    │  │ 2. Extract embeddings       │    │
    │  │ 3. Index in LanceDB         │    │
    │  │ SLA: < 20 min               │    │
    │  └─────────────────────────────┘    │
    │                                     │
    └─────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────┐
│ SLA MONITORING & ALERTS                                          │
│                                                                  │
│ If job_mim_etl:                                                  │
│  ✅ Completed in < 30 min:  GREEN, logged in eventos_job        │
│  ⚠️  Completed in 30-60 min: YELLOW, alert sent                 │
│  ❌ Failed or > 60 min:      RED, PagerDuty alert               │
│  ❌ Never ran:               RED, "missing execution" alert      │
│                                                                  │
│ See: config/job_scheduling.py::JobMonitor.check_job_sla()       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔄 RETRY STRATEGY (EXPONENTIAL BACKOFF)

```
Job fails → Retry Policy:

Attempt 1: Failed
  ├─ Wait: 1 second
  └─ Attempt 2: Failed
      ├─ Wait: 2 seconds
      └─ Attempt 3: Failed
          ├─ Wait: 4 seconds
          └─ Attempt 4: Failed
              ├─ Wait: 8 seconds
              └─ FINAL FAIL: Give up, emit 'failed' event


Exponential backoff formula: wait_seconds = 2^(attempt - 1)

Benefits:
 ✅ Reduces load on system
 ✅ Gives transient errors time to resolve
 ✅ Prevents thundering herd
 ✅ Logs all failures for debugging
```

---

## 🚨 FALLBACK PATHS

### Path 1: Job Timeout
```
Job running > 5 minutes → TIMEOUT
  ↓
  emit_event(run_id, 'failed', data={'reason': 'timeout'})
  ↓
  Run status → 'parcial'
  ↓
  Notify client: "Query timed out, partial results available"
```

### Path 2: Max Retries Exceeded
```
Attempt 4 fails → MAX_ATTEMPTS exceeded
  ↓
  emit_event(run_id, 'failed', data={'reason': 'max_retries', 'attempts': 4})
  ↓
  Run status → 'parcial'
  ↓
  Audit log: claim_propuesto + rejection reason in audit_claims
```

### Path 3: Invalid Claims
```
LLM generates claim → Fuzzy match fails (< 80% similarity)
  ↓
  ValidadorClaims.validar_claim() → REJECTED
  ↓
  INSERT audit_claims:
    - claim_propuesto: "manufactura ilegal"
    - motivo_rechazo: "Similitud insuficiente (45%)"
  ↓
  Exclude from results, continue with valid claims
```

### Path 4: Database Connection Lost
```
Exception: psycopg error
  ↓
  Retry logic catches it (Attempt N → N+1)
  ↓
  If all retries fail → emit 'failed', status='parcial'
```

---

## 🎯 PERFORMANCE TARGETS

| Operation | Target | Limit | Status |
|-----------|--------|-------|--------|
| Job enqueue | < 10ms | - | ✅ |
| Job execution | < 5 min | TIMEOUT | ✅ |
| Retry wait | 1-8s | exponential | ✅ |
| Event broadcast | < 100ms | - | ✅ |
| DuckDB query | < 100ms | - | ✅ |
| Claim validation | < 50ms | per claim | ✅ |
| MIM ETL nightly | < 30 min | SLA | ⏳ |

---

## 📊 EVENT TYPES

```sql
-- eventos_job.evento column values:

'created'    → Job enqueued
'started'    → Job execution began
'progress'   → Mid-execution status update (data: {percent, message})
'completed'  → Job finished successfully
'failed'     → Job failed after all retries (data: {error, attempts})
```

---

## 🔧 OPERATIONAL COMMANDS

### Monitor Jobs (Development)
```bash
# Watch worker logs in real-time
tail -f logs/worker.log | grep job_mim_etl

# Check recent jobs
psql $DATABASE_URL -c "
  SELECT task_name, status, attempts, MAX(created_at)
  FROM procrastinate_jobs
  GROUP BY task_name, status, attempts
  ORDER BY created_at DESC LIMIT 20;
"

# Check SLA violations
python scripts/check_job_sla.py
```

### Manual Job Enqueue
```bash
# Enqueue from shell (for testing)
python -c "
  import asyncio
  from config.procrastinate_config import app
  
  async def enqueue():
    async with app.open():
      result = await app.tasks['job_mim_etl'].defer(
        snapshot_version='2026-08-test'
      )
      print(f'Enqueued job {result.id}')
  
  asyncio.run(enqueue())
"
```

---

## 📋 DEBUGGING CHECKLIST

If jobs aren't running:

```
☐ Worker process is running
  psctl aux | grep start_worker.py

☐ Procrastinate tables exist
  psql $DATABASE_URL -c "\dt procrastinate_*"

☐ Event callbacks configured
  Grep "setup_event_callbacks()" in start_worker.py

☐ WebSocket endpoint registered
  GET http://localhost:8000/openapi.json | grep ws

☐ Database connection working
  psql $DATABASE_URL -c "SELECT 1"

☐ Job definitions loaded
  python -c "from config.procrastinate_config import app; print(list(app._tasks.keys()))"

☐ No hanging jobs
  SELECT COUNT(*) FROM procrastinate_jobs WHERE status = 'started' AND created_at < NOW() - INTERVAL '1 hour'
```

---

## 📚 REFERENCES

- **Procrastinate Docs:** https://procrastinate.readthedocs.io/
- **PostgreSQL LISTEN/NOTIFY:** For true streaming (future optimization)
- **Supervisord Config:** See deployment guide for nightly job scheduling
- **Monitoring:** Prometheus metrics from worker stdout logs

