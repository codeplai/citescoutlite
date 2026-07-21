import sqlite3
import json
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
                etapa INTEGER,
                modelo TEXT,
                respuesta_json TEXT,
                snapshot_version TEXT,
                creado_en TEXT DEFAULT (datetime('now'))
            );
            """)

    def obtener(self, clave: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT respuesta_json FROM cache_llm WHERE clave_hash = ?", (clave,))
            row = cur.fetchone()
            if row:
                return json.loads(row[0])
            return None

    def guardar(self, clave: str, valor: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            INSERT OR REPLACE INTO cache_llm (clave_hash, respuesta_json)
            VALUES (?, ?)
            """, (clave, json.dumps(valor)))
