from dominio.insumo import InsumoInterpretado
from dominio.resultado_busqueda import ResultadoBusqueda
from casos_de_uso.dependencias import Dependencias

def _detectar_uso_directo(ingredientes_texto: str, sinonimos_insumo: list[str]) -> bool:
    """Verifica si el insumo aparece directamente en el texto de ingredientes."""
    if not ingredientes_texto:
        return False
    ingredientes_lower = ingredientes_texto.lower()
    for sinonimo in sinonimos_insumo:
        sinonimo_lower = sinonimo.lower()
        if sinonimo_lower in ingredientes_lower:
            return True
    return False

def buscar_productos(d: Dependencias, interpretado: InsumoInterpretado) -> ResultadoBusqueda:
    resultado = d.catalogo.buscar(interpretado.sinonimos_busqueda)

    n_directos = 0
    for producto in resultado.productos:
        es_directo = _detectar_uso_directo(producto.ingredientes, interpretado.sinonimos_busqueda)
        producto.usa_insumo_directo = es_directo
        if es_directo:
            n_directos += 1

    resultado.n_directos = n_directos
    return resultado
