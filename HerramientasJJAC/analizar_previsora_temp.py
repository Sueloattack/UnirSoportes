"""
Script temporal para analizar los PDFs de Previsora y extraer patrones
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pypdf

def analizar_previsora():
    carpeta = r'c:\Users\GLOSAS\Documents\JJAC\UnirSoportes\HerramientasJJAC\calixto\Previsora'
    
    # Archivos de muestra para analizar
    archivos_muestra = [
        '27139833_S18-01_0001..pdf',
        'CDF_2627551_202511010741.pdf',
        '7801778_S06.pdf'
    ]
    
    resultados = {}
    
    for archivo in archivos_muestra:
        ruta = os.path.join(carpeta, archivo)
        if os.path.exists(ruta):
            try:
                with open(ruta, 'rb') as f:
                    pdf = pypdf.PdfReader(f)
                    texto = pdf.pages[0].extract_text()
                    resultados[archivo] = texto[:2500]
                    print(f"\n{'='*70}")
                    print(f"ARCHIVO: {archivo}")
                    print('='*70)
                    print(texto[:2500])
                    print('\n')
            except Exception as e:
                print(f"Error al leer {archivo}: {e}")
                resultados[archivo] = f"ERROR: {e}"
    
    return resultados

if __name__ == "__main__":
    print("\n*** ANÁLISIS DE ARCHIVOS PREVISORA ***\n")
    analizar_previsora()
    print("\n*** FIN DEL ANÁLISIS ***\n")
