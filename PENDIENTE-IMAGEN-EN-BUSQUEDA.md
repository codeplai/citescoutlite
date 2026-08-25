# Pendiente: llevar `imagen_url` de la base a la búsqueda y a la ficha

**Abierto el 2026-08-24.** Estado del snapshot: `2026-07`.

El dato existe y es real, pero se queda a mitad de camino: está en el archivo
del snapshot y **no llega al índice vectorial ni a la interfaz**. Hoy, una
consulta devuelve productos sin foto aunque la URL esté guardada.

---

## Qué hay hecho

| Dónde | ¿Tiene `imagen_url`? |
|---|---|
| `datasets/2026-07/productos_merged.json` | **Sí** — 20.187 de 28.690 productos OFF (70 %) |
| Tabla LanceDB `productos` | No |
| `adaptadores/busqueda_lancedb.py` (`_COLUMNAS`) | No |
| `dominio/producto_existente.py` (`ProductoExistente`) | No |
| Ficha en la SPA | No |

La URL se deriva del código de barras y **se verifica con un HEAD** antes de
escribirla; cuando la imagen no existe, el campo queda en `null`. Los productos
USDA quedan siempre en `null`: su ficha no publica imagen y derivarla del código
de OFF apuntaría a otro producto.

Lo genera `etl/imagenes_off.py`. Las 28.635 comprobaciones están cacheadas en
`datasets/2026-07/imagenes_off.jsonl`, así que **rehacer este paso cuesta 7
segundos, no 95 minutos**, mientras ese archivo siga ahí.

---

## Lo que falta, en orden

### 1. La columna en LanceDB

La tabla tiene hoy nueve columnas más `embedding`, y sus 29.508 filas ya están
indexadas. Dos caminos:

**a) Añadir la columna sin reindexar** (minutos). `add_columns` acepta un dict
de expresiones SQL, y `merge_insert` permite luego volcar el valor por fila
cruzando por `id`:

```python
tabla.add_columns({"imagen_url": "''"})          # existe en lancedb 0.36
tabla.merge_insert("id").when_matched_update_all().execute(filas)
```

Hay que comprobar sobre una copia que `merge_insert` no obligue a reescribir
también el `embedding`: si lo pide, esta vía deja de ser barata.

**b) Reindexar entero** con `etl/tier4_gpu.py` añadiendo el campo (15-30 min de
GPU). Más lento pero sin sorpresas de API.

Sea cual sea, hay que añadir `imagen_url` a la construcción de filas de
`etl/indexar_incremental.py` para que lo nuevo también la traiga.

### 2. El adaptador de búsqueda

`adaptadores/busqueda_lancedb.py:20` — añadir `"imagen_url"` a `_COLUMNAS`.

La lista excluye `embedding` a propósito, para no arrastrar 1024 flotantes por
fila. Una URL sí cabe.

### 3. El dominio — **ojo con la caché**

`dominio/producto_existente.py` — añadir el campo al modelo, y rellenarlo en
`busqueda_lancedb.py` al construir cada `ProductoExistente`.

**Este paso invalida caché.** La clave incluye la huella del esquema de la etapa
(`_huella_de_esquema`, en `casos_de_uso/etapas/ejecutor.py`): tocar los campos
de un modelo tira lo cacheado que dependa de él, y es deliberado —evita que una
etapa siga sirviendo un resultado al que le falta justo el campo nuevo, y en
silencio—. Después hay que resembrar:

```bash
uv run python scripts/sembrar_cache_local.py
```

Necesita red y credenciales de Supabase. Sin resembrar, `test_plan_b_sqlite`
falla: corre sin api_key a propósito y se queda sin nada que servir.

### 4. La ficha en la SPA

`frontend/src/components/Result.vue` — pintar la miniatura.

Tiene que aguantar el `null`: **3 de cada 10 productos OFF no tienen imagen**, y
la ficha no puede quedar rota ni mostrar un hueco sin explicar.

---

## Coste y limitaciones

Unos **30-40 min** de trabajo, más el reindexado si se va por la vía (b) y el
resembrado de caché del paso 3.

Dos cosas que conviene saber antes de empezar:

- **Es la primera foto subida, no la frontal curada.** La API de OFF sirve
  `image_front_url` en el idioma del producto; traerla son 28.642 peticiones a
  las 16-37 por minuto que aguanta esa API, entre 13 y 30 horas. La imagen `1`
  suele ser la frontal, pero no siempre.
- **El 30 % se queda sin foto** y eso no se arregla con más descargas: esos
  productos no tienen ninguna imagen en OFF.

---

## Cómo comprobar que quedó bien

```bash
# la columna llegó al índice
./venv/Scripts/python.exe -c "import lancedb; print([f.name for f in lancedb.connect('vectores').open_table('productos').schema])"

# una búsqueda real devuelve la URL
./venv/Scripts/python.exe -c "from adaptadores.busqueda_lancedb import BusquedaLanceDB; print(BusquedaLanceDB('vectores').buscar(['leche de coco'], k=3).productos[0])"

# no se rompió nada
./venv/Scripts/python.exe -m evals.runner_s2     # golden set: 5/5
uv run python -m pytest test/ -q
```

---

## Contexto

Sale de la actualización del snapshot del 2026-08-24, que dejó 29.508 productos
(29.054 + 406 terminados de PE/CH/DE + 48 de la canasta peruana). El
procedimiento completo está en `datasets/2026-07/README.md`; el pipeline
desatendido, en `pipeline.bat`.
