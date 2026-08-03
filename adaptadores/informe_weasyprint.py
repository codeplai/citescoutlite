from pathlib import Path
from puertos.repositorio_informes import RepositorioInformes
from dominio.dossier_regulatorio import DossierRegulatorio
from dominio.hipotesis_formulacion import HipotesisFormulacion
from dominio.informe_scout import InformeScout
from dominio.insight_mercado import InsightDeMercado
from dominio.mapa_comercial import MapaComercial
from puertos.auditoria import Ejecucion

import markdown

class InformeWeasyPrint(RepositorioInformes):
    def __init__(self, output_dir: str = "informes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    #: Filas de la tabla del mapa en el **PDF**.
    #:
    #: Con los ingredientes a texto completo cada fila ocupa casi media página:
    #: con 25 el informe salía de 13 páginas y la tabla se comía el 85 % del
    #: documento. Con 12 se queda en ~7 y el resto del informe vuelve a pesar
    #: algo. La aplicación no tiene este problema y las pagina todas, así que lo
    #: que aquí se recorta no se pierde: se dice cuántas hay y dónde están.
    FILAS_TABLA = 12

    @staticmethod
    def _bloque_paywall(que_falta: str) -> str:
        return (f"_Esta sección requiere el plan premium: {que_falta} no se "
                f"generó para este informe._\n\n")

    @staticmethod
    def _celda(valor) -> str:
        """Celda de la tabla del mapa. Lo que no hay se escribe **sin dato**.

        Ni se oculta la columna ni se rellena con un guion: un guion se lee como
        "no aplica" y estos campos sí aplican, simplemente no se conocen. Es el
        gesto visual del bloque 2 del guion.
        """
        if valor is None or valor == "" or valor == []:
            return "_sin dato_"
        if isinstance(valor, list):
            valor = ", ".join(str(v) for v in valor)
        # El pipe partiria la fila de la tabla en markdown.
        return str(valor).replace("|", "\\|")

    #: Marcas que delimitan la sección del mapa dentro del markdown.
    #:
    #: El PDF necesita la tabla escrita; la SPA no, porque recibe el mapa como
    #: objeto y pinta una tabla paginada con los 200 productos. Sin estas marcas
    #: la SPA enseñaría las dos: la suya y las 25 filas del markdown.
    #:
    #: Son comentarios HTML a propósito: ni python-markdown ni xhtml2pdf los
    #: imprimen, así que el PDF no se entera de que están.
    MARCA_MAPA_INICIO = "<!--MAPA-->"
    MARCA_MAPA_FIN = "<!--/MAPA-->"

    def _seccion_mapa(self, mapa) -> str:
        """Tabla del mapa comercial: país · marca · presentación · precio · fecha."""
        if mapa is None:
            return ""

        contenido = f"{self.MARCA_MAPA_INICIO}\n\n## 🗺️ Mapa comercial\n\n"

        if not mapa.productos:
            contenido += ("_Sin datos: no se encontró ningún producto para este "
                          "insumo en el snapshot._\n\n")
            contenido += self._nota_niveles(mapa)
            return contenido + f"{self.MARCA_MAPA_FIN}\n\n"

        paises, marcas = mapa.paises(), mapa.marcas()
        contenido += (
            f"**{len(mapa.productos)} productos** en **{len(paises)} países** y "
            f"**{len(marcas)} marcas**, del snapshot `2026-07`.\n\n")

        contenido += self._seccion_precio(mapa)

        # Columnas pensadas desde quien lee: un tecnólogo de alimentos. Fuera
        # `fecha` (es la última modificación del registro en OFF, no el
        # lanzamiento del producto) y fuera `presentación`, para dejarle sitio a
        # los ingredientes. `Precio` se queda porque es el hueco que hay que
        # enseñar, y con una columna vacía basta para enseñarlo.
        contenido += "| Producto | País | Marca | Precio | Aditivos | Ingredientes |\n"
        contenido += "|---|---|---|---|---|---|\n"
        for p in mapa.productos[:self.FILAS_TABLA]:
            # El nombre enlaza a la ficha de origen: la URL entera ocuparia
            # media fila y asi sigue siendo comprobable con un clic.
            # El recorte lleva puntos suspensivos: un nombre cortado que se lee
            # como completo es un dato mal presentado, aunque sea de refilon.
            nombre = self._celda(p.nombre)
            if len(nombre) > 38:
                nombre = nombre[:37].rstrip() + "…"
            producto = f"[{nombre}]({p.url})"
            # Los ingredientes van en texto plano y completos: es la columna que
            # de verdad se lee en un informe impreso, y recortarla la volveria
            # decorativa.
            contenido += (
                f"| {producto} "
                f"| {self._celda(p.paises_iso)} "
                f"| {self._celda(p.marca)} "
                f"| {self._celda(p.precio_rango)} "
                f"| {self._celda(p.aditivos)} "
                f"| {self._celda(p.ingredientes)} |\n")
        contenido += "\n"

        if len(mapa.productos) > self.FILAS_TABLA:
            contenido += (f"_Se muestran {self.FILAS_TABLA} de "
                          f"{len(mapa.productos)} productos; los "
                          f"{len(mapa.productos)} están en la aplicación, "
                          f"paginados._\n\n")

        sin_marca = mapa.sin_marca()
        if sin_marca:
            contenido += (f"_{sin_marca} de los {len(mapa.productos)} productos no "
                          f"traen marca en la fuente._\n\n")

        # Lo que la tabla enseña vacio, dicho con todas las letras. Es la
        # afirmacion que sostiene el bloque 2 del guion, y es verificable.
        contenido += (
            "> **La columna Precio sale vacía en todas las filas**, y la "
            "presentación y el canal de venta ni siquiera se recogen. No es un "
            "fallo de este informe ni una limitación del plan contratado: esos "
            "tres campos no existen en el snapshot de datos abiertos, y una "
            "sonda sobre 100 códigos de barras encontró precio para el 3 %, "
            "ninguno en Perú. Rellenarlos es el trabajo del nivel 3 de "
            "descubrimiento comercial, que no está disponible en esta "
            "versión.\n\n")

        con_aditivos = sum(1 for p in mapa.productos if p.aditivos)
        con_alergenos = sum(1 for p in mapa.productos if p.alergenos)
        contenido += (
            f"_Aditivos leídos del texto de la etiqueta en {con_aditivos} de "
            f"{len(mapa.productos)} productos. Alérgenos **declarados** en "
            f"{con_alergenos}: una celda vacía significa que la etiqueta no los "
            f"declara, no que el producto no los tenga._\n\n")

        contenido += self._nota_niveles(mapa)
        return contenido + f"{self.MARCA_MAPA_FIN}\n\n"

    @staticmethod
    def _seccion_precio(mapa) -> str:
        """Precio de la materia prima. Sección propia, no columna de la tabla.

        Va separada del listado de productos a propósito. Son dos preguntas
        distintas —a cuánto está el kilo de palta, frente a a cuánto vende su
        guacamole una marca— y ponerlas en la misma tabla haría creer que el
        precio de góndola existe y está detrás del plan de pago. No existe.
        """
        precios = getattr(mapa, "precios_materia_prima", None) or []

        contenido = "### 💰 Precio de la materia prima\n\n"
        if not precios:
            return contenido + (
                f"_El boletín diario de MIDAGRI no publica precio mayorista para "
                f"**{mapa.insumo}**. Los mercados de Lima no lo comercializan en "
                f"volumen: en el caso del arándano, porque casi toda la "
                f"producción peruana va a exportación._\n\n")

        contenido += "| Variedad | Mercado | S/ por kg | Var. semanal |\n"
        contenido += "|---|---|---:|---:|\n"
        for p in precios:
            variacion = (f"{p.variacion_pct:+.1f} %"
                         if p.variacion_pct is not None else "_sin dato_")
            contenido += (f"| {p.producto} | {p.mercado} "
                          f"| {p.precio_soles_kg:.2f} | {variacion} |\n")
        contenido += "\n"

        reciente = max(precios, key=lambda p: p.fecha)
        contenido += (
            f"_Fuente: {reciente.fuente}, boletín del "
            f"{reciente.fecha.strftime('%d/%m/%Y')} en "
            f"{reciente.mercado_nombre}._\n\n"
            "> Este es el precio del **insumo como materia prima**, que es con "
            "el que se costea una formulación. **No es el precio en góndola de "
            "los productos de la tabla siguiente**, que no lo tenemos.\n\n")
        return contenido

    @staticmethod
    def _nota_niveles(mapa) -> str:
        """La linea que declara lo que no se consulto."""
        if not mapa.niveles_no_disponibles:
            return ""
        nombres = {1: "snapshot local", 2: "API licenciada", 3: "agente web"}
        faltan = ", ".join(f"nivel {n} ({nombres.get(n, '?')})"
                           for n in mapa.niveles_no_disponibles)
        return f"_Fuentes no consultadas: {faltan}._\n\n"

    def pide_reformulacion(self, ejecucion: Ejecucion) -> InformeScout:
        return InformeScout(
            parcial=False,
            snapshot_version=ejecucion.snapshot_version,
            ruta_pdf=None,
            ejecucion_id=ejecucion.id,
            markdown_content=None
        )

    def emitir(self, ejecucion: Ejecucion, insight: InsightDeMercado | None,
               parcial: bool,
               hipotesis: HipotesisFormulacion | None = None,
               dossier: DossierRegulatorio | None = None,
               mapa: MapaComercial | None = None) -> InformeScout:
        md_path = self.output_dir / f"{ejecucion.id}.md"
        pdf_path = self.output_dir / f"{ejecucion.id}.pdf"
        
        # Mejorar los saltos de línea para que markdown los procese como párrafos
        def format_text(text):
            if not text: return ""
            return text.replace('\\n', '\n\n').replace('\n', '\n\n').replace('\n\n\n', '\n\n')

        contenido = f"# 🚀 Informe AgroScout IA Lite\n"
        contenido += f"**Generado por CITEagroindustrial Chavimochic**\n\n"
        contenido += f"---\n\n"
        
        contenido += f"**Insumo evaluado:** `{ejecucion.insumo_texto.upper()}`\n\n"
        
        contenido += f"## 📊 Insight de Mercado\n\n"

        # insight a None significa que el run se detuvo antes de la etapa 3, hoy
        # solo por presupuesto agotado (T6.3). Se emite informe igualmente, con
        # el hueco declarado: degradar a "sin dato", nunca a error.
        if insight is None:
            contenido += ("_Sin datos: el presupuesto asignado se agotó antes de "
                          "generar el análisis de mercado. No se ejecutó ninguna "
                          "llamada al modelo._\n\n")
            # El mapa sí sobrevive: la etapa 2b no gasta presupuesto, así que un
            # run sin saldo conserva de qué países y marcas hay producto.
            contenido += self._seccion_mapa(mapa)
            return self._componer(ejecucion, contenido, md_path, pdf_path, parcial,
                                  None, hipotesis, dossier, mapa)

        # Badge-style for coverage
        color = "green" if insight.cobertura.lower() == "alta" else "orange" if insight.cobertura.lower() == "media" else "red"
        contenido += f"**Cobertura de datos en bases abiertas:** {insight.cobertura.capitalize()} 🟢\n\n"

        contenido += f"### 💡 Resumen de Oportunidad\n{format_text(insight.resumen)}\n\n"

        if insight.formatos_comunes:
            contenido += f"### 📦 Formatos Comunes Identificados\n"
            for f in insight.formatos_comunes:
                contenido += f"- {f}\n"
            contenido += "\n"
                
        # Etapa 2b. Va aquí, cerrando lo que ve el plan gratuito, y antes de las
        # dos secciones premium.
        contenido += self._seccion_mapa(mapa)

        # Etapa 4 - premium. Si no viene, no es que fallara: es que no se
        # ejecutó. El bloque de paywall ocupa su sitio en vez de dejar el hueco.
        contenido += f"### 🧪 Hipótesis de Formulación e Ingeniería Inversa\n"
        if hipotesis:
            contenido += f"{format_text(hipotesis.hipotesis)}\n\n"
            if hipotesis.ingredientes_probables:
                contenido += "**Ingredientes probables:**\n"
                for i in hipotesis.ingredientes_probables:
                    contenido += f"- {i}\n"
                contenido += "\n"
            if hipotesis.procesos_sugeridos:
                contenido += "**Procesos sugeridos:**\n"
                for p in hipotesis.procesos_sugeridos:
                    contenido += f"- {p}\n"
                contenido += "\n"
        else:
            contenido += self._bloque_paywall("la ingeniería inversa de la formulación")

        # Etapa 5 - premium. El plan gratuito conserva la nota orientativa del
        # insight (D4); lo que se compra aquí son citas verificables.
        contenido += f"### ⚖️ Dossier Regulatorio\n"
        if dossier and not dossier.sin_dato:
            if dossier.restricciones:
                for r in dossier.restricciones:
                    contenido += f"- {r}\n"
                contenido += "\n"
            if dossier.citas:
                contenido += "**Fuentes verificables:**\n\n"
                for c in dossier.citas:
                    contenido += f"- **{c.fuente}**"
                    if c.fecha:
                        contenido += f" ({c.fecha})"
                    contenido += f": {c.texto}\n"
                    if c.url:
                        contenido += f"  Fuente: `{c.url}`\n"
                contenido += "\n"
        elif dossier and dossier.sin_dato:
            contenido += ("_Sin datos: el corpus normativo consultado no contiene "
                          "normas aplicables a este insumo._\n\n")
        else:
            contenido += self._bloque_paywall("el dossier con citas verificables")

        if insight.nota_regulatoria:
            contenido += (f"> **Nota regulatoria orientativa.** "
                          f"{format_text(insight.nota_regulatoria)}\n\n")

        if insight.citas:
            contenido += f"### 📚 Citas y Productos de Referencia\n"
            for c in insight.citas:
                contenido += f"- `{c}`\n"

        return self._componer(ejecucion, contenido, md_path, pdf_path, parcial,
                              insight, hipotesis, dossier, mapa)

    def _componer(self, ejecucion, contenido, md_path, pdf_path, parcial,
                  insight, hipotesis, dossier, mapa=None) -> InformeScout:
        """Markdown -> HTML -> PDF. Comun a los dos caminos de emitir()."""
        # Guardar markdown original para referencia
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(contenido)
            
        # Convertir Markdown a HTML con extensiones útiles
        html_content = markdown.markdown(contenido, extensions=['tables', 'sane_lists'])
        
        # Estilos avanzados para el PDF
        estilos_html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{
                    size: A4;
                    margin: 2cm;
                    @frame footer {{
                        -pdf-frame-content: footerContent;
                        bottom: 1cm;
                        margin-left: 2cm;
                        margin-right: 2cm;
                        height: 1cm;
                    }}
                }}
                body {{ 
                    font-family: "Helvetica Neue", Helvetica, Arial, sans-serif; 
                    line-height: 1.6; 
                    color: #2c3e50; 
                    font-size: 11pt;
                }}
                h1 {{ 
                    color: #1a5276; 
                    font-size: 24pt;
                    border-bottom: 3px solid #2980b9; 
                    padding-bottom: 5px; 
                    margin-bottom: 5px;
                }}
                h2 {{ 
                    color: #2980b9; 
                    font-size: 16pt;
                    margin-top: 1.5em;
                    background-color: #ebf5fb;
                    padding: 8px 12px;
                    border-left: 5px solid #2980b9;
                }}
                h3 {{ 
                    color: #117864; 
                    font-size: 13pt;
                    margin-top: 1.2em;
                    border-bottom: 1px solid #d1f2eb;
                    padding-bottom: 4px;
                }}
                p {{ 
                    text-align: justify; 
                    margin-bottom: 10px;
                }}
                li {{ 
                    margin-bottom: 6px; 
                    text-align: justify;
                }}
                hr {{
                    border: 0;
                    border-top: 1px solid #bdc3c7;
                    margin: 20px 0;
                }}
                strong {{
                    color: #2c3e50;
                }}
                code {{
                    background-color: #f2f4f4;
                    padding: 2px 5px;
                    border-radius: 3px;
                    font-family: "Courier New", Courier, monospace;
                    font-size: 10pt;
                    color: #c0392b;
                }}
                /*
                   Tabla del mapa comercial. Hasta S4 ningun informe traia
                   tablas, asi que no habia estilos y xhtml2pdf la componia con
                   los suyos por defecto: con la columna de ingredientes a texto
                   completo, salia desbordada del ancho de pagina.

                   table-layout fijo y font pequena es lo que hace que las seis
                   columnas quepan en un A4 con margenes de 2 cm.
                */
                table {{
                    width: 100%;
                    table-layout: fixed;
                    border-collapse: collapse;
                    font-size: 6.5pt;
                    margin: 10px 0;
                }}
                th {{
                    background-color: #ebf5fb;
                    border: 1px solid #bdc3c7;
                    padding: 3px 4px;
                    text-align: left;
                    font-size: 7pt;
                }}
                td {{
                    border: 1px solid #d5dbdb;
                    padding: 3px 4px;
                    text-align: left;
                    vertical-align: top;
                    word-wrap: break-word;
                }}
                td em {{
                    color: #7f8c8d;
                    font-style: normal;
                    font-size: 6pt;
                }}
            </style>
        </head>
        <body>
            {html_content}
            <div id="footerContent" style="text-align: center; font-size: 9pt; color: #7f8c8d; border-top: 1px solid #bdc3c7; padding-top: 5px;">
                AgroScout IA Lite - CITEagroindustrial Chavimochic &bull; Página <pdf:pagenumber>
            </div>
        </body>
        </html>
        """
        
        # Generar PDF con xhtml2pdf.
        #
        # No es WeasyPrint pese al nombre del modulo (historico; renombrarlo es
        # limpieza barata para T7). WeasyPrint necesita las librerias nativas de
        # GTK/Pango, que en Windows no estan: la llamada moria en
        # `cannot load library 'libgobject-2.0-0'` y por eso informes/ tenia 0
        # PDFs y solo el .md, que se escribe antes. Ademas la plantilla de
        # arriba ya estaba escrita para xhtml2pdf: @frame, -pdf-frame-content y
        # <pdf:pagenumber> son directivas suyas que WeasyPrint no entiende.
        from xhtml2pdf import pisa

        with open(pdf_path, "wb") as salida:
            resultado = pisa.CreatePDF(src=estilos_html, dest=salida,
                                       encoding="utf-8")
        if resultado.err:
            raise RuntimeError(
                f"No se pudo generar el PDF de {ejecucion.id}: "
                f"{resultado.err} error(es) de composicion")


        return InformeScout(
            parcial=parcial,
            snapshot_version=ejecucion.snapshot_version,
            ruta_pdf=str(pdf_path),
            ejecucion_id=ejecucion.id,
            markdown_content=contenido,
            insight=insight,
            hipotesis=hipotesis,
            dossier=dossier,
            mapa=mapa
        )
