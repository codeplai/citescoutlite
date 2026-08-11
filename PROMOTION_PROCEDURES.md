# Promoción de ofertas — manual de operación

**Para:** equipo CITE que opera el panel
**Última revisión:** 2026-08-11 (S7)

Este documento explica cómo funciona la promoción de ofertas, cómo ajustarla y
cómo averiguar por qué una oferta concreta no entró. Está pensado para poder
operar sin pedir ayuda a desarrollo.

---

## 1. Qué es la promoción

El agente investigador busca productos en la web y los deja en **cuarentena**
(`staging_agente`). Nada de lo que encuentra se publica solo: primero hay que
promoverlo.

Promover una oferta significa marcarla como verificada. **No la mueve de sitio**:
la fila se queda donde está y se le ponen tres cosas.

```sql
promoted_at      = now()              -- cuándo
no_verificado    = false              -- ya no está en cuarentena
promotion_source = 'auto_watermark'   -- o 'manual_human'
```

> Si alguien menciona una tabla `catalogo_comercial`, no existe y no se va a
> crear. Fue una decisión de arquitectura (D1, agosto 2026): la procedencia de
> cada dato ya queda registrada, y una tabla más solo añadía sitios donde el
> mismo producto podía descuadrar.

**La cuarentena caduca a las 24 horas.** Lo que nadie promueva ni revise se
borra solo. No es un fallo: es lo que impide que se acumulen datos sin revisar.

---

## 2. El reparto 80/20

Cada noche, el sistema decide qué ofertas intenta promover solo:

- **~80 %** va por la vía automática: se validan contra las reglas y, si pasan,
  quedan promovidas sin que nadie intervenga.
- **~20 %** se aparta para revisión humana. Ese es el trabajo de la pestaña
  **Promociones** del panel.

El reparto **no es un sorteo cada vez**. Se calcula a partir del identificador de
la oferta y de una semilla que cambia **cada lunes a las 00:00 UTC**. Esto tiene
dos consecuencias prácticas:

1. Si el trabajo nocturno se repite, la misma oferta cae **siempre del mismo
   lado** esa semana. Reintentar no cambia decisiones ya tomadas.
2. Como la semilla cambia cada semana, el 20 % que se revisa a mano **no es
   siempre el mismo grupo de tiendas**. Si fuera fijo, las mismas tiendas
   acabarían eternamente en revisión manual y nadie miraría las demás.

El porcentaje se puede cambiar (ver §6).

---

## 3. Las reglas

Una oferta de la vía automática solo se promueve si cumple **todas** las reglas
activas. Están en la tabla `promotion_rules`.

### Estado actual

| Regla | Activa | Qué comprueba |
|---|---|---|
| `dato_fresco` | **Sí** | Que la captura no tenga más de 7 días |
| `url_presente` | **Sí** | Que haya URL de origen y sea `http(s)` |
| `grounding_ok` | **Sí** | Que los valores extraídos estuvieran de verdad en la página |
| `precio_vs_historico` | No | Que el precio esté dentro de un rango del histórico |
| `stock_minimo` | No | Que haya unidades disponibles |
| `tienda_no_marketplace` | No | Que la tienda no sea un marketplace |

**Las tres apagadas no son un olvido.** Están escritas pero el sistema todavía no
tiene el dato que necesitan:

- **`precio_vs_historico`** — no hay serie de precios por producto. Lo que existe
  (`tendencias_insumo`) es por insumo y trimestre, no por oferta concreta.
- **`stock_minimo`** — la mayoría de fichas de producto no dan una cifra de
  stock; dicen "disponible", que no es un número.
- **`tienda_no_marketplace`** — no hay clasificación de tiendas todavía.

Si enciendes una de ellas, **todas las ofertas serán rechazadas** con el motivo
`regla_no_evaluable` explicando qué falta. Es deliberado: se prefiere rechazar y
que se vea, antes que dar la regla por cumplida y que el informe diga que se
comprobó algo que nadie miró. Nada se pierde — lo rechazado sigue disponible
para revisión manual durante 24 h.

### Cómo cambiar una regla

> **Nota:** el editor de reglas en el panel **no está construido todavía**
> (quedó fuera de S7). De momento se hace con SQL.

