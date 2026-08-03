import json
import sqlite3

from adaptadores.migracion_sqlite import asegurar_esquema
from puertos.cache_llm import CacheLLM


class CacheSQLite(CacheLLM):
    def __init__(self, db_path: str = "agroscout.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_llm (
                clave_hash TEXT PRIMARY KEY,
                etapa TEXT,
                modelo TEXT,
                respuesta_json TEXT,
                snapshot_version TEXT,
                creado_en TEXT DEFAULT (datetime('now'))
            );
            """)
        asegurar_esquema(self.db_path)

    def obtener(self, clave: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            fila = conn.execute(
                "SELECT respuesta_json FROM cache_llm WHERE clave_hash = ?",
                (clave,)).fetchone()
        return json.loads(fila[0]) if fila else None

    def guardar(self, clave: str, valor: dict, etapa: str | None = None,
                modelo: str | None = None,
                snapshot_version: str | None = None) -> None:
        # etapa, modelo y snapshot_version se escriben de verdad: hasta S2 este
        # INSERT solo ponia clave y respuesta, y los dejaba en NULL (P02).
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            INSERT OR REPLACE INTO cache_llm
                (clave_hash, etapa, modelo, respuesta_json, snapshot_version)
            VALUES (?, ?, ?, ?, ?)
            """, (clave, str(etapa) if etapa is not None else None, modelo,
                  json.dumps(valor, ensure_ascii=False), snapshot_version))

    def vaciar_pendientes(self) -> None:
        """Escribe al vuelo: no hay nada pendiente que vaciar."""
