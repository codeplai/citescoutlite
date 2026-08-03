#!/usr/bin/env python
"""
T1.1 - Contrato de entorno contra Supabase.

Verifica que las claves de .env existen, mide el RTT real a la base y sondea
el modo de firma de los JWT (T1.2). No imprime el valor de ninguna clave.

Uso:
  uv run python scripts/verificar_supabase.py

Gate T1.1: RTT p95 < 300 ms. Por encima de 500 ms hay que rehacer la cuenta
de latencia del plan (PLAN-TIERS-S3.md, riesgo R1) antes de escribir adaptadores.
"""

import json
import os
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from adaptadores.entorno import ALIAS_CLAVE_SERVICIO, nombre_clave_de_servicio

GATE_P95_MS = 300
MUESTRAS = 20


def _cargar_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("[ERROR] Falta python-dotenv en el entorno activo")
        return False
    load_dotenv()
    return True


def verificar_variables():
    """Comprueba presencia (nunca contenido) de las variables de PLAN-TIERS-S3 §0."""
    faltan = []
    for nombre in ("SUPABASE_URL", "SUPABASE_ANON_KEY", "DATABASE_URL",
                   "SUPABASE_BUCKET_INFORMES"):
        if not os.environ.get(nombre, "").strip():
            faltan.append(nombre)

    servicio = nombre_clave_de_servicio()
    if servicio is None:
        faltan.append(" | ".join(ALIAS_CLAVE_SERVICIO))
    else:
        print(f"[OK]   Clave de servicio presente en {servicio}")

    if faltan:
        for nombre in faltan:
            print(f"[ERROR] Falta o esta vacia: {nombre}")
        return False

    print("[OK]   Las 5 variables obligatorias estan presentes")
    return True


def describir_conexion():
    """Identifica pooler vs conexion directa y si el host resuelve en IPv4."""
    partes = urlsplit(os.environ["DATABASE_URL"])
    host, puerto = partes.hostname, partes.port or 5432

    if puerto == 6543 or "pooler.supabase.com" in (host or ""):
        modo = "pooler de transacciones"
    else:
        modo = "conexion DIRECTA"

    print(f"[INFO] Host {host}:{puerto} -> {modo}")

    familias = set()
    try:
        for info in socket.getaddrinfo(host, puerto, proto=socket.IPPROTO_TCP):
            familias.add("IPv4" if info[0] == socket.AF_INET else "IPv6")
    except socket.gaierror as e:
        print(f"[ERROR] El host no resuelve: {e}")
        return False

    print(f"[INFO] Resuelve en: {', '.join(sorted(familias))}")
    if familias == {"IPv6"}:
        print("[AVISO] Solo IPv6. Funciona en esta red, pero una red IPv4 pura "
              "(la del CITE el dia de la demo) no llegara: usar el pooler 6543.")
    return True


def medir_rtt():
    """20 x 'select 1' sobre una conexion ya abierta. Devuelve (p50, p95) en ms."""
    try:
        import psycopg
    except ImportError:
        print("[ERROR] Falta psycopg. Instalar con: uv add \"psycopg[binary,pool]>=3.2\"")
        return None

    # prepare_threshold=None es obligatorio con el pooler de transacciones:
    # pgbouncer no conserva las sentencias preparadas entre checkouts y aparecen
    # errores intermitentes 'prepared statement "_pg3_0" already exists'.
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None,
                             connect_timeout=15) as conexion:
            usuario, version = conexion.execute(
                "select current_user, version()").fetchone()
            print(f"[OK]   Conectado como {usuario}")
            print(f"[INFO] {version.split(' on ')[0]}")

            latencias = []
            for _ in range(MUESTRAS):
                inicio = time.perf_counter()
                conexion.execute("select 1").fetchone()
                latencias.append((time.perf_counter() - inicio) * 1000)
    except Exception as e:
        print(f"[ERROR] {type(e).__name__}: {e}")
        return None

    latencias.sort()
    return statistics.median(latencias), latencias[int(len(latencias) * 0.95) - 1]


def sondear_jwks():
    """T1.2: si /jwks.json trae claves, la firma es asimetrica y no hace falta
    SUPABASE_JWT_SECRET; si viene vacio o 404, el proyecto usa HS256 heredado."""
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1/.well-known/jwks.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            claves = json.load(r).get("keys", [])
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        print(f"[AVISO] No se pudo sondear JWKS ({e}); decidir T1.2 a mano")
        return

    if claves:
        algoritmos = sorted({k.get("alg", "?") for k in claves})
        print(f"[OK]   JWT asimetrico ({', '.join(algoritmos)}): verificar por JWKS. "
              "SUPABASE_JWT_SECRET no se usa.")
    else:
        print("[OK]   JWT HS256 heredado: hace falta SUPABASE_JWT_SECRET.")


def main():
    print("=== T1.1 - Contrato de entorno Supabase ===")
    if not _cargar_env() or not verificar_variables():
        return 1
    if not describir_conexion():
        return 1

    medicion = medir_rtt()
    if medicion is None:
        return 1

    p50, p95 = medicion
    print(f"[INFO] RTT sobre {MUESTRAS} consultas: p50 {p50:.0f} ms - p95 {p95:.0f} ms")

    sondear_jwks()

    if p95 < GATE_P95_MS:
        print(f"[OK]   GATE T1.1 SUPERADO: p95 {p95:.0f} ms < {GATE_P95_MS} ms")
        return 0

    print(f"[ERROR] GATE T1.1 FALLA: p95 {p95:.0f} ms >= {GATE_P95_MS} ms")
    if p95 >= 500:
        print("        Por encima de 500 ms: rehacer la cuenta del riesgo R1 "
              "antes de escribir los adaptadores de T3.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
