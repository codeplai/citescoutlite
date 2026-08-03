"""
TIER 2 · T2.1 (S4): normalización de país a ISO-3166 alpha-2.

`normalizar("United States, World")` → `["US"]`. Función pura, sin estado y sin
I/O: se aplica **al leer**, no reescribiendo `productos_merged.json` ni el índice
`vectores/productos.lance`. Así se evita la reindexación y el bug de `sys.modules`
que costó TIER 4 de S2.

El snapshot trae 1.577 variantes de país para 28.927 filas: `United States`
(9.986), `en:United States` (1.633), `en:us` (1.005), `United States, World` (852)
y `en:united-states` (785) son el mismo país. Tras partir por coma, quitar
prefijos y plegar tildes quedan 474 tokens atómicos, que es lo que esta tabla
mapea.

Dos hallazgos del snapshot que cambian las reglas del plan §T2.1:

1. **Los prefijos de idioma se anidan.** Hay valores `en:en:us`, `fr:en:fr` y
   `fr:fr:france`. Un solo paso de "quitar `en:`" deja `en:us` crudo y falla el
   gate de 0 filas con prefijo. El pelado se repite hasta punto fijo.

2. **`world` no es el único no-país.** También aparecen `european union`,
   `union europeenne` y `europaische union`. Se descartan igual que `world`:
   son entidades supranacionales, no países, y colarlas en un mapa por país es
   exactamente el tipo de dato inventado que P04 persigue.

Regla 5 del plan, la que manda: **sin correspondencia no se adivina.** El token
sale de la lista y entra al reporte. Por eso quedan fuera a propósito los
históricos (`yugoslavia`, `east germany`), las regiones y localidades
(`mallorca`, `cantabria`, `santona`) y los valores rotos (`france spain`, `en`):
mapearlos exigiría suponer, y el mapa del informe se lee como si fuera un hecho.

Uso como librería:
    from etl.normalizar_paises import normalizar
    normalizar("en:united-states")   # -> ["US"]

Uso como reporte (gate de T2.1):
    uv run python -m etl.normalizar_paises
"""

import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# ISO 3166-1 alpha-2 completo. Es lo que hace verdadera la regla "no se adivina":
# sin este conjunto, un token de dos letras como `en` (código de idioma, no de
# país) pasaría como "EN" y ensuciaría el mapa.
# ---------------------------------------------------------------------------
ISO_ALPHA2 = set("""
AD AE AF AG AI AL AM AO AQ AR AS AT AU AW AX AZ BA BB BD BE BF BG BH BI BJ BL
BM BN BO BQ BR BS BT BV BW BY BZ CA CC CD CF CG CH CI CK CL CM CN CO CR CU CV
CW CX CY CZ DE DJ DK DM DO DZ EC EE EG EH ER ES ET FI FJ FK FM FO FR GA GB GD
GE GF GG GH GI GL GM GN GP GQ GR GS GT GU GW GY HK HM HN HR HT HU ID IE IL IM
IN IO IQ IR IS IT JE JM JO JP KE KG KH KI KM KN KP KR KW KY KZ LA LB LC LI LK
LR LS LT LU LV LY MA MC MD ME MF MG MH MK ML MM MN MO MP MQ MR MS MT MU MV MW
MX MY MZ NA NC NE NF NG NI NL NO NP NR NU NZ OM PA PE PF PG PH PK PL PM PN PR
PS PT PW PY QA RE RO RS RU RW SA SB SC SD SE SG SH SI SJ SK SL SM SN SO SR SS
ST SV SX SY SZ TC TD TF TG TH TJ TK TL TM TN TO TR TT TV TW TZ UA UG UM US UY
UZ VA VC VE VG VI VN VU WF WS YE YT ZA ZM ZW
""".split())

# Alpha-3 observados en el snapshot. No se añade la tabla completa: solo lo que
# el dato trae.
ALPHA3 = {"usa": "US", "kor": "KR", "ken": "KE"}

# No son países. Se descartan en silencio, no van al reporte de no mapeados.
NO_ES_PAIS = {
    "world", "monde", "welt", "mundo", "wereld", "mondo", "swiat", "verden",
    "european union", "union europeenne", "europaische union", "unione europea",
}

