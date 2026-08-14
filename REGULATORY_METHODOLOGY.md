# Metodología regulatoria — qué se consulta, cómo y hasta dónde llega

**Versión:** 3.0 · **Actualizado:** 2026-08-14
**Sustituye a la v2.0**, que declaraba un corpus de «4100+ regulaciones de 5 fuentes»
que **no existía**. Ver §7.

---

## 1. Resumen

CiteScout responde una pregunta concreta: **¿está autorizado este aditivo, en este
alimento, en este mercado?** Y responde con la cifra, la referencia y el fragmento de norma
que la sostiene, o dice que no lo sabe.

Los tres mercados **no se consultan igual**, porque las tres fuentes no se parecen. Esa
asimetría es el diseño, no una carencia.

| Mercado | Fuente | Mecanismo | Estado (2026-08-14) |
|---|---|---|---|
| 🇺🇸 **Estados Unidos** | eCFR, título 21 | Búsqueda **en vivo** + corpus local | ✅ 8.406 secciones |
| 🇪🇺 **Unión Europea** | Anexo II del Reg. (CE) 1333/2008 | Ingesta única, consulta local | ✅ 14.590 usos, 116 categorías |
| 🌍 **Codex** | GSFA (CXS 192-1995) | **Curación manual** | 🟡 2 de 34 filas |

---

## 2. Estados Unidos — búsqueda en vivo

**Ranking:** `https://www.ecfr.gov/api/search/v1/results`, permitido por el `robots.txt` del
eCFR. Es lo que localiza la sección aplicable: para `"calcium disodium EDTA"` devuelve
§172.120 como primer resultado de 29.

**Texto:** distribución oficial del GPO en `govinfo.gov/bulkdata/ECFR/title-21/`
(21,7 MB, 8.406 secciones), reingerible con `python -m etl.ingerir_ecfr`.

> **Por qué no se usa la API que sirve el texto.** El `robots.txt` de `ecfr.gov` trae
> `Disallow: /api/versioner/v1/full/`, que es justo ese endpoint. Y la página que ve una
> persona (`/current/title-21/...`) es una SPA: devuelve un shell de 10.595 bytes sin el
> texto de la norma. La ruta de govinfo no está restringida y trae el título entero.

**Cobertura por parte del título 21:** 184 (215 secciones) · 172 (153) · 101 (50) · 146 (20)
· 145 (13) · 169 (11) · 150 (3), entre otras.

**Extracción:** el modelo lee la sección y devuelve una *lectura* (qué cobertura da, qué
alimento nombra, qué cifra); **el veredicto lo decide el código**, no el prompt. Y la cita
—`referencia_texto` y `referencia_url`— se construye desde el identificador de sección con
el que se pidió el documento: **citar una norma inexistente es imposible por
construcción**, no por comprobación.

**Latencia medida:** 14,5–35,9 s por aditivo en frío (p95 ≈ 36 s); < 10 ms en caliente.

---

## 3. Unión Europea — ingesta única

**Fuente:** `CELEX:32011R1129`, el Reglamento (UE) 1129/2011, que es el que **rellenó** el
Anexo II. Un documento de 3,4 MB con 602 tablas.

**Lo que se extrae:** 2.177 filas de la Parte E → 14.590 usos, sobre 116 categorías de
alimento, más los cuatro grupos de la Parte C (Grupo I: 137 aditivos, II: 15, III: 16,
IV: 7) y los 321 pares E→nombre de la Parte B.

**La sexta columna es la que decide.** De las 14.590 filas: 52,0 % sin restricción ·
31,1 % «solo …» · 6,2 % «… excepto …» · 1,2 % ambas · 9,4 % otras. **Casi el 40 % restringe
por alimento**, y ahí está el veredicto — no en que la fila exista.

> **Ejemplo, y es el caso de referencia del proyecto.** El E 200 aparece en la categoría
> 04.2.4.1 con 1.000 mg/kg. Parece un sí. La restricción completa dice: *«solo preparados
> de fruta y verdura […] **excepto el puré**, la mousse, la compota, las ensaladas y los
> productos similares en conserva»*. Para una pulpa, un parser que se quedara en la fila
> daría la respuesta contraria a la correcta.

**Designaciones colectivas.** 444 filas traen rangos (`E 200-203`, `E 338-452`) que **no
son intervalos aritméticos**: expandir `E 338-452` como `range(338,453)` metería el E 400
(ácido algínico) dentro de «fosfatos». Se derivan del propio documento cruzando la Parte B
por consistencia de nombre. Fallos conocidos de esa derivación, todos **por defecto**
(sale `SIN_DATO`, nunca autorizado de más): siglas (`TBHQ`), familias sin raíz común
(`Ribonucleótidos`/`Ácido guanílico`) y dos erratas del propio Diario Oficial
(`E 341 "Fostatos"`, `E 355-228` con inicio > fin).

**Latencia:** < 8 ms. Es un diccionario en memoria.

---

## 4. Codex — curación manual, y por qué

El GSFA **no es consultable por máquina**. Sondeadas las cuatro rutas (2026-08-13 y 14):

| Ruta | Resultado |
|---|---|
| `fao.org/gsfaonline/*` | 403 de Cloudflare; las fichas usan `?id=`, vetado por `Disallow: /*?id=*` |
| Web Unlocker de Bright Data | **rechaza**: «not available … in accordance with robots.txt» |
| Enlace `sh-proxy` al PDF de la CXS 192 | 403 |
| `workspace.fao.org/.../CXS_192e.pdf` | 200, pero es una página de login de SharePoint |

