import os
import pypdf

def unir_pdf_unico_a_epicras(carpeta_raiz, ruta_pdf_a_unir):
    """
    Recorre las subcarpetas de carpeta_raiz, busca la Epicrisis y le pega
    al principio el contenido de ruta_pdf_a_unir.
    """
    print(f"--- INICIANDO PROCESO DE UNIÓN DE PDF ÚNICO ---\n")
    print(f"PDF a insertar: {os.path.basename(ruta_pdf_a_unir)}")
    
    if not os.path.exists(ruta_pdf_a_unir):
        print(f"❌ Error: El PDF a unir no existe: {ruta_pdf_a_unir}")
        return

    # Leer el PDF una sola vez para verificar validez, 
    # pero tendremos que re-leerlo o copiar páginas en cada iteración.
    try:
        lector_unico = pypdf.PdfReader(ruta_pdf_a_unir)
        num_paginas_insertar = len(lector_unico.pages)
        print(f"-> Páginas a insertar: {num_paginas_insertar}\n")
    except Exception as e:
        print(f"❌ Error al leer el PDF a unir: {e}")
        return

    contador_exitos = 0
    contador_errores = 0
    
    # Iterar subcarpetas
    try:
        subcarpetas = [os.path.join(carpeta_raiz, d) for d in os.listdir(carpeta_raiz) 
                      if os.path.isdir(os.path.join(carpeta_raiz, d))]
    except FileNotFoundError:
        print(f"❌ Error: Carpeta raíz no existe: {carpeta_raiz}\n")
        return

    for ruta_subcarpeta in subcarpetas:
        nombre_subcarpeta = os.path.basename(ruta_subcarpeta)
        print(f"Analizando: '{nombre_subcarpeta}'...")

        # Buscar epicrisis
        ruta_epicrisis = None
        for nombre_archivo in os.listdir(ruta_subcarpeta):
            if nombre_archivo.lower().endswith('.pdf') and 'EPICRIS' in nombre_archivo.upper():
                ruta_epicrisis = os.path.join(ruta_subcarpeta, nombre_archivo)
                break
        
        if not ruta_epicrisis:
            print(f"  -> 🟡 No se encontró Epicrisis. Saltando.")
            continue

        try:
            print(f"  -> 🔄 Uniendo a {os.path.basename(ruta_epicrisis)}...")
            escritor = pypdf.PdfWriter()

            # 1. Agregar las páginas del PDF único (re-leemos para evitar conflictos de handles cerrados)
            lector_insertar = pypdf.PdfReader(ruta_pdf_a_unir)
            for pagina in lector_insertar.pages:
                escritor.add_page(pagina)

            # 2. Agregar las páginas de la Epicrisis original
            lector_epicrisis = pypdf.PdfReader(ruta_epicrisis)
            for pagina in lector_epicrisis.pages:
                escritor.add_page(pagina)

            # 3. Sobrescribir
            base, ext = os.path.splitext(ruta_epicrisis)
            ruta_salida = base + ".pdf"
            
            with open(ruta_salida, 'wb') as f_salida:
                escritor.write(f_salida)
            
            if ruta_salida != ruta_epicrisis and os.path.exists(ruta_epicrisis):
                try:
                    os.remove(ruta_epicrisis)
                except Exception:
                    pass
            
            print(f"  -> ✅ ÉXITO.")
            contador_exitos += 1

        except Exception as e:
            print(f"  -> ❌ ERROR al unir: {e}")
            contador_errores += 1

    print("\n" + "="*60)
    print("      REPORTE FINAL")
    print("="*60)
    print(f"✅ Archivos modificados: {contador_exitos}")
    print(f"❌ Errores: {contador_errores}")
    print("="*60 + "\n")

if __name__ == '__main__':
    print("="*60)
    print("  UNIR PDF ÚNICO A TODAS LAS EPICRISIS")
    print("  (Pega un archivo al principio de cada Epicrisis encontrada)")
    print("="*60 + "\n")
    
    raiz = input("Ruta a la carpeta con subcarpetas de EPICRISIS:\n> ").strip().strip('"')
    pdf_unico = input("Ruta del archivo PDF ÚNICO a pegar:\n> ").strip().strip('"')
    
    if not os.path.isdir(raiz):
        print("❌ Ruta raíz no válida.")
    elif not os.path.isfile(pdf_unico) or not pdf_unico.lower().endswith('.pdf'):
        print("❌ Ruta del PDF a unir no válida.")
    else:
        unir_pdf_unico_a_epicras(raiz, pdf_unico)
    
    input("\nProceso finalizado. Presiona Enter para salir.")
