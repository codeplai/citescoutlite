#!/usr/bin/env python
"""
S8.0 - Crea el bucket de Storage donde viven los PDF de los informes.

## Por que hacia falta

El proyecto de Supabase no tenia **ningun** bucket. `RepositorioInformesSupabase`
sube el PDF al que diga `SUPABASE_BUCKET_INFORMES` (por defecto 'informes'), y
sin el la subida respondia:

    400 {"statusCode":"404","error":"Bucket not found","code":"NoSuchBucket"}

Como emitir el informe es el ultimo paso de `/consultas`, el efecto era que la
consulta **hacia todo el trabajo —y lo pagaba— y luego devolvia 500**. La fila
de `informes` no se escribia nunca, y por eso la tabla estaba a 0 mientras
`ejecuciones` se llenaba. Los cinco errores de test_e2e_s3.py eran esto.

## Privado, no publico

Se crea privado a proposito. Un informe es de un usuario concreto: la fila de
`public.informes` dice de quien, y lo que se entrega es una URL firmada con
caducidad (`_firmar`, y `firmar_de_nuevo` para regenerarla). Un bucket publico
haria que cualquiera con la ruta pudiera leer el informe de otro, que es justo
lo que el filtrado por dueno de `/informes/{id}` evita.

Es idempotente: si el bucket ya esta, no hace nada.

Uso:
  uv run python scripts/crear_bucket_informes.py
"""

import sys


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv()

    import httpx
    from adaptadores.entorno import (bucket_informes, cabeceras_servicio,
                                     url_supabase)

    nombre = bucket_informes()
    base = url_supabase()
    cabeceras = {**cabeceras_servicio(), "Content-Type": "application/json"}

    print("=== S8.0 - Bucket de informes ===")

    with httpx.Client(headers=cabeceras, timeout=30) as cliente:
        respuesta = cliente.get(f"{base}/storage/v1/bucket")
        respuesta.raise_for_status()
        existentes = [b.get("name") for b in respuesta.json()]

        if nombre in existentes:
            print(f"[OK]   El bucket '{nombre}' ya existe")
            return 0

        print(f"[INFO] Buckets actuales: {existentes or 'ninguno'}")

        respuesta = cliente.post(
            f"{base}/storage/v1/bucket",
            json={
                "name": nombre,
                "id": nombre,
                # Privado: se sirve con URL firmada, no por ruta adivinable.
                "public": False,
                "allowed_mime_types": ["application/pdf"],
                # 20 MB. Un informe ronda las decenas de KB; el tope esta para
                # que un fallo no llene el almacenamiento del proyecto.
                "file_size_limit": 20 * 1024 * 1024,
            },
        )

        if respuesta.status_code >= 300:
            print(f"[ERROR] No se pudo crear: {respuesta.status_code} "
                  f"{respuesta.text[:200]}")
            return 1

        print(f"[OK]   Bucket '{nombre}' creado (privado, solo PDF, max 20 MB)")

        comprobacion = cliente.get(f"{base}/storage/v1/bucket/{nombre}")
        if comprobacion.status_code == 200:
            datos = comprobacion.json()
            print(f"[OK]   Verificado: public={datos.get('public')}")
        else:
            print(f"[AVISO] No se pudo releer el bucket: {comprobacion.status_code}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
