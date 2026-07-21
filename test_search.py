import asyncio
from adaptadores.busqueda_lancedb import BusquedaLanceDB

async def main():
    busqueda = BusquedaLanceDB()
    resultado = busqueda.buscar(sinonimos=["mango peel"])
    print(f"Productos encontrados: {len(resultado.productos)}")
    for p in resultado.productos:
        print(f"- [{p.id_fuente}] {p.nombre} (Directo: {p.usa_insumo_directo})")
        print(f"  URL: {p.url}")
        print(f"  Ingredientes: {p.ingredientes[:100]}...")

if __name__ == "__main__":
    asyncio.run(main())
