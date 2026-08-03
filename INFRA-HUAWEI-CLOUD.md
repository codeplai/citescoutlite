# Infraestructura en Huawei Cloud — despliegue del MVP

**Fecha:** 2026-08-02 · **Proyecto:** AgroScout IA (CITEagroindustrial Chavimochic)
**Alcance:** desplegar el MVP de las semanas 1-4 para el CDR del **2026-08-28**
**Decisión tomada:** **todo dentro de Huawei Cloud**, incluida la base de datos
(RDS for PostgreSQL). Supabase sale de la foto — §1 y §13.

---

## 0. Qué se despliega (medido, no estimado)

| Pieza | Tamaño real | Dónde vive |
|---|---|---|
| API FastAPI (`api/`, `casos_de_uso/`, `adaptadores/`) | ~60 KB de código | Contenedor en ECS |
| **Modelo bge-m3 en memoria** | **~2,3 GB** (568 M parámetros, fp32) | RAM del ECS |
| Índice LanceDB `vectores/` | **135 MB** (`productos.lance` 131 MB) | Disco EVS |
| Snapshot `datasets/2026-07/` | **66 MB** | Disco EVS + copia en OBS |
| SPA Vue ya compilada (`frontend/dist/`) | **173 KB** | Nginx en el mismo ECS |
| PDFs generados | 5,3 MB y creciendo | **OBS** |
| Estado de aplicación (`ejecuciones`, `etapas_ejecucion`, `cache_llm`, `informes`, `perfiles`, `usuarios`) | KB | **RDS for PostgreSQL** |
| LLM (5 etapas por run premium) | US$ 0,19-0,23 por run en frío | **ModelArts MaaS**, ya contratado |

Dos consecuencias que mandan sobre el dimensionado:

1. **La RAM la fija el modelo, no el tráfico.** `adaptadores/modelo_embeddings.py` carga
   bge-m3 como singleton de proceso porque son ~2,3 GB y ~8 s de arranque. Con PyTorch y
   el runtime alrededor, el proceso se sitúa en **3,5-4,5 GB en reposo**. Un ECS de 4 GB
   se queda corto; el mínimo honesto es **8 GB**.
2. **La búsqueda no necesita GPU.** El gate P03 se midió en CPU: **p95 176 ms** contra
   un techo de 2 s, con 11× de margen. Pagar una instancia con GPU para el MVP no compra
   nada.

---

## 1. La base de datos entra en la VPC

**Decisión: `RDS for PostgreSQL` en la misma VPC que el ECS.** Postgres deja de estar en
Supabase (AWS São Paulo) y pasa a ser un servicio gestionado de Huawei con IP privada.

### Lo que se gana

| | Supabase (cross-cloud) | RDS en la VPC |
|---|---|---|
| RTT por consulta | 40-60 ms | **< 2 ms** |
| Sobrecoste por run (8-12 viajes, plan S3) | **0,4-0,7 s** | **< 25 ms** |
| Egress entre nubes | Sí, se paga | No |
| Superficie pública de la base | Endpoint en internet | **Ninguna**: solo IP privada |
| Residencia del dato | AWS São Paulo | **Huawei, la región contratada** |

El riesgo **R1 del plan de S3** —"8-12 viajes a Supabase por run desde Perú"— y su gate
de *sobrecoste < 1 s* dejan de ser un problema: en red privada ese presupuesto sobra por
un factor de 40. Desaparece también el `prepare_threshold=None`, que era un parche
contra el *transaction pooler* de Supabase: RDS acepta sentencias preparadas con
normalidad.

### Lo que se pierde, y hay que decirlo

**No hay equivalente gestionado de Supabase Auth.** IAM y OneAccess son para identidades
corporativas de la consola y de aplicaciones empresariales, no para los usuarios finales
de una SaaS. El login **vuelve a ser código propio**: bcrypt + JWT con expiración, que es
justo lo que la Semana 3 acababa de reemplazar. `adaptadores/autenticacion.py` sigue en
el repo (se conservó para la rama `sqlite`), así que no se parte de cero, pero es trabajo
real: §13.

Se pierde también la comodidad de `auth.uid()` en las políticas RLS. Sin multi-tenant
—decisión de S3— el filtrado por `usuario_id` en la aplicación es suficiente; quien
quiera RLS igualmente la tiene con `SET LOCAL app.usuario_id` por request.

