"""
T5 — El análisis de ingredientes por mercado, servido para la pestaña.

## El cliente no es fuente de verdad sobre lo que se analiza

El endpoint recibe **dos identificadores**, no una lista de aditivos. Podría
haber recibido `{"aditivos": ["E200"], "categoria": "Jams"}` desde la SPA y
ahorrarse una consulta, y sería un error: quien manda la lista decide el
resultado, y entonces el informe deja de decir lo que dice el snapshot para
decir lo que le mandaron. Los aditivos se releen del producto que la etapa 2b
publicó en `etapas_ejecucion.salida_json`, que es la evidencia auditable del
run.

Efecto lateral que importa: dos personas que abran el mismo producto del mismo
informe ven exactamente lo mismo.

## 404 y 200 no son lo que parecen

- **404** si el producto no está en ese informe *o el informe no es tuyo*. No se
  distingue: un 403 confirmaría que el id existe, que es el mismo criterio que
  ya usa `GET /informes/{id}`.
- **200 con `aditivos: []`** cuando el producto no lleva ninguno reconocido. Es
  el **49,8 % del snapshot** y no es un error ni un hueco: es una etiqueta
  limpia, y para quien formula eso es información.

## Por qué esto puede tardar y aun así responde

La columna de EE. UU. va por agente en vivo (T1): 15-36 s medidos. Los aditivos
se evalúan en paralelo (T4), así que el producto cuesta lo que su aditivo más
lento, y cada uno tiene un techo de 45 s tras el cual **ese mercado** sale
`SIN_DATO` y los otros dos se entregan igual. La petición está acotada; lo que
no está garantizado es que las tres tarjetas vengan llenas, y eso la pantalla lo
dice.
"""

import json
import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from adaptadores.entorno import ruta_db_sqlite
from api.auth import USA_SUPABASE, get_current_user, usuario_actual_id
from casos_de_uso.analizar_aditivos_mercados import AnalizadorAditivos

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analisis-aditivos", tags=["analisis"])

# La etapa que publica el mapa comercial. Su `salida_json` es un MapaComercial
# entero, con la lista de productos.
ETAPA_MAPA = "2b"


def _analizador() -> AnalizadorAditivos:
    """Construye el analizador con lo que haya montado.

    Cada pieza se intenta por separado y a propósito: si falta el corpus del
    eCFR pero está el Anexo II, la pestaña enseña la columna europea en vez de
    no enseñar nada. `AnalizadorAditivos` ya devuelve `SIN_DATO` explicando qué
    mercado no se consultó.
    """
    agente = evaluador_ue = evaluador_codex = cache = None

    try:
        from adaptadores.agente_ecfr import AgenteECFR
        agente = AgenteECFR()
    except Exception as e:
        logger.warning("Sin agente del eCFR: %s", e)

    try:
        from adaptadores.evaluador_ue import EvaluadorUE
        evaluador_ue = EvaluadorUE()
    except Exception as e:
        logger.warning("Sin Anexo II: %s", e)

    try:
        from adaptadores.corpus_codex import EvaluadorCodex
        evaluador_codex = EvaluadorCodex()
    except Exception as e:
        logger.warning("Sin tabla del Codex: %s", e)

    try:
        if USA_SUPABASE:
            from adaptadores.cache_postgres import CachePostgres
            cache = CachePostgres()
        else:
            from adaptadores.cache_sqlite import CacheSQLite
            cache = CacheSQLite(ruta_db_sqlite())
    except Exception as e:
        logger.warning("Sin caché para el agente: %s", e)

    return AnalizadorAditivos(agente_us=agente, evaluador_ue=evaluador_ue,
                              evaluador_codex=evaluador_codex, cache=cache)


