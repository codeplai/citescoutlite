# Semana 1 · PREPARACIÓN Y SETUP DE PRODUCCIÓN

**Objetivo:** Infraestructura lista para recibir código v3; stack operativo sin cambios en aplicación.

**Duración:** 5 días · **Equipo:** DevOps (1) + Infra (1)

---

## ITEMS SEMANA 1

### 1.1 DECIDIR PROVEEDOR CLOUD Y APROVISIONAR VPC
- **Descripción:** Seleccionar AWS/DigitalOcean/Hetzner según cobertura LATAM, costo, soporte
- **Tareas:**
  - [ ] Comparar 3 proveedores: cobertura, pricing, soporte 24/7
  - [ ] Presupuestar 11 semanas de infra
  - [ ] Crear VPC con subnetting (public: LB, private: DB+app)
  - [ ] Configurar security groups: inbound 443/80 público, SSH 22 restringido
- **Duración:** 1 día
- **Dependencias:** Decisión del CITE sobre región primaria (us-east-1? sa-east-1?)
- **DoD:** VPC operativa, subnets públicas y privadas creadas, SGs configurados

---

### 1.2 PROVISIONAR POSTGRES REPLICADO (PRIMARY + 2 REPLICAS)
- **Descripción:** Base de datos en alta disponibilidad con PITR 7 días
- **Tareas:**
  - [ ] Crear instancia primary (postgres 15, 100 GB, 4 vCPU)
  - [ ] Crear 2 replicas read (misma config)
  - [ ] Configurar replicación streaming (WAL archiving a S3)
  - [ ] Backup diario a S3 con retención 30 días
  - [ ] Configurar PITR (point-in-time recovery) con gólem de 7 días
  - [ ] Test: restore desde backup a DB nueva, validar integridad
- **Duración:** 1.5 días
- **Dependencias:** VPC lista (1.1)
- **DoD:** Primary + 2 replicas en sync, backups automatizados, restore test exitoso

---

### 1.3 PROVISIONAR LOAD BALANCER + 2 NODOS API
- **Descripción:** Frente escalable para la API FastAPI
- **Tareas:**
  - [ ] LB (ALB o equivalent): escuchar 443 (HTTPS), balancear round-robin a 2 nodos
  - [ ] 2 nodos API (t4g.xlarge o 4 vCPU equiv): Debian/Ubuntu latest
  - [ ] Clonar repo v2 en ambos nodos (no cambios, solo setup)
  - [ ] Systemd units para FastAPI (reinicio automático, logging a stdout)
  - [ ] Health check: `/health` endpoint que toca DB, devuelve 200 ok
  - [ ] Test: matar 1 nodo → tráfico fluye a la otra sin DROP
- **Duración:** 1.5 días
- **Dependencias:** VPC (1.1), DB primaria (1.2)
- **DoD:** LB en 443, 2 nodos healthy, failover automático

---

### 1.4 CONFIGURAR OBSERVABILIDAD (PROMETHEUS + GRAFANA + PAGERDUTY)
- **Descripción:** Visibilidad completa del sistema
- **Tareas:**
  - [ ] Prometheus: scrape configs (nodos API, DB, LB metrics)
  - [ ] Grafana: dashboards
    - [ ] Nodos: CPU, memoria, disk, conexiones TCP
    - [ ] DB: qps, latencia, replication lag, cache hit rate
    - [ ] API: req/s, latencia p95/p99, error rate por endpoint
  - [ ] Alertas en Prometheus: CPU > 80%, DB lag > 1s, API p99 > 5s
  - [ ] PagerDuty integración: oncall schedule, críticas despiertan
  - [ ] Test: simular CPU spike, alerta se dispara
- **Duración:** 1 día
- **Dependencias:** Nodos API (1.3)
- **DoD:** Grafana con 5+ dashboards, PagerDuty escalation funciona

---

### 1.5 CONFIGURAR OBJECT STORAGE (S3/R2) + CDN
- **Descripción:** Almacenamiento escalable para datasets, backups, PDFs
- **Tareas:**
  - [ ] S3 (o R2 de Cloudflare): bucket `agroscout-prod`
  - [ ] Subfolders: `/datasets/2026-07/`, `/backups/`, `/informes/`
  - [ ] Versionado habilitado en `/datasets/` (rollback ante corrupción)
  - [ ] CDN (Cloudflare o Bunny): cache `/datasets/` y `/informes/` con TTL 1h
  - [ ] Origin headers: CORS `Accept-Origin: https://app.cite.ai`
  - [ ] Migrate `datasets/2026-07/` desde local a S3; validar checksums
  - [ ] API env var: `S3_BUCKET=agroscout-prod`
- **Duración:** 0.5 días
- **Dependencias:** VPC (1.1)
- **DoD:** Datasets en S3, CDN cacheando, checksums validados

---