### La deuda que no puede volver

El motivo por el que S3 se fue a Supabase Auth era eliminar `cite2026` en texto plano en
el repositorio. Al reponer el auth propio, **las contraseñas se hashean con bcrypt y los
usuarios demo se crean con un script que recibe la contraseña por argumento**. Si esa
línea vuelve al repo, el cambio de infraestructura habrá costado una vulnerabilidad.

### La alternativa barata, y por qué no

Postgres en un contenedor en el mismo ECS ahorra el coste de RDS, pero compite por los
8 GB de RAM con un proceso que ya usa 3,5-4,5 GB para bge-m3, y deja los backups a mano.
**Es la opción a considerar solo si el presupuesto no admite RDS**, y en ese caso hay que
subir el ECS a 16 GB — con lo que el ahorro se evapora.

---

## 2. Región: LA-Santiago

Con la base de datos dentro de la VPC, quedan dos latencias:

| Tramo | Desde Santiago | Desde Singapur |
|---|---|---|
| Usuario (Lima/Trujillo) → app | **~40-60 ms** | ~250-300 ms |
| App → RDS (misma VPC) | **< 2 ms** | < 2 ms |
| App → MaaS (`ap-southeast-1`, Singapur) | ~300-350 ms | ~5 ms |

La base de datos ya no vota. Queda el usuario contra el LLM: el tramo al LLM se paga
**una vez por etapa sobre una generación de 3-10 s** (+300 ms es ruido), mientras que la
latencia del usuario la paga **cada clic de la SPA** y se nota en una demo de 15 min.

**Decisión: LA-Santiago**, la región de Huawei Cloud más cercana a Perú. MaaS se queda en
Singapur, que es donde sirve los modelos GLM y DeepSeek que el proyecto ya usa.

**Gate de la decisión** — mismo método que los TIERS: desde el ECS recién creado, medir
`RTT p95` a la instancia RDS y a `api-ap-southeast-1.modelarts-maas.com`, y anotarlo.
Esperado: **< 2 ms** a RDS y **< 400 ms** a MaaS.

> **Cuenta internacional.** LA-Santiago existe en Huawei Cloud **International**
> (`huaweicloud.com/intl`). Las cuentas del sitio de China continental no comparten
> regiones ni consola. Verificarlo antes de crear recursos: migrar después es rehacerlo
> todo.

---

## 3. Arquitectura

```
                    Internet
                       │
              ┌────────▼─────────┐
              │  EIP + Anti-DDoS │  (básico, incluido)
              └────────┬─────────┘
   ┌───────────────────▼───────────────────────────────┐
   │  VPC  10.0.0.0/16 · LA-Santiago                   │
   │  ┌─────────────────────────────────────────────┐  │
   │  │ Subred pública 10.0.1.0/24                  │  │
   │  │  ┌───────────────────────────────────────┐  │  │
   │  │  │  ECS  s7n.xlarge.2                    │  │  │
   │  │  │  4 vCPU · 8 GB · Ubuntu 22.04         │  │  │
   │  │  │  ┌─────────────────────────────────┐  │  │  │
   │  │  │  │ nginx :443 → SPA · /api         │  │  │  │
   │  │  │  │ uvicorn 127.0.0.1:8001 (Docker) │  │  │  │
   │  │  │  │   · bge-m3 en RAM 2,3 GB        │  │  │  │
   │  │  │  │   · LanceDB en /data            │  │  │  │
   │  │  │  └─────────────────────────────────┘  │  │  │
   │  │  │  EVS 100 GB SSD → /data               │  │  │
   │  │  └───────────────┬───────────────────────┘  │  │
   │  └──────────────────│──────────────────────────┘  │
   │                     │ 5432, solo desde el SG del  │
   │  ┌──────────────────▼──────────────────────────┐  │
   │  │ Subred privada 10.0.2.0/24                  │  │
   │  │  ┌───────────────────────────────────────┐  │  │
   │  │  │  RDS for PostgreSQL 16                │  │  │
   │  │  │  rds.pg.n1.large.2 · 2 vCPU · 4 GB    │  │  │
   │  │  │  40 GB SSD · backup diario + PITR     │  │  │
   │  │  │  SIN acceso público                   │  │  │
   │  │  └───────────────────────────────────────┘  │  │
   │  └─────────────────────────────────────────────┘  │
   └──────┬─────────────┬──────────────┬───────────────┘
          │             │              │
      ┌───▼───┐    ┌────▼─────┐   ┌────▼──────────┐
      │  OBS  │    │   LTS    │   │ CES + SMN     │
      │ PDFs  │    │  logs    │   │ alarmas       │
      │snapshot│   └──────────┘   └───────────────┘
      │modelos│
      └───────┘
                          ·  ·  ·  ·
                  ┌──────────────────┐
                  │ ModelArts MaaS   │
                  │ (ap-southeast-1) │
                  └──────────────────┘
```

