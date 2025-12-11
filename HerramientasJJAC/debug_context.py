import pypdf
import sys

ruta = sys.argv[1] if len(sys.argv) > 1 else "calixto/Previsora/test/FECR331617.pdf"

with open(ruta, 'rb') as f:
    lector = pypdf.PdfReader(f)
    texto = ""
    for pagina in lector.pages:
        texto += pagina.extract_text()
    
    # Buscar el contexto alrededor de "1002"
    idx = texto.find('1002')
    if idx != -1:
        contexto = texto[max(0, idx-50):min(len(texto), idx+200)]
        print("Contexto alrededor de '1002':")
        print(repr(contexto))
        print()
        print("Texto legible:")
        print(contexto)
