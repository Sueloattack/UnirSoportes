import os
import pypdf
import re

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

def limpiar_texto(texto):
    """
    Limpia el texto para facilitar la comparación side-by-side.
    """
    if not texto:
        return ""
    return re.sub(r'\s+', '', texto).lower()

def verificar_union_agotamiento(carpeta_raiz, carpeta_certificados, archivo_inicial_prepend):
    """
    Verifica si los certificados ya han sido unidos a las epicrisis.
    ASUME: [Archivo Inicial] + [Certificado] + [Epicrisis Original]
    Por lo tanto, salta N páginas (tamaño archivo inicial) y compara la siguiente.
    """
    print(f"--- INICIANDO VERIFICACIÓN DE UNIÓN DE AGOTAMIENTO ---\n")

    # 0. Calcular Offset del archivo inicial
    offset_paginas = 0
    if archivo_inicial_prepend:
        if os.path.isfile(archivo_inicial_prepend):
            try:
                lector_ini = pypdf.PdfReader(archivo_inicial_prepend)
                offset_paginas = len(lector_ini.pages)
                print(f"📁 Archivo Inicial: {os.path.basename(archivo_inicial_prepend)}")
                print(f"   -> Desplazamiento (Offset): {offset_paginas} páginas.\n")
            except Exception as e:
                print(f"❌ Error al leer archivo inicial: {e}")
                return
        else:
             print(f"❌ El archivo inicial no existe: {archivo_inicial_prepend}")
             return
    else:
        print("ℹ️ No se definió archivo inicial. Se verificará desde la página 0.\n")

    resultados = {
        'ya_unidos': [],
        'pendientes': [],
        'sin_certificado': [],
        'sin_epicrisis': [],
        'errores': []
    }

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

        # 3. Buscar epicrisis
        ruta_epicrisis = None
        codigo_epicrisis = None

        for nombre_archivo in os.listdir(ruta_subcarpeta):
            if nombre_archivo.lower().endswith('.pdf') and 'EPICRIS' in nombre_archivo.upper():
                ruta_epicrisis = os.path.join(ruta_subcarpeta, nombre_archivo)
                codigo_epicrisis = extraer_codigo_epicrisis(nombre_archivo)
                break

        if not ruta_epicrisis:
            resultados['sin_epicrisis'].append(nombre_subcarpeta)
            continue

        if not codigo_epicrisis:
            pass

        # 4. Buscar certificado correspondiente
        ruta_certificado = None
        if codigo_epicrisis:
            ruta_certificado = certificados_disponibles.get(codigo_epicrisis)
        
        if not ruta_certificado:
            resultados['sin_certificado'].append({'carpeta': nombre_subcarpeta, 'codigo': codigo_epicrisis})
            continue

        # 5. Comparar
        try:
            lector_ep = pypdf.PdfReader(ruta_epicrisis)
            lector_cert = pypdf.PdfReader(ruta_certificado)

            if len(lector_ep.pages) <= offset_paginas:
                # El archivo es más corto que el offset, imposible que tenga el cert después
                resultados['errores'].append({'carpeta': nombre_subcarpeta, 'razon': 'PDF muy corto (menor al offset)'})
                resultados['pendientes'].append({'carpeta': nombre_subcarpeta, 'codigo': codigo_epicrisis}) # Asumimos pendiente
                continue
            
            if len(lector_cert.pages) == 0:
                resultados['errores'].append({'carpeta': nombre_subcarpeta, 'razon': 'Certificado vacío'})
                continue

            # Extraemos la página del epicrisis que DEBERÍA ser el inicio del certificado
            pagina_objetivo = lector_ep.pages[offset_paginas]
            texto_ep_target = limpiar_texto(pagina_objetivo.extract_text())
            texto_cert_p1 = limpiar_texto(lector_cert.pages[0].extract_text())
            
            es_unido = False
            
            # Verificación por texto
            if len(texto_cert_p1) > 50 and (texto_cert_p1[:100] in texto_ep_target):
                 es_unido = True
            elif len(texto_cert_p1) > 0 and texto_cert_p1 == texto_ep_target:
                 es_unido = True
            
            if es_unido:
                resultados['ya_unidos'].append({'carpeta': nombre_subcarpeta, 'codigo': codigo_epicrisis})
            else:
                resultados['pendientes'].append({'carpeta': nombre_subcarpeta, 'codigo': codigo_epicrisis})

        except Exception as e:
            resultados['errores'].append({'carpeta': nombre_subcarpeta, 'razon': str(e)})

    # 6. Reporte final
    print("\n" + "="*60)
    print("      REPORTE DE VERIFICACIÓN")
    print("="*60)
    print(f"📁 Offset aplicado: {offset_paginas} páginas (Archivo Inicial)")
    print(f"✅ YA UNIDOS: {len(resultados['ya_unidos'])}")
    print(f"🕑 PENDIENTES POR UNIR: {len(resultados['pendientes'])}")
    print(f"⚪ SIN CERTIFICADO: {len(resultados['sin_certificado'])}")
    print(f"❌ SIN EPICRISIS: {len(resultados['sin_epicrisis'])}")
    print(f"⚠️ ERRORES/CORTOS: {len(resultados['errores'])}")
    print("="*60 + "\n")

    if resultados['pendientes']:
        print("--- LISTADO DE PENDIENTES ---")
        for item in resultados['pendientes']:
            print(f" [ ] {item['carpeta']} ({item['codigo']})")
        print("\n")
    
    if resultados['sin_certificado']:
         print("--- LISTADO SIN CERTIFICADO ---")
         for item in resultados['sin_certificado']:
            print(f" [?] {item['carpeta']} ({item['codigo']})")
         print("\n")

if __name__ == '__main__':
    print("="*60)
    print("  VERIFICADOR DE UNIÓN DE AGOTAMIENTO")
    print("  (Verifica si [Archivo Inicial] + [Certificado] ya existen en Epicrisis)")
    print("="*60 + "\n")
    
    raiz = input("Ruta a la carpeta con subcarpetas de EPICRISIS:\n> ").strip().strip('"')
    certificados = input("Ruta a la carpeta con CERTIFICADOS AGOTAMIENTO:\n> ").strip().strip('"')
    archivo_ini = input("Ruta del ARCHIVO INICIAL (que va primero): (Deja vacío si no hay)\n> ").strip().strip('"')

    if not os.path.isdir(raiz):
        print("❌ Ruta raíz no válida.")
    elif not os.path.isdir(certificados):
        print("❌ Ruta de certificados no válida.")
    else:
        verificar_union_agotamiento(raiz, certificados, archivo_ini)
    
    input("\nProceso finalizado. Presiona Enter para salir.")