| Servicio Huawei | Para qué | Nivel MVP |
|---|---|---|
| **ECS** Elastic Cloud Server | API + nginx + SPA | 1 × `s7n.xlarge.2` |
| **RDS for PostgreSQL** | Estado de aplicación, cache LLM, perfiles, usuarios | 1 × `rds.pg.n1.large.2`, nodo único |
| **EVS** | `/data`: índice LanceDB, snapshot, PDFs de trabajo | 100 GB SSD |
| **VPC** + 2 subredes + 2 Security Groups | Aislamiento; la base sin cara pública | 1 VPC |
| **EIP** | IP pública del ECS | 5 Mbps, pago por tráfico |
| **OBS** | PDFs, copia del snapshot, pesos de bge-m3 | 1 bucket privado |
| **SCM** / Certificate Manager · **DNS** | TLS y dominio | 1 certificado |
| **IAM Agency** | El ECS accede a OBS sin AK/SK en disco | 1 agency |
| **CBR** | Copia diaria del disco de datos | 7 días |
| **DAS** Data Admin Service | Consola SQL contra RDS (sustituye al SQL Editor de Supabase) | — |
| **LTS** · **CES + SMN** | Logs y 5 alarmas | 7 días |
| **ModelArts MaaS** | Los modelos del DAG | Ya contratado |

**Lo que deliberadamente no se usa:** CCE/CCI (Kubernetes para un contenedor es operación
sin cuello que resolver), ELB (una instancia no balancea), FunctionGraph (2,3 GB de
modelo no caben en un arranque en frío), DCS/Redis (la cola va sobre Postgres, ADR-003),
WAF y CDN. Todo eso, con su disparador, en §12.

---

## 4. Dimensionamiento

### ECS

| Recurso | Valor | Por qué |
|---|---|---|
| Flavor | **`s7n.xlarge.2`** — 4 vCPU / 8 GB | bge-m3 son 2,3 GB + PyTorch; en reposo el proceso queda en 3,5-4,5 GB |
| Imagen | Ubuntu 22.04 LTS | Wheels de PyTorch CPU sin sorpresas |
| Disco sistema | 40 GB SSD | La imagen Docker con PyTorch CPU pesa ~1,5 GB |
| Disco datos | **EVS 100 GB SSD → `/data`** | 201 MB hoy; el margen es para PDFs, logs y el snapshot siguiente |

**Si el presupuesto aprieta:** 8 GB es el suelo. Antes que bajar de RAM, bajar de vCPU
(2 vCPU / 8 GB): la búsqueda es memoria, y en una demo hay una consulta a la vez.

### RDS

| Recurso | Valor | Por qué |
|---|---|---|
| Motor | **PostgreSQL 16** | Es lo que asume el esquema de S3 (`jsonb`, `gen_random_uuid()`, `date_trunc`) |
| Flavor | **`rds.pg.n1.large.2`** — 2 vCPU / 4 GB | El estado de aplicación son kilobytes; la carga real es el `cache_llm` y unas pocas filas por run |
| Almacenamiento | 40 GB SSD (mínimo) | Con `entrada_json`/`salida_json` en `jsonb`, 40 GB dan para años de demo |
| Despliegue | **Nodo único** | La HA primario/en espera **duplica el coste** y el MVP tolera una ventana de restauración |
| Backup | Automático diario, retención **7 días**, PITR activado | Reemplaza el PITR que daba Supabase |
| Acceso público | **Desactivado** | Solo IP privada dentro de la VPC |

