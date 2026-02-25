import os

def comprobar_xml(carpeta_raiz):
    """
    Recorre subcarpetas y verifica que si existe un archivo PDF terminado en 
    _FACOSTE o _FACTURA, exista su versión .xml en la misma ubicación.
    """
    print(f"--- INICIANDO COMPROBACIÓN DE XMLs ---\n")
    
    contador_pdfs = 0
    faltantes = []
    
    try:
        # Recorremos recursivamente os.walk para abarcar subcarpetas profundas si es necesario,
        # o solo iteramos subcarpetas directas si esa es la estructura estricta.
        # Basado en la solicitud, "listado de subcarpetas" sugiere una estructura plana de subcarpetas.
        # Usaremos os.walk para ser más robustos.
        for raiz, directorios, archivos in os.walk(carpeta_raiz):
            for archivo in archivos:
                nombre_lower = archivo.lower()
                if nombre_lower.endswith('_facoste.pdf') or nombre_lower.endswith('_factura.pdf'):
                    contador_pdfs += 1
                    ruta_pdf = os.path.join(raiz, archivo)
                    
                    # Determinar nombre del XML esperado
                    nombre_xml = os.path.splitext(archivo)[0] + '.xml'
                    ruta_xml = os.path.join(raiz, nombre_xml)
                    
                    if not os.path.exists(ruta_xml):
                        faltantes.append(ruta_pdf)
                        print(f"❌ FALTA XML para: {archivo}")
                        print(f"   Ubicación: {raiz}")
                    
    except Exception as e:
        print(f"❌ Error al recorrer directorios: {e}")
        return

    print("\n" + "="*60)
    print("      REPORTE FINAL DE COMPROBACIÓN")
    print("="*60)
    print(f"📄 Total PDFs analizados (FACOSTE/FACTURA): {contador_pdfs}")
    
    if len(faltantes) == 0:
        print(f"✅ EXCELENTE: Todos los {contador_pdfs} PDFs tienen su XML.")
    else:
        print(f"❌ Se encontraron {len(faltantes)} archivos sin XML correspondiente.")
        # Opcional: imprimir lista completa si es larga
        # for f in faltantes:
        #     print(f" - {os.path.basename(f)}")
    
    print("="*60 + "\n")

if __name__ == '__main__':
    print("="*60)
    print("  COMPROBADOR DE XMLs PARA FACOSTE/FACTURA")
    print("="*60 + "\n")
    
    raiz = input("Ruta a la carpeta raíz para analizar:\n> ").strip().strip('"')
    
    if not os.path.isdir(raiz):
        print("❌ Ruta no válida.")
    else:
        comprobar_xml(raiz)
    
    input("\nProceso finalizado. Presiona Enter para salir.")
