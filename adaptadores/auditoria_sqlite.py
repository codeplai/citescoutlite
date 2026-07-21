import sqlite3
import json
import uuid
from datetime import datetime
from puertos.auditoria import Auditoria, Ejecucion

class EjecucionConcreta:
    def __init__(self, id_ej: str, snapshot_version: str, insumo_texto: str):
        self.id = id_ej
        self.snapshot_version = snapshot_version
        self.insumo_texto = insumo_texto

class AuditoriaSQLite(Auditoria):
    def __init__(self, db_path: str = "agroscout.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
            CREATE TABLE IF NOT EXISTS ejecuciones (
                id TEXT PRIMARY KEY,
                insumo_texto TEXT,
                snapshot_version TEXT,
                estado TEXT CHECK(estado IN ('ok','parcial','reformular','error')),
                creado_en TEXT DEFAULT (datetime('now'))
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS etapas_ejecucion (
                ejecucion_id TEXT REFERENCES ejecuciones(id),
                etapa INTEGER,
                entrada_json TEXT,
                salida_json TEXT,
                duracion_ms INTEGER,
                costo_usd REAL,
                tokens INTEGER DEFAULT 0,
                tokens_entrada INTEGER DEFAULT 0,
                tokens_salida INTEGER DEFAULT 0
            );
            """)

    def iniciar(self, texto: str, snapshot_version: str) -> Ejecucion:
        id_ej = str(uuid.uuid4())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            INSERT INTO ejecuciones (id, insumo_texto, snapshot_version, estado)
            VALUES (?, ?, ?, 'ok')
            """, (id_ej, texto, snapshot_version))
        return EjecucionConcreta(id_ej, snapshot_version, texto)

    def registrar_etapa(self, ejecucion: Ejecucion, etapa: int, entrada: dict, salida: dict, duracion_ms: int, costo_usd: float, tokens: int = 0, tokens_entrada: int = 0, tokens_salida: int = 0) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
            INSERT INTO etapas_ejecucion (ejecucion_id, etapa, entrada_json, salida_json, duracion_ms, costo_usd, tokens, tokens_entrada, tokens_salida)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ejecucion.id, etapa, json.dumps(entrada), json.dumps(salida), duracion_ms, costo_usd, tokens, tokens_entrada, tokens_salida))