---

## 5. Red y seguridad

### Dos Security Groups, no uno

**`sg-app`** (ECS):

| Dirección | Puerto | Origen/Destino | Para qué |
|---|---|---|---|
| Entrada | 443/TCP | `0.0.0.0/0` | La aplicación |
| Entrada | 80/TCP | `0.0.0.0/0` | Redirección a 443 y reto ACME |
| Entrada | 22/TCP | **IP fija del equipo** | Administración. Nunca `0.0.0.0/0` |
| Salida | 443/TCP | `0.0.0.0/0` | MaaS, OBS, OFF |
| Salida | 5432/TCP | `sg-db` | La base |

**`sg-db`** (RDS):

| Dirección | Puerto | Origen | Para qué |
|---|---|---|---|
| Entrada | 5432/TCP | **`sg-app`** (el grupo, no un CIDR) | Solo la aplicación entra |

Referenciar el *security group* de origen en vez de un rango de IP es lo que hace que la
regla siga siendo correcta cuando la instancia cambie de IP.

**El puerto 8001 no se abre.** Uvicorn escucha en `127.0.0.1:8001` y nginx hace de proxy.
Hoy `api/main.py` arranca con `host="0.0.0.0"` y `reload=True`: **las dos cosas se
cambian** en el `CMD` del contenedor.

### TLS, CORS y credenciales

- Certificado gratuito de Huawei SCM con el dominio, o Let's Encrypt vía `certbot`.
- `allow_origins` pasa a listar **solo el dominio de producción** (hoy tiene `localhost`).
- **`.env` en `/opt/agroscout/.env`, `chmod 600`**, montado como volumen, fuera de la
  imagen y fuera de git.
- **La contraseña de RDS** se fija al crear la instancia y vive solo en ese `.env`. Con
  la base sin cara pública, una filtración del fichero no basta para entrar desde fuera.
- **OBS sin AK/SK en disco:** IAM Agency de tipo *Cloud service → ECS* con permiso
  acotado al bucket; el SDK toma credenciales temporales del metadata service.
- **CSMS** (Cloud Secret Management) es la vía correcta para la fase institucional; en
  una sola máquina añade una llamada de red en el arranque sin quitar el fichero.

---

## 6. Empaquetado y despliegue

### Dockerfile

```dockerfile
FROM python:3.11-slim

# PyTorch CPU: el wheel por defecto arrastra CUDA (~2,5 GB) que aquí no se usa.
ENV HF_HOME=/data/modelos \
    SENTENCE_TRANSFORMERS_HOME=/data/modelos \
    HF_HUB_OFFLINE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && \
    uv export --frozen --no-dev -o requirements.txt && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

COPY dominio casos_de_uso puertos adaptadores api etl evals ./
CMD ["uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8001", "--workers", "1"]
```

Tres cosas no obvias:

- **`--workers 1`.** Cada worker carga su propia copia de bge-m3: dos workers son 4,6 GB
  solo de modelo.
- **`HF_HUB_OFFLINE=1` + `HF_HOME=/data/modelos`.** Sin esto, el primer arranque descarga
  2,3 GB de HuggingFace, y si HF falla el día de la demo la API no levanta. Los pesos se
  suben **una vez** a OBS.
- **Pango/Cairo** son de WeasyPrint. Sin ellas el PDF falla en tiempo de ejecución, es
  decir, delante del CITE.

### Layout en la máquina

```
/opt/agroscout/            docker-compose.yml · .env (600) · nginx.conf
/data/vectores/            135 MB · índice LanceDB      ← desde OBS
/data/datasets/2026-07/     66 MB · snapshot + manifest ← desde OBS
/data/modelos/             2,3 GB · pesos de bge-m3     ← desde OBS
/data/informes/            PDFs de trabajo (la copia buena va a OBS)
```

> **Rutas relativas.** El código lee `datasets/2026-07/manifest.json` y `vectores/`
> relativos al directorio de trabajo. En el contenedor se resuelven con *bind mounts* de
> `/data/vectores` sobre `/app/vectores` y `/data/datasets` sobre `/app/datasets`, sin
> tocar el código. **No renombrar la carpeta `datasets/` en producción**: la convivencia
> con el paquete `datasets` de HuggingFace es el caso que `modelo_embeddings.py` ya
> mitiga, y salirse de él es estrenar el bug en la demo.

