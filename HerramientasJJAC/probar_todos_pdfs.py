import os
import sys

# Ajustar imports para encontrar la carpeta logica
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- CORRECCIÓN DE IMPORT ---
# Importamos extraer_serie_numero_de_nombre (NO identificar...)
try:
    from logica.workers.automatizador_radicacion_logic import extraer_datos_carta_glosa, extraer_serie_numero_de_nombre
except ImportError as e:
    print(f"❌ ERROR DE IMPORTACIÓN: {e}")
    print("Verifica que automatizador_radicacion_logic.py tenga la función 'extraer_serie_numero_de_nombre'")
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
        
        # Usamos el nombre correcto de la función
        serie, numero = extraer_serie_numero_de_nombre(archivo)
        
        # Extraer datos
        datos = extraer_datos_carta_glosa(ruta_pdf)
        
        # Determinar etiqueta para mostrar
        tipo_final = "GLOSA PARCIAL"
        if datos['es_pdf_escaneado']: tipo_final = "⚠️ IMAGEN/ESCANEADO"
        elif datos['es_devolucion_total']: tipo_final = "DEVOLUCIÓN TOTAL"
        elif datos['es_devolucion_simple']: tipo_final = "DEVOLUCIÓN (CARTA/OFICIO)"
        elif datos['es_gt']: tipo_final = "GLOSA TOTAL"
        elif not datos['tiene_valor']: tipo_final = "DEVOLUCIÓN (SALDO CARTERA)"
        
        valor = datos.get('valor_objecion', 0)
        icon = "🟢" if valor > 0 else "🔴"
        if datos['es_pdf_escaneado']: icon = "⚠️ "
        
        print(f"📄 {archivo:<20} | {serie}-{numero}")
        print(f"   {icon} Tipo Detectado: {tipo_final}")
        print(f"   💰 Valor: ${valor:,.0f}")

        # Mostrar items si es parcial (o si el usuario quiere verlos siempre, pero la petición dice parciales)
        items = datos.get('items_detectados', [])
        if "PARCIAL" in tipo_final and items:
            print(f"   📝 Items Detectados: {len(items)}")
            for i, item in enumerate(items, 1):
                # Recortamos si es muy largo para que no ensucie la consola
                print(f"      {i}. {item[:100]}...")
        elif items:
            # Opcional: Mostrar conteo discreto para otros tipos
            print(f"   ℹ️  Items encontrados en texto: {len(items)}")

        print("-" * 60)

if __name__ == "__main__":
    carpeta = sys.argv[1] if len(sys.argv) > 1 else ""
    
    if not carpeta:
        try:
            entrada = input("📂 Ingresa la ruta de la carpeta (Enter para usar 'calixto/Previsora/test'): ").strip()
            carpeta = entrada if entrada else r"calixto/Previsora/test"
        except EOFError:
            carpeta = r"calixto/Previsora/test"

    probar_carpeta(carpeta)