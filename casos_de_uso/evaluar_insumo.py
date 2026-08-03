from dominio.informe_scout import InformeScout
from casos_de_uso.dependencias import Dependencias
from casos_de_uso.etapas.ejecutor import etapa, etapa_sync
from casos_de_uso.etapas.interpretar_insumo import interpretar_insumo
from casos_de_uso.etapas.buscar_productos import buscar_productos
from casos_de_uso.etapas.generar_insight import generar_insight, generar_insight_parcial


async def evaluar_insumo(texto: str, d: Dependencias,
                         usuario_id: str | None = None) -> InformeScout:
    ejecucion = d.auditoria.iniciar(texto, d.snapshot_version, usuario_id)

    # El estado se decide al final y se escribe en el finally. Hasta S2 se
    # escribia 'ok' al empezar y no se corregia nunca, asi que un run parcial
    # quedaba registrado como correcto.
    estado, motivo = "error", None
    try:
        interpretado = await etapa(d, ejecucion, "1", interpretar_insumo, texto)
        if not interpretado.reconocible:
            estado = "reformular"
            return d.informes.pide_reformulacion(ejecucion)

        resultado = etapa_sync(d, ejecucion, "2a", buscar_productos, interpretado)

        # Etapa 5 (todavia incorporada al contexto; T5.3 la saca a etapa propia)
        contexto_reg = ""
        if d.verificador_fda:
            insumo_en = interpretado.terminos_ingles[0] if interpretado.terminos_ingles else interpretado.insumo_normalizado
            contexto_reg += d.verificador_fda.verificar(insumo_en, texto) + "\n\n"
        if d.verificador_rag:
            contexto_reg += d.verificador_rag.verificar(interpretado.insumo_normalizado, texto) + "\n\n"

        # Guard tecnico. No es el paywall: eso llega en T6 con motivo 'paywall'.
        if resultado.n_directos <= 2:
            insight = await etapa(d, ejecucion, "3", generar_insight_parcial, resultado, contexto_regulatorio=contexto_reg)
            estado, motivo = "parcial", "pocos_productos"
            return d.informes.emitir(ejecucion, insight, parcial=True)

        insight = await etapa(d, ejecucion, "3", generar_insight, resultado, contexto_regulatorio=contexto_reg)
        estado = "ok"
        return d.informes.emitir(ejecucion, insight, parcial=False)
    finally:
        # Siempre, incluso si el run reventó: el adaptador de Postgres acumula
        # las etapas en memoria y este es el punto donde se vuelcan.
        d.cache.vaciar_pendientes()
        d.auditoria.cerrar(ejecucion, estado, motivo)