### docker-compose.yml

```yaml
services:
  api:
    image: agroscout:latest
    restart: unless-stopped
    env_file: /opt/agroscout/.env
    network_mode: host           # uvicorn en 127.0.0.1:8001
    volumes:
      - /data/vectores:/app/vectores:ro
      - /data/datasets:/app/datasets:ro
      - /data/modelos:/data/modelos:ro
      - /data/informes:/app/informes
    logging:
      driver: json-file
      options: { max-size: "50m", max-file: "3" }
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8001/docs')"]
      interval: 30s
      start_period: 120s        # el modelo tarda ~8 s en cargar; margen amplio
```

`start_period` largo a propósito: un healthcheck impaciente reinicia el contenedor en
bucle mientras el modelo carga, y el síntoma parece un fallo de la API.

### SPA

`npm run build` en local (ya existe `frontend/dist/`, 173 KB) → `scp` a
`/var/www/agroscout` → nginx la sirve como estático y hace proxy de `/api` a
`127.0.0.1:8001`.

---

## 7. Datos, snapshots y respaldo

**Dos almacenes con dueño distinto, y ninguno es el disco del ECS:**

```
RDS ─────────► estado de aplicación · PITR + backup diario 7 días
obs://agroscout-cite/
  ├── snapshots/2026-07/   productos_merged.json · manifest.json · corpus
  ├── vectores/2026-07/    productos.lance/ (135 MB)
  ├── modelos/bge-m3/      pesos, subidos una vez
  └── informes/            PDFs servidos con URL prefirmada
```

- **Versionado del bucket activado.** Es el respaldo de los datasets (hueco H8 del ADR).
- **Aprovisionar el nodo = pull desde OBS.** Reconstruir la máquina son tres
  `obsutil sync`, no un reindexado de horas: el índice de 135 MB deja de ser punto único
  de fallo.
- **CBR diario con retención de 7 días** sobre `/data`, y **backup automático de RDS con
  PITR**. Juntos cubren el RPO ≤ 24 h / RTO ≤ 4 h del ADR-003.
- **Probar una restauración de RDS antes del 28 de agosto.** Un backup no verificado no
  es un backup, y ahora el PITR es responsabilidad propia, no de Supabase.

---

## 8. Observabilidad y alarmas

Cinco alarmas de **CES** con notificación por **SMN** a correo. Ni una más:

| Alarma | Umbral | Por qué |
|---|---|---|
| CPU del ECS | > 85 % durante 5 min | El pico real es la generación del PDF |
| **Memoria del ECS** | > 85 % | Es el recurso escaso: 2,3 GB de modelo sobre 8 GB |
| Disco `/data` | > 80 % | Los PDFs crecen sin poda |
| Instancia caída | 1 fallo | Trivial, y la que de verdad importa |
| **Conexiones y almacenamiento de RDS** | > 80 % | Nuevo: la base ya no es problema de otro |

**LTS** recoge logs de nginx y del contenedor, retención 7 días.

**La alarma de gasto de LLM no es de Huawei:** la lleva el kill-switch de S3
(`PRESUPUESTO_GLOBAL_MES_USD`, hoy 10). Con **US$ 0,19-0,23 por run premium en frío**,
ese tope son ~45 runs al mes para toda la institución: sobra para la demo, se queda corto
para uso real. Conviene además el aviso de presupuesto en la consola de facturación.

---

## 9. Coste mensual estimado

Órdenes de magnitud para LA-Santiago, **a verificar en la calculadora de Huawei Cloud**
antes de comprometer cifras con el CITE:

| Concepto | Pago por uso | Con compromiso anual |
|---|---|---|
| ECS `s7n.xlarge.2` (4 vCPU / 8 GB) | US$ 70-110 | US$ 45-70 |
| **RDS PostgreSQL `n1.large.2`, nodo único + 40 GB** | **US$ 50-90** | **US$ 35-60** |
| EVS 100 GB SSD | US$ 12-15 | US$ 10-13 |
| EIP + tráfico (pago por tráfico, uso bajo) | US$ 5-10 | US$ 5-10 |
| OBS (~10 GB + peticiones) | US$ 1-2 | US$ 1-2 |
| CBR (backup 100 GB) | US$ 5-10 | US$ 5-10 |
| LTS + CES + SMN (volumen bajo) | US$ 0-5 | US$ 0-5 |
| **Subtotal Huawei** | **US$ 143-242** | **US$ 101-170** |
| ModelArts MaaS (~100 runs premium/mes) | US$ 20-25 | — |
| **Total** | **US$ 163-267** | **US$ 121-195** |

