import pypdf
import os

carpeta = r'c:\Users\GLOSAS\Documents\JJAC\UnirSoportes\HerramientasJJAC\calixto\Previsora'

# Archivos de muestra para analizar
archivos_muestra = [
    '7801778_S06.pdf'
]

for archivo in archivos_muestra:
    ruta = os.path.join(carpeta, archivo)
    if os.path.exists(ruta):
        try:
            with open(ruta, 'rb') as f:
                pdf = pypdf.PdfReader(f)
                texto = pdf.pages[0].extract_text()
                print(f"\n{'='*60}")
                print(f"ARCHIVO: {archivo}")
                print('='*60)
                print(texto)
                print('\n')
        except Exception as e:
            print(f"Error al leer {archivo}: {e}")


