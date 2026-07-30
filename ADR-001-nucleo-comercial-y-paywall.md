# ADR-001 · Reorientación a núcleo comercial, puertos en cascada y paywall como frontera de casos de uso

- **Estado:** Propuesto
- **Fecha:** 2026-07-22
- **Contexto del proyecto:** AgroScout IA (CITEagroindustrial Chavimochic) — evolución de la arquitectura `IA Lite v6` → `v7`
- **Origen:** reunión con el CITE (revisión del MVP, 22-07-2026)
- **Decisores:** Codeplai (arquitectura) · CITE (negocio/dominio)

---

## 1. Contexto

El MVP `v6` está diseñado como un motor **técnico-regulatorio**: interpreta un insumo, hace match por composición sobre Open Food Facts / USDA, propone formulación e ingeniería inversa y verifica regulación. La arquitectura es sólida y consciente del costo (archivos locales sobre NVMe, ETL batch mensual, cache de LLM, puertos hexagonales, un único servidor dedicado ~US$85/mes).

En la reunión, el CITE validó que el MVP captó la necesidad base, pero pidió un **cambio de tesis del producto**:

> No basta el "estado del arte" técnico-regulatorio. El valor está en **inteligencia comercial global**: qué productos *ya existen* en el mercado mundial a partir de un insumo, en qué país, a qué precio y **dónde se venden** (URL / canal). El objetivo es romper el sesgo de conocimiento local del CITE y permitir que el emprendedor o MIPYME tome decisiones estratégicas.

Restricciones y señales adicionales de la reunión:

- **Modelo de negocio SaaS por suscripción:** fase abierta (gratuita) que identifica productos; tras el pago, la formulación a detalle.
- **Mayor preocupación operativa: costo de las búsquedas** — servidores, antibots, y el costo de las llamadas en vivo. Se está evaluando un LLM más económico (GLM / Z.ai, con Mistral puntual).
- **Urgencia comercial:** se necesita el entregable para firmar el CDR y el contrato.
- **Fuera de alcance por ahora:** el segundo programa (informes de laboratorio con IA), que se financia con otro fondo.

## 2. Decisión

Reorientar la arquitectura a `v7` manteniendo la base hexagonal y de persistencia local, con cinco cambios:

### 2.1 El núcleo pasa a ser el Mapa Comercial Global

Se parte la etapa `2 · BuscarProductos` en dos:

- **2a · MatchInsumo→Productos** (local, vectores + DuckDB, sin LLM): match semántico por composición. Sin cambios de fondo.
- **2b · MapaComercialGlobal** (nueva, núcleo del MVP gratuito): por cada producto entrega `país · marca · rango de precio · canal · URL · fecha`.

La geografía y el canal se vuelven **atributos de dominio de primera clase**, no un extra opcional. Nueva entidad de dominio:

```
ProductoEnMercado {
  insumo, producto, pais, marca,
  precioRango, fuente, url, fecha
}
```

### 2.2 El precio se vuelve atributo, no etapa aislada

`PrecioReferencial` deja de ser una etapa tardía separada. El precio es un atributo de cada `ProductoEnMercado`, poblado por el mismo puerto de descubrimiento y por el rollup referencial (Open Prices / Comtrade / MIDAGRI ya existentes).

### 2.3 Puerto `DescubrimientoComercial` con adaptadores en cascada por costo

Nuevo puerto que resuelve la preocupación de costo/antibots aplicando el principio **"ingerir por lotes, no raspar en vivo"**:

| Orden | Adaptador | Costo | Uso |
|---|---|---|---|
| 1 | Datasets batch indexados (OFF con marca/país, Comtrade) | ~nulo, local | **default** |
| 2 | API de búsqueda/producto licenciada (SerpAPI-style / marketplaces) | de pago | tras circuit breaker |
| 3 | Scraping en vivo | alto + riesgo ToS/antibots | solo Plan Avanzado, con rate-limit |

Cada adaptador externo se envuelve con **`cockatiel`** (retry + circuit breaker + bulkhead) — *library-first, sin lógica propia de reintentos* — y un **decorador de cache** con clave `insumo+país+mes`. El scraping en vivo queda aislado y opt-in: es el único vector real de costo y riesgo legal.

