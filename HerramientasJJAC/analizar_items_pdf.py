import pypdf
import sys
import re

ruta = sys.argv[1] if len(sys.argv) > 1 else "calixto/Previsora/test/FECR343879.pdf"

with open(ruta, 'rb') as f:
    lector = pypdf.PdfReader(f)
    texto = ""
    for pagina in lector.pages:
        texto += pagina.extract_text()
    
    print("=" * 80)
    print("BÚSQUEDA DE VALORES DE OBJECIÓN EN ÍTEMS")
    print("=" * 80)
    
    # Buscar patrones de "Objecion" seguido de valor
    # Formato: "Objecion\n$ 0,00" o "Objecion\n$ 227.900,00"
    patron = r'Objeci[oó]n[\\s\\n]+\\$\\s*([\\d,.]+)'
    matches = list(re.finditer(patron, texto, re.IGNORECASE))
    
    print(f"\nEncontrados {len(matches)} valores de objeción en ítems:")
    
    valores = []
    for i, match in enumerate(matches, 1):
        valor_str = match.group(1).replace('.', '').replace(',', '.')
        try:
            valor = float(valor_str)
            valores.append(valor)
            print(f"  {i}. ${valor:,.2f}")
        except:
            print(f"  {i}. {match.group(1)} (no se pudo convertir)")
    
    print(f"\nAnálisis:")
    if valores:
        valores_cero = sum(1 for v in valores if v == 0)
        valores_positivos = sum(1 for v in valores if v > 0)
        print(f"  - Ítems con Objeción = $0: {valores_cero}")
        print(f"  - Ítems con Objeción > $0: {valores_positivos}")
        print(f"  - Total ítems: {len(valores)}")
        
        if valores_cero > 0 and valores_positivos > 0:
            print(f"\n  ✅ GLOSA PARCIAL (mezcla de ítems con y sin objeción)")
        elif valores_cero == len(valores):
            print(f"\n  ⚠️  Todos los ítems tienen Objeción=$0")
        elif valores_positivos == len(valores):
            print(f"\n  ✅ DEVOLUCIÓN TOTAL (todos los ítems con objeción)")