# Alias → ISO, agrupado por país para que se lea y se mantenga. Cubre los tokens
# realmente presentes en el snapshot (ES/EN/FR/DE más lo que trajo la cola:
# nl, pl, cs, sk, hu, hr, sr, fi, sv, da, no, ro, bg, el, ru, ar, th, zh, ja).
_ALIAS: dict[str, tuple[str, ...]] = {
    "US": ("united states", "united states of america", "etats unis",
           "estados unidos", "vereinigte staaten von amerika",
           "vereinigte staaten", "verenigde staten van amerika",
           "stany zjednoczone", "yhdysvallat", "amerique", "etats unis d'amerique",
           "美国", "アメリカ合衆国"),
    "FR": ("france", "francia", "frankreich", "francie", "franca", "frankrijk",
           "francja", "franta", "prantsusmaa", "ranska", "frankrig",
           "franciaorszag", "francuska", "an fhraing", "frankrike",
           "フランス", "ประเทศฝรงเศส"),
    "DE": ("germany", "deutschland", "allemagne", "alemania", "alemanha",
           "germania", "duitsland", "niemcy", "nemecko", "njemacka",
           "nemetorszag", "tyskland", "saksa", "germanija",
           "германия", "ประเทศเยอรมน"),
    "GB": ("united kingdom", "uk", "royaume uni", "reino unido", "regno unito",
           "vereinigtes konigreich", "verenigd koninkrijk", "wielka brytania",
           "zjednoczone krolestwo", "spojene kralovstvi",
           "yhdistynyt kuningaskunta", "an rioghachd aonaichte", "scotland",
           "gran bretana", "grossbritannien", "england", "wales"),
    "ES": ("spain", "espana", "espagne", "spanien", "espanha", "spagna",
           "hiszpania", "spanje", "espanja", "spania", "spanjolska"),
    "IT": ("italy", "italia", "italie", "italien", "italija", "wlochy",
           "италия"),
    "CA": ("canada", "kanada", "quebec", "كندا"),
    "NL": ("netherlands", "the netherlands", "nederland", "pays bas",
           "niederlande", "paises bajos", "holandia", "holanda", "olanda"),
    "BE": ("belgium", "belgique", "belgie", "belgien", "belgica", "belgia",
           "belgio", "belgija", "белгия"),
    "CH": ("switzerland", "suisse", "schweiz", "svizzera", "suiza", "suica",
           "zwitserland", "svicarska", "szwajcaria"),
    "AT": ("austria", "osterreich", "autriche", "rakousko", "austrija",
           "oostenrijk", "ausztria"),
    "PT": ("portugal", "portugalia"),
    "IE": ("ireland", "irlande", "irland", "irlanda", "irska", "irlandia"),
    "PL": ("poland", "polska", "pologne", "polen", "polonia", "polsko",
           "poljska", "puola"),
    "CZ": ("czech republic", "czechia", "cesko", "ceska", "tschechien",
           "republique tcheque", "republica checa", "czechy", "ceska republika"),
    "SK": ("slovakia", "slovensko", "slowakei", "slovaquie", "slowakije",
           "slovacka", "słowacja", "eslovaquia"),
    "HU": ("hungary", "magyarorszag", "hongrie", "ungarn", "hongarije",
           "hungria", "madarsko", "mađarska", "wegry"),
    "RO": ("romania", "roumanie", "rumanien", "rumunia", "rumunjska",
           "rumania"),
    "BG": ("bulgaria", "bulgarie", "bulgarien", "bugarska", "българия",
           "румъния"),
    "HR": ("croatia", "hrvatska", "croatie", "croacia", "kroatien"),
    "RS": ("serbia", "srbija", "servia", "serbien", "србија"),
    "SI": ("slovenia", "slovenija", "slowenien", "eslovenia"),
    "BA": ("bosnia and herzegovina", "bosna i hercegovina",
           "bosnia y herzegovina"),
    "ME": ("montenegro", "crna gora"),
    "MK": ("north macedonia", "republique de macedoine", "sjeverna makedonija",
           "macedonia"),
    "AL": ("albania", "albanija", "albanie"),
    # Kosovo (1 fila) no tiene ISO-3166 oficial: se queda sin mapear, al reporte.
    "SE": ("sweden", "sverige", "suede", "schweden", "suecia", "ruotsi",
           "szwecja"),
    "NO": ("norway", "norge", "norvege", "norwegen", "noruega", "norja",
           "noorwegen"),
    "DK": ("denmark", "danmark", "danemark", "danemarca", "dinamarca", "dania"),
    "FI": ("finland", "suomi", "finlande", "finnland", "finlandia"),
    "IS": ("iceland", "islandia", "islande"),
    "EE": ("estonia", "eesti", "estonie", "viro"),
    "LV": ("latvia", "letonia", "lettonie", "latvija", "łotwa", "латвія"),
    "LT": ("lithuania", "republic of lithuania", "lituania", "lietuva",
           "lituanie", "litwa"),
    "RU": ("russia", "russland", "russie", "rusia", "россия"),
    "UA": ("ukraine", "ucrania", "украіна"),
    "BY": ("belarus", "bielorrusia", "белоруссия"),
    "MD": ("moldova", "moldavia"),
    "GR": ("greece", "grecia", "grece", "griechenland", "griekenland",
           "grecja", "ελλαδα"),
    "CY": ("cyprus", "chipre", "κυπρος"),
    "MT": ("malta",),
    "LU": ("luxembourg", "luxemburg", "luxemburgo", "lussemburgo"),
    "LI": ("liechtenstein",),
    "AD": ("andorra",),
    "MC": ("monaco",),
    "SM": ("san marino",),
    "TR": ("turkey", "turkiye", "türkiye", "turquie", "turquia", "turkei",
           "ประเทศตุรกี"),
    "IL": ("israel",),
    "SA": ("saudi arabia", "arabie saoudite", "arabia saudita", "السعودية"),
    "AE": ("united arab emirates", "emiratos arabes unidos"),
    "QA": ("qatar",),
    "KW": ("kuwait", "الكويت"),
    "BH": ("bahrain", "bahrein"),
    "JO": ("jordan", "hashemite kingdom of jordan", "jordania"),
    "LB": ("lebanon", "liban", "libano"),
    "IQ": ("iraq", "irak"),
    "IR": ("iran",),
    "EG": ("egypt", "egitto", "egipto", "egypte"),
    "MA": ("morocco", "maroc", "marruecos", "marokko", "marrocos"),
    "DZ": ("algeria", "algerien", "algerie", "argelia"),
    "TN": ("tunisia", "tunisie", "tunez"),
    "LY": ("libya", "libia"),
    "ZA": ("south africa", "afrique du sud", "sudafrica", "sudafrika"),
    "NG": ("nigeria",),
    "KE": ("kenya", "kenia"),
    "GH": ("ghana",),
    "ET": ("ethiopia", "etiopia"),
    "SN": ("senegal",),
    "ML": ("mali",),
    "CI": ("cote d'ivoire", "cote d ivoire", "ivory coast"),
    "TG": ("togo",),
    "GA": ("gabon",),
    "RW": ("rwanda",),
    "DJ": ("djibouti",),
    "CD": ("democratic republic of the congo", "congo kinshasa"),
    "MU": ("mauritius", "maurice", "mauricio", "毛里求斯"),
    "MX": ("mexico", "mexique", "mexiko", "messico"),
    "BR": ("brazil", "brasil", "bresil", "brasilien"),
    "AR": ("argentina", "argentine"),
    "CL": ("chile", "chili"),
    "CO": ("colombia", "kolumbien", "colombie"),
    "PE": ("peru", "perou"),
    "BO": ("bolivia", "bolivie"),
    "EC": ("ecuador", "equateur"),
    "PY": ("paraguay",),
    "UY": ("uruguay",),
    "VE": ("venezuela",),
    "GY": ("guyana",),
    "SR": ("surinam", "suriname"),
    "CR": ("costa rica",),
    "PA": ("panama",),
    "GT": ("guatemala",),
    "HN": ("honduras",),
    "SV": ("el salvador",),
    "NI": ("nicaragua",),
    "CU": ("cuba",),
    "DO": ("dominican republic", "republica dominicana", "republique dominicaine"),
    "HT": ("haiti",),
    "JM": ("jamaica", "jamaique"),
    "TT": ("trinidad and tobago", "trinidad y tobago"),
    "BB": ("barbados",),
    "BS": ("bahamas", "the bahamas"),
    "DM": ("dominica",),
    "GD": ("grenada",),
    "VC": ("saint vincent and the grenadines",),
    "AW": ("aruba",),
    "CW": ("curazao", "curacao"),
    "PR": ("puerto rico",),
    "IN": ("india", "inde", "indien"),
    "CN": ("china", "chine"),
    "JP": ("japan", "japon", "日本"),
    "KR": ("south korea", "sudkorea", "coree du sud", "corea del sur"),
    "TW": ("taiwan",),
    "HK": ("hong kong", "hongkong"),
    "SG": ("singapore", "singapour", "singapur", "ประเทศสงคโปร"),
    "TH": ("thailand", "tailandia", "thailande", "ประเทศไทย"),
    "VN": ("vietnam", "viet nam"),
    "MY": ("malaysia", "malasia", "malaisie"),
    "ID": ("indonesia", "indonesie"),
    "PH": ("philippines", "filipinas"),
    "KH": ("cambodia", "camboya", "cambodge"),
    "MM": ("myanmar", "birmania"),
    "BN": ("brunei",),
    "NP": ("nepal",),
    "BT": ("bhutan", "butan"),
    "LK": ("sri lanka",),
    "PK": ("pakistan",),
    "BD": ("bangladesh",),
    "MV": ("maldives", "maldivas"),
    "KZ": ("kazakhstan", "kazajistan"),
    "AZ": ("azerbaijan", "azerbaiyan"),
    "GE": ("georgia", "georgie"),
    "AU": ("australia", "australie", "australien"),
    "NZ": ("new zealand", "nueva zelanda", "nouvelle zelande", "neuseeland",
           "noua zeelanda"),
    "RE": ("reunion",),
    "GP": ("guadeloupe", "guadalupe"),
    "MQ": ("martinique", "martinica"),
    "GF": ("guayana francesa", "guyane francaise", "french guiana"),
    "PF": ("french polynesia", "polynesie francaise"),
    "NC": ("new caledonia", "nouvelle caledonie"),
    "WF": ("wallis and futuna",),
    "PM": ("saint pierre and miquelon",),
    "YT": ("mayotte",),
    # "san martin" queda fuera a propósito: es tanto Saint-Martin (MF) como la
    # región peruana de San Martín. Ambiguo = al reporte, no se adivina.
    "MF": ("saint martin",),
    "GU": ("guam",),
    "VI": ("virgin islands",),
    "FO": ("faroe islands", "islas feroe"),
    "GI": ("gibraltar",),
    "JE": ("jersey",),
    "GG": ("guernsey",),
    "IM": ("isle of man",),
}

