import os
import re
import pypdf

def extraer_codigo_certificado(nombre_archivo):
    """
    Extrae el código del certificado.
    Formato: 730010082601_FECR218764_SOAT.pdf
    Retorna: FECR218764
    """
    partes = nombre_archivo.split('_')
    if len(partes) >= 2:
        return partes[1]
    return None

def extraer_codigo_epicrisis(nombre_archivo):
    """
    Extrae el código de la epicrisis.
    Formato: NUMERO_FECR218764_EPICRIS.pdf
    Retorna: FECR218764
    """
    partes = nombre_archivo.split('_')
    if len(partes) >= 2:
        return partes[1]
    return None

def unir_documentos_agotamiento(carpeta_raiz, carpeta_certificados):
    """
    Une documentos de agotamiento a las Epicrisis en el siguiente orden:
    1. Certificado Agotamiento
    2. Epicrisis (contenido original)
    """
    resultados = {
        'unidos_completos': [],
        'sin_certificado': [],
        'sin_epicrisis': [],
        'fallidos': []
    }

    print(f"--- INICIANDO PROCESO DE UNIÓN DE DOCUMENTOS AGOTAMIENTO ---\n")

    # 1. Indexar certificados
    print(f"Indexando certificados en: {carpeta_certificados}")
    certificados_disponibles = {}
    try:
        for f in os.listdir(carpeta_certificados):
            if f.lower().endswith('.pdf'):
                codigo = extraer_codigo_certificado(f)
                if codigo:
                    certificados_disponibles[codigo] = os.path.join(carpeta_certificados, f)
        print(f"-> Se encontraron {len(certificados_disponibles)} certificados.\n")
    except FileNotFoundError:
        print(f"❌ Error: Carpeta de certificados no existe: {carpeta_certificados}\n")
        return

    # 2. Iterar sobre subcarpetas en carpeta raíz
    try:
        subcarpetas = [os.path.join(carpeta_raiz, d) for d in os.listdir(carpeta_raiz) 
                      if os.path.isdir(os.path.join(carpeta_raiz, d))]
    except FileNotFoundError:
        print(f"❌ Error: Carpeta raíz no existe: {carpeta_raiz}\n")
        return

    for ruta_subcarpeta in subcarpetas:
        nombre_subcarpeta = os.path.basename(ruta_subcarpeta)
        print(f"\nAnalizando carpeta: '{nombre_subcarpeta}'...")

        # 3. Buscar epicrisis
        ruta_epicrisis = None
        codigo_epicrisis = None

        for nombre_archivo in os.listdir(ruta_subcarpeta):
            if nombre_archivo.lower().endswith('.pdf') and 'EPICRIS' in nombre_archivo.upper():
                ruta_epicrisis = os.path.join(ruta_subcarpeta, nombre_archivo)
                codigo_epicrisis = extraer_codigo_epicrisis(nombre_archivo)
                break

        if not ruta_epicrisis:
            print("  -> ❌ ERROR: No se encontró Epicrisis.")
            resultados['sin_epicrisis'].append({'carpeta': nombre_subcarpeta})
            continue

        if not codigo_epicrisis:
            print(f"  -> ⚠️ ADVERTENCIA: No se pudo extraer código de Epicrisis.")
            resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': 'Código no extraíble'})
            continue

        # 4. Buscar documentos correspondientes
        cert = certificados_disponibles.get(codigo_epicrisis)

        if not cert:
            print(f"  -> 🟡 Falta: Certificado")
            resultados['sin_certificado'].append({'carpeta': nombre_subcarpeta})
            continue

        print(f"  -> Código: {codigo_epicrisis}")
        print(f"     ✅ Certificado: {os.path.basename(cert)}")

        # 5. Realizar la fusión
        try:
            print("  -> 🔄 Uniendo documentos...")
            escritor = pypdf.PdfWriter()

            # Orden: Certificado -> Epicrisis
            lector = pypdf.PdfReader(cert)
            for pagina in lector.pages:
                escritor.add_page(pagina)

            # Epicrisis al final
            lector_epicrisis = pypdf.PdfReader(ruta_epicrisis)
            for pagina in lector_epicrisis.pages:
                escritor.add_page(pagina)

            # Sobrescribir epicrisis con extensión .pdf minúscula
            base, ext = os.path.splitext(ruta_epicrisis)
            ruta_salida = base + ".pdf"
            
            with open(ruta_salida, 'wb') as f_salida:
                escritor.write(f_salida)
            
            if ruta_salida != ruta_epicrisis and os.path.exists(ruta_epicrisis):
                try:
                    os.remove(ruta_epicrisis)
                except Exception:
                    pass

            print("  -> ✅ ÉXITO: Certificado unido.")
            resultados['unidos_completos'].append({
                'carpeta': nombre_subcarpeta
            })

        except Exception as e:
            print(f"  -> ❌ ERROR durante la fusión: {e}")
            resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': str(e)})

    # 6. Reporte final
    print("\n" + "="*60)
    print("      REPORTE FINAL DE UNIÓN DE DOCUMENTOS")
    print("="*60)
    print(f"✅ Uniones exitosas: {len(resultados['unidos_completos'])}")
    print(f"🟡 Sin Certificado: {len(resultados['sin_certificado'])}")
    print(f"❌ Errores/Sin Epicrisis: {len(resultados['fallidos']) + len(resultados['sin_epicrisis'])}")
    print("="*60 + "\n")

if __name__ == '__main__':
    print("="*60)
    print("  UNIR DOCUMENTOS DE AGOTAMIENTO A EPICRISIS")
    print("  (Solo Certificados)")
    print("="*60 + "\n")
    
    raiz = input("Ruta a la carpeta con subcarpetas de EPICRISIS:\n> ").strip().strip('"')
    certificados = input("Ruta a la carpeta con CERTIFICADOS AGOTAMIENTO:\n> ").strip().strip('"')
    
    if not os.path.isdir(raiz):
        print("❌ Ruta raíz no válida.")
    elif not os.path.isdir(certificados):
        print("❌ Ruta de certificados no válida.")
    else:
        unir_documentos_agotamiento(raiz, certificados)
    
    input("\nProceso finalizado. Presiona Enter para salir.")