Un proveedor de pago negándose a saltarse ese `robots.txt` zanja el asunto. La tabla la
rellena **una persona**, en [data/codex/gsfa_aditivos.csv](data/codex/gsfa_aditivos.csv).

Cada fila declara su `estado`, y el cargador **falla ruidosamente** si una fila dice estar
resuelta sin URL, sin cita, sin responsable o sin fecha:

- `VERIFICADO` — alguien abrió el GSFA y lo anotó. Es el único que da un `SI` limpio.
- `SECUNDARIA` — el dato viene de un documento interno. **Nunca da `SI` a secas**: se
  degrada a `SI_CONDICIONADO` y la nota dice de dónde salió.
- `PENDIENTE` — nadie lo ha mirado. Devuelve `SIN_DATO`, **jamás «no autorizado»**.

**Estado hoy: 2 de 34 filas resueltas**, y las dos como `SECUNDARIA` (proceden de
`acido1.pptx` y `acido2.pptx`, no del GSFA).

---

## 5. El asterisco

`SÍ*` y `NO*` no son adorno: significan **«el aditivo sí, pero de tu categoría no tenemos
confirmación»**. Es el estado más frecuente del sistema, y hay tres motivos para llegar a él:

1. **La categoría se dedujo.** El campo `categoria` de OpenFoodFacts es texto libre con
   8.322 valores distintos; se mapea por segmentos de la ruta de taxonomía y se acierta en
   el **61,0 %** de las filas con aditivo (techo real: 79,5 %, porque el 20,5 % no trae
   categoría). Una categoría deducida **nunca sostiene un `SI` limpio**.
2. **La restricción no se pudo resolver leyendo.** La cláusula dice «puré» y el producto es
   «pulpa». Que una pulpa sea un «producto similar» es un juicio de tecnólogo de alimentos;
   **el sistema no lo firma**: enseña la cláusula entera y condiciona el veredicto.
3. **La cobertura es por designación colectiva** (`E 200-203`, `Grupo I`) y no por una fila
   con el número del aditivo.

---

## 6. Verificabilidad

**P-ADI** ([casos_de_uso/validar_analisis.py](casos_de_uso/validar_analisis.py)) valida
cada respuesta contra los corpus **de hoy**, no contra los de cuando se extrajo:

| Regla | Qué exige |
|---|---|
| P-ADI-1 | Todo veredicto ≠ `SIN_DATO` trae URL y cita literal |
| P-ADI-2 | Esa cita **aparece en la fuente que dice citar** |
| P-ADI-3 | Cada aditivo trae los tres mercados, en orden |
| P-ADI-4 | `SIN_DATO` no arrastra cifras |
| P-ADI-5 | El límite interno sale de un mercado que autoriza |

**P-ADI distingue tres resultados por celda, no dos:** comprobada, fallida y **no
verificable**. Las del Codex son no verificables por definición —su fuente es una persona—
y darlas por buenas sería dar por auditado lo que nadie auditó.

**Sonda de URLs** (`python -m etl.sondar_urls_regulatorias`), también con tres estados:
viva, muerta y **opaca**. Una URL de la FAO devuelve 403 a una máquina y se abre sin
problema en un navegador: marcarla «muerta» haría borrar una cita buena.

---

## 7. Lo que esta versión corrige de la v2.0

> La versión anterior de este documento declaraba:
>
> | Fuente | Entradas |
> |---|---|
> | eCFR | 3500+ |
> | EFSA | 400+ |
> | Codex | 200+ |
> | INACAL | 10+ |
> | DIGESA | 6+ |
> | **TOTAL** | **4100+** |
>
> **Ninguna de esas cifras era real.** Contadas contra el Postgres el 2026-08-13, las seis
> tablas del corpus (`ecfr_regulations`, `efsa_regulations`, `codex_standards`,
> `inacal_nts`, `digesa_directivas`, `regulacion_cita`) estaban **a cero**. Lo único con
> contenido era el índice RAG `vectores/regulatorio.lance`: 734 pasajes, 702 de eCFR y 32
> de DIGESA, **sin una sola entrada de Codex ni de la UE**, y sin la parte 172 del CFR —
> donde vive medio catálogo de aditivos, incluido el EDTA.
>
> También declaraba un job semanal `corpus_ingest` con historial de actualizaciones y un
> apartado de «estadísticas de uso» con búsquedas por fuente. Nada de eso existía.

Las cifras de este documento se pueden reproducir:

```bash
python -m etl.ingerir_ecfr          # imprime secciones y partes
python -m etl.ingerir_anexo_ii      # imprime filas, categorías y grupos
python -m etl.sondar_urls_regulatorias
```

---

## 8. Lo que este sistema NO hace

- **No cubre Perú.** INACAL y DIGESA quedan fuera del alcance de esta función, que son
  tres mercados de exportación. Los 32 pasajes de DIGESA del índice RAG siguen ahí, sin
  mecanismo propio.
- **No está al día con la UE.** El 1129/2011 es la foto de 2011. El E 960 (glucósidos de
  esteviol), autorizado meses después por el 1131/2011, sale `SIN_DATO`.
- **No contabiliza el coste por tokens.** El agente llama a litellm directamente; se
  registra `llamadas_agente`, no el gasto.
- **No interpreta.** Enseña la norma, la cifra y la cláusula. La decisión de si un producto
  concreto cae dentro de una categoría es de quien exporta.
- **No es asesoría regulatoria.** Verificar siempre en la fuente oficial y confirmar la
  clasificación del producto antes de cada envío.

---

**Mantenedor:** CITE MVP Team · **Email:** codeplaigamessac@gmail.com
