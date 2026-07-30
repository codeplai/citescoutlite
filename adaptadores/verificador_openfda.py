import urllib.request
import urllib.parse
import json
from puertos.verificador_regulatorio import VerificadorRegulatorio

class VerificadorOpenFDA(VerificadorRegulatorio):
    def __init__(self, offline: bool = False):
        self.offline = offline

    def verificar(self, insumo_en: str, insumo_es: str) -> str:
        if self.offline:
            return "openFDA (EE.UU.): [MODO OFFLINE] API no disponible. Sin datos de alertas/recalls. (https://open.fda.gov/)"
        try:
            # FDA usa ingles. Buscamos recalls recientes sobre el insumo
            query = urllib.parse.quote(f'"{insumo_en}"')
            url = f"https://api.fda.gov/food/enforcement.json?search=product_description:{query}&limit=3"
            
            req = urllib.request.Request(url, headers={"User-Agent": "AgroScout-CITE/0.1"})
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode())
            
            if "results" not in data or len(data["results"]) == 0:
                return "openFDA (EE.UU.): No se encontraron alertas o recalls recientes para este insumo. (URL: https://open.fda.gov/)"
                
            alertas = []
            for res in data["results"]:
                motivo = res.get("reason_for_recall", "Sin motivo")
                fecha = res.get("report_date", "Desconocida")
                alertas.append(f"- [{fecha}] {motivo}")
                
            return f"openFDA (EE.UU.): Se encontraron {len(alertas)} alertas/recalls recientes. (URL: https://open.fda.gov/)\n" + "\n".join(alertas)
            
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "openFDA (EE.UU.): No se encontraron alertas o recalls para este insumo. (URL: https://open.fda.gov/)"
            return f"openFDA (EE.UU.): Error al consultar API ({e.code})."
        except Exception as e:
            return f"openFDA (EE.UU.): No se pudo consultar la API ({str(e)})."
