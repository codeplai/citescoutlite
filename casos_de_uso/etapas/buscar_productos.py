from dominio.insumo import InsumoInterpretado
from dominio.resultado_busqueda import ResultadoBusqueda
from casos_de_uso.dependencias import Dependencias

def buscar_productos(d: Dependencias, interpretado: InsumoInterpretado) -> ResultadoBusqueda:
    return d.catalogo.buscar(interpretado.sinonimos_busqueda)
