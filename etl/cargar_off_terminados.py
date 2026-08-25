"""
Carga de PRODUCTOS TERMINADOS desde Open Food Facts.

Por que existe, y por que no basta con `cargar_off_bulk`. El snapshot de S2 se
filtro a cinco INSUMOS ('mango', 'quinua', ...), asi que la gondola encuentra
materia prima suelta pero no la forma de producto que se compra en una tienda:
quien consulta 'barras de quinua' recibia quinua a granel. Este modulo trae los
terminados —nectar, mermelada, muesli, chips— para los tres mercados del MVP.

## Por que la API nueva y no la de `cargar_off.py`

`https://world.openfoodfacts.org/cgi/search.pl` devuelve 503 (es la decision
D-A del snapshot: por eso S2 fue por el export masivo). `/api/v2/search`
tambien. Lo unico que responde hoy es search-a-licious:

    https://search.openfoodfacts.org/search                     -> codigos
    https://world.openfoodfacts.org/api/v2/product/{code}.json  -> ficha

Son dos viajes porque el indice de busqueda **no guarda ingredientes ni marca**:
pedirlos en `fields` devuelve el hit sin esos campos, en silencio. Y sin
ingredientes el producto no sirve: `_detectar_uso_directo` compara los sinonimos
contra `ingredientes`, de modo que una fila sin ellos nunca cuenta como directo
y solo infla el conteo del snapshot.

## Limites de peticiones

OFF publica 10 busquedas/min y 100 fichas/min. Los `sleep` de abajo salen de
ahi, no de una estimacion. Ir mas rapido devuelve 429 y termina siendo mas lento.

## Se reanuda

Las dos fases dejan su avance en disco (`off_terminados_codigos.json` y
`off_terminados_fichas.jsonl`), asi que volver a lanzar el mismo comando
continua donde se quedo en vez de empezar de cero. Con 10 busquedas por minuto,
rehacer lo ya hecho cuesta mas que el trabajo que falta. Para forzar un
descubrimiento nuevo, borra el JSON de codigos.

Uso:
    ./venv/Scripts/python.exe -m etl.cargar_off_terminados --dry-run
    ./venv/Scripts/python.exe -m etl.cargar_off_terminados
"""
import argparse
import json
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import requests

DATASET = Path("datasets/2026-07")

# Las rutas dependen de la campana y las fija `_fijar_rutas`. Que cada campana
# tenga sus propios archivos no es cosmetico: el JSON de codigos es lo que hace
# reanudable la fase de busqueda, asi que si dos campanas lo compartieran, la
# segunda daria por descubierto lo de la primera y no buscaria nada.
SALIDA = DATASET / "off_terminados.json"
LOG = DATASET / "etl_off_terminados.log"

# Las dos fases se guardan en disco para poder reanudar. La primera corrida no
# lo hacia y perdio los 11 min de busquedas al cortarse en las fichas; con una
# fuente que limita a 10 peticiones por minuto, rehacer el trabajo ya hecho no
# es una molestia, es la diferencia entre 20 minutos y una tarde.
CODIGOS = DATASET / "off_terminados_codigos.json"
FICHAS = DATASET / "off_terminados_fichas.jsonl"


def _fijar_rutas(campana: str):
    """Apunta los cuatro archivos de estado a los de esta campana."""
    global SALIDA, LOG, CODIGOS, FICHAS
    SALIDA = DATASET / f"off_{campana}.json"
    LOG = DATASET / f"etl_off_{campana}.log"
    CODIGOS = DATASET / f"off_{campana}_codigos.json"
    FICHAS = DATASET / f"off_{campana}_fichas.jsonl"

BUSQUEDA = "https://search.openfoodfacts.org/search"
FICHA = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
UA = "AgroScout-CITE/0.1 (CITEagroindustrial; codeplaigamessac@gmail.com)"

ESPERA_BUSQUEDA = 6.5   # 10/min
# Medido, no estimado. A 0,7 s OFF corta con 429 a los 40 codigos. A 1,1 s
# aguanta ~60 seguidos y luego corta: cada corte cuesta 30 s de espera, con lo
# que el ritmo efectivo cayo a 15 fichas/min. A 1,6 s no llega al tope y salen
# ~37/min sostenidas, mas del doble. Ir despacio es aqui ir mas rapido.
ESPERA_FICHA = 1.6