def _plegar(texto: str) -> str:
    """Minúsculas, sin tildes, guiones a espacios, espacios colapsados.

    También quita un paréntesis final (`ประเทศไทย (Thai)` → `ประเทศไทย`): OFF
    anota ahí el idioma del valor, y sin quitarlo el token no casa con nada.
    """
    texto = texto.replace("-", " ").replace("_", " ").lower().strip()
    if texto.endswith(")") and "(" in texto:
        texto = texto[:texto.rindex("(")].strip()
    texto = "".join(c for c in unicodedata.normalize("NFD", texto)
                    if unicodedata.category(c) != "Mn")
    return " ".join(texto.split())


# alias → ISO, invertido una vez al importar. Las claves se pliegan con la misma
# función que el dato: escribir "España" o "Türkiye" en la tabla de arriba debe
# funcionar igual que escribir "espana". Sin este plegado, un alias con tilde no
# casa nunca y falla en silencio, que es como se coló `ประเทศไทย` en el primer
# reporte.
ALIAS: dict[str, str] = {}
for _iso, _nombres in _ALIAS.items():
    for _n in _nombres:
        ALIAS[_plegar(_n)] = _iso


def _pelar_prefijos(token: str) -> str:
    """Quita `en:`, `fr:`… hasta punto fijo.

    El snapshot trae prefijos anidados (`en:en:us`, `fr:en:fr`): un solo paso
    dejaría `en:us` crudo y el gate de T2.1 exige 0 filas con prefijo.
    """
    anterior = None
    while anterior != token:
        anterior = token
        if len(token) > 3 and token[2] == ":" and token[:2].isalpha():
            token = token[3:].strip()
    return token


