import os
import pypdf

def extraer_codigo(nombre_archivo):
    """
    Extrae el código del nombre del archivo.
    Se asume el formato: 730010082601_FECR178877_SOAT.pdf
    El código sería el segundo elemento separado por '_': FECR178877
    """
    partes = nombre_archivo.split('_')
    if len(partes) >= 2:
        return partes[1]
    return None

def unir_certificados_a_epicrisis(carpeta_raiz, carpeta_certificados):
    """
    Une certificados (SOAT) a las Epicrisis correspondientes basándose en un código común.
    El certificado se coloca ANTES de la epicrisis.
    """
    resultados = {
        'unidos': [],
        'sin_certificado': [],
        'sin_epicrisis': [],
        'fallidos': []
    }

    print(f"--- INICIANDO PROCESO DE UNIÓN DE CERTIFICADOS A EPICRISIS ---")

    # 1. Indexar todos los certificados disponibles por su código.
    print(f"Indexando certificados en: {carpeta_certificados}")
    certificados_disponibles = {}
    
    try:
        archivos_cert = os.listdir(carpeta_certificados)
    except FileNotFoundError:
        print(f"❌ Error: La carpeta de certificados no existe: {carpeta_certificados}")
        return

    for f in archivos_cert:
        if f.lower().endswith('.pdf'):
            codigo = extraer_codigo(f)
            if codigo:
                certificados_disponibles[codigo] = os.path.join(carpeta_certificados, f)
    
    print(f"-> Se encontraron {len(certificados_disponibles)} certificados válidos para procesar.\n")

    # 2. Iterar sobre cada subcarpeta en la carpeta raíz de destino.
    try:
        subcarpetas = [os.path.join(carpeta_raiz, d) for d in os.listdir(carpeta_raiz) if os.path.isdir(os.path.join(carpeta_raiz, d))]
    except FileNotFoundError:
        print(f"❌ Error: La carpeta raíz no existe: {carpeta_raiz}")
        return

    for ruta_subcarpeta in subcarpetas:
        nombre_subcarpeta = os.path.basename(ruta_subcarpeta)
        print(f"\nAnalizando carpeta: '{nombre_subcarpeta}'...")
        
        # 3. Encontrar el archivo de epicrisis de destino en la subcarpeta.
        nombre_epicrisis_destino = None
        ruta_epicrisis_destino = None
        codigo_epicrisis = None

        for nombre_archivo in os.listdir(ruta_subcarpeta):
            if nombre_archivo.lower().endswith('.pdf') and 'EPICRIS' in nombre_archivo.upper():
                nombre_epicrisis_destino = nombre_archivo
                ruta_epicrisis_destino = os.path.join(ruta_subcarpeta, nombre_archivo)
                codigo_epicrisis = extraer_codigo(nombre_archivo)
                break

        if not nombre_epicrisis_destino:
            print("  -> ❌ ERROR: No se encontró un archivo Epicrisis en esta carpeta.")
            resultados['sin_epicrisis'].append({'carpeta': nombre_subcarpeta})
            continue

        if not codigo_epicrisis:
             print(f"  -> ⚠️ ADVERTENCIA: No se pudo extraer código del archivo '{nombre_epicrisis_destino}'.")
             resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': 'No se pudo extraer código de Epicrisis'})
             continue

        # 4. Verificar si el certificado correspondiente existe en nuestro índice.
        if codigo_epicrisis in certificados_disponibles:
            ruta_certificado_origen = certificados_disponibles[codigo_epicrisis]
            
            print(f"  -> Se encontró coincidencia: Código '{codigo_epicrisis}'")
            print(f"     Epicrisis: {nombre_epicrisis_destino}")
            print(f"     Certificado: {os.path.basename(ruta_certificado_origen)}")

            # 5. Realizar la fusión.
            try:
                print("  -> 🔄 Uniendo archivos...")
                
                escritor = pypdf.PdfWriter()

                # Añadir el CERTIFICADO primero
                lector_certificado = pypdf.PdfReader(ruta_certificado_origen)
                for pagina in lector_certificado.pages:
                    escritor.add_page(pagina)
                
                # Añadir la EPICRISIS después
                lector_epicrisis = pypdf.PdfReader(ruta_epicrisis_destino)
                for pagina in lector_epicrisis.pages:
                    escritor.add_page(pagina)

                # Sobrescribir el archivo epicrisis de destino con extensión .pdf minúscula
                base, ext = os.path.splitext(ruta_epicrisis_destino)
                ruta_salida = base + ".pdf"
                
                with open(ruta_salida, 'wb') as f_salida:
                    escritor.write(f_salida)

                if ruta_salida != ruta_epicrisis_destino and os.path.exists(ruta_epicrisis_destino):
                    try:
                        os.remove(ruta_epicrisis_destino)
                    except Exception:
                        pass

                print("  -> ✅ ÉXITO: Certificado anexado correctamente.")
                resultados['unidos'].append({'carpeta': nombre_subcarpeta, 'archivo': nombre_epicrisis_destino})
            
            except Exception as e:
                print(f"  -> ❌ ERROR durante la fusión de PDF: {e}")
                resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': f"Error al unir PDFs: {e}"})

        else:
            print(f"  -> 🟡 No se encontró certificado para el código '{codigo_epicrisis}'.")
            resultados['sin_certificado'].append({'carpeta': nombre_subcarpeta, 'codigo': codigo_epicrisis})
            
    # 6. Reporte final
    print("\n" + "="*60)
    print("      REPORTE FINAL DE UNIÓN DE CERTIFICADOS")
    print("="*60)
    print(f"✅ Uniones exitosas: {len(resultados['unidos'])}")
    print(f"🟡 Certificados no encontrados: {len(resultados['sin_certificado'])}")
    print(f"❌ Errores (sin epicrisis/fallos): {len(resultados['fallidos']) + len(resultados['sin_epicrisis'])}")
    print("="*60 + "\n")

    if resultados['unidos']:
        print("--- DETALLE DE ÉXITOS ---")
        for exito in resultados['unidos']:
            print(f"  - Carpeta: '{exito['carpeta']}' -> OK")
        print("\n")

    if resultados['sin_certificado']:
        print("--- DETALLE DE FALTANTES ---")
        for item in resultados['sin_certificado']:
            print(f"  - Carpeta: '{item['carpeta']}' | Falta cert para código: {item['codigo']}")
        print("\n")

if __name__ == '__main__':
    raiz = input("Ruta a la carpeta con subcarpetas de EPICRISIS:\n> ").strip().strip('"')
    certificados = input("Ruta a la carpeta con los CERTIFICADOS sueltos:\n> ").strip().strip('"')
    
    if not os.path.isdir(raiz):
        print("❌ Ruta raíz no válida.")
    elif not os.path.isdir(certificados):
        print("❌ Ruta de certificados no válida.")
    else:
        unir_certificados_a_epicrisis(raiz, certificados)

    input("\nProceso finalizado. Presiona Enter para salir.")
