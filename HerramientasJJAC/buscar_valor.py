import pypdf
import sys

ruta = sys.argv[1] if len(sys.argv) > 1 else "calixto/Previsora/test/FECR350277.pdf"

with open(ruta, 'rb') as f:
    lector = pypdf.PdfReader(f)
    texto = ""
    for pagina in lector.pages:
        texto += pagina.extract_text()
    
    # Buscar "Total" y mostrar contexto
    lines = texto.split('\n')
    for i, line in enumerate(lines):
        if 'total' in line.lower() or '524' in line or 'devolucion' in line.lower():
            print(f"{i}: {line}")
