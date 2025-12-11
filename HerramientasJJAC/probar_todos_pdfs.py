import os
import sys

# Ajustar imports para encontrar la carpeta logica
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar las funciones del OTRO archivo
try:
    from logica.workers.automatizador_radicacion_logic import extraer_datos_carta_glosa, identificar_serie_y_numero
except ImportError as e:
    print(f"❌ ERROR DE IMPORTACIÓN: {e}")
    print("Asegúrate de que la estructura de carpetas sea correcta.")
    sys.exit(1)

def probar_carpeta(ruta_carpeta):
    print(f"📂 Probando carpeta: {ruta_carpeta}\n")
    
    if not os.path.exists(ruta_carpeta):
        print("❌ La carpeta no existe.")
        return

    pdfs = [x for x in os.listdir(ruta_carpeta) if x.endswith('.pdf')]
    print(f"Encontrados {len(pdfs)} PDFs.\n" + "="*60)

    for archivo in sorted(pdfs):
        ruta_pdf = os.path.join(ruta_carpeta, archivo)
        serie, numero = identificar_serie_y_numero(archivo)
        
        # Llamar a la lógica
        datos = extraer_datos_carta_glosa(ruta_pdf)
        
        tipo = datos.get('tipo', 'Desconocido')
        valor = datos.get('valor_objecion', 0)
        es_img = datos.get('es_pdf_escaneado', False)
        
        icon = "🟢" if valor > 0 else "🔴"
        if es_img: icon = "⚠️ "
        
        print(f"📄 {archivo:<20} | {serie}-{numero}")
        print(f"   {icon} Tipo: {tipo}")
        print(f"   💰 Valor: ${valor:,.0f}")
        print("-" * 60)

if __name__ == "__main__":
    # Capturar argumento de carpeta o usar defecto
    carpeta = sys.argv[1] if len(sys.argv) > 1 else r"calixto/Previsora/test"
    probar_carpeta(carpeta)