Encender o apagar:

```sql
update public.promotion_rules set activo = true  where nombre_regla = 'stock_minimo';
update public.promotion_rules set activo = false where nombre_regla = 'dato_fresco';
```

Cambiar un parámetro (por ejemplo, aceptar datos de hasta 14 días):

```sql
update public.promotion_rules
   set expresion = '{"tipo": "date_freshness", "max_dias": 14}'::jsonb,
       updated_at = now()
 where nombre_regla = 'dato_fresco';
```

Ver cómo están ahora:

```sql
select nombre_regla, activo, expresion from public.promotion_rules order by activo desc;
```

**El campo `tipo` no se toca.** Es lo que le dice al sistema qué comprobación
aplicar; si se cambia por algo que no reconoce, la regla rechaza todo con el
motivo "Tipo de regla desconocido".

### Ejemplo: ¿qué pasa si cambio el rango de precio a 70-130 %?

```sql
update public.promotion_rules
   set expresion = '{"tipo": "price_range", "min_pct_historico": 70, "max_pct_historico": 130}'::jsonb
 where nombre_regla = 'precio_vs_historico';
```

**Hoy, nada.** La regla sigue apagada, y aunque se encendiera, no hay histórico
de precios contra el que comparar: rechazaría todo.

Cuando ese dato exista, el efecto sería: ampliar el rango deja pasar más ofertas
(un precio a mitad del histórico ya no se descarta) y estrecharlo rechaza más.
La forma de decidir el número no es adivinarlo, sino mirarlo: se deja una semana
con la regla puesta y se consulta cuántas rechazó (§5). Si rechaza casi todo, el
rango es demasiado estrecho para la realidad del mercado; si no rechaza nada, no
está protegiendo de nada.

---

## 4. Revisar el 20 % manual

En el panel, pestaña **Promociones**.

La lista trae las ofertas que esperan decisión: las que el reparto apartó para
revisión y las que el trabajo nocturno rechazó por alguna regla. Están ordenadas
poniendo delante **las que ya tienen un motivo de rechazo conocido** y, dentro de
esas, **las más antiguas**, que son las que están más cerca de caducar.

Por cada oferta se ve el producto, el precio, el enlace a la página original, las
horas que lleva en cuarentena (en ámbar si pasa de 18 h, o sea, quedan menos de
6) y el estado: los motivos por los que falló, o la etiqueta de que salió en el
muestreo manual.

- **Promover** — la da por buena. Antes de promover, el sistema **la vuelve a
  validar**, porque entre que se cargó la lista y se pulsa el botón puede haber
  pasado tiempo y un dato fresco haber caducado. Si falla alguna regla, **se
  promueve igual**: la decisión humana manda. Lo que no pasa es que se pierda el
  rastro — queda escrito qué reglas fallaban y quién decidió promoverla.
- **Rechazar** — deja constancia de que alguien la miró y dijo que no. No borra
  nada: caduca sola a las 24 h. La diferencia entre rechazar y no hacer nada es
  que en el registro queda la diferencia entre "se revisó y no valía" y "nadie
  llegó a mirarla".
- **Promover seleccionadas** — marca varias y promuévelas de una vez. Cada una se
  resuelve por separado: si una ya no está disponible, las demás entran igual y
  el aviso dice cuántas entraron y qué pasó con el resto.

**Promover y rechazar requieren rol de administrador.** Ver la lista puede
hacerlo cualquiera del equipo. Para nombrar a alguien administrador:

```sql
update public.perfiles set rol = 'admin' where email = 'quien@cite.gob.pe';
```

---

## 5. Interpretar los rechazos

### Qué se rechazó y por qué, hoy

```sql
select e ->> 'regla' as regla, e ->> 'motivo' as motivo, count(*)
  from public.promotion_log,
       lateral jsonb_array_elements(validation_errors) as e
 where result = 'rejected'
   and created_at >= now() - interval '24 hours'
 group by 1, 2
 order by 3 desc;
```

El widget del panel enseña lo mismo resumido, en "Motivos de rechazo".

### Por qué no entró una oferta concreta

