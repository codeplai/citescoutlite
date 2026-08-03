"""
Composicion de los casos de uso.

Dos composiciones, no una con banderas: el paywall se resuelve componiendo casos
de uso, no filtrando campos de un objeto ya generado (ADR-001 §2.4).

    generar_mapa_comercial -> etapas 1, 2a, 2b, 3        (plan gratuito)
    generar_dossier        -> etapas 1, 2a, 2b, 3, 4, 5  (plan premium)

La 2b (S4) va entre la busqueda y el insight, y esta en las dos composiciones:
el mapa comercial es lo que ve el plan gratuito, no un extra de pago. No llama
al LLM, asi que no consume presupuesto y no se comprueba el tope antes de ella.

`atender_consulta` es la frontera: lee el entitlement, arma el presupuesto del
run y elige. Vive aqui y no en api/main.py para que la regla de negocio no
dependa del framework web.
"""

from dataclasses import replace

from casos_de_uso.dependencias import Dependencias
from casos_de_uso.etapas.buscar_productos import buscar_productos
from casos_de_uso.etapas.ejecutor import etapa, etapa_sync
from casos_de_uso.etapas.formular_hipotesis import formular_hipotesis
from casos_de_uso.etapas.generar_insight import generar_insight, generar_insight_parcial
from casos_de_uso.etapas.interpretar_insumo import interpretar_insumo
from casos_de_uso.etapas.mapear_comercio import mapear_comercio
from casos_de_uso.etapas.verificar_regulacion import verificar_regulacion
from casos_de_uso.politica_suscripcion import entitlement_de
from casos_de_uso.presupuesto import Presupuesto
from dominio.dossier_regulatorio import DossierRegulatorio
from dominio.informe_scout import InformeScout

# Un run puede ser parcial por mas de una razon a la vez, pero `motivo_parcial`
# es una sola columna con check de tres valores (T2.1), porque P06 exige poder
# distinguirlos sin interpretar cadenas de texto. Cuando coinciden manda este
# orden:
#
#   presupuesto      - se dejaron de ejecutar etapas: es lo que mas cambia el
#                      resultado y lo unico que el operador puede corregir hoy.
#   pocos_productos  - el snapshot dio poco. Decirle "paga" a quien ademas tiene
#                      datos finos seria enganoso: las etapas premium tampoco
#                      habrian tenido de donde sacar mas.
#   paywall          - solo faltan las etapas que no cubre su plan.
PRECEDENCIA_MOTIVOS = ("presupuesto", "pocos_productos", "paywall")


def _motivo_dominante(motivos: set[str]) -> str | None:
    return next((m for m in PRECEDENCIA_MOTIVOS if m in motivos), None)


def _sin_presupuesto(d: Dependencias) -> bool:
    return d.presupuesto is not None and d.presupuesto.agotado


async def _etapas_premium(d, ejecucion, resultado, interpretado, texto, motivos):
    """Etapas 4 y 5, comprobando el presupuesto antes de cada una."""
    if _sin_presupuesto(d):
        motivos.add("presupuesto")
        return None, DossierRegulatorio(restricciones=[], citas=[], sin_dato=True)

    hipotesis = await etapa(d, ejecucion, "4", formular_hipotesis, resultado)

    if _sin_presupuesto(d):
        motivos.add("presupuesto")
        return hipotesis, DossierRegulatorio(restricciones=[], citas=[], sin_dato=True)

    dossier = await etapa(d, ejecucion, "5", verificar_regulacion,
                          interpretado, texto=texto)
    return hipotesis, dossier


