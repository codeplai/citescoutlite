#!/usr/bin/env python
"""
S8 - Puebla `staging_agente` con ofertas REALES del agente N3.

Es la contraparte de scripts/sembrar_staging_demo.py, que mete filas
sinteticas. Este corre el agente de verdad: busca en tiendas peruanas, extrae
la ficha, calcula el grounding y persiste.

## Por que hasta ahora no se podia

Tres cosas lo impedian, y las tres se cerraron en S8.0:

  1. La credencial de ModelArts daba 403. Resuelta (clave nueva).
  2. Nadie escribia la tabla. Resuelto: adaptadores/repositorio_staging.py.
  3. El agente no encontraba tiendas ni sacaba precios. Resuelto: la busqueda
     ahora es comercial y el precio sale del JSON-LD de la pagina.

## El camino es el de produccion

Se llama a `DescubrimientoCascada.descubrir_n3()`, que es lo que ejecutara el
flujo real cuando se conecte la cascada, y no a una version paralela para el
script. Lo que aqui se prueba es el camino de verdad.

Uso:
  uv run python scripts/poblar_staging_real.py
  uv run python scripts/poblar_staging_real.py --insumos quinua cacao maca
  uv run python scripts/poblar_staging_real.py --limpiar-demo
"""

import argparse
import asyncio
import logging
import sys

# Insumos del piloto. Ver datasets/ y la taxonomia de CITE.
INSUMOS_POR_DEFECTO = ["quinua", "arandano", "cacao", "cafe", "maca"]


async def ejecutar(insumos: list[str], pais: str, usuario_id: str,
                   limpiar_demo: bool) -> int:
    from adaptadores.db import pool
    from adaptadores.descubrimiento_cascada import DescubrimientoCascada
    from adaptadores.repositorio_staging import RepositorioStaging

    repo = RepositorioStaging()
    cascada = DescubrimientoCascada()

    if limpiar_demo:
        with pool().connection() as conn, conn.cursor() as cur:
            cur.execute("delete from public.staging_agente "
                        " where fuente_url like %s or fuente_url = ''",
                        ("%ejemplo.pe%",))
            print(f"[OK]   {cur.rowcount} oferta(s) sinteticas borradas")

    total_guardadas = 0
    total_con_grounding = 0

    for insumo in insumos:
        print(f"\n=== {insumo}")
        try:
            resultado, items = await cascada.descubrir_n3(insumo, pais)
        except Exception as e:
            print(f"   [ERROR] {type(e).__name__}: {str(e)[:160]}")
            continue

        if not items:
            print(f"   [AVISO] 0 ofertas ({resultado.estado}); "
                  f"{len(resultado.errores)} error(es) de descarga")
            continue

        ids = repo.guardar(items, usuario_id)
        total_guardadas += len(ids)

        for item in items:
            paso = (item.get("grounding_check_status") or {}).get("passed")
            total_con_grounding += 1 if paso else 0
            producto = item["producto_json"]
            marca = "OK  " if paso else "SIN "
            conversion = producto.get("conversion_soles") or {}
            en_soles = conversion.get("precio_pen")
            origen = conversion.get("moneda_origen")
            # Se enseña la cifra en soles y, si hubo conversión, de qué venía:
            # una tabla que solo muestre el resultado esconde que dos de estas
            # ofertas no son peruanas.
            columna = (f"S/ {en_soles}" if en_soles is not None
                       else str(producto.get("precio_local") or producto.get("precio")))
            desde = f"  <- {producto.get('precio')} {origen}" if origen and origen != "PEN" else ""
            print(f"   [{marca}] {str(producto.get('nombre'))[:40]:<42} "
                  f"{columna:<12} via={item['modelo_usado']}{desde}")

    print(f"\n[OK]   {total_guardadas} ofertas guardadas, "
          f"{total_con_grounding} con grounding en verde")

    with pool().connection() as conn, conn.cursor() as cur:
        n = cur.execute("select count(*) from public.staging_agente "
                        " where promoted_at is null").fetchone()[0]
    print(f"[OK]   staging_agente en cuarentena: {n} filas")
    return 0 if total_guardadas else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--insumos", nargs="+", default=INSUMOS_POR_DEFECTO)
    parser.add_argument("--pais", default="Peru")
    parser.add_argument("--email", default="demo-premium@cite.gob.pe")
    parser.add_argument("--limpiar-demo", action="store_true",
                        help="Borra antes las ofertas sinteticas de ejemplo.pe")
    parser.add_argument("--verboso", action="store_true")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()
    from adaptadores.bucle_asincrono import asegurar_bucle_compatible
    asegurar_bucle_compatible()

    logging.basicConfig(
        level=logging.INFO if args.verboso else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s")

    from adaptadores.db import pool

    with pool().connection() as conn, conn.cursor() as cur:
        fila = cur.execute("select id from auth.users where email = %s",
                           (args.email,)).fetchone()
    if not fila:
        print(f"[ERROR] No existe {args.email}. Corre antes:\n"
              f"        uv run python scripts/crear_usuarios_demo.py")
        return 1

    print("=== S8 - Poblar staging_agente con ofertas reales ===")
    print(f"[INFO] insumos: {', '.join(args.insumos)} | pais: {args.pais}")

    return asyncio.run(ejecutar(args.insumos, args.pais, str(fila[0]),
                                args.limpiar_demo))


if __name__ == "__main__":
    sys.exit(main())
