import pypdf
import sys
import re

ruta = sys.argv[1] if len(sys.argv) > 1 else "calixto/Previsora/test/FECR342713.pdf"

with open(ruta, 'rb') as f:
    lector = pypdf.PdfReader(f)
    texto = ""
    for pagina in lector.pages:
        texto += pagina.extract_text()
    
    print("=" * 80)
    print("BÚSQUEDA DE '1002' Y CONTEXTO")
    print("=" * 80)
    
    # Buscar "1002"
    idx = texto.find('1002')
    if idx != -1:
        contexto = texto[max(0, idx-100):min(len(texto), idx+300)]
        print("\nContexto alrededor de '1002':")
        print(repr(contexto))
        print("\nTexto legible:")
        print(contexto)
    else:
        print("\nNO SE ENCONTRÓ '1002' en el PDF")
        
        # Buscar "Objecion" o "Objeción"
        print("\n" + "=" * 80)
        print("BÚSQUEDA DE 'OBJECION'")
        print("=" * 80)
        
        matches = list(re.finditer(r'objeci[oó]n', texto, re.IGNORECASE))
        if matches:
            print(f"\nEncontradas {len(matches)} ocurrencias de 'objecion'")
            for i, match in enumerate(matches[:3], 1):  # Solo primeras 3
                start = max(0, match.start() - 100)
                end = min(len(texto), match.end() + 200)
                contexto = texto[start:end]
                print(f"\n--- Ocurrencia {i} ---")
                print(repr(contexto))
        else:
            print("\nNO SE ENCONTRÓ 'objecion' en el PDF")
