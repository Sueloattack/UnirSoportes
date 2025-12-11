import pypdf
import sys

ruta = sys.argv[1] if len(sys.argv) > 1 else "calixto/Previsora/test/FECR331617.pdf"

with open(ruta, 'rb') as f:
    lector = pypdf.PdfReader(f)
    texto = ""
    for pagina in lector.pages:
        texto += pagina.extract_text()
    
    # Buscar líneas con "1002" o "Objecion"
    lineas = texto.split('\n')
    for i, linea in enumerate(lineas):
        if '1002' in linea or 'obje' in linea.lower():
            print(f"Línea {i}: {repr(linea)}")
