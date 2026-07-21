from dominio.informe_scout import InformeScout
from casos_de_uso.dependencias import Dependencias
from casos_de_uso.etapas.ejecutor import etapa, etapa_sync
from casos_de_uso.etapas.interpretar_insumo import interpretar_insumo
from casos_de_uso.etapas.buscar_productos import buscar_productos
from casos_de_uso.etapas.generar_insight import generar_insight, generar_insight_parcial

async def evaluar_insumo(texto: str, d: Dependencias) -> InformeScout:
    ejecucion = d.auditoria.iniciar(texto, d.snapshot_version)

    interpretado = await etapa(d, ejecucion, 1, interpretar_insumo, texto)
    if not interpretado.reconocible:
        return d.informes.pide_reformulacion(ejecucion)

    resultado = etapa_sync(d, ejecucion, 2, buscar_productos, interpretado)
    
    # Etapa 5 (incorporada al contexto)
    contexto_reg = ""
    if d.verificador_fda:
        insumo_en = interpretado.terminos_ingles[0] if interpretado.terminos_ingles else interpretado.insumo_normalizado
        contexto_reg += d.verificador_fda.verificar(insumo_en, texto) + "\n\n"
    if d.verificador_rag:
        contexto_reg += d.verificador_rag.verificar(interpretado.insumo_normalizado, texto) + "\n\n"
        
    # Guardamos el contexto regulatorio en el insight
    if resultado.n_directos <= 2:
        insight = await etapa(d, ejecucion, 3, generar_insight_parcial, resultado, contexto_regulatorio=contexto_reg)
        return d.informes.emitir(ejecucion, insight, parcial=True)

    insight = await etapa(d, ejecucion, 3, generar_insight, resultado, contexto_regulatorio=contexto_reg)
    return d.informes.emitir(ejecucion, insight, parcial=False)
