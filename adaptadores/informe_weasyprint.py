from pathlib import Path
from puertos.repositorio_informes import RepositorioInformes
from dominio.dossier_regulatorio import DossierRegulatorio
from dominio.hipotesis_formulacion import HipotesisFormulacion
from dominio.informe_scout import InformeScout
from dominio.insight_mercado import InsightDeMercado
from puertos.auditoria import Ejecucion

import markdown

class InformeWeasyPrint(RepositorioInformes):
    def __init__(self, output_dir: str = "informes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    @staticmethod
    def _bloque_paywall(que_falta: str) -> str:
        return (f"_Esta sección requiere el plan premium: {que_falta} no se "
                f"generó para este informe._\n\n")

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
               dossier: DossierRegulatorio | None = None) -> InformeScout:
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
            return self._componer(ejecucion, contenido, md_path, pdf_path, parcial,
                                  None, hipotesis, dossier)

        # Badge-style for coverage
        color = "green" if insight.cobertura.lower() == "alta" else "orange" if insight.cobertura.lower() == "media" else "red"
        contenido += f"**Cobertura de datos en bases abiertas:** {insight.cobertura.capitalize()} 🟢\n\n"

        contenido += f"### 💡 Resumen de Oportunidad\n{format_text(insight.resumen)}\n\n"

        if insight.formatos_comunes:
            contenido += f"### 📦 Formatos Comunes Identificados\n"
            for f in insight.formatos_comunes:
                contenido += f"- {f}\n"
            contenido += "\n"
                
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
                              insight, hipotesis, dossier)

    def _componer(self, ejecucion, contenido, md_path, pdf_path, parcial,
                  insight, hipotesis, dossier) -> InformeScout:
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
            dossier=dossier
        )