def normalizar(countries: str | None) -> list[str]:
    """`countries` de OFF → lista de ISO-3166 alpha-2, sin repetir y ordenada.

    Devuelve `[]` si no se pudo mapear nada: **no se adivina**. Los no-países
    (`world`, `european union`) se descartan sin dejar rastro; los tokens
    desconocidos se pueden recoger con `no_mapeados()` para el reporte.
    """
    if not countries:
        return []

    isos: list[str] = []
    for parte in str(countries).split(","):
        token = _plegar(_pelar_prefijos(_plegar(parte)))
        if not token or token in NO_ES_PAIS:
            continue

        if token in ALIAS:
            iso = ALIAS[token]
        elif len(token) == 2 and token.upper() in ISO_ALPHA2:
            iso = token.upper()
        elif token in ALPHA3:
            iso = ALPHA3[token]
        else:
            continue  # sin correspondencia: fuera de la lista, al reporte

        if iso not in isos:
            isos.append(iso)

    return sorted(isos)


def no_mapeados(countries: str | None) -> list[str]:
    """Tokens que `normalizar()` descartó por desconocidos. Para el reporte."""
    if not countries:
        return []
    sueltos = []
    for parte in str(countries).split(","):
        token = _plegar(_pelar_prefijos(_plegar(parte)))
        if not token or token in NO_ES_PAIS:
            continue
        if token in ALIAS or token in ALPHA3:
            continue
        if len(token) == 2 and token.upper() in ISO_ALPHA2:
            continue
        sueltos.append(token)
    return sueltos


