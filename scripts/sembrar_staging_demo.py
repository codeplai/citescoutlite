#!/usr/bin/env python
"""
S8.0.5 - Siembra `staging_agente` con ofertas de demostracion.

## Por que hace falta

La tabla esta a 0 filas desde S2 y nadie la escribia (ver
adaptadores/repositorio_staging.py). Todo S7 —watermark, validador, job
nocturno, panel de revision— se construyo y se probo sobre cero ofertas. Sin
esto, la pantalla de Promociones del panel de S8 se demuestra vacia.

## Estas ofertas son sinteticas, y se nota a proposito

Las URL apuntan a `*.ejemplo.pe`, que no existe. No se usan dominios de tiendas
reales: seria fabricar precios y stock atribuidos a una empresa concreta, en la
misma tabla sobre la que despues se construye un registro de auditoria. Un dato
inventado que parece real es peor que ningun dato.

Por eso tambien son borrables de un golpe: `--limpiar` se lleva exactamente las
filas cuya `fuente_url` cae en ese dominio, sin tocar nada que venga del agente.

## Que ejercita

El reparto cubre las tres reglas que hoy estan activas en `promotion_rules`,
para que el validador de S7.3 tenga algo que rechazar y el panel algo que
mostrar en "motivos de rechazo":

  dato_fresco    unas cuantas con fecha vieja (el limite son 7 dias)
  url_presente   una con la URL vacia
  grounding_ok   varias con el grounding check en fallo

Las otras tres reglas siguen apagadas por falta de dato, no por falta de
fixtures: no hay serie de precios por producto, ni cifra de stock fiable, ni
clasificacion de tienda.

Uso:
  uv run python scripts/sembrar_staging_demo.py
  uv run python scripts/sembrar_staging_demo.py --limpiar
  uv run python scripts/sembrar_staging_demo.py --limpiar --cuantas 40
"""

import argparse
import random
import sys
from datetime import datetime, timedelta, timezone

DOMINIO = "ejemplo.pe"

# Insumos del ambito del proyecto (agro peruano), con rangos de precio y unidad
# plausibles para que los graficos del panel no salgan absurdos.
INSUMOS = [
    ("quinua", "cereales", "kg", (12.0, 28.0)),
    ("arandano", "frutas", "kg", (18.0, 42.0)),
    ("cacao", "cacao y derivados", "kg", (22.0, 55.0)),
    ("cafe", "cafe", "kg", (25.0, 68.0)),
    ("maca", "raices andinas", "kg", (30.0, 90.0)),
]

TIENDAS = ["andina", "surco", "mercado-central", "organicos", "valle"]

MARCAS = ["Cumbres Andinas", "Valle Sagrado", "Inka Fields", "Altiplano",
          "Sol de Oro", None]


def _oferta(rng: random.Random, indice: int) -> dict:
    insumo, categoria, unidad, (minimo, maximo) = rng.choice(INSUMOS)
    tienda = rng.choice(TIENDAS)
    precio = round(rng.uniform(minimo, maximo), 2)

    # Una de cada seis no da cifra de stock. Es el caso real: la mayoria de
    # fichas dicen "disponible" y el extractor deja null antes que inventarlo.
    stock = rng.choice([None, None, rng.randint(5, 400)])

    producto = {
        "nombre": f"{insumo.capitalize()} {rng.choice(['Organica', 'Premium', 'Selecta', 'Convencional'])}",
        "precio": precio,
        "precio_local": f"S/ {precio:.2f}",
        "marca": rng.choice(MARCAS),
        "stock": stock,
        "descripcion": f"{insumo.capitalize()} de productor nacional.",
        "unidad": unidad,
        "categoria": categoria,
        "pais_origen": "Peru",
        "fecha_disponibilidad": None,
    }

    # grounding_ok: una de cada cinco no paso el check. Es la regla que mas
    # rechaza en la practica, porque el modelo tiende a completar la marca.
    paso = rng.random() > 0.2
    grounding = {
        "passed": paso,
        "errores": [] if paso else [{
            "campo": "marca",
            "valor": producto["marca"] or "",
            "razon": "no encontrado en HTML",
        }],
        "campos_verificados": 4,
        "campos_ok": 4 if paso else 3,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "insumo": insumo,
        "pais": "Peru",
        "mes": datetime.now(timezone.utc).strftime("%Y-%m"),
        "producto_json": producto,
        # url_presente: la primera va sin URL, para que la regla tenga un caso.
        "fuente_url": "" if indice == 0
                      else f"https://tienda-{tienda}.{DOMINIO}/producto/{insumo}-{indice}",
        "html_capturado": f"<p>{producto['nombre']} — S/ {precio:.2f} por {unidad}</p>",
        "provenance": "agente",
        "grounding_check_status": grounding,
    }