**El cambio cuesta unos US$ 50-90/mes**: es lo que costaba Supabase en su plan gratuito o
de US$ 25. A cambio, todo queda en un proveedor, en red privada y con residencia
controlada. Si el requisito de residencia existe, el precio está justificado; si no
existe, conviene saber que se está pagando por él.

**El apagar/encender importa:** detener el ECS entre ensayos ahorra la mayor parte del
cómputo. RDS también se puede detener temporalmente, pero **el almacenamiento se sigue
cobrando** y una instancia detenida se reactiva sola pasados unos días.

---

## 10. Puesta en marcha — orden exacto

Medio día largo. Conviene hacerlo **la semana del 17**, no la del 24.

1. Verificar que la cuenta es Huawei Cloud **International** y que LA-Santiago está
   disponible.
2. VPC `agroscout-vpc` 10.0.0.0/16 + subred pública 10.0.1.0/24 + **subred privada
   10.0.2.0/24**.
3. Security Groups `sg-app` y `sg-db` con las reglas de §5.
4. **RDS PostgreSQL 16**, `rds.pg.n1.large.2`, nodo único, 40 GB, **sin acceso público**,
   en la subred privada y con `sg-db`. Anotar la contraseña una sola vez.
5. Activar backup automático con retención de 7 días y PITR.
6. ECS `s7n.xlarge.2` con clave SSH + EVS 100 GB montado en `/data` + `sg-app`.
7. EIP con pago por tráfico, asociada al ECS.
8. **Medir el gate de §2** desde el ECS: RTT p95 a RDS (< 2 ms) y a MaaS (< 400 ms).
9. Aplicar las migraciones de `supabase/migraciones/` **ya adaptadas** (§13) con
   `scripts/aplicar_migracion.py` o desde DAS.
10. Bucket OBS privado + versionado + IAM Agency asociada al ECS.
11. Subir a OBS y sincronizar a `/data`: snapshot, `vectores/` y pesos de bge-m3.
12. Docker + compose; construir la imagen; `.env` en `/opt/agroscout` con `chmod 600`.
13. nginx + certificado TLS + registro DNS A → EIP. Cerrar `allow_origins` al dominio.
14. Crear los 2 usuarios demo con el script de §13 (contraseña por argumento, nunca en el
    repo).
15. Correr el **golden set de los 5 insumos** contra la máquina real y comparar con local.
16. CBR, LTS y las 5 alarmas de CES.
17. **Ensayo del guion de 15 min contra el dominio de producción**, no contra `localhost`.

---

## 11. Riesgos

| # | Riesgo | Mitigación |
|---|---|---|
| **R1** | **El auth propio vuelve, y con él la tentación de las contraseñas en el repo** | bcrypt obligatorio, contraseña por argumento en el script, y un test que falle si aparece una contraseña literal en el código |
| **R2** | **La descarga de bge-m3 (2,3 GB) desde HuggingFace falla el día del despliegue** | Pesos en OBS y arranque con `HF_HUB_OFFLINE=1` |
| **R3** | **Memoria del ECS.** Un `--workers 2` descuidado duplica el modelo y mata la instancia | `--workers 1` fijado en el `CMD` y alarma al 85 % |
| **R4** | **RDS de nodo único: no hay conmutación automática** | Aceptado en el MVP. PITR + `APP_DB=sqlite` como plan B en portátil. La HA es un cambio de configuración, no de arquitectura |
| **R5** | **Faltan librerías de WeasyPrint** y el PDF falla en producción | Instaladas en el Dockerfile y verificadas en el paso 15 generando un PDF real |
| **R6** | **El cambio de Supabase a RDS se hace con S3 ya escrito** (§13) | Está acotado: 2 adaptadores y 3 scripts. Hacerlo **antes** de la Semana 4, no después |
| **R7** | **Latencia a MaaS desde Santiago (~300 ms/llamada)** | Medida en el paso 8. Sobre generaciones de 3-10 s es ruido |
| **R8** | **`reload=True` y `host=0.0.0.0`** en el arranque actual | Se cambian en el `CMD`; el 8001 no se abre en `sg-app` |

