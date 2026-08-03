"""
T6 - Equivalente local del contexto de suscripcion. Plan B de la demo.

La rama sqlite tiene que distinguir gratuito de premium igual que la remota: el
bloque del guion que ensena el paywall usa las dos cuentas, y si aqui todo el
mundo fuera premium el plan B no serviria para ensayarlo.

El plan vive en `usuarios.plan`, que anade migracion_sqlite.
"""

import sqlite3
from contextlib import closing, contextmanager

from adaptadores.entorno import ruta_db_sqlite
from adaptadores.migracion_sqlite import asegurar_esquema
from puertos.suscripciones import ContextoSuscripcion, Suscripciones

PLAN_POR_DEFECTO = "gratuito"


class SuscripcionesSQLite(Suscripciones):
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or ruta_db_sqlite()
        asegurar_esquema(self.db_path)

    @contextmanager
    def _conexion(self):
        with closing(sqlite3.connect(self.db_path)) as conexion, conexion:
            yield conexion

    def contexto_de(self, usuario_id: str | None) -> ContextoSuscripcion:
        if not usuario_id:
            return ContextoSuscripcion(PLAN_POR_DEFECTO, 0.0, 0.0)

        with self._conexion() as conexion:
            fila = conexion.execute(
                "SELECT plan FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
            plan = (fila[0] if fila and fila[0] else PLAN_POR_DEFECTO)

            # strftime('%Y-%m') sobre creado_en: el equivalente local de
            # date_trunc('month'). El historico migrado tiene usuario_id nulo,
            # asi que no suma a nadie.
            usuario = conexion.execute("""
                SELECT COALESCE(SUM(x.costo_usd), 0) FROM etapas_ejecucion x
                  JOIN ejecuciones e ON e.id = x.ejecucion_id
                 WHERE e.usuario_id = ?
                   AND strftime('%Y-%m', e.creado_en) = strftime('%Y-%m', 'now')
            """, (usuario_id,)).fetchone()[0]

            global_ = conexion.execute("""
                SELECT COALESCE(SUM(x.costo_usd), 0) FROM etapas_ejecucion x
                  JOIN ejecuciones e ON e.id = x.ejecucion_id
                 WHERE strftime('%Y-%m', e.creado_en) = strftime('%Y-%m', 'now')
            """).fetchone()[0]

        return ContextoSuscripcion(plan, float(usuario), float(global_))