def limpiar(conexion) -> int:
    """Borra solo las de demostracion. Se reconocen por el dominio."""
    borradas = conexion.execute(
        "delete from public.staging_agente where fuente_url like %s or fuente_url = ''",
        (f"%{DOMINIO}%",)).rowcount
    return borradas


def envejecer(conexion, ids: list, rng: random.Random) -> int:
    """Reparte las fechas hacia atras para que `dato_fresco` tenga que actuar.

    Esto lo hace el sembrado y **no** el repositorio: `creado_en` lo pone el
    esquema con `now()`, que es lo correcto para una oferta de verdad. Poder
    retrasarlo es una necesidad de la demostracion, no del dominio, y no tiene
    por que ensuciar el unico camino de escritura.
    """
    viejas = 0
    for staging_id in ids:
        # Una de cada cinco por encima del limite de 7 dias de `dato_fresco`.
        if rng.random() < 0.2:
            dias = rng.uniform(8, 20)
            viejas += 1
        else:
            dias = rng.uniform(0, 6)
        conexion.execute(
            "update public.staging_agente set creado_en = now() - %s::interval "
            "where staging_id = %s",
            (f"{dias:.2f} days", staging_id))
    return viejas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cuantas", type=int, default=25)
    parser.add_argument("--limpiar", action="store_true",
                        help="Borra las ofertas de demostracion anteriores")
    parser.add_argument("--email", default="demo-premium@cite.gob.pe",
                        help="Dueno de las ofertas sembradas")
    parser.add_argument("--semilla", type=int, default=20260811,
                        help="Semilla del generador: mismo valor, mismas ofertas")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv()
    import psycopg
    from adaptadores.entorno import url_base_datos
    from adaptadores.repositorio_staging import RepositorioStaging

    rng = random.Random(args.semilla)

    print("=== S8.0.5 - Sembrado de staging_agente (ofertas sinteticas) ===")

    with psycopg.connect(url_base_datos(), prepare_threshold=None,
                         autocommit=True, connect_timeout=15) as conexion:
        fila = conexion.execute(
            "select id from auth.users where email = %s", (args.email,)).fetchone()
        if not fila:
            print(f"[ERROR] No existe {args.email}. Corre antes:\n"
                  f"        uv run python scripts/crear_usuarios_demo.py")
            return 1
        usuario_id = str(fila[0])

        if args.limpiar:
            print(f"[OK]   {limpiar(conexion)} oferta(s) de demostracion borradas")

        items = [_oferta(rng, i) for i in range(args.cuantas)]
        ids = RepositorioStaging().guardar(items, usuario_id)
        print(f"[OK]   {len(ids)} ofertas insertadas para {args.email}")

        viejas = envejecer(conexion, ids, rng)
        print(f"[OK]   {viejas} con mas de 7 dias (las rechazara 'dato_fresco')")

        sin_grounding = sum(
            1 for i in items if not i["grounding_check_status"]["passed"])
        sin_url = sum(1 for i in items if not i["fuente_url"])
        print(f"[INFO] {sin_grounding} sin grounding, {sin_url} sin URL")

        total = conexion.execute(
            "select count(*) from public.staging_agente where promoted_at is null"
        ).fetchone()[0]
        print(f"[OK]   staging_agente en cuarentena: {total} filas")

    print("[OK]   Sembrado. Las URL son de ejemplo.pe: ninguna tienda real.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