def _mapa_del_run(ejecucion_id: str, usuario_id: str | None) -> dict | None:
    """El `MapaComercial` que publicó la etapa 2b de ese run, si es del usuario.

    El filtro por dueño va **en la consulta**, no después: comprobarlo en Python
    obliga a traerse el mapa entero de un run ajeno para luego tirarlo, y basta
    olvidar una rama para que se escape.
    """
    if USA_SUPABASE:
        from adaptadores.db import pool
        with pool().connection() as conexion:
            fila = conexion.execute("""
                select x.salida_json
                  from public.etapas_ejecucion x
                  join public.ejecuciones e on e.id = x.ejecucion_id
                 where x.ejecucion_id = %s and x.etapa = %s and e.usuario_id = %s
                 order by x.id desc limit 1
            """, (ejecucion_id, ETAPA_MAPA, usuario_id)).fetchone()
        if not fila:
            return None
        return fila[0] if isinstance(fila[0], dict) else json.loads(fila[0])

    # Plan B en SQLite: no hay columna de usuario en `ejecuciones`, así que
    # tampoco hay a quién filtrar. Es una base local de un solo operador.
    #
    # `rowid` y no `id`: la tabla de SQLite (`auditoria_sqlite.py`) **no declara
    # columna `id`**, así que `ORDER BY id` lanzaba «no such column» y la rama
    # entera del plan B fallaba con un 500. Todas las tablas de SQLite tienen
    # `rowid` implícito salvo las WITHOUT ROWID, y esta no lo es.
    with sqlite3.connect(ruta_db_sqlite()) as conexion:
        fila = conexion.execute(
            "SELECT salida_json FROM etapas_ejecucion "
            "WHERE ejecucion_id = ? AND etapa = ? ORDER BY rowid DESC LIMIT 1",
            (ejecucion_id, ETAPA_MAPA)).fetchone()
    return json.loads(fila[0]) if fila and fila[0] else None


@router.get("/{ejecucion_id}/{producto_id:path}")
async def analizar_producto(ejecucion_id: str, producto_id: str,
                            current_user: dict = Depends(get_current_user)):
    """Las tres tarjetas de un producto del mapa comercial.

    `producto_id` va como `:path` porque los ids del snapshot llevan prefijo de
    fuente con dos puntos —`OFF:00000036`— y un id con barra tumbaría el
    enrutado si se declarara como segmento normal.
    """
    mapa = _mapa_del_run(ejecucion_id, usuario_actual_id(current_user))
    if not mapa:
        raise HTTPException(status_code=404, detail="Informe no encontrado")

    producto = next((p for p in mapa.get("productos", [])
                     if p.get("producto_id") == producto_id), None)
    if producto is None:
        raise HTTPException(
            status_code=404, detail="El producto no está en este informe")

    analizador = _analizador()
    try:
        analisis = await analizador.analizar(
            producto_id=producto_id,
            nombre=producto.get("nombre") or "",
            ingredientes=producto.get("ingredientes"),
            categoria=producto.get("categoria"),
        )
    except Exception as e:
        logger.exception("Análisis de aditivos falló para %s/%s",
                         ejecucion_id, producto_id)
        # El detalle lleva el tipo de excepción, no solo «no se pudo».
        #
        # La primera versión devolvía un texto genérico, y la pantalla lo
        # pintaba debajo de su propio encabezado genérico: el usuario veía dos
        # veces la misma frase y cero información sobre qué había pasado.
        # Diagnosticarlo exigía entrar al servidor a leer el log.
        #
        # Va el nombre de la clase, no el mensaje: un mensaje de excepción puede
        # arrastrar una ruta, una consulta o parte de una credencial.
        raise HTTPException(
            status_code=500,
            detail=f"No se pudo completar el análisis ({type(e).__name__}). "
                   f"El detalle está en el log del servidor.")

    p_adi = _aplicar_p_adi(analisis)

    respuesta = analisis.model_dump(mode="json")
    # Lo que la pantalla necesita para ser honesta sin recalcularlo: cuántos
    # mercados han respondido de verdad. Sin esto, la interfaz tendría que
    # recorrer las evaluaciones y contar, y acabaría contando distinto.
    resumen = _resumen(analisis)
    resumen["p_adi"] = p_adi
    resumen["llamadas_agente"] = analizador.llamadas_agente
    respuesta["resumen"] = resumen

    _auditar(ejecucion_id, producto_id, current_user, resumen)
    return respuesta


