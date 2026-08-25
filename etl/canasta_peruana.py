"""
Campana 'canasta': 20 formas de producto por cada uno de los 20 insumos que mas
consume un hogar peruano. Solo vegetal, sin carnes ni pescado.

Se separa de `cargar_off_terminados.py` porque son dos objetivos distintos y
conviene no mezclarlos. Aquella campana busca el terminado de exportacion en
gondola suiza y alemana —nectar, mermelada, muesli—; esta busca la canasta
interna: chuno, cancha, pasta de aji, chifles.

`tokens` es el filtro de pertinencia y funciona igual que en la otra campana:
prefijos tras un limite de palabra, sin cerrar con \\b para que el compuesto
case. Los negativos explicitos son los falsos amigos medidos:

    papa(?!ya)      'papaya' no es papa
    ajo(?!njoli)    'ajonjoli' es sesamo, no ajo
    haba(?!nero)    'habanero' es un aji, no un haba

Los terminos van en espanol porque el mercado es Peru. Varios son muy locales
—'chuno', 'tunta', 'cancha serrana', 'aji charapita', 'tarwi', 'casabe'— y se
espera que rindan poco: el catalogo peruano de Open Food Facts esta muy
incompleto (medido: yuca, zapallo y camote tienen cero filas con pais=Peru en el
snapshot 2026-07). Se dejan a proposito. Que una busqueda vuelva vacia es un
dato sobre la fuente, y es preferible a no haber preguntado.
"""

