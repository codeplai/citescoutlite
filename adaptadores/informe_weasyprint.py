from pathlib import Path
from puertos.repositorio_informes import RepositorioInformes
from dominio.informe_scout import InformeScout
from dominio.insight_mercado import InsightDeMercado
from puertos.auditoria import Ejecucion

import markdown

class InformeWeasyPrint(RepositorioInformes):
    def __init__(self, output_dir: str = "informes"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def pide_reformulacion(self, ejecucion: Ejecucion) -> InformeScout:
        return InformeScout(
            parcial=False,
            snapshot_version=ejecucion.snapshot_version,
            ruta_pdf=None,
            ejecucion_id=ejecucion.id,
            markdown_content=None
        )

    def emitir(self, ejecucion: Ejecucion, insight: InsightDeMercado, parcial: bool) -> InformeScout:
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
        
        # Badge-style for coverage
        color = "green" if insight.cobertura.lower() == "alta" else "orange" if insight.cobertura.lower() == "media" else "red"
        contenido += f"**Cobertura de datos en bases abiertas:** {insight.cobertura.capitalize()} 🟢\n\n"
        
        contenido += f"### 💡 Resumen de Oportunidad\n{format_text(insight.resumen)}\n\n"
        
        if insight.formatos_comunes:
            contenido += f"### 📦 Formatos Comunes Identificados\n"
            for f in insight.formatos_comunes:
                contenido += f"- {f}\n"
            contenido += "\n"
                
        contenido += f"### 🧪 Hipótesis de Formulación e Ingeniería Inversa\n{format_text(insight.hipotesis_formulacion)}\n\n"
        
        contenido += f"### ⚖️ Verificación Regulatoria Orientativa\n{format_text(insight.verificacion_regulatoria)}\n\n"
        
        if insight.citas:
            contenido += f"### 📚 Citas y Productos de Referencia\n"
            for c in insight.citas:
                contenido += f"- `{c}`\n"
                
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
        
        # Generar PDF con xhtml2pdf
        from xhtml2pdf import pisa
        with open(pdf_path, "wb") as pdf_file:
            pisa_status = pisa.CreatePDF(estilos_html, dest=pdf_file)
            
        return InformeScout(
            parcial=parcial,
            snapshot_version=ejecucion.snapshot_version,
            ruta_pdf=str(pdf_path),
            ejecucion_id=ejecucion.id,
            markdown_content=contenido
        )
