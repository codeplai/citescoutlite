# Evaluación de Contabo como alternativa de servidor

|  |  |
|---|---|
| Fecha | 2026-08-24 |
| Proyecto | AgroScout IA — CITEagroindustrial Chavimochic |
| Pregunta | El cliente considera caro el servidor dedicado previsto. ¿Sirve Contabo? |
| Documentos relacionados | `INFRA-HUAWEI-CLOUD.md` · `PRESUPUESTO-IA-INFRA-MONGODB.xlsx` (hojas `MongoDB-OFF` y `Bare-metal`) |
| Precios consultados | 2026-08-24, tarifas de lista de los proveedores |

---

## 0. Resumen ejecutivo

**Sí, Contabo sirve — pero la línea VDS, no la línea Core VPS.** Con MongoDB fuera de la
ecuación (§1), el sistema pide ~16 GB de RAM, no 192. Un **Cloud VDS M a US$ 59/mes**
cubre el requisito con holgura y ahorra **US$ 190/mes (~US$ 2.280 al año)** frente al
servidor de US$ 249 que se estaba evaluando.

Quedan dos preguntas abiertas, una técnica y una que no lo es:

1. **Técnica:** el chip de Contabo (EPYC 7282, Zen 2) es más lento por núcleo que el
   Ryzen 7900. Hay que medir el p95 antes de comprometerse. Cuesta US$ 59 y una tarde.
2. **No técnica, y es la que decide todo:** ¿exige el CITE que el dato resida en Perú, o
   prohíbe alojarlo en EE. UU.? Contabo no tiene sede en Latinoamérica. Si la respuesta
   es sí, Contabo muere por la misma razón que ReliableSite y Hetzner, y la respuesta
   vuelve a ser Huawei optimizado.

**El CDR es el 28 de agosto.** Nada de infraestructura se toca antes de esa fecha.

---

## 1. El contexto: por qué la máquina de 192 GB sobra