# ---------------------------------------------------------------------------
# Reporte: mide el gate de T2.1 sobre el snapshot completo.
# ---------------------------------------------------------------------------

DATASET = Path("datasets/2026-07")
PRODUCTOS = DATASET / "productos_merged.json"
REPORTE = DATASET / "paises_no_mapeados.json"


def main() -> int:
    if not PRODUCTOS.exists():
        print(f"[PAÍSES] No existe {PRODUCTOS}")
        return 1

    productos = json.loads(PRODUCTOS.read_text(encoding="utf-8"))
    total = len(productos)

    con_iso = crudos = 0
    sueltos: Counter[str] = Counter()
    isos: Counter[str] = Counter()

    for p in productos:
        bruto = p.get("pais")
        resultado = normalizar(bruto)
        if resultado:
            con_iso += 1
            for iso in resultado:
                isos[iso] += 1
        for token in no_mapeados(bruto):
            sueltos[token] += 1
        if bruto and ":" in str(bruto):
            # ¿queda algún prefijo crudo tras normalizar?
            if any(":" in _plegar(_pelar_prefijos(_plegar(x)))
                   for x in str(bruto).split(",")):
                crudos += 1

    pct = 100.0 * con_iso / total
    print(f"\n[PAÍSES] {con_iso:,}/{total:,} filas con al menos un ISO = {pct:.2f} %")
    print(f"[PAÍSES] Países distintos: {len(isos)}")
    print(f"[PAÍSES] Top 12: {dict(isos.most_common(12))}")
    print(f"[PAÍSES] Filas con prefijo crudo tras normalizar: {crudos}")
    print(f"[PAÍSES] Variantes no mapeadas: {len(sueltos)} "
          f"({sum(sueltos.values()):,} filas)")

    if sueltos:
        print("\n[PAÍSES] Top 25 no mapeados (revisar a ojo):")
        for token, n in sueltos.most_common(25):
            print(f"          {n:>5,}  {token}")

    REPORTE.write_text(
        json.dumps({
            "filas": total,
            "con_iso": con_iso,
            "pct_con_iso": round(pct, 2),
            "filas_con_prefijo_crudo": crudos,
            "paises_distintos": len(isos),
            "distribucion_iso": dict(isos.most_common()),
            "no_mapeados": dict(sueltos.most_common()),
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n[PAÍSES] Reporte -> {REPORTE}")

    # Gates de T2.1
    ok_pct = pct >= 95.0
    ok_crudos = crudos == 0
    ok_variantes = len(sueltos) <= 200
    print(f"\n[GATE] ≥95 % con ISO ......... {'PASA' if ok_pct else 'FALLA'} ({pct:.2f} %)")
    print(f"[GATE] 0 filas con `en:` crudo  {'PASA' if ok_crudos else 'FALLA'} ({crudos})")
    print(f"[GATE] ≤200 variantes sueltas . {'PASA' if ok_variantes else 'FALLA'} ({len(sueltos)})")
    return 0 if (ok_pct and ok_crudos and ok_variantes) else 1


if __name__ == "__main__":
    sys.exit(main())
