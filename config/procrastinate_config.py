"""Procrastinate configuration for AgroScout job queue."""

import os
from dotenv import load_dotenv
import procrastinate

load_dotenv(".env")

# Conectar a Supabase Postgres
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not configured in .env")

# Crear la app de Procrastinate con psycopg3
app = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=DATABASE_URL))


# ============================================================
# EJEMPLO DE JOBS
# ============================================================

@app.task(name="hello_world")
async def hello_world(name: str):
    """Job de prueba."""
    return f"Hola {name} desde Procrastinate!"


@app.task(name="generate_report")
async def generate_report(consulta_id: int, etapa: str):
    """Generar reporte para una consulta (stub para S1)."""
    print(f"📝 Generando reporte para consulta {consulta_id}, etapa {etapa}")
    # TODO: Implementar lógica de reporte en S6
    return {"status": "pending", "consulta_id": consulta_id}


@app.task(name="run_agent")
async def run_agent(insumo: str, pais: str, nivel_costo: int):
    """Ejecutar agente de búsqueda (stub para S10)."""
    print(f"🤖 Ejecutando agente: {insumo} en {pais} (nivel {nivel_costo})")
    # TODO: Implementar lógica del agente en S10
    return {"status": "pending", "insumo": insumo, "pais": pais}


if __name__ == "__main__":
    # Inicializar base de datos
    import asyncio
    asyncio.run(app.open())
    print("✅ Procrastinate app configured and ready")