```sql
select passed, errores, reglas_evaluadas, created_at
  from public.promotion_validation_log
 where staging_id = 'PEGA-AQUI-EL-ID'
 order by created_at desc;
```

`errores` trae una entrada por regla incumplida, con el motivo escrito en
castellano.

### De qué lado cayó una oferta en el reparto

```sql
select semilla, cubo, porcentaje, automatica
  from public.promotion_watermark_log
 where staging_id = 'PEGA-AQUI-EL-ID';
```

`cubo` es un número de 0 a 99. Si es menor que `porcentaje`, la oferta iba por la
vía automática. Sirve para responder "¿por qué esta no se promovió sola?" cuando
la respuesta es simplemente que le tocó revisión.

### Quién promovió qué

```sql
select l.created_at, l.promotion_type, l.result, p.email, s.producto_json ->> 'nombre'
  from public.promotion_log l
  left join public.perfiles p on p.id = l.promoted_by
  left join public.staging_agente s on s.staging_id = l.staging_id
 where l.created_at >= now() - interval '7 days'
 order by l.created_at desc;
```

`promoted_by` vacío significa que lo hizo el proceso automático. El nombre del
producto puede salir vacío si la oferta ya caducó: **el registro sobrevive
aunque la oferta desaparezca**, que es justo para lo que está.

---

## 6. El trabajo nocturno

Corre **cada día a las 04:00 UTC** (23:00 en Perú del día anterior), una hora
después del de alertas para que no coincidan. Necesita que el worker esté en
marcha:

```bash
uv run python scripts/start_worker.py
```

Lanzarlo a mano, sin esperar a la noche:

```bash
uv run python -c "
import asyncio
from dotenv import load_dotenv; load_dotenv()
from config.job_promotion_auto import job_promotion_auto
print(asyncio.run(job_promotion_auto()))
"
```

Probar con otro porcentaje **sin cambiar nada de forma permanente** — útil para
ver cuánto entraría si se estrechara el automático:

```bash
uv run python -c "
import asyncio
from dotenv import load_dotenv; load_dotenv()
from config.job_promotion_auto import job_promotion_auto
print(asyncio.run(job_promotion_auto(porcentaje=50)))
"
```

Devuelve un resumen con cuántas promovió, cuántas apartó para revisión, cuántas
rechazó y por qué regla. Debe terminar en menos de 15 minutos; el propio
resumen lo indica en `sla_ok`.

---

## 7. Problemas frecuentes

| Lo que se ve | Qué suele ser |
|---|---|
| No se promueve nada y todo aparece rechazado | Alguna regla sin dato está encendida. Mirar §5 y apagarla |
| La lista de revisión está vacía | O no hay ofertas nuevas, o la cuarentena caducó. Revisar si el agente está trayendo productos |
| "Necesitas rol de administrador" | La cuenta es de operador. Ver §4 |
| "No está en cuarentena (¿ya promovida o caducada?)" | Entre cargar la lista y pulsar, la oferta caducó o la promovió otro. Actualizar la lista |
| El panel muestra todo a cero | Normal si no ha corrido el trabajo nocturno o no hay ofertas |

---

## 8. Estado actual (agosto 2026)

Conviene saberlo antes de la demostración:

- **La cuarentena está vacía.** El agente no está trayendo productos porque la
  credencial del proveedor de modelos (Huawei ModelArts) responde *403 sin
  acceso* para todos los modelos del proyecto. Hasta que se renueve, el trabajo
  nocturno corre correctamente sobre cero ofertas y el panel muestra ceros.
- **El editor de reglas del panel no está construido.** Se hace por SQL (§3).
- **Tres de las seis reglas están apagadas** por falta de datos (§3).
- Lo que sí está probado de punta a punta es la mecánica: el reparto, la
  validación, la promoción, el registro y los avisos.

---

## Referencias

- Decisiones y estado detallado: [TIERSV3/S7_AUDITORIA_PREVIA.md](TIERSV3/S7_AUDITORIA_PREVIA.md)
- Plan de la semana: [TIERSV3/S7_PROMOCION_AUTOMATICA.md](TIERSV3/S7_PROMOCION_AUTOMATICA.md)
