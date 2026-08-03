import json
import sqlite3
import uuid
from contextlib import closing, contextmanager

from adaptadores.ejecucion import EjecucionConcreta
from adaptadores.entorno import ruta_db_sqlite
from adaptadores.migracion_sqlite import asegurar_esquema
from puertos.auditoria import Auditoria, Ejecucion


class AuditoriaSQLite(Auditoria):
    """Rama local. Es el plan B de la demo (D5) y el modo en que corren los
    tests que no deben depender de la red.

    Escribe al vuelo, sin acumular como el adaptador de Postgres: contra un
    archivo local no hay RTT que amortizar.
    """

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or ruta_db_sqlite()
        self._init_db()

    @contextmanager
    def _conexion(self):
        """Confirma y cierra.

        `with sqlite3.connect(...)` confirma la transaccion pero **no** cierra
        la conexion, asi que usado tal cual deja un descriptor abierto sobre el
        archivo en cada llamada. closing() cierra; el `with conexion` anidado
        mantiene el commit.
        """
        with closing(sqlite3.connect(self.db_path)) as conexion, conexion:
            yield conexion

    def _init_db(self):
        with self._conexion() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("""
            CREATE TABLE IF NOT EXISTS ejecuciones (
                id TEXT PRIMARY KEY,
                usuario_id TEXT,
                insumo_texto TEXT,
                snapshot_version TEXT,
                estado TEXT CHECK(estado IN ('ok','parcial','reformular','error')),
                motivo_parcial TEXT CHECK(motivo_parcial IS NULL OR motivo_parcial IN ('paywall','pocos_productos','presupuesto')),
                creado_en TEXT DEFAULT (datetime('now'))
            );
            """)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS etapas_ejecucion (
                ejecucion_id TEXT REFERENCES ejecuciones(id),
                etapa TEXT,
                modelo TEXT,
                entrada_json TEXT,
                salida_json TEXT,
                duracion_ms INTEGER,
                costo_usd REAL,
                tokens INTEGER DEFAULT 0,
                tokens_entrada INTEGER DEFAULT 0,
                tokens_salida INTEGER DEFAULT 0,
                snapshot_version TEXT,
                cache_hit INTEGER DEFAULT 0
            );
            """)
        # Los CREATE de arriba no tocan un archivo que ya existe: la puesta al
        # dia de un .db viejo la hace esto (ver T2.3).
        asegurar_esquema(self.db_path)

    def iniciar(self, texto: str, snapshot_version: str,
                usuario_id: str | None = None) -> Ejecucion:
        id_ej = str(uuid.uuid4())
        with self._conexion() as conn:
            conn.execute("""
            INSERT INTO ejecuciones (id, usuario_id, insumo_texto, snapshot_version, estado)
            VALUES (?, ?, ?, ?, 'ok')
            """, (id_ej, usuario_id, texto, snapshot_version))
        return EjecucionConcreta(id_ej, snapshot_version, texto, usuario_id)

    def registrar_etapa(self, ejecucion: Ejecucion, etapa: str, entrada: dict,
                        salida: dict, duracion_ms: int, costo_usd: float,
                        tokens: int = 0, tokens_entrada: int = 0,
                        tokens_salida: int = 0, modelo: str | None = None,
                        cache_hit: bool = False) -> None:
        with self._conexion() as conn:
            conn.execute("""
            INSERT INTO etapas_ejecucion (ejecucion_id, etapa, modelo, entrada_json, salida_json, duracion_ms, costo_usd, tokens, tokens_entrada, tokens_salida, snapshot_version, cache_hit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ejecucion.id, str(etapa), modelo,
                  json.dumps(entrada, ensure_ascii=False),
                  json.dumps(salida, ensure_ascii=False),
                  duracion_ms, costo_usd, tokens, tokens_entrada, tokens_salida,
                  ejecucion.snapshot_version, int(cache_hit)))

    def cerrar(self, ejecucion: Ejecucion, estado: str,
               motivo_parcial: str | None = None) -> None:
        with self._conexion() as conn:
            conn.execute("""
            UPDATE ejecuciones SET estado = ?, motivo_parcial = ? WHERE id = ?
            """, (estado, motivo_parcial, ejecucion.id))