# Por debajo de esto se repite la busqueda con el insumo a secas (ver el bloque
# de respaldo en main). 10 y no 0 porque un pais con 3 hits tampoco da para una
# gondola: `_has_gaps` pide 3 productos, 2 paises y 2 marcas.
UMBRAL_RESPALDO = 10

# Los 20 terminados. `es` es como se busca en una gondola peruana y `de` como
# se etiqueta en una alemana o en la Suiza germanofona; no son traducciones
# literales sino el nombre comercial de cada mercado, que es lo que indexa OFF.
#
# `tokens` es el filtro de pertinencia, y no es opcional: la busqueda de OFF es
# difusa y por debajo de cierto puntaje devuelve cualquier cosa del pais. Medido
# con 'pure de manzana' + countries_tags:"en:peru": de los 15 primeros hits, los
# 7 ultimos eran 'Panettone Visconti', 'Mayonesa', 'Ramen sabor a Camaron'. Sin
# este filtro el snapshot se llenaria de filas que no contienen el insumo, que
# es justo el dato de relleno que el MVP promete no tener.
#
# Son prefijos, no palabras completas, y esa es la razon de no cerrar el patron
# con \b: el aleman compone ('Apfelmus', 'Kokosmilch', 'Karottensaft',
# 'Bananenchips') y exigir palabra entera dejaria fuera precisamente los
# terminados que se vienen a buscar. Dos llevan un negativo explicito: 'papa'
# si no se traga 'papaya', y 'coco' se traga el 'cocoa' ingles, que es cacao y
# no coco.
PRODUCTOS = [
    {"insumo": "mango",     "es": "néctar de mango",         "de": "Mango Nektar",
     "base_es": "mango", "base_de": "Mango",
     "tokens": ["mango"]},
    {"insumo": "quinua",    "es": "barras de quinua",        "de": "Quinoa Riegel",
     "base_es": "quinua", "base_de": "Quinoa",
     "tokens": ["quinoa", "quinua"]},
    {"insumo": "manzana",   "es": "puré de manzana",         "de": "Apfelmus",
     "base_es": "manzana", "base_de": "Apfel",
     "tokens": ["manzana", "apfel", "apple"]},
    {"insumo": "arándano",  "es": "arándanos deshidratados", "de": "getrocknete Blaubeeren",
     "base_es": "arándano", "base_de": "Heidelbeeren",
     "tokens": ["arandano", "blueberr", "heidelbeer", "blaubeer"]},
    {"insumo": "limón",     "es": "limonada de limón",       "de": "Zitronenlimonade",
     "base_es": "limón", "base_de": "Zitrone",
     "tokens": ["limon", "lemon", "zitrone"]},
    {"insumo": "avena",     "es": "muesli de avena",         "de": "Hafermüsli",
     "base_es": "avena", "base_de": "Hafer",
     "tokens": ["avena", "oat", "hafer"]},
    {"insumo": "piña",      "es": "piña en conserva",        "de": "Ananas Konserve",
     "base_es": "piña", "base_de": "Ananas",
     "tokens": ["pina", "ananas", "pineapple"]},
    {"insumo": "zanahoria", "es": "jugo de zanahoria",       "de": "Karottensaft",
     "base_es": "zanahoria", "base_de": "Karotten",
     "tokens": ["zanahoria", "carrot", "karotte", "mohre"]},
    {"insumo": "palta",     "es": "aceite de palta",         "de": "Avocadoöl",
     "base_es": "palta", "base_de": "Avocado",
     "tokens": ["palta", "aguacate", "avocado"]},
    {"insumo": "coco",      "es": "leche de coco",           "de": "Kokosmilch",
     "base_es": "coco", "base_de": "Kokos",
     "tokens": ["coco(?!a)", "kokos", "coconut"]},
    {"insumo": "tomate",    "es": "salsa de tomate",         "de": "Tomatenpassata",
     "base_es": "tomate", "base_de": "Tomaten",
     "tokens": ["tomate", "tomato", "tomaten"]},
    {"insumo": "sésamo",    "es": "pasta de sésamo",         "de": "Tahin",
     "base_es": "sésamo", "base_de": "Sesam",
     "tokens": ["sesamo", "sesame", "sesam", "tahin", "ajonjoli"]},
    {"insumo": "papa",      "es": "chips de papa",           "de": "Kartoffelchips",
     "base_es": "papa", "base_de": "Kartoffel",
     "tokens": ["papa(?!ya)", "patata", "potato", "kartoffel"]},
    {"insumo": "cacao",     "es": "chocolate negro",         "de": "Zartbitterschokolade",
     "base_es": "cacao", "base_de": "Kakao",
     "tokens": ["cacao", "cocoa", "kakao"]},
    {"insumo": "naranja",   "es": "jugo de naranja",         "de": "Orangensaft",
     "base_es": "naranja", "base_de": "Orangen",
     "tokens": ["naranja", "orange"]},
    {"insumo": "uva",       "es": "pasas",                   "de": "Rosinen",
     "base_es": "uva", "base_de": "Trauben",
     "tokens": ["uva", "grape", "traube", "rosine", "raisin", "pasas"]},
    {"insumo": "cúrcuma",   "es": "bebida de cúrcuma",       "de": "Kurkuma Latte",
     "base_es": "cúrcuma", "base_de": "Kurkuma",
     "tokens": ["curcuma", "turmeric", "kurkuma"]},
    {"insumo": "banano",    "es": "chips de banano",         "de": "Bananenchips",
     "base_es": "plátano", "base_de": "Bananen",
     "tokens": ["banana", "banane", "platano", "banano"]},
    {"insumo": "jengibre",  "es": "infusión de jengibre",    "de": "Ingwertee",
     "base_es": "jengibre", "base_de": "Ingwer",
     "tokens": ["jengibre", "ginger", "ingwer"]},
    {"insumo": "maracuyá",  "es": "mermelada de maracuyá",   "de": "Maracuja Konfitüre",
     "base_es": "maracuyá", "base_de": "Maracuja",
     "tokens": ["maracuya", "maracuja", "passion", "passionsfrucht"]},
]

