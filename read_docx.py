import zipfile
import xml.etree.ElementTree as ET

def read_docx(file_path):
    with zipfile.ZipFile(file_path) as docx:
        xml_content = docx.read('word/document.xml')
        tree = ET.fromstring(xml_content)
        
        # XML namespace for Word
        ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        
        paragraphs = []
        for p in tree.findall('.//w:p', ns):
            texts = p.findall('.//w:t', ns)
            if texts:
                paragraphs.append(''.join([t.text for t in texts if t.text]))
        
        return '\n'.join(paragraphs)

with open("propuesta.md", "w", encoding="utf-8") as f:
    f.write(read_docx('AgroScout_IA_Lite_Propuesta.docx'))