### 2.4 El paywall es una frontera de composición de casos de uso (no de datos)

El tiering vive en la **capa de aplicación**, nunca en las entidades de dominio:

- **`GenerarMapaComercial`** (gratuito) → etapas 1, 2a, 2b, 3.
- **`GenerarDossierDeFormulacion`** (premium) → + etapa 4 (Formulación) + etapa 5 (Regulación a detalle).

Una `PoliticaDeSuscripcion` (entitlement guard) lee el plan desde Supabase en la frontera de aplicación y hace **early return** con el informe gratuito si no hay derecho. Se distingue explícitamente del guard técnico ya existente (`0-2 productos → informe parcial`): son guard clauses distintas y no deben mezclarse.

### 2.5 Regulación y Formulación pasan a premium

Se conservan, pero detrás del paywall y más tarde en el DAG. Dejan de ser el titular.

## 3. Impacto en almacenes y ETL

- **Nuevo almacén `catalogo_comercial`** (dataset DuckDB + índice vectorial semántico), snapshotteado en `datasets/AAAA-MM/` como el resto. Columnas nuevas: `url`, `pais`, `canal`. Mantiene la filosofía de cero servidores de BD.
- **Nueva fuente en ETL batch:** *Catálogo comercial* vía APIs licenciadas / marketplaces, respetando ToS (sin scraping masivo).
- **`SQLite` (estado de app):** el cost-meter por etapa que ya se audita se expone a la enforcement de cuotas por plan.
- El swap al "LLM más barato" es **solo un cambio de adaptador** detrás del `PuertoLLM`: impacto cero en el dominio.

## 4. Alternativas consideradas

1. **Scraping directo de e-commerce como fuente primaria.** Rechazada: máximo costo y exposición a antibots/ToS, justo la preocupación central del CITE. Se degrada a adaptador de último recurso (Plan Avanzado).
2. **Paywall implementado en la capa de datos (filtrar filas por plan).** Rechazada: filtra el modelo de negocio hacia el dominio, viola separación de responsabilidades y dificulta pruebas. Se resuelve por composición de casos de uso.
3. **Mantener el enfoque técnico-regulatorio como núcleo.** Rechazada: contradice explícitamente lo pedido en la reunión.

## 5. Consecuencias

**Positivas**

- El entregable estrella (mapa comercial: qué existe, dónde, a cuánto) queda alineado con el valor que el CITE percibe frente a Promperú / ADEX / SIICEX.
- El costo se controla por diseño: cascada por costo + cache + circuit breaker; lo caro es opt-in y medido.
- El paywall no contamina el dominio; las capas gratuita/premium son solo composiciones distintas.
- La base local, hexagonal y de bajo costo (~US$85/mes) se preserva.

**Negativas / riesgos**

- **Licenciamiento y ToS** de la data comercial/e-commerce: obliga a usar APIs licenciadas u orígenes ODbL/abiertos; el scraping es el riesgo legal y de costo.
- **Cobertura desigual** de productos comerciales LATAM: las fichas CITE + Comtrade mitigan, pero el e-commerce global es irregular.
- **Frescura vs. costo** del precio en vivo: por eso el precio en vivo va en Plan Avanzado; el batch puede quedar algo desactualizado.
- **Scope creep** ("lo más profundo posible"): exige acotar con firmeza el tier gratuito o el costo se dispara.

## 6. Acciones derivadas

- Definir el contrato del puerto `DescubrimientoComercial` y su primer adaptador (batch OFF con marca/país).
- Seleccionar y evaluar 1 API de búsqueda/producto licenciada (costo, cobertura, ToS).
- Modelar `ProductoEnMercado` y el dataset `catalogo_comercial`.
- Implementar `PoliticaDeSuscripcion` como entitlement guard contra Supabase.
- Instrumentar el cost-meter por etapa hacia cuotas por plan.
- Cerrar con el CITE el alcance exacto del tier gratuito vs. premium (frontera formulación).