POR_INSUMO = {p["insumo"]: p for p in PRODUCTOS}

# insumo -> tokens de pertinencia de la campana en curso. Lo llena `main`; el
# valor de arranque es el de 'terminados' para que importar el modulo y llamar a
# `menciona` desde un test siga funcionando sin montar una campana.
TOKENS = {p["insumo"]: p["tokens"] for p in PRODUCTOS}


def campana(nombre: str) -> list[dict]:
    """Entradas normalizadas de una campana.

    Cada entrada trae `insumo`, `tokens`, `base` por idioma y `terminos` por
    idioma. Las dos campanas se diferencian solo en cuantos terminos hay por
    insumo —una, o veinte— y en que idiomas; el resto del modulo no necesita
    saber cual esta corriendo.
    """
    if nombre == "terminados":
        return [{"insumo": p["insumo"],
                 "tokens": p["tokens"],
                 "base": {"es": p["base_es"], "de": p["base_de"]},
                 "terminos": {"es": [p["es"]], "de": [p["de"]]}}
                for p in PRODUCTOS]

    if nombre == "canasta":
        from etl.canasta_peruana import CANASTA
        return [{"insumo": c["insumo"],
                 "tokens": c["tokens"],
                 "base": {"es": c["base"]},
                 "terminos": {"es": c["terminos"]}}
                for c in CANASTA]

    raise SystemExit(f"Campana desconocida: {nombre!r}. Usa 'terminados' o 'canasta'.")

# El idioma con el que se busca cada mercado. Suiza va en aleman porque es la
# lengua de la mayor parte de su catalogo en OFF; el frances y el italiano
# quedan fuera y se anota como limitacion, no se inventa cobertura.
MERCADOS = {
    "peru":     {"tag": "en:peru",        "idioma": "es"},
    "suiza":    {"tag": "en:switzerland", "idioma": "de"},
    "alemania": {"tag": "en:germany",     "idioma": "de"},
}


def normalizar(texto: str) -> str:
    """Minusculas y sin tildes, para comparar 'Avocadoöl' con 'avocado'."""
    descompuesto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def menciona(texto: str, tokens: list[str]) -> bool:
    """Si el texto nombra el insumo. Prefijo tras un limite de palabra."""
    plano = normalizar(texto)
    return any(re.search(r"\b" + tok, plano) for tok in tokens)


def log(msg: str):
    linea = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(linea, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linea + "\n")