def _auditar(ejecucion_id: str, producto_id: str, usuario: dict,
             resumen: dict) -> None:
    """Deja constancia de la consulta. Nunca tumba la respuesta.

    Solo contra Postgres: `auditoria_panel` no existe en el SQLite del plan B, y
    dejar que falle en cada petición llenaría el log de la demo con un error que
    no lo es.
    """
    if not USA_SUPABASE:
        return
    try:
        from adaptadores.auditoria_panel import AuditoriaPanel
        AuditoriaPanel().registrar(
            "analisis_aditivos_consultado",
            usuario_id=usuario_actual_id(usuario),
            usuario_email=usuario.get("email"),
            entidad="producto", entidad_id=producto_id,
            detalles={"ejecucion_id": ejecucion_id, **resumen},
        )
    except Exception as e:
        logger.warning("No se pudo auditar el análisis: %s", e)


def _aplicar_p_adi(analisis) -> dict:
    """Pasa P-ADI y **degrada las celdas que no lo pasan**, no solo las anota.

    Registrar el fallo en el log y enseñar la celda igual sería quedarse a
    medias: quien lee la pantalla no ve el log. Una celda cuya cita no aparece
    en la fuente que dice citar es exactamente lo que este subsistema promete
    que no va a existir, así que se sustituye por `SIN_DATO` diciendo por qué.

    Cuesta unos milisegundos porque los dos corpus ya están cargados como
    singletons: es el mismo diccionario que acaba de responder la consulta.
    """
    try:
        from adaptadores.corpus_anexo_ii import corpus as corpus_ue
        from adaptadores.corpus_ecfr import corpus as corpus_us
        from casos_de_uso.validar_analisis import validar
    except Exception as e:
        logger.warning("P-ADI no disponible: %s", e)
        return {"ejecutado": False}

    try:
        resultado = validar(analisis, corpus_ecfr=_o_none(corpus_us),
                            corpus_anexo=_o_none(corpus_ue))
    except Exception as e:
        logger.warning("P-ADI falló: %s: %s", type(e).__name__, e)
        return {"ejecutado": False}

    degradadas = 0
    for fallo in resultado.fallos:
        logger.warning("P-ADI: %s", fallo)
        if fallo.regla != "P-ADI-2":
            continue
        for aditivo in analisis.aditivos:
            if aditivo.nombre != fallo.aditivo:
                continue
            for n, evaluacion in enumerate(aditivo.evaluaciones):
                if evaluacion.mercado != fallo.mercado:
                    continue
                aditivo.evaluaciones[n] = evaluacion.model_copy(update={
                    "autorizado": "SIN_DATO",
                    "limite_valor": None,
                    "cita_literal": "",
                    "nota": ("La cita de esta celda ya no se encuentra en la "
                             "fuente que dice citar, así que no se publica el "
                             "veredicto. Comprobar a mano en el enlace."),
                })
                degradadas += 1

    return {
        "ejecutado": True,
        "verificadas": resultado.verificadas,
        "no_verificables": resultado.no_verificables,
        "degradadas": degradadas,
        "fallos": [str(f) for f in resultado.fallos],
    }


def _o_none(constructor):
    """El corpus, o `None` si no está montado. P-ADI trata `None` como
    «no verificable», que es lo correcto: sin corpus no se comprobó nada."""
    try:
        return constructor()
    except Exception:
        return None


def _resumen(analisis) -> dict:
    """Cuántas celdas hay de cada clase. Es lo que se dice en voz alta."""
    celdas = [e for a in analisis.aditivos for e in a.evaluaciones]
    return {
        "aditivos": len(analisis.aditivos),
        "celdas": len(celdas),
        "sin_dato": sum(1 for e in celdas if e.autorizado == "SIN_DATO"),
        "condicionadas": sum(1 for e in celdas if e.condicionado),
        "prohibiciones": sum(
            1 for e in celdas if e.autorizado in ("NO", "NO_CONDICIONADO")),
        "categoria_deducida": analisis.matriz_ue is not None,
        "mercados_que_prohiben": analisis.mercados_que_prohiben(),
    }
