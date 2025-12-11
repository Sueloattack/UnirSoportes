"""
Script de prueba para verificar la extracción de datos de los PDFs de ejemplo
"""

import sys
import os

# Agregar el directorio raíz al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logica.workers.automatizador_radicacion_logic import (
    extraer_serie_numero_de_nombre,
    extraer_datos_carta_glosa
)

def probar_extraccion():
    """Prueba la extracción de datos de los PDFs de ejemplo"""
    
    carpeta_test = r"calixto\Previsora\test"
    pdfs_test = [
        "COEX30126.pdf",  # Devolución (sin valor)
        "COEX13088.pdf",  # Con clasificación y valor
        "FECR329375.pdf"  # Con clasificación y valor
    ]
    
    print("="*70)
    print("PRUEBA DE EXTRACCIÓN DE DATOS DE CARTA GLOSAS")
    print("="*70)
    print()
    
    for pdf_nombre in pdfs_test:
        print(f"\n{'='*70}")
        print(f"Archivo: {pdf_nombre}")
        print(f"{'='*70}")
        
        # 1. Extraer serie y número del nombre
        serie, numero = extraer_serie_numero_de_nombre(pdf_nombre)
        print(f"\n📄 Extracción del nombre:")
        print(f"   Serie: {serie}")
        print(f"   Número: {numero}")
        
        # 2. Extraer datos del PDF
        ruta_pdf = os.path.join(carpeta_test, pdf_nombre)
        if os.path.exists(ruta_pdf):
            datos = extraer_datos_carta_glosa(ruta_pdf)
            
            print(f"\n📊 Datos extraídos del PDF:")
            print(f"   Tiene valor: {datos['tiene_valor']}")
            print(f"   Valor objeción: ${datos['valor_objecion']:,.0f}" if datos['valor_objecion'] else "   Valor objeción: No encontrado")
            print(f"   Clasificación: {datos['clasificacion']}" if datos['clasificacion'] else "   Clasificación: No encontrada")
            
            # 3. Determinar tipo de glosa según lógica de negocio
            print(f"\n🔍 Lógica de negocio:")
            if not datos['tiene_valor']:
                print(f"   → Tipo de Glosa: DEVOLUCIÓN")
                print(f"   → Valor Glosa: Saldo en Cartera del sistema")
                print(f"   → Razón: PDF no contiene valor de objeción")
            elif datos['clasificacion'] == 'NU' or not datos['clasificacion']:
                print(f"   → Tipo de Glosa: GLOSA PARCIAL")
                print(f"   → Valor Glosa: ${datos['valor_objecion']:,.0f}")
                print(f"   → Razón: Clasificación es NU o no existe")
            else:
                print(f"   → Tipo de Glosa: GLOSA PARCIAL")
                print(f"   → Valor Glosa: ${datos['valor_objecion']:,.0f}")
                print(f"   → Razón: Clasificación existe ({datos['clasificacion']})")
        else:
            print(f"\n❌ ERROR: No se encontró el archivo {ruta_pdf}")
    
    print(f"\n{'='*70}")
    print("PRUEBA COMPLETADA")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    probar_extraccion()
    input("\nPresiona Enter para salir...")