---

## 12. Camino a la fase institucional

| Disparador | Cambio | Servicio |
|---|---|---|
| El MVP pasa a servicio real | RDS a **primario/en espera** (HA) | RDS |
| p95 o CPU sostenidas | 2-3 réplicas de la API detrás de **ELB** | ELB, ECS |
| Lecturas pesadas del panel | **Réplica de lectura** de RDS | RDS |
| Cola de jobs (F4 del ADR) | `procrastinate` sobre el mismo RDS; el worker es **un segundo contenedor en el mismo ECS** antes que una máquina nueva | — |
| Agente web (P11) | Salida por **NAT Gateway** con IP fija, para identificarse ante los sitios y respetar rate-limits | NAT Gateway |
| Tráfico real de usuarios | **CDN** para la SPA y **WAF** delante del ELB | CDN, WAF |
| Varias organizaciones | RLS por `organizacion_id` con `SET LOCAL`; la columna `usuario_id` ya está desde S3 | — |

---

## 13. Qué cuesta el cambio en el código

**No hay que tocar nada todavía** — esto es el presupuesto de la decisión, medido sobre
el código que ya está commiteado (`4853af5 fin s3, s4 ya casi`).

### No se toca (243 líneas ya escritas)

`adaptadores/auditoria_postgres.py` (141), `cache_postgres.py` (63) y
`suscripciones_postgres.py` (39) son **Postgres estándar**: funcionan contra RDS sin
cambiar una línea. Es exactamente lo que compró la arquitectura hexagonal.

### Se cambia

| Pieza | Qué pasa | Esfuerzo |
|---|---|---|
| `adaptadores/db.py` (59 líneas) | Solo cambia `DATABASE_URL`. Se **quita** `prepare_threshold=None`: era un parche para el pooler de Supabase | 0,5 h |
| `adaptadores/auth_supabase.py` (120 líneas, JWKS ES256) | Se sustituye por auth propio sobre `autenticacion.py`, que sigue en el repo. `/token` deja de ser proxy y valida contra la tabla `usuarios` | 4-5 h |
| `adaptadores/repositorio_informes_supabase.py` (112 líneas) | → `repositorio_informes_obs.py`: subida a OBS y **URL prefirmada** en vez de `signedURL` de Storage | 3 h |
| `supabase/migraciones/001_esquema_s3.sql` | 3 claves foráneas `references auth.users(id)` → `public.usuarios(id)`; 3 políticas con `auth.uid()` → filtrado por aplicación o `current_setting('app.usuario_id')` | 1 h |
| `supabase/migraciones/003_perfiles_trigger.sql` | **Desaparece**: sin `auth.users` no hay trigger; el perfil se crea en el mismo INSERT que el usuario | 0,5 h |
| `scripts/crear_usuarios_demo.py` | La Admin API de Supabase → INSERT con hash bcrypt | 1 h |
| `scripts/verificar_supabase.py`, `etl/migrar_sqlite_a_supabase.py` | Renombrar y ajustar cadena de conexión | 0,5 h |
| `adaptadores/entorno.py`, `api/main.py`, `.env.example` | Fuera las 5 variables `SUPABASE_*`; entra `DATABASE_URL` de RDS y las de OBS | 1 h |
| `test/test_e2e_s3.py`, `test/test_sobrecoste_estado.py` | Los tests de auth y de sobrecoste se reescriben contra la nueva realidad | 2 h |

**Total: 13,5-15 h — unos dos días.** La ventana barata era antes de escribir T3 y T4 de
la Semana 3; ahora hay que desmontar y volver a probar. Sigue siendo mucho menos que
descubrir un requisito de residencia después del CDR.

**Cuándo hacerlo:** antes de empezar la Semana 4. El plan de S4 solo toca el estado de
aplicación a través de los adaptadores que **no** cambian, así que el orden correcto es
migrar, verificar el E2E de S3 en verde contra RDS, y recién entonces seguir con la etapa
2b.
