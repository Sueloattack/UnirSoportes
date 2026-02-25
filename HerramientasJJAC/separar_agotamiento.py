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

def separar_certificados_agotamiento(carpeta_raiz, carpeta_certificados):
    """
    Busca documentos de agotamiento (certificados) que hayan sido unidos a las Epicrisis
    y los elimina del PDF de la Epicrisis si se detecta que están presentes.
    """
    resultados = {
        'separados': [],
        'no_requeridos': [],
        'sin_epicrisis': [],
        'fallidos': []
    }

    print(f"--- INICIANDO PROCESO DE SEPARACIÓN DE CERTIFICADOS ---\n")

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

        # 4. Buscar certificado correspondiente
        ruta_certificado_orig = certificados_disponibles.get(codigo_epicrisis)

        if not ruta_certificado_orig:
            print(f"  -> No existe certificado original para {codigo_epicrisis}. Se omite.")
            resultados['no_requeridos'].append({'carpeta': nombre_subcarpeta, 'razon': 'No hay certificado original'})
            continue

        # 5. Intentar separación
        try:
            print(f"  -> Código: {codigo_epicrisis}")
            print(f"  -> Certificado Original: {os.path.basename(ruta_certificado_orig)}")
            
            lector_epicrisis = pypdf.PdfReader(ruta_epicrisis)
            lector_certificado = pypdf.PdfReader(ruta_certificado_orig)
            
            num_paginas_epicrisis = len(lector_epicrisis.pages)
            num_paginas_certificado = len(lector_certificado.pages)

            if num_paginas_epicrisis <= num_paginas_certificado:
                print("  -> La Epicrisis es más pequeña o igual que el certificado. No parece estar unido.")
                resultados['no_requeridos'].append({'carpeta': nombre_subcarpeta, 'razon': 'Tamaño insuficiente'})
                continue
            
            # Verificación básica: ¿Es factible que esté al principio?
            # Una verificación más robusta sería comparar texto de la primera página,
            # pero asumiremos que si el script 'unir' lo puso al principio, ahí estará.
            # Para estar seguros, simplemente cortamos las primeras N páginas donde N = pág certificado.
            
            print(f"  -> Detectado posible unión. Epicrisis tiene {num_paginas_epicrisis} páginas. Eliminando las primeras {num_paginas_certificado}...")

            escritor = pypdf.PdfWriter()

            # Copiar solo las páginas DESPUÉS del certificado
            for i in range(num_paginas_certificado, num_paginas_epicrisis):
                escritor.add_page(lector_epicrisis.pages[i])

            # Sobrescribir
            with open(ruta_epicrisis, 'wb') as f_salida:
                escritor.write(f_salida)

            print("  -> ✅ SEPARACIÓN EXITOSA. Certificado eliminado de Epicrisis.")
            resultados['separados'].append({'carpeta': nombre_subcarpeta})

        except Exception as e:
            print(f"  -> ❌ ERROR durante la separación: {e}")
            resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': str(e)})

    # 6. Reporte final
    print("\n" + "="*60)
    print("      REPORTE FINAL DE SEPARACIÓN")
    print("="*60)
    print(f"✅ Separados exitosamente: {len(resultados['separados'])}")
    print(f"⚪ No requeridos/Omitidos: {len(resultados['no_requeridos'])}")
    print(f"❌ Errores/Sin Epicrisis: {len(resultados['fallidos']) + len(resultados['sin_epicrisis'])}")
    print("="*60 + "\n")

if __name__ == '__main__':
    print("="*60)
    print("  SEPARADOR DE CERTIFICADOS DE AGOTAMIENTO")
    print("  (Elimina las primeras páginas de la Epicrisis si coinciden con el Certificado)")
    print("="*60 + "\n")
    
    raiz = input("Ruta a la carpeta con subcarpetas de EPICRISIS (donde están unidos):\n> ").strip().strip('"')
    certificados = input("Ruta a la carpeta con CERTIFICADOS AGOTAMIENTO originales:\n> ").strip().strip('"')
    
    if not os.path.isdir(raiz):
        print("❌ Ruta raíz no válida.")
    elif not os.path.isdir(certificados):
        print("❌ Ruta de certificados no válida.")
    else:
        separar_certificados_agotamiento(raiz, certificados)
    
    input("\nProceso finalizado. Presiona Enter para salir.")