### 1.6 CONFIGURAR TLS Y HTTPS
- **Descripción:** Encriptación en tránsito
- **Tareas:**
  - [ ] Certificado SSL/TLS: comprar o generar (Let's Encrypt válido 3m+)
  - [ ] Instalar en LB
  - [ ] Redirigir HTTP → HTTPS en LB
  - [ ] HSTS header: 31536000 (1 año)
  - [ ] Test: curl https://api.cite.ai/ → 200, no warnings
- **Duración:** 0.5 días
- **Dependencias:** LB (1.3)
- **DoD:** HTTPS funciona, HSTS presente, sin cert warnings

---

### 1.7 INTEGRACIÓN CON DATOS V2 (MIGRAR DATASETS)
- **Descripción:** Traer los datos de v2 a la nueva infra
- **Tareas:**
  - [ ] Volcar DB v2 (SQLite → Postgres dump)
  - [ ] Restaurar en primary v3
  - [ ] Copiar `datasets/2026-07/` a S3
  - [ ] Verificar integridad: row count por tabla, checksums de archivos
  - [ ] Actualizar API env var: `DATABASE_URL=postgresql://...` (nueva DB)
  - [ ] Test canary: reiniciar API, verificar que query a /consultas responde igual
- **Duración:** 0.5 días
- **Dependencias:** DB (1.2), S3 (1.5), Nodos API (1.3)
- **DoD:** Datos v2 íntegros en v3, API respondiendo igual

---

### 1.8 NETWORKING Y CORTESÍA (WHITELIST IPS DE TERCEROS)
- **Descripción:** Configurar ACLs para servicios externos
- **Tareas:**
  - [ ] Tavily IPs: whitelist en security group (API puede conectar)
  - [ ] Bright Data IPs: whitelist para webhook incoming
  - [ ] openFDA: no requiere whitelist (es outbound HTTP)
  - [ ] RASFF: no requiere whitelist
  - [ ] DNS: apuntar api.cite.ai → LB IP
- **Duración:** 0.5 días
- **Dependencias:** VPC (1.1), LB (1.3)
- **DoD:** Resolución DNS correcta, conectividad a Tavily/Bright Data

---

### 1.9 RESTORE TEST COMPLETO (DISASTER RECOVERY)
- **Descripción:** Validar que la recuperación ante desastre funciona
- **Tareas:**
  - [ ] Crear DB nueva desde backup de 24h atrás
  - [ ] Restaurar datos completos, verificar integridad (row count, último insert timestamp)
  - [ ] Tiempo de restauración documentado (target < 1 hora)
  - [ ] Documentar procedimiento: qué pasos, quién ejecuta, cuánto toma
- **Duración:** 0.5 días
- **Dependencias:** DB (1.2), Backups (1.2)
- **DoD:** Restore test ejecutado, tiempo documentado, procedimiento escrito

---

### 1.10 FAILOVER TEST (ALTA DISPONIBILIDAD)
- **Descripción:** Validar que si primary cae, las replicas toman el relevo sin data loss
- **Tareas:**
  - [ ] Test 1: Matar primary → esperar detección automática (< 30s) → replica promueve
  - [ ] Verificar: no hay DROP de queries en el cliente durante failover
  - [ ] Verificar: replication lag = 0 post-promotion
  - [ ] Test 2: Matar replica 1 → observar que queda primary + 1 replica
  - [ ] Documentar: alertas que se disparan, cuánto tarda la detección
- **Duración:** 0.5 días
- **Dependencias:** DB (1.2), Observabilidad (1.4)
- **DoD:** Failover < 30s, zero data loss verificado, alertas funciona

---

### 1.11 LOAD TEST DE LÍNEA BASE (BASELINE)
- **Descripción:** Medir cómo perfoma la infra con carga normal v2
- **Tareas:**
  - [ ] Herramienta: ab (Apache Bench) o k6; 10 req/s por 5 min
  - [ ] Endpoints a testear: `/consultas` (GET), `/etapas/{id}/resultado` (GET)
  - [ ] Métricas: latencia p50/p95/p99, CPU, memoria, conexiones DB
  - [ ] Benchmarks: p95 < 500ms (línea base v2)
  - [ ] Documentar resultados en Grafana
- **Duración:** 0.5 días
- **Dependencias:** LB (1.3), API (1.3), Observabilidad (1.4)
- **DoD:** Baseline documentado, gráficos en Grafana, p95 < 500ms

---

## DEFINITION OF DONE (S1)

- [ ] VPC + subnetting operativo
- [ ] Postgres primary + 2 replicas en sync
- [ ] LB + 2 nodos API health-checking
- [ ] Observabilidad (Prometheus + Grafana + PagerDuty) completa
- [ ] Object storage (S3) + CDN funcionando
- [ ] TLS/HTTPS en LB
- [ ] Datos v2 migrados, API respondiendo
- [ ] Networking configurado (Tavily, Bright Data, DNS)
- [ ] Restore test exitoso (tiempo documentado)
- [ ] Failover test exitoso (zero data loss)
- [ ] Load baseline capturado (p95 < 500ms)
- [ ] Documentación: runbook de operación iniciado

---

## RIESGOS S1

| Riesgo | Mitigación |
|---|---|
| Proveedor cloud saturado, cuotas excedidas | Verificar cuotas día 1; tener 2 proveedores como backup |
| Replicación streaming falla (lag > 1s) | Tuning de wal_level, max_wal_senders; testing diario |
| LB no balancea bien, un nodo recibe 80% | Configurar health check más estricto; monitorear distribución |
| Restore test tarda > 1h | Usar snapshots en lugar de dump + restore si es muy lento |
| Failover tarda > 30s | Tuner timeout de detección (recovery_target_timeline) |

---

## NOTAS

- **Inicio:** Día 1 post-firma (asumiendo 2026-10-01)
- **Cloud:** Decisión la toma el CITE (región, proveedor)
- **DevOps:** 1 persona time-full; puede paralelizar tareas (Tavily, S3, TLS en paralelo mientras DB se provisiona)
- **Budget:** ~$1000/mes infra; incluido en presupuesto de v3
