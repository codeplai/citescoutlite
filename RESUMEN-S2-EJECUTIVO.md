# Resumen Ejecutivo: Auditoría Semana 2

**Fecha:** 2026-07-30  
**Estado:** Código listo para empezar S2 (S1 debe entregar 8 items críticos)

---

## ¿Qué es Semana 2?

**Objetivo:** 5 insumos piloto con datos reales (250-1000 productos) indexados y buscables con embeddings bge-m3.

**Resultado esperado:** 
- PDF de consulta con datos verificables en OFF (URL navegable)
- P03 en verde (búsqueda < 2s, 30+ productos)
- Base de datos para S3 (auth + paywall) y S4 (mapa comercial)

---

## Bloqueantes de Semana 1 (CRÍTICOS)

**Semana 1 DEBE entregar esto, o S2 no arranca:**

| Bloqueante | Impacto si falta | Test |
|---|---|---|
| Cost-meter real (`costo_usd > 0`) | PDF muestra US$0.00 → financieros cierran carpeta | `assert cost_usd > 0` |
| `fecha_dato` real (no `date.today()`) | Demo falla en vivo cuando CITE verifica en navegador | Comparar con OFF timestamp |
| Etapas 4 y 5 separadas | Paywall no es posible; costo por etapa invisible | `len(etapas) == 6` |
| Modelo por etapa (E1≠E3) | Costo falso; hits de cache cruzados | Cache key incluye modelo |
| Auth + JWT real | RLS no protege; demo de multi-tenant es ficción | Todos endpoints requieren JWT |
| Huawei MaaS verificado | Si no hay modelo barato, pitch se cae 2026-08-28 | Prueba modelos GLM accesibles |

**Acción:** Viernes 1 ago PM, pedirle a S1 demostración de cada uno arriba.

---

## Riesgos principales de S2

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| **OFF descarga lenta/timeout** | Media | Fallback a DEMO data → demo muestra inventado | Día 1: medir tiempo; si >10 min, usar export offline (descargar 2GB local) |
| **bge-m3 indexación tarda horas** | Baja | S5 no termina el jueves | Medir en máquina real; si >30 min, pasar a modelo más pequeño |
| **USDA_API_KEY no disponible** | Media | USDA = 0 productos, pero P03 alcanzable solo con OFF | Verificar Día 1; si falta, proceder con OFF |
| **Corpus eCFR no consigue** | Media | P08 base débil | Plan B: usar lista GRAS conocida (PDF público) |
| **4 semanas no admiten imprevistos** | Alta | Cualquier cosa que tarde 2h → se desborda | Orden de sacrificio: OCR → minería DuckDB → panel mínimo |

---

## Desglose de tiempo (5 días hábiles)

| Día | Tarea | Horas | Critico? |
|---|---|---|---|
| **Lun 5** | Setup + estructura | 2h | Sí |
| **Mar 6** | OFF + USDA paralelo | 8h | Sí |
| **Mié 7** | Embeddings bge-m3 | 6h | Sí |
| **Jue 8** | P95 latencia < 2s | 4h | Sí |
| **Vie 9** | E2E + corpus regulatorio | 8h | Sí |

**Total:** ≈28 horas de código + 12-24 de espera (descargas, embeddings). Paralelizable:
- Día 2: OFF + USDA en paralelo (2 devs)
- Día 5-6: Búsqueda + corpus regulatorio en paralelo

---

## Decisiones que hay que tomar YA

| Decisión | Opciones | Recomendación | Plazo |
|---|---|---|---|
| **OFF descarga: API live o export offline?** | A) API live (lento) · B) Export 2GB local (confiable) | Medir Día 1; si tarda >10 min, cambiar a B | Hoy |
| **USDA: esperar clave propia o ir sin?** | A) Esperar USDA_API_KEY · B) Proceder solo con OFF | Verificar today; si no hay, B | Hoy |
| **Motor PDF: xhtml2pdf (corre) o WeasyPrint (en docs)?** | Declarar Y usar uno; arreglar la clase | Mantener xhtml2pdf (ya funciona); renombrar clase | S1 cierre |
| **Embeddings: bge-m3 (438 MB) o modelo pequeño (33 MB)?** | Medir tiempo real en tu máquina; si >30 min, pequeño | bge-m3 es el plan; si falla, pequeño + declarar | Día 4 |

---

## Checklist de inicio S2 (Día 1 Lunes)

- [ ] S1 entregó: cost-meter real, fecha_dato real, etapas separadas, auth JWT
- [ ] USDA_API_KEY disponible en `.env.local` (o documentado "no disponible")
- [ ] `datasets/2026-07/` estructura creada
- [ ] API OFF y USDA probadas con curl
- [ ] Decisión: OFF live vs offline (guardar en `datasets/2026-07/README.md`)
- [ ] Equipo asignado: 2 devs (uno OFF/USDA, uno embeddings/búsqueda), 1 QA

---

## Hitos de cierre (Día 7 Viernes EOD)

**Esto demuestra que S2 está listo:**

```bash
# 1. Datos reales
ls -lh datasets/2026-07/off_productos.json
# Esperado: >50 KB, >250 líneas

# 2. Embeddings
python -c "import lancedb; db=lancedb.connect('vectores/'); print(db.open_table('productos').count_rows())"
# Esperado: ≥250

# 3. P95 < 2s
pytest test/test_latency.py -v
# Esperado: PASS

# 4. Golden set 5/5
python -m evals.runner_s2
# Esperado: 5/5 PASS

# 5. E2E sin errores
curl -H "Authorization: Bearer $JWT" http://localhost:8000/consultas \
  -d '{"insumo": "arándano"}' -o test.pdf && file test.pdf
# Esperado: PDF con datos reales, URLs navegables
```

**Si los 5 pasan → S2 LISTO para S3**

---

## Qué PASA SI S2 no termina a tiempo

| Escenario | Semana 3 | Semana 4 | Demo CDR |
|---|---|---|---|
| **Todo en verde Vie 9** | ✓ Multi-tenant + paywall limpio | ✓ Mapa comercial 2b | ✓ Demostrable |
| **S2 termina Lun 12 (3 días tarde)** | Presión en S3; RLS sin datos reales | P04/P05 dudosas | Riesgoso |
| **S2 bloqueado >5 días (datos incompletos)** | S3 comienza sin datos; todo inventado | 2b es ficción; demo es ficción | **COLAPSA** |

**Tolerancia:** S2 puede estar 48h en retraso; no más.

---

## Próxima acción

1. **Hoy:** Verificar que S1 entrega 8 bloqueantes (tabla arriba)
2. **Hoy:** Decidir OFF live vs offline; comunicar a devs
3. **Lunes 5 ago 8 AM:** Kickoff S2 con estructura de archivos + permisos de API
4. **Martes 6 ago PM:** Verificación de mitad de semana (OFF + USDA descargados)
5. **Viernes 9 ago EOD:** Demostración de todos los 5 hitos arriba

---

**Contacto para dudas:** Revisar `AUDITORIA-SEMANA-2.md` para análisis profundo  
**Cambios de código:** Ver `PLAN-EJECUCION-S2.md` con pseudocódigo ejecutable