CANASTA = [
    {"insumo": "arroz", "base": "arroz",
     "tokens": ["arroz", "rice"],
     "terminos": [
        "arroz extra", "arroz integral", "arroz parboiled", "harina de arroz",
        "leche de arroz", "bebida de arroz", "galletas de arroz", "tortitas de arroz",
        "arroz inflado", "cereal infantil de arroz", "fideos de arroz", "papel de arroz",
        "vinagre de arroz", "sémola de arroz", "almidón de arroz", "arroz con leche",
        "arroz precocido", "snack de arroz", "jarabe de arroz", "arroz aromático"]},

    {"insumo": "papa", "base": "papa",
     "tokens": ["papa(?!ya)", "patata", "potato", "chuno", "tunta"],
     "terminos": [
        "papas fritas en hojuelas", "chips de papa nativa", "papa prefrita congelada",
        "puré de papa instantáneo", "papa seca", "chuño", "tunta", "almidón de papa",
        "harina de papa", "papas al hilo", "croquetas de papa", "ñoquis de papa",
        "tortilla de papa", "papa en conserva", "snack de papa horneado", "papas onduladas",
        "papa deshidratada en escamas", "papas rejilla", "papa amarilla envasada",
        "papas fritas artesanales"]},

    {"insumo": "trigo", "base": "trigo",
     "tokens": ["trigo", "wheat", "semola", "harina"],
     "terminos": [
        "pan de molde", "pan integral", "fideos spaghetti", "fideos tallarín",
        "harina de trigo", "harina integral", "galletas de soda", "galletas dulces",
        "panetón", "tostadas", "pan pita", "bizcocho", "sémola de trigo", "salvado de trigo",
        "germen de trigo", "fideos cabello de ángel", "macarrones", "lasaña",
        "crackers integrales", "pan francés"]},

    {"insumo": "maíz", "base": "maíz",
     "tokens": ["maiz", "corn", "maicena", "choclo", "polenta"],
     "terminos": [
        "harina de maíz", "maíz morado", "cancha serrana", "mote", "choclo en conserva",
        "palomitas de maíz", "hojuelas de maíz", "chicha morada", "maicena",
        "tortillas de maíz", "nachos de maíz", "sémola de maíz", "aceite de maíz",
        "jarabe de maíz", "snack de maíz", "maíz gigante del Cusco", "cornflakes",
        "polenta", "humita", "maíz tostado"]},

    {"insumo": "limón", "base": "limón",
     "tokens": ["limon", "lemon", "lime", "citrico"],
     "terminos": [
        "jugo de limón concentrado", "limonada envasada", "gaseosa de limón",
        "agua saborizada de limón", "mermelada de limón", "cáscara de limón deshidratada",
        "aderezo de limón", "vinagreta de limón", "sal de limón", "caramelos de limón",
        "galletas de limón", "queque de limón", "helado de limón", "té helado de limón",
        "aceite esencial de limón", "ralladura de limón", "gelatina de limón",
        "limón en polvo", "pisco sour mix", "refresco de limón"]},

    {"insumo": "ajo", "base": "ajo",
     "tokens": ["ajo(?!njoli)", "garlic", "knoblauch"],
     "terminos": [
        "ajo en polvo", "pasta de ajo", "ajo molido", "ajo deshidratado",
        "ajo en escamas", "aceite de ajo", "ajo encurtido", "sal de ajo", "aderezo de ajo",
        "mayonesa de ajo", "pan de ajo", "salsa de ajo", "ajo negro", "ajo granulado",
        "condimento de ajo", "ajo frito crocante", "ajo en conserva", "chimichurri",
        "alioli", "ajo confitado"]},

    {"insumo": "cebolla", "base": "cebolla",
     "tokens": ["cebolla", "onion", "zwiebel"],
     "terminos": [
        "cebolla deshidratada", "cebolla en polvo", "cebolla frita crocante",
        "aros de cebolla", "cebolla encurtida", "sopa de cebolla", "salsa criolla",
        "cebolla caramelizada", "cebolla granulada", "condimento de cebolla",
        "cebolla en escamas", "cebolla china deshidratada", "mermelada de cebolla",
        "aderezo de cebolla", "cebolla congelada", "snack sabor cebolla", "crema de cebolla",
        "cebolla en conserva", "sal de cebolla", "cebolla morada encurtida"]},

    {"insumo": "zanahoria", "base": "zanahoria",
     "tokens": ["zanahoria", "carrot", "karotte"],
     "terminos": [
        "jugo de zanahoria", "zanahoria rallada en conserva", "puré de zanahoria",
        "zanahoria baby", "zanahoria congelada", "sopa de zanahoria", "queque de zanahoria",
        "mermelada de zanahoria", "chips de zanahoria", "zanahoria deshidratada",
        "papilla de zanahoria", "néctar de zanahoria", "zanahoria encurtida",
        "ensalada de zanahoria", "zanahoria en cubos", "jugo de zanahoria y naranja",
        "snack de zanahoria", "zanahoria en polvo", "crema de zanahoria",
        "zanahoria en conserva"]},

    {"insumo": "avena", "base": "avena",
     "tokens": ["avena", "oat", "hafer"],
     "terminos": [
        "hojuelas de avena", "avena instantánea", "harina de avena", "bebida de avena",
        "leche de avena", "granola con avena", "barras de avena", "galletas de avena",
        "avena precocida", "salvado de avena", "avena con quinua", "avena saborizada",
        "porridge de avena", "muesli", "avena integral", "panqueques de avena",
        "yogur con avena", "avena en polvo", "cereal de avena", "avena orgánica"]},

    {"insumo": "palta", "base": "palta",
     "tokens": ["palta", "aguacate", "avocado"],
     "terminos": [
        "aceite de palta", "guacamole", "pulpa de palta congelada", "palta en conserva",
        "crema de palta", "mayonesa de palta", "palta deshidratada", "aderezo de palta",
        "hummus de palta", "palta liofilizada", "mantequilla de palta", "salsa de palta",
        "palta Hass", "palta Fuerte", "extracto de palta", "harina de semilla de palta",
        "aceite de semilla de palta", "palta en cubos congelada", "dip de palta",
        "palta orgánica"]},

    {"insumo": "tomate", "base": "tomate",
     "tokens": ["tomate", "tomato", "ketchup"],
     "terminos": [
        "pasta de tomate", "salsa de tomate", "kétchup", "tomate pelado en conserva",
        "puré de tomate", "jugo de tomate", "tomate deshidratado", "tomate seco en aceite",
        "salsa napolitana", "salsa boloñesa", "sofrito de tomate", "tomate cherry en conserva",
        "sopa de tomate", "gazpacho", "passata de tomate", "tomate triturado",
        "tomate en polvo", "tomate confitado", "salsa pomodoro", "aderezo de tomate"]},

    {"insumo": "ají", "base": "ají",
     "tokens": ["aji", "rocoto", "chili", "capsicum", "paprika", "pimiento"],
     "terminos": [
        "pasta de ají amarillo", "pasta de ají panca", "ají amarillo en conserva",
        "ají molido", "ají en polvo", "salsa de ají", "crema de ají", "ají deshidratado",
        "rocoto molido", "pasta de rocoto", "salsa huancaína", "aderezo de ají",
        "ají amarillo congelado", "ají charapita", "salsa picante", "ají mirasol",
        "ají limo", "condimento de ají", "ají en escabeche", "ají panca molido"]},

    {"insumo": "yuca", "base": "yuca",
     "tokens": ["yuca", "cassava", "manioc", "tapioca", "casabe", "sagu"],
     "terminos": [
        "harina de yuca", "almidón de yuca", "chifles de yuca", "yuca congelada",
        "yuca frita precocida", "pan de yuca", "perlas de tapioca", "fécula de yuca",
        "yuca deshidratada", "snack de yuca", "chips de yuca", "casabe",
        "harina de tapioca", "yuca en trozos congelada", "croquetas de yuca",
        "puré de yuca", "yuca en conserva", "sagú", "bebida de tapioca", "galletas de yuca"]},

    {"insumo": "naranja", "base": "naranja",
     "tokens": ["naranja", "mandarina", "orange", "mandarin", "citrico"],
     "terminos": [
        "jugo de naranja", "néctar de naranja", "mermelada de naranja",
        "gaseosa de naranja", "naranja en conserva", "cáscara de naranja confitada",
        "aceite esencial de naranja", "refresco de mandarina", "jugo de mandarina",
        "mandarina en conserva", "agua saborizada de naranja", "té de naranja",
        "caramelos de naranja", "chocolate con naranja", "queque de naranja",
        "jugo concentrado de naranja", "naranja deshidratada", "pulpa de naranja",
        "ralladura de naranja", "marmalade de naranja"]},

    {"insumo": "aceite vegetal", "base": "aceite vegetal",
     "tokens": ["aceite vegetal", "aceite de soya", "aceite de soja", "aceite de girasol",
                "aceite de maiz", "aceite de canola", "aceite de oliva", "aceite de palma",
                "aceite de coco", "aceite de ajonjoli", "aceite de linaza", "margarina",
                "grasa vegetal", "vegetable oil", "sunflower oil", "rapeseed oil",
                "palm oil", "soybean oil"],
     "terminos": [
        "aceite de soya", "aceite de girasol", "aceite de maíz",
        "aceite vegetal mixto", "aceite de canola", "aceite de oliva", "margarina",
        "manteca vegetal", "aceite en spray", "aceite de sacha inchi", "aceite de ajonjolí",
        "aceite de palma", "aceite refinado", "aceite de linaza", "aceite de coco",
        "aceite de semilla de uva", "aceite alto oleico", "aceite para freír",
        "aceite vegetal orgánico", "mantequilla vegetal"]},

    {"insumo": "plátano", "base": "plátano",
     "tokens": ["platano", "banana", "banane", "plantain", "chifle"],
     "terminos": [
        "chifles", "harina de plátano", "plátano deshidratado", "puré de plátano",
        "néctar de plátano", "plátano congelado", "chips de plátano", "banana liofilizada",
        "mermelada de plátano", "papilla de plátano", "plátano en almíbar",
        "snack de plátano", "queque de plátano", "batido de plátano", "plátano en polvo",
        "plátano verde precocido", "tostones", "harina de plátano verde",
        "barra de plátano", "plátano bizcocho"]},

    {"insumo": "zapallo", "base": "zapallo",
     "tokens": ["zapallo", "calabaza", "pumpkin", "kurbis", "squash", "loche"],
     "terminos": [
        "puré de zapallo", "zapallo congelado", "sopa de zapallo", "crema de zapallo",
        "zapallo en conserva", "semillas de zapallo", "aceite de semilla de zapallo",
        "papilla de zapallo", "zapallo deshidratado", "harina de zapallo",
        "mermelada de zapallo", "pasta de zapallo loche", "snack de semillas de zapallo",
        "puré instantáneo de zapallo", "zapallo en cubos", "jugo de zapallo",
        "dulce de zapallo", "zapallo italiano congelado", "zapallo en polvo",
        "calabaza en conserva"]},

    {"insumo": "quinua", "base": "quinua",
     "tokens": ["quinua", "quinoa"],
     "terminos": [
        "quinua perlada", "harina de quinua", "hojuelas de quinua", "quinua pop",
        "barras de quinua", "galletas de quinua", "fideos de quinua", "bebida de quinua",
        "leche de quinua", "granola con quinua", "quinua tricolor", "quinua roja",
        "quinua negra", "quinua orgánica", "snack de quinua", "quinua precocida",
        "mix de quinua y menestras", "papilla de quinua", "cereal de quinua",
        "quinua expandida"]},

    {"insumo": "menestras", "base": "lenteja",
     "tokens": ["lenteja", "frijol", "frejol", "garbanzo", "pallar", "arveja",
                "haba(?!nero)", "tarwi", "lentil", "chickpea", "bean", "hummus"],
     "terminos": [
        "lenteja seca", "frijol canario", "frijol negro", "pallar", "garbanzo",
        "arveja partida", "hummus", "pasta de garbanzo", "harina de lenteja",
        "harina de garbanzo", "frijol en conserva", "lentejas en conserva",
        "sopa de lentejas", "snack de garbanzo", "fideos de lenteja", "fideos de garbanzo",
        "mix de menestras", "frejol castilla", "arveja seca", "tarwi"]},

    {"insumo": "camote", "base": "camote",
     "tokens": ["camote", "batata", "boniato", "sweet potato", "susskartoffel"],
     "terminos": [
        "camote deshidratado", "chips de camote", "puré de camote", "harina de camote",
        "camote congelado", "camote frito precocido", "dulce de camote",
        "camote en almíbar", "papilla de camote", "snack de camote",
        "camote morado en polvo", "jugo de camote", "camote asado envasado",
        "croquetas de camote", "camote en cubos", "colorante de camote morado",
        "camote liofilizado", "pan de camote", "mermelada de camote",
        "camote amarillo envasado"]},
]
