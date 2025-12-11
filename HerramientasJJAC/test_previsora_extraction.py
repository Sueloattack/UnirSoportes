"""
Script de prueba para verificar la extracción de códigos de factura de Previsora
"""
import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logica.workers.renombrar_previsora_logic import extraer_codigo_factura_previsora

def probar_extraccion():
    carpeta = r'c:\Users\GLOSAS\Documents\JJAC\UnirSoportes\HerramientasJJAC\calixto\Previsora'
    
    # Archivos de muestra para probar
    archivos_prueba = [
        '27139833_S18-01_0001..pdf',  # Esperado: FECR344616
        'CDF_2627551_202511010741.pdf',  # Esperado: FERD618
        '7801778_S06.pdf'  # Esperado: FECR344540 (según la imagen)
    ]
    
    print("\n" + "="*70)
    print("PRUEBA DE EXTRACCIÓN DE CÓDIGOS DE FACTURA - PREVISORA")
    print("="*70 + "\n")
    
    for archivo in archivos_prueba:
        ruta = os.path.join(carpeta, archivo)
        if os.path.exists(ruta):
            codigo = extraer_codigo_factura_previsora(ruta)
            
            if codigo:
                print(f"✓ {archivo}")
                print(f"  → Código extraído: {codigo}")
                print(f"  → Nuevo nombre: {codigo}.pdf\n")
            else:
                print(f"✗ {archivo}")
                print(f"  → No se pudo extraer código\n")
        else:
            print(f"⚠ {archivo}")
            print(f"  → Archivo no encontrado\n")
    
    print("="*70)
    print("FIN DE LA PRUEBA")
    print("="*70 + "\n")

if __name__ == "__main__":
    probar_extraccion()
