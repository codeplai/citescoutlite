#!/usr/bin/env python
"""
Generador de contratos (JSON Schema) desde modelos Pydantic.
Ejecutar en CI antes de tests.

Uso:
  uv run python scripts/generar_contratos.py
"""

import json
import sys
from pathlib import Path

def generar_contratos():
    """Genera esquemas JSON de todos los dominios."""
    try:
        from dominio.insumo import InsumoInterpretado
        from dominio.insight_mercado import InsightDeMercado
        from dominio.hipotesis_formulacion import HipotesisFormulacion
        from dominio.dossier_regulatorio import DossierRegulatorio
        from dominio.resultado_busqueda import ResultadoBusqueda
        from dominio.producto_existente import ProductoExistente
        from dominio.producto_en_mercado import ProductoEnMercado
        from dominio.informe_scout import InformeScout
        from puertos.auditoria import Ejecucion

        contratos = {
            "InsumoInterpretado": InsumoInterpretado.model_json_schema(),
            "ProductoExistente": ProductoExistente.model_json_schema(),
            "ResultadoBusqueda": ResultadoBusqueda.model_json_schema(),
            # Etapa 2b (S4). Una fila del mapa comercial, con una sola fuente.
            # `presentacion`, `precio_rango` y `canal` estan en el esquema y son
            # siempre null en el MVP: el hueco se declara, no se esconde.
            "ProductoEnMercado": ProductoEnMercado.model_json_schema(),
            # Etapas 3, 4 y 5. Hasta S2 eran un solo objeto: los dos campos
            # premium salian de la misma llamada que el resumen gratuito.
            "InsightDeMercado": InsightDeMercado.model_json_schema(),
            "HipotesisFormulacion": HipotesisFormulacion.model_json_schema(),
            "DossierRegulatorio": DossierRegulatorio.model_json_schema(),
            "InformeScout": InformeScout.model_json_schema(),
        }

        # Crear directorio contratos/
        contratos_dir = Path("contratos")
        contratos_dir.mkdir(exist_ok=True)

        # Guardar schemas.json
        schemas_file = contratos_dir / "schemas.json"
        with open(schemas_file, "w", encoding="utf-8") as f:
            json.dump(contratos, f, indent=2, ensure_ascii=False)

        # Guardar archivo de índice
        index_file = contratos_dir / "README.md"
        with open(index_file, "w", encoding="utf-8") as f:
            f.write("# Contratos de AgroScout MVP\n\n")
            f.write("Esquemas JSON Schema de los modelos de dominio.\n\n")
            f.write("## Modelos\n\n")
            for modelo in contratos.keys():
                f.write(f"- **{modelo}**: Definición completa en `schemas.json`\n")

        print(f"[OK] Contratos generados: {schemas_file}")
        print(f"     {len(contratos)} modelos incluidos")
        print(f"[OK] README creado: {index_file}")
        return 0

    except ImportError as e:
        print(f"[ERROR] Falta importar módulo: {e}")
        return 1
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1


if __name__ == "__main__":
    sys.exit(generar_contratos())
