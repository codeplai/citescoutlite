"""
Grounding check: valida que valores extraídos existen realmente en HTML (S2.4).

Previene "alucinaciones" del LLM: asegura que el agente solo reporta
datos que realmente están presentes en la fuente HTML.

Por cada campo crítico (nombre, precio, marca, stock):
  1. Busca substring literal en HTML
  2. Si no está, marca como failed
  3. Retorna {passed: bool, errors: []}
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import re


@dataclass
class GroundingError:
    """Un error de grounding: campo no encontrado en HTML."""
    campo: str
    valor: str
    razon: str  # "no encontrado en HTML", "coincidencia parcial", etc.


@dataclass
class GroundingCheckResult:
    """Resultado de validación de grounding."""
    passed: bool = False
    errores: list[GroundingError] = field(default_factory=list)
    campos_verificados: int = 0
    campos_ok: int = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_json(self) -> dict:
        """Convierte a dict para guardar en JSONB de staging_agente."""
        return {
            "passed": self.passed,
            "errores": [
                {"campo": e.campo, "valor": e.valor, "razon": e.razon}
                for e in self.errores
            ],
            "campos_verificados": self.campos_verificados,
            "campos_ok": self.campos_ok,
            "timestamp": self.timestamp.isoformat(),
        }


class GroundingChecker:
    """Valida que datos extraídos están en el HTML capturado."""

    # Campos críticos que DEBEN estar en HTML
    CAMPOS_CRITICOS = {"nombre", "precio"}
    # Campos opcionales que se verifican si están presentes
    CAMPOS_OPCIONALES = {"marca", "stock", "descripcion", "unidad"}

    def __init__(self, case_sensitive: bool = False):
        self.case_sensitive = case_sensitive

    def _normalizar_texto(self, texto: str) -> str:
        """Normaliza texto para búsqueda (espacios múltiples, etc)."""
        texto = re.sub(r'\s+', ' ', texto).strip()
        if not self.case_sensitive:
            texto = texto.lower()
        return texto

    def _buscar_en_html(self, html: str, valor: str) -> bool:
        """
        Busca substring literal de valor en HTML.
        Retorna True si encuentra coincidencia significativa.
        """
        if not html or not valor:
            return False

        valor_norm = self._normalizar_texto(str(valor))
        html_norm = self._normalizar_texto(html)

        # Búsqueda exacta (substring)
        if valor_norm in html_norm:
            return True

        # Para números (ej: precio), busca también variaciones
        if re.search(r'\d', valor_norm):
            # Extrae números del valor
            numeros = re.findall(r'\d+\.?\d*', valor_norm)
            if numeros:
                # Busca si el número principal está en HTML
                numero_principal = numeros[0]
                if re.search(rf'\b{re.escape(numero_principal)}', html_norm):
                    return True

        return False

    def verificar(self, html: str, producto: dict) -> GroundingCheckResult:
        """
        Verifica grounding de producto contra HTML.

        Args:
            html: HTML capturado de la página
            producto: dict con campos del producto (ej: {"nombre": "...", "precio": 50})

        Returns:
            GroundingCheckResult con resultado y errores detectados
        """
        resultado = GroundingCheckResult()
        errores = []

        # 1. Verificar campos críticos
        for campo in self.CAMPOS_CRITICOS:
            valor = producto.get(campo)
            if valor is None:
                errores.append(
                    GroundingError(
                        campo=campo,
                        valor="<null>",
                        razon="Campo requerido no está presente en producto extraído"
                    )
                )
                continue

            resultado.campos_verificados += 1
            if self._buscar_en_html(html, valor):
                resultado.campos_ok += 1
            else:
                errores.append(
                    GroundingError(
                        campo=campo,
                        valor=str(valor),
                        razon=f"No encontrado en HTML capturado"
                    )
                )

        # 2. Verificar campos opcionales (si están presentes)
        for campo in self.CAMPOS_OPCIONALES:
            valor = producto.get(campo)
            if valor is None:
                continue  # Opcional, no verificar si es None

            resultado.campos_verificados += 1
            if self._buscar_en_html(html, valor):
                resultado.campos_ok += 1
            else:
                errores.append(
                    GroundingError(
                        campo=campo,
                        valor=str(valor)[:50],  # Limitar longitud
                        razon="No encontrado en HTML capturado (opcional)"
                    )
                )

        # 3. Determinar si pasó
        # Todos los campos críticos deben pasar (estar presentes y en HTML)
        criticos_fallidos = [e.campo for e in errores if e.campo in self.CAMPOS_CRITICOS]
        resultado.passed = len(criticos_fallidos) == 0
        resultado.errores = errores

        return resultado


# Instancia global
_grounding_checker = GroundingChecker(case_sensitive=False)


def grounding_check(html: str, producto: dict) -> GroundingCheckResult:
    """
    Verifica que datos de producto están en HTML capturado.
    """
    return _grounding_checker.verificar(html, producto)


def grounding_check_json(html: str, producto: dict) -> dict:
    """
    Verifica grounding y retorna como JSON (para guardar en BD).
    """
    resultado = grounding_check(html, producto)
    return resultado.to_json()
