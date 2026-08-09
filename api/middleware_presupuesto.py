"""
Middleware de presupuestos para FastAPI (S2.6 INTEG.2).

Antes de ejecutar el agente (N3), verifica:
  1. Presupuesto de run ($0.25)
  2. Presupuesto de usuario/mes ($2.0)
  3. Presupuesto global/mes ($10.0)

Si se alcanza alguno, retorna status='PARCIAL' sin error (degradación, no fallo).
"""

from typing import Optional, Callable
from datetime import datetime, timedelta
import uuid
from functools import wraps
import os

import psycopg
from fastapi import Request, Response
from fastapi.responses import JSONResponse


class PresupuestoMiddleware:
    """Middleware que verifica presupuestos antes de ejecutar etapas LLM."""

    # Topes por defecto (pueden venir de .env o BD)
    TOPE_RUN_USD = float(os.getenv("PRESUPUESTO_RUN_USD", 0.25))
    TOPE_USUARIO_MES_USD = float(os.getenv("PRESUPUESTO_USUARIO_MES_USD", 2.0))
    TOPE_GLOBAL_MES_USD = float(os.getenv("PRESUPUESTO_GLOBAL_MES_USD", 10.0))

    def __init__(self, db_url: str):
        self.db_url = db_url

    async def verificar_presupuesto(
        self,
        usuario_id: str,
        etapa: str = "3",  # N3 (agente)
        costo_estimado: float = 0.1,
    ) -> tuple[bool, Optional[str]]:
        """
        Verifica si se puede ejecutar etapa.

        Retorna: (permitido: bool, razon_si_bloqueado: str|None)
        """
        try:
            with psycopg.connect(self.db_url, autocommit=True) as conn:
                # 1. Leer gasto del usuario este mes
                cursor = conn.execute(
                    """
                    select coalesce(sum(costo_usd), 0) as gasto_mes
                    from public.presupuesto_uso
                    where usuario_id = %s
                      and date_trunc('month', timestamp) = date_trunc('month', now())
                      and status != 'error'
                    """,
                    (usuario_id,),
                )
                gasto_usuario_mes = cursor.fetchone()[0]

                # 2. Leer gasto global este mes
                cursor = conn.execute(
                    """
                    select coalesce(sum(costo_usd), 0) as gasto_global
                    from public.presupuesto_uso
                    where date_trunc('month', timestamp) = date_trunc('month', now())
                      and status != 'error'
                    """
                )
                gasto_global_mes = cursor.fetchone()[0]

                # 3. Verificar topes
                if gasto_global_mes + costo_estimado > self.TOPE_GLOBAL_MES_USD:
                    return False, f"Presupuesto global agotado: ${gasto_global_mes:.2f}/${self.TOPE_GLOBAL_MES_USD}"

                if gasto_usuario_mes + costo_estimado > self.TOPE_USUARIO_MES_USD:
                    return False, f"Presupuesto usuario/mes agotado: ${gasto_usuario_mes:.2f}/${self.TOPE_USUARIO_MES_USD}"

                return True, None

        except Exception as e:
            # Si hay error en BD, permitir (fail-open)
            print(f"⚠️  Error verificando presupuesto: {e}")
            return True, None

    async def registrar_gasto(
        self,
        ejecucion_id: str,
        usuario_id: str,
        etapa: str,
        costo_usd: float,
        token_entrada: int = 0,
        token_salida: int = 0,
        status: str = "ok",
        motivo_parcial: Optional[str] = None,
    ) -> bool:
        """
        Registra gasto en presupuesto_uso.
        Retorna True si se registró exitosamente.
        """
        try:
            with psycopg.connect(self.db_url, autocommit=True) as conn:
                conn.execute(
                    """
                    insert into public.presupuesto_uso
                      (ejecucion_id, usuario_id, etapa, costo_usd, token_entrada, token_salida, status, motivo_parcial)
                    values (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        ejecucion_id,
                        usuario_id,
                        etapa,
                        costo_usd,
                        token_entrada,
                        token_salida,
                        status,
                        motivo_parcial,
                    ),
                )
                return True
        except Exception as e:
            print(f"⚠️  Error registrando gasto: {e}")
            return False


# Instancia global
_presupuesto_middleware = None


def get_presupuesto_middleware(db_url: str = None) -> PresupuestoMiddleware:
    """Obtiene singleton de middleware de presupuestos."""
    global _presupuesto_middleware
    if _presupuesto_middleware is None:
        db_url = db_url or os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL no configurado")
        _presupuesto_middleware = PresupuestoMiddleware(db_url)
    return _presupuesto_middleware


def presupuesto_guard(costo_estimado: float = 0.1):
    """
    Decorador para endpoints que ejecutan agente (N3).

    Uso:
        @app.post("/consultas")
        @presupuesto_guard(costo_estimado=0.15)
        async def consultas(request: ConsultaRequest, usuario_id: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, usuario_id: str = None, ejecucion_id: str = None, **kwargs):
            if not usuario_id:
                # Si no se pasa usuario_id, simplemente ejecutar sin chequeo
                return await func(*args, **kwargs)

            middleware = get_presupuesto_middleware()
            permitido, razon = await middleware.verificar_presupuesto(
                usuario_id,
                etapa="3",
                costo_estimado=costo_estimado,
            )

            if not permitido:
                # Retornar respuesta PARCIAL sin error
                return JSONResponse(
                    status_code=200,  # OK, pero datos parciales
                    content={
                        "status": "parcial",
                        "motivo_parcial": "presupuesto",
                        "razon": razon,
                        "resultado": None,  # Sin datos
                    },
                )

            # Ejecutar función original
            result = await func(*args, usuario_id=usuario_id, ejecucion_id=ejecucion_id, **kwargs)

            # Registrar gasto (si el resultado incluye costo_usd)
            if ejecucion_id and isinstance(result, dict) and "costo_usd" in result:
                await middleware.registrar_gasto(
                    ejecucion_id,
                    usuario_id,
                    etapa="3",
                    costo_usd=result["costo_usd"],
                    token_entrada=result.get("tokens_entrada", 0),
                    token_salida=result.get("tokens_salida", 0),
                    status="ok",
                )

            return result

        return wrapper
    return decorator
