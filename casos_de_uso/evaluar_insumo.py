from dominio.informe_scout import InformeScout
from casos_de_uso.dependencias import Dependencias
from casos_de_uso.etapas.ejecutor import etapa, etapa_sync
from casos_de_uso.etapas.interpretar_insumo import interpretar_insumo
from casos_de_uso.etapas.buscar_productos import buscar_productos
from casos_de_uso.etapas.generar_insight import generar_insight, generar_insight_parcial


def _contexto_regulatorio(d: Dependencias, interpretado, texto: str) -> str:
    """Etapa 5 todavia incorporada al contexto de la 3. T5.3 la saca a etapa
    propia, con su cache, su auditoria y su costo."""
    contexto = ""
    if d.verificador_fda:
        insumo_en = (interpretado.terminos_ingles[0] if interpretado.terminos_ingles
                     else interpretado.insumo_normalizado)
        contexto += d.verificador_fda.verificar(insumo_en, texto) + "\n\n"
    if d.verificador_rag:
        contexto += d.verificador_rag.verificar(interpretado.insumo_normalizado, texto) + "\n\n"
    return contexto


async def evaluar_insumo(texto: str, d: Dependencias,
                         usuario_id: str | None = None) -> InformeScout:
    ejecucion = d.auditoria.iniciar(texto, d.snapshot_version, usuario_id)

    # El estado se decide al final y se escribe en el finally. Hasta S2 se
    # escribia 'ok' al empezar y no se corregia nunca, asi que un run parcial
    # quedaba registrado como correcto.
    estado, motivo, emitir = "error", None, None
    try:
        interpretado = await etapa(d, ejecucion, "1", interpretar_insumo, texto)

        if not interpretado.reconocible:
            estado = "reformular"
            emitir = lambda: d.informes.pide_reformulacion(ejecucion)  # noqa: E731
        else:
            resultado = etapa_sync(d, ejecucion, "2a", buscar_productos, interpretado)
            contexto_reg = _contexto_regulatorio(d, interpretado, texto)

            # Guard tecnico. No es el paywall: eso llega en T6 con motivo
            # 'paywall', y P06 exige poder distinguirlos.
            if resultado.n_directos <= 2:
                insight = await etapa(d, ejecucion, "3", generar_insight_parcial,
                                      resultado, contexto_regulatorio=contexto_reg)
                estado, motivo = "parcial", "pocos_productos"
            else:
                insight = await etapa(d, ejecucion, "3", generar_insight,
                                      resultado, contexto_regulatorio=contexto_reg)
                estado = "ok"

            parcial = estado == "parcial"
            emitir = lambda: d.informes.emitir(ejecucion, insight, parcial)  # noqa: E731
    finally:
        # Siempre, incluso si el run reventó: la auditoria de Postgres acumula
        # el run entero en memoria y este es el punto donde se escribe.
        d.cache.vaciar_pendientes()
        d.auditoria.cerrar(ejecucion, estado, motivo)

    # Fuera del try a proposito: informes.ejecucion_id tiene FK a ejecuciones,
    # asi que el informe solo se puede emitir con el run ya escrito.
    return emitir()