async def _ejecutar(texto: str, d: Dependencias, usuario_id: str | None,
                    con_premium: bool) -> InformeScout:
    ejecucion = d.auditoria.iniciar(texto, d.snapshot_version, usuario_id)

    # El estado se decide al final y se escribe en el finally. Hasta S2 se
    # escribia 'ok' al empezar y no se corregia nunca, asi que un run parcial
    # quedaba registrado como correcto.
    estado, motivos, emitir = "error", set(), None
    try:
        if _sin_presupuesto(d):
            # Kill-switch antes de la etapa 1: cero llamadas al modelo. La
            # respuesta sigue siendo 200 con un informe vacio y su motivo.
            estado = "parcial"
            motivos.add("presupuesto")
            emitir = lambda: d.informes.emitir(ejecucion, None, True)  # noqa: E731
        else:
            interpretado = await etapa(d, ejecucion, "1", interpretar_insumo, texto)

            if not interpretado.reconocible:
                estado = "reformular"
                emitir = lambda: d.informes.pide_reformulacion(ejecucion)  # noqa: E731
            else:
                resultado = etapa_sync(d, ejecucion, "2a", buscar_productos, interpretado)

                # Etapa 2b: el mapa comercial. Va antes de comprobar el
                # presupuesto a proposito: no llama al LLM, no hay nada que
                # gastar, y un run que se queda sin saldo puede seguir
                # ensenando de que paises y marcas hay producto.
                mapa = etapa_sync(d, ejecucion, "2b", mapear_comercio, interpretado)

                # Guard tecnico. No es el paywall, y P06 comprueba justamente
                # que no se confundan.
                if resultado.n_directos <= 2:
                    motivos.add("pocos_productos")

                if _sin_presupuesto(d):
                    estado = "parcial"
                    motivos.add("presupuesto")
                    # Sin insight, pero con mapa: 2b ya corrio y no gasto nada.
                    emitir = lambda: d.informes.emitir(  # noqa: E731
                        ejecucion, None, True, mapa=mapa)
                else:
                    redactor = (generar_insight_parcial
                                if "pocos_productos" in motivos else generar_insight)
                    # El insight recibe tambien el mapa: los paises y marcas
                    # reales son material de cita (T4.2). Va como kwarg, asi
                    # que entra en la clave de cache.
                    insight = await etapa(d, ejecucion, "3", redactor, resultado,
                                          mapa=mapa.resumen_para_llm())

                    hipotesis = dossier = None
                    if con_premium:
                        hipotesis, dossier = await _etapas_premium(
                            d, ejecucion, resultado, interpretado, texto, motivos)
                    else:
                        motivos.add("paywall")

                    estado = "parcial" if motivos else "ok"
                    parcial = bool(motivos)
                    emitir = lambda: d.informes.emitir(  # noqa: E731
                        ejecucion, insight, parcial,
                        hipotesis=hipotesis, dossier=dossier, mapa=mapa)
    finally:
        # Siempre, incluso si el run reventó: la auditoria de Postgres acumula
        # el run entero en memoria y este es el punto donde se escribe.
        d.cache.vaciar_pendientes()
        d.auditoria.cerrar(ejecucion, estado, _motivo_dominante(motivos))

    # Fuera del try a proposito: informes.ejecucion_id tiene FK a ejecuciones,
    # asi que el informe solo se puede emitir con el run ya escrito.
    #
    # El motivo se adjunta aqui y no dentro de emitir(): el repositorio compone
    # el documento, pero quien sabe por que el run quedo parcial es la
    # composicion. Es el mismo valor que se escribe en ejecuciones.motivo_parcial.
    return emitir().model_copy(
        update={"motivo_parcial": _motivo_dominante(motivos)})


async def generar_mapa_comercial(texto: str, d: Dependencias,
                                 usuario_id: str | None = None) -> InformeScout:
    """Etapas 1, 2a y 3. Lo que ve el plan gratuito."""
    return await _ejecutar(texto, d, usuario_id, con_premium=False)


async def generar_dossier(texto: str, d: Dependencias,
                          usuario_id: str | None = None) -> InformeScout:
    """Etapas 1, 2a, 3, 4 y 5. Lo que ve el plan premium."""
    return await _ejecutar(texto, d, usuario_id, con_premium=True)


async def atender_consulta(texto: str, d: Dependencias,
                           usuario_id: str | None = None) -> InformeScout:
    """Frontera de aplicacion: entitlement, presupuesto y eleccion de composicion.

    El presupuesto se crea **por run** y se inyecta en una copia de
    Dependencias. Dependencias se construye una sola vez al arrancar y se
    comparte entre peticiones concurrentes: un contador mutable dentro del
    objeto compartido mezclaria el gasto de dos usuarios distintos.
    """
    if d.suscripciones is None:
        # Sin adaptador de suscripciones no hay paywall ni topes: es el modo en
        # que corren los tests deterministas de S2.
        return await generar_dossier(texto, d, usuario_id)

    contexto = d.suscripciones.contexto_de(usuario_id)
    entitlement = entitlement_de(contexto)
    presupuesto = Presupuesto.desde_entorno(contexto, entitlement.tope_mes_usd)

    d_run = replace(d, presupuesto=presupuesto)
    composicion = generar_dossier if entitlement.es_premium else generar_mapa_comercial
    return await composicion(texto, d_run, usuario_id)


async def evaluar_insumo(texto: str, d: Dependencias,
                         usuario_id: str | None = None) -> InformeScout:
    """Nombre historico de S1/S2. Se conserva para no romper llamadores."""
    return await generar_dossier(texto, d, usuario_id)