El servidor que se estaba evaluando —[ReliableSite AMD Ryzen 7900, 12 núcleos, 192 GB
DDR5 *non-ECC*, 2×4 TB NVMe, **US$ 249/mes**](https://www.reliablesite.net/dedicated-servers/12-core-server/amd-ryzen-7900-192GB)—
está dimensionado para importar el volcado completo de MongoDB de Open Food Facts. Ese
requisito **no existe**.

### 1.1 Lo que de verdad consume RAM

| Pieza | RAM/disco real | Fuente |
|---|---|---|
| bge-m3 en el proceso de la API | **3,5-4,5 GB** | medido, `INFRA-HUAWEI-CLOUD.md` §0 |
| LanceDB con **100.000 productos** | **~460 MB** | hoy 29.460 productos → 135 MB medidos; 4,58 KB/producto |
| Postgres (estado de aplicación) | MB | `ejecuciones`, `cache_llm`, `informes` |
| nginx + SPA + worker de PDF | < 1 GB | `frontend/dist` son 173 KB |
| **Total en marcha** | **~7-8 GB** | |

Los 100 mil vectores **no votan en el dimensionado**: 100.000 × 1024 dims × 4 bytes =
410 MB. El único inquilino grande es bge-m3, y es una constante de 4,5 GB.

Con holgura razonable, el número honesto es **16 GB**.

### 1.2 El dato que elimina MongoDB (verificado el 2026-08-24)

Open Food Facts publica hoy un **export Parquet** que la hoja `MongoDB-OFF` no contempla:

```
food.parquet (HuggingFace)   7,26 GiB   4.692.771 productos
```

Sumando el tamaño comprimido de las 12 columnas que AgroScout lee de verdad —`code`,
`product_name`, `brands`, `brands_tags`, `categories_tags`, `countries_tags`,
`ingredients_text`, `ingredients_tags`, `labels_tags`, `additives_tags`,
`last_modified_t`, `quantity`:

| | Tamaño comprimido | % del fichero |
|---|---|---|
| Fichero entero | 7.696 MB | 100 % |
| `environmental_score_data` (nadie lo lee) | **4.051 MB** | **53 %** |
| **Las 12 columnas que AgroScout sí lee** | **752 MB** | **9,8 %** |

DuckDB lee ese Parquet por columnas y por predicado, y **el proyecto ya usa DuckDB**
(`shelf_facts.duckdb`, etapa 2a). Consecuencias:

- No hay volcado de 15,5 GB que descargar ni restaurar.
- No hay colección de 27 GB ni 300 GB de disco para que convivan volcado y colección.
- No hay 3 h de `mongorestore` ni 1,5 h de construcción de índices.
- No hay working set de 16 GB. **No hay MongoDB.**

Se mantiene la atribución ODbL anotada en el punto 6 del veredicto de la hoja.

> **La única razón para conservar Mongo** sería necesitar escrituras o consultas ad-hoc
> sobre el documento completo con sus 1.066 campos. El patrón de acceso de AgroScout es
> lectura por EAN más filtros por tag: columnar gana sin discusión.

---

## 2. Qué ofrece Contabo hoy

| Línea | Configuración relevante | Precio | CPU |
|---|---|---|---|
| Core VPS 8 | 8 vCPU · 24 GB · 300 GB SSD | €16,80/mes | **compartida** |
| Core VPS 12 | 12 vCPU · 48 GB · 400 GB SSD | €30,00/mes | compartida |
| **Cloud VDS M ★** | **8 núcleos dedicados · 32 GB · 240 GB NVMe** | **US$ 59/mes** | **dedicada** · EPYC 7282 |
| Cloud VDS L | 12 núcleos · 48 GB · 360 GB NVMe | US$ 83/mes | dedicada |

**Sedes:** UE, Reino Unido, **EE. UU. (Nueva York, St. Louis, Seattle)**, Singapur,
Japón, India, Australia. **No hay Latinoamérica.** Las sedes de EE. UU. llevan una
*location fee* pequeña (€1-2/mes en la línea VPS).

---

## 3. Por qué VDS y no VPS — la decisión de verdad

El gate P03 del proyecto es **p95 < 2 s, con 176 ms medidos**, y ese p95 está dominado
por una sola cosa: la inferencia de bge-m3 en CPU. No por disco, no por red, no por RAM.
Eso reduce toda la decisión sobre Contabo a una única pregunta: **¿dan CPU determinista?**

- **Core VPS** — vCPU compartida y sobresuscrita. Es la crítica histórica más consistente
  a Contabo. Bajo un vecino ruidoso, una carga de *matmul* como bge-m3 puede degradarse
  2-5×. Seguiría por debajo de los 2 s, pero de forma **no determinista**, y latencia
  impredecible delante del CITE es el peor modo de fallo posible en una demo.
- **Cloud VDS** — núcleos dedicados. Es la línea que existe justamente para esto.

**La contrapartida del VDS es el chip.** El EPYC 7282 es Zen 2 (2019) a 2,8 GHz y **sin
AVX-512**. Un núcleo Zen 4 como el del Ryzen 7900 ejecuta bge-m3 bastante más rápido.
Estimación: **1,5-2,5× más lento por núcleo** en el *encode*. Sobre 176 ms serían
~350-450 ms — todavía con 4-5× de margen contra el gate de 2 s, pero **es una estimación,
no una medida**. Es exactamente lo que hay que medir antes de firmar (§5.2).

---

## 4. Dónde queda Contabo frente a las demás opciones

| Opción | US$/mes | RAM | CPU | Latencia a Lima | ECC |
|---|---|---|---|---|---|
| ReliableSite Ryzen 7900 (lo evaluado) | **249** | 192 GB | 12c Zen 4, dedicada | ~70-90 ms (Miami) | **No** |
| Huawei sin Mongo (opción A) | 110-160 | 16 GB | 4 vCPU | 40-60 ms | Sí |
| **Contabo VDS M** | **59** | 32 GB | 8c Zen 2, dedicada | ~100-130 ms (NY) | Sí, a nivel de host |
| Contabo Core VPS 8 | ~19 | 24 GB | 8 vCPU **compartida** | ~100-130 ms | Sí, a nivel de host |
| Hetzner AX42 | ~50 | 64 GB | Zen 4 dedicada, hierro propio | ~180-220 ms (Alemania) | Sí |

Dos cosas que saltan de esa tabla:

1. **El servidor de US$ 249 lleva DDR5 *non-ECC*; un VDS de US$ 59 corre sobre plataforma
   EPYC, que sí lleva ECC registrada.** No se controla desde el cliente, pero está ahí.
   Pagar 4× más por *perder* ECC es difícil de defender ante el cliente.
2. **La ventaja de Contabo sobre Hetzner no es el precio, es la geografía.** Hetzner da
   mejor hierro por dinero similar; Contabo da ~90 ms menos de RTT contra Lima, que es el
   tramo que el usuario paga en **cada clic de la SPA**.

**Ahorro frente al servidor evaluado: US$ 190/mes ≈ US$ 2.280 al año.**

---

## 5. Qué verificar antes de comprometerse

### 5.1 El precio real a 1 mes

Los €16,80 son tarifa de **suscripción a 24 meses e IVA incluido**. El precio mensual sin
compromiso es más alto y suele llevar cuota de alta; y siendo una entidad peruana,
probablemente el IVA no aplique. Verificar ambas cosas en el configurador.

*Reencuadre para el cliente:* €16,80 × 24 = ~€403 de compromiso total, **menos de dos
meses del servidor de US$ 249**. El lock-in es nominal en términos absolutos.

### 5.2 El gate, con el método que el proyecto ya tiene definido

Alquilar un VDS M un mes, levantar el contenedor de la API y medir:

| Medida | Techo | Referencia |
|---|---|---|
| p95 de `/buscar` | **< 2 s** | 176 ms medidos hoy en el ECS de Huawei (gate P03) |
| RTT p95 desde una conexión de Lima | anotar y comparar | 40-60 ms desde Santiago, `INFRA-HUAWEI-CLOUD.md` §2 |

Es la misma prueba que ya está definida en `INFRA-HUAWEI-CLOUD.md` §2. Cuesta US$ 59 y
una tarde, y responde la única pregunta técnica abierta.

### 5.3 Copias de seguridad

El auto-backup de Contabo se paga aparte y sus *snapshots* son limitados. La mitigación
ya está escrita en la hoja `Bare-metal`: **conservar el bucket OBS (~US$ 1,50/mes)** con
`pgBackRest` o `pg_dump` nocturno. Vale igual aquí, y es la pieza barata que hace que un
proveedor de bajo coste deje de dar miedo.

---

## 6. Las dos objeciones honestas

**Soporte y SLA.** Contabo es un proveedor de bajo coste: soporte por ticket, tiempos de
respuesta variables, SLA fino. Para un MVP y una demo es suficiente; para un servicio que
el CITE publique a sus asociados es una conversación que conviene tener **antes** del
primer incidente, no después.

**Residencia del dato — sigue siendo el bloqueante.** Contabo no tiene sede en
Latinoamérica: se acaba en EE. UU. o la UE, igual que con ReliableSite o Hetzner. Si el
CITE exige residencia en Perú o prohíbe EE. UU., Contabo muere por la misma razón que las
demás. **Esa pregunta a administración es la que decide todo, y no es técnica.**

---

## 7. Recomendación

1. **Si no hay requisito de residencia:** **Cloud VDS M en US East (Nueva York)**,
   contratado **1 mes primero** para medir el p95 (§5.2), y solo entonces pasar a 12 o 24
   meses.
2. **Si el gate sale mal** por el EPYC 7282: el escalón siguiente es Hetzner AX42
   aceptando los ~200 ms, o volver a la opción A de Huawei.
3. **Si hay requisito de residencia:** el análisis termina — Huawei LA-Santiago
   optimizado (compromiso anual, sin instancia de MongoDB, sin los 300 GB de EVS).
4. **En cualquier caso, conservar el bucket OBS** de respaldo externo (~US$ 1,50/mes).
5. **No tocar infraestructura antes del CDR del 28 de agosto.** Lo que sí se puede
   adelantar sin tocar infraestructura es el **ETL de Parquet + DuckDB** (§1.2), que es
   donde está el ahorro grande y que no depende de qué servidor se elija.

---

## Fuentes

- [ReliableSite · AMD Ryzen 7900 192 GB](https://www.reliablesite.net/dedicated-servers/12-core-server/amd-ryzen-7900-192GB) — US$ 249/mes, 192 GB DDR5 non-ECC, 2×4 TB NVMe
- [Contabo · VPS](https://contabo.com/en/vps/) · [Contabo · VDS](https://contabo.com/en/vds/)
- [Contabo · sedes de EE. UU.](https://contabo.com/en-us/locations/united-states/) · [location fees](https://contabo.com/en-us/location-fees/)
- [Hetzner · AX42](https://www.hetzner.com/dedicated-rootserver/ax42/) · [AX52](https://www.hetzner.com/dedicated-rootserver/ax52?currency=EUR)
- Tamaños de Open Food Facts verificados por HTTP contra `static.openfoodfacts.org` y el Parquet de HuggingFace el 2026-08-24
- Cifras del propio proyecto: `INFRA-HUAWEI-CLOUD.md` §0 y §2 · `PRESUPUESTO-IA-INFRA-MONGODB.xlsx`, hojas `MongoDB-OFF` y `Bare-metal`