class Agotado(Exception):
    """OFF sigue devolviendo 429 tras agotar los reintentos.

    Es una excepcion y no un `None` a proposito. `None` significa "OFF no tiene
    esta ficha" y se registra como decidida; si el limite de peticiones se
    colara por esa misma via, la corrida daria por resuelto un codigo que en
    realidad no se llego a preguntar, y al reanudar no se volveria a intentar.
    Medido: la primera corrida perdio filas asi, en silencio.
    """


def _get(url: str, params: dict, intentos: int = 5):
    """GET con reintento ante 429/503. Devuelve el JSON, None, o lanza Agotado.

    El limite real no es el que documenta OFF. Con 0,7 s entre fichas (los
    100/min publicados) devolvio 429 a los 40 codigos, despues de 11 min de
    busquedas: el presupuesto parece ser por IP y compartido entre endpoints,
    no por endpoint. A 1 s y con la cuota descansada pasan 9 de 10 (el decimo
    era un 404 legitimo). De ahi el espaciado de abajo y esta espera larga.
    """
    for intento in range(intentos):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=60)
            if r.status_code in (429, 503):
                cabecera = r.headers.get("Retry-After")
                espera = int(cabecera) if (cabecera or "").isdigit() else 30 * (intento + 1)
                log(f"      {r.status_code}; reintento {intento + 1}/{intentos} en {espera}s")
                time.sleep(espera)
                continue
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            if intento == intentos - 1:
                log(f"      ERROR {type(e).__name__}: {e}")
                return None
            time.sleep(10)
    raise Agotado(url)


def buscar_codigos(termino: str, tag_pais: str, por_pagina: int) -> list[str]:
    """Codigos de barras de un termino en un pais. Lista vacia si no hay."""
    consulta = termino + ' countries_tags:"' + tag_pais + '"'
    d = _get(BUSQUEDA, {"q": consulta,
                        "page_size": por_pagina,
                        "fields": "code,product_name,countries_tags"})
    if not d:
        return []
    return [h["code"] for h in d.get("hits", []) if h.get("code")]


def traer_ficha(code: str, insumos: list[str]) -> tuple[dict | None, str]:
    """Ficha completa y por que se acepto o se descarto.

    Devuelve `(producto, motivo)`, con motivo en {'ok', 'sin_ficha',
    'sin_ingredientes', 'no_pertinente'}, para que el resumen distinga "OFF no
    tiene la ficha" de "la ficha existe pero no habla del insumo": son dos
    problemas distintos y solo el segundo dice algo del termino de busqueda.

    Descartar el producto sin `ingredients_text` es deliberado y es la misma
    regla de `cargar_off.py`: sin ingredientes la fila no puede contar como uso
    directo, y una fila que solo suma al total es exactamente el dato de relleno
    que el MVP se compromete a no tener.
    """
    d = _get(FICHA.format(code=code),
             {"fields": "code,product_name,brands,categories,"
                        "ingredients_text,countries,last_modified_t"})
    if not d or d.get("status") != 1:
        return None, "sin_ficha"
    p = d.get("product") or {}
    ingredientes = (p.get("ingredients_text") or "").strip()
    nombre = (p.get("product_name") or "").strip()
    if not ingredientes or not nombre:
        return None, "sin_ingredientes"

    # Pertinencia: basta con que UNO de los insumos por los que salio este
    # producto aparezca en su nombre o en sus ingredientes.
    texto = nombre + " " + ingredientes
    if not any(menciona(texto, TOKENS[i]) for i in insumos if i in TOKENS):
        return None, "no_pertinente"

    return {
        "id_fuente": "OFF:" + str(p["code"]),
        "nombre": nombre,
        "categoria": (p.get("categories") or "").strip(),
        "ingredientes": ingredientes,
        "url": "https://world.openfoodfacts.org/product/" + str(p["code"]),
        "usa_insumo_directo": False,
        "fecha_dato": p.get("last_modified_t"),
        "marca": (p.get("brands") or "").strip(),
        "pais": (p.get("countries") or "").strip(),
    }, "ok"


