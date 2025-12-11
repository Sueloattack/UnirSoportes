import os
import sys
# Asegurar que el directorio raíz está en el path para importar logica
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logica.workers.automatizador_radicacion_logic import extraer_datos_carta_glosa

# Rutas de prueba
TEST_DIR = r"c:\Users\GLOSAS\Documents\JJAC\UnirSoportes\HerramientasJJAC\calixto\Previsora\test"

def run_analysis():
    print("--- Iniciando Análisis de PDFs de Prueba ---")
    
    files_to_test = [
        "FECR343879.pdf", # Caso Mezcla (Glosa Parcial)
        "FECR350277.pdf", # Caso Oficio (Devolución)
        "FECR342713.pdf"  # Caso Escaneado (OCR)
    ]

    for filename in files_to_test:
        pdf_path = os.path.join(TEST_DIR, filename)
        print(f"\nAnalizando: {filename}")
        
        if not os.path.exists(pdf_path):
            print(f"❌ Archivo no encontrado: {pdf_path}")
            continue
            
        try:
            resultado = extraer_datos_carta_glosa(pdf_path)
            
            print(f"  > Tiene Valor: {resultado['tiene_valor']}")
            print(f"  > Valor Objeción: {resultado['valor_objecion']}")
            print(f"  > Clasificación: {resultado['clasificacion']}")
            print(f"  > Es GT: {resultado['es_gt']}")
            print(f"  > Es Glosa Parcial: {resultado['es_glosa_parcial']}")
            print(f"  > Es Devolución Total: {resultado['es_devolucion_total']}")
            print(f"  > Es Devolución Simple: {resultado.get('es_devolucion_simple', False)}")
            print(f"  > Es Escaneado: {resultado['es_pdf_escaneado']}")
            if resultado['error']:
                print(f"  > Error: {resultado['error']}")
                
        except Exception as e:
            print(f"❌ Error excepcional ejecutando análisis: {e}")

if __name__ == "__main__":
    run_analysis()
