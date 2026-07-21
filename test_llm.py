import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from adaptadores.redactor_glm import RedactorGLM
from dominio.resultado_busqueda import ResultadoBusqueda
from dominio.producto_existente import ProductoExistente

async def main():
    api_key = os.environ["HUAWEI_MAAS_API_KEY"]
    base_url = os.environ["HUAWEI_MAAS_BASE_URL"]
    
    redactor = RedactorGLM(api_key=api_key, base_url=base_url)
    
    productos = ResultadoBusqueda(
        n_directos=1,
        productos=[ProductoExistente(
            id_fuente="OFF:123",
            nombre="Producto Test",
            categoria="Test",
            ingredientes="ingrediente1",
            usa_insumo_directo=True,
            url="http://test",
            fecha_dato="2026-07-20"
        )]
    )
    
    try:
        res = await redactor.redactar_insight(productos)
        print(res)
    except Exception as e:
        print("Error:", repr(e))

if __name__ == "__main__":
    asyncio.run(main())