def fase_busqueda(entradas: list[dict], mercados: dict, por_pagina: int) -> dict:
    """Descubrimiento. Devuelve {code: {'insumos': [...], 'mercados': [...]}}.

    Si `CODIGOS` ya existe se reutiliza tal cual: son cientos de busquedas a 10
    por minuto y no cambian de una corrida a la siguiente.
    """
    if CODIGOS.exists():
        datos = json.loads(CODIGOS.read_text(encoding="utf-8"))
        log(f"Codigos ya descubiertos: {len(datos)} (de {CODIGOS}, se reutiliza)")
        return datos

    codigos: dict[str, dict] = {}
    por_mercado = {m: 0 for m in mercados}

    for entrada_insumo in entradas:
        insumo = entrada_insumo["insumo"]
        for mercado, cfg in mercados.items():
            idioma = cfg["idioma"]
            terminos = entrada_insumo["terminos"].get(idioma)
            if not terminos:
                # La campana no tiene terminos en la lengua de este mercado.
                # Se omite en vez de traducir a ojo: un termino inventado
                # devuelve resultados que nadie puede justificar.
                log(f"  {insumo:<16} {mercado:<9} (sin terminos en '{idioma}', se omite)")
                continue

            del_insumo: set[str] = set()
            for termino in terminos:
                encontrados = buscar_codigos(termino, cfg["tag"], por_pagina)
                del_insumo.update(encontrados)
                por_mercado[mercado] += len(encontrados)
                log(f"  {insumo:<16} {mercado:<9} {termino[:32]:<34} -> {len(encontrados)}")
                time.sleep(ESPERA_BUSQUEDA)

            # Respaldo por el insumo a secas. El catalogo suizo de OFF es fino y
            # la forma terminada devuelve 0 en la mitad de los casos medidos
            # ('Zitronenlimonade', 'Hafermuesli', 'Karottensaft', 'Avocadooel',
            # 'Tomatenpassata'). Preguntar entonces por 'Zitrone' recupera
            # productos que SI llevan el insumo, que es lo que se pide; la forma
            # terminada era el atajo para encontrarlos, no el requisito.
            #
            # El umbral se compara contra lo reunido por TODOS los terminos del
            # insumo, no termino a termino: con veinte formas de producto es
            # normal que varias vuelvan vacias sin que al insumo le falte nada.
            if len(del_insumo) < UMBRAL_RESPALDO:
                base = entrada_insumo["base"].get(idioma)
                if base:
                    extra = buscar_codigos(base, cfg["tag"], por_pagina)
                    nuevos = [c for c in extra if c not in del_insumo]
                    del_insumo.update(nuevos)
                    por_mercado[mercado] += len(nuevos)
                    log(f"  {insumo:<16} {mercado:<9} respaldo '{base}'"
                        f"{'':<20} -> +{len(nuevos)}")
                    time.sleep(ESPERA_BUSQUEDA)

            for c in del_insumo:
                entrada = codigos.setdefault(c, {"insumos": [], "mercados": []})
                if insumo not in entrada["insumos"]:
                    entrada["insumos"].append(insumo)
                if mercado not in entrada["mercados"]:
                    entrada["mercados"].append(mercado)

    CODIGOS.write_text(json.dumps(codigos, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    log("-" * 70)
    log(f"Codigos unicos: {len(codigos)} · guardados en {CODIGOS}")
    log(f"Hits por mercado (con solapamiento): {por_mercado}")
    return codigos


def fichas_resueltas() -> dict:
    """Lo ya decidido en corridas anteriores: {code: (producto|None, motivo)}."""
    if not FICHAS.exists():
        return {}
    resueltas = {}
    for linea in FICHAS.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        try:
            fila = json.loads(linea)
        except json.JSONDecodeError:
            continue  # linea a medias de un corte; se vuelve a pedir
        resueltas[fila["code"]] = (fila.get("producto"), fila["motivo"])
    return resueltas


def fase_fichas(codigos: dict) -> dict:
    """Pide las fichas que faltan y las va anotando en `FICHAS`, una por linea.

    Se escribe segun llegan y no al final: un corte a mitad conserva todo lo
    pedido hasta ese momento, que es lo unico caro de esta fase.
    """
    resueltas = fichas_resueltas()
    pendientes = [c for c in codigos if c not in resueltas]
    log(f"Fichas: {len(resueltas)} ya resueltas, {len(pendientes)} pendientes "
        f"(~{len(pendientes) * ESPERA_FICHA / 60:.0f} min)")

    with open(FICHAS, "a", encoding="utf-8") as salida:
        for i, code in enumerate(pendientes, 1):
            try:
                producto, motivo = traer_ficha(code, codigos[code]["insumos"])
            except Agotado:
                # No se anota: al reanudar hay que volver a preguntar por el.
                log(f"    limite de OFF alcanzado en {code}; quedan "
                    f"{len(pendientes) - i + 1} por pedir. Reanuda con el mismo comando.")
                break
            salida.write(json.dumps({"code": code, "motivo": motivo,
                                     "producto": producto},
                                    ensure_ascii=False) + "\n")
            salida.flush()
            resueltas[code] = (producto, motivo)
            if i % 100 == 0:
                utiles = sum(1 for p, _ in resueltas.values() if p)
                log(f"    {i}/{len(pendientes)} · utiles {utiles}")
            time.sleep(ESPERA_FICHA)

    return resueltas


def main(dry_run: bool, por_pagina: int, nombre_campana: str = "terminados",
         mercados_pedidos: list[str] | None = None) -> int:
    global TOKENS
    _fijar_rutas(nombre_campana)
    entradas = campana(nombre_campana)
    TOKENS = {e["insumo"]: e["tokens"] for e in entradas}

    mercados = ({m: MERCADOS[m] for m in mercados_pedidos}
                if mercados_pedidos else MERCADOS)
    n_terminos = sum(len(t) for e in entradas for i, t in e["terminos"].items()
                     if any(cfg["idioma"] == i for cfg in mercados.values()))

    log("=" * 70)
    log(f"OFF · campana '{nombre_campana}' · {len(entradas)} insumos · "
        f"{n_terminos} terminos · mercados {list(mercados)} · page_size={por_pagina}")
    log("=" * 70)

    recien_buscado = not CODIGOS.exists()
    codigos = fase_busqueda(entradas, mercados, por_pagina)

    if dry_run:
        log("--dry-run: no se piden fichas ni se escribe la salida.")
        return 0

    # Respiro entre fases. El presupuesto de OFF parece ser por IP y compartido:
    # encadenar las fichas justo detras de ~100 busquedas fue lo que disparo los
    # 429 de la primera corrida. Un minuto aqui ahorra varios de reintentos.
    if recien_buscado:
        log("Pausa de 60 s para que descanse la cuota antes de las fichas...")
        time.sleep(60)

    resueltas = fase_fichas(codigos)

    productos = []
    motivos = {}
    aceptados_por_mercado = {m: 0 for m in mercados}
    for code, (producto, motivo) in resueltas.items():
        motivos[motivo] = motivos.get(motivo, 0) + 1
        if producto:
            productos.append(producto)
            for m in codigos.get(code, {}).get("mercados", []):
                aceptados_por_mercado[m] += 1

    SALIDA.write_text(json.dumps(productos, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    log("-" * 70)
    log(f"Escritos {len(productos)} productos en {SALIDA}")
    log(f"Desglose de {len(resueltas)} codigos resueltos: {motivos}")
    log(f"Aceptados por mercado (con solapamiento): {aceptados_por_mercado}")

    faltan = len(codigos) - len(resueltas)
    if faltan:
        log(f"AVISO: quedan {faltan} codigos sin pedir. Vuelve a lanzar el "
            f"mismo comando para continuar donde se quedo.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Solo busca y cuenta; no pide fichas ni escribe")
    ap.add_argument("--page-size", type=int, default=50,
                    help="Resultados por termino y mercado (por defecto 50)")
    ap.add_argument("--campana", default="terminados", choices=["terminados", "canasta"],
                    help="'terminados' (20 formas de exportacion en PE/CH/DE) o "
                         "'canasta' (400 formas de consumo interno peruano)")
    ap.add_argument("--mercados", default=None,
                    help="Lista separada por comas: peru,suiza,alemania. "
                         "Por defecto, los tres.")
    args = ap.parse_args()
    pedidos = [m.strip() for m in args.mercados.split(",")] if args.mercados else None
    for m in pedidos or []:
        if m not in MERCADOS:
            raise SystemExit(f"Mercado desconocido: {m!r}. Hay: {list(MERCADOS)}")
    sys.exit(main(args.dry_run, args.page_size, args.campana, pedidos))
