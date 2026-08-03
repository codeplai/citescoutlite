"""
Pone al dia el esquema de agroscout.db.

Existe por lo que se verifico en T2.3: `CREATE TABLE IF NOT EXISTS` no migra
nada, asi que el archivo del repo se quedo con el esquema del dia que se creo
mientras el codigo seguia avanzando. Resultado: el INSERT de la auditoria y el
SELECT del login fallaban contra la base que esta en el repositorio, y con
ellos el plan B de la demo (APP_DB=sqlite), que segun el riesgo R4 solo existe
si esta rama funciona.

Se aplica sola al construir los adaptadores SQLite. Es idempotente: consulta
las columnas que hay y solo anade las que faltan.
"""

import sqlite3
from contextlib import closing

# tabla -> (columna, tipo). Solo se anaden columnas; nunca se borra ni se
# reescribe nada, para no tocar las 54/94/47 filas del historico.
COLUMNAS_REQUERIDAS: dict[str, tuple[tuple[str, str], ...]] = {
    "ejecuciones": (
        ("usuario_id", "TEXT"),
        ("motivo_parcial", "TEXT"),
    ),
    "etapas_ejecucion": (
        ("modelo", "TEXT"),
        ("snapshot_version", "TEXT"),
        ("cache_hit", "INTEGER DEFAULT 0"),
    ),
    "usuarios": (
        # api/main.py la lee en el login de la rama sqlite.
        ("org_id", "TEXT"),
        # El plan B tiene que distinguir gratuito de premium igual que la rama
        # remota, o el bloque del guion que ensena el paywall no se puede
        # ensayar sin red.
        ("plan", "TEXT DEFAULT 'gratuito'"),
    ),
    "cache_llm": (
        ("etapa", "TEXT"),
        ("modelo", "TEXT"),
        ("snapshot_version", "TEXT"),
    ),
}


def asegurar_esquema(db_path: str) -> list[str]:
    """Anade las columnas que falten. Devuelve las que anadio, para poder
    reportarlas en los tests en vez de arreglar en silencio."""
    anadidas: list[str] = []
    # closing() ademas del `with`: el context manager de sqlite3 confirma la
    # transaccion pero no cierra la conexion, y este helper lo llama cada
    # adaptador al construirse.
    with closing(sqlite3.connect(db_path)) as conexion, conexion:
        existentes = {
            fila[0] for fila in conexion.execute(
                "select name from sqlite_master where type = 'table'")
        }
        for tabla, columnas in COLUMNAS_REQUERIDAS.items():
            if tabla not in existentes:
                continue
            actuales = {
                fila[1] for fila in conexion.execute(f"pragma table_info({tabla})")
            }
            for nombre, tipo in columnas:
                if nombre not in actuales:
                    conexion.execute(
                        f"alter table {tabla} add column {nombre} {tipo}")
                    anadidas.append(f"{tabla}.{nombre}")
    return anadidas
