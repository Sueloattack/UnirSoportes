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

def extraer_codigo_nota_credito(nombre_archivo):
    """
    Extrae el código de la nota de crédito.
    Formato: 311-NCEG-60774 Nota Credito FECR177799.pdf
    Retorna: FECR177799
    """
    match = re.search(r'FECR\d+', nombre_archivo)
    if match:
        return match.group()
    return None

def extraer_codigo_oficio(nombre_archivo):
    """
    Extrae el código del oficio.
    Formato: FECR218764.pdf
    Retorna: FECR218764
    """
    nombre_sin_ext = os.path.splitext(nombre_archivo)[0]
    if re.match(r'FECR\d+$', nombre_sin_ext):
        return nombre_sin_ext
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

def unir_documentos_agotamiento(carpeta_raiz, carpeta_certificados, carpeta_notas, carpeta_oficios):
    """
    Une documentos de agotamiento a las Epicrisis en el siguiente orden:
    1. Certificado Agotamiento
    2. Nota Crédito
    3. Oficio Explicatorio
    4. Epicrisis (contenido original)
    """
    resultados = {
        'unidos_completos': [],
        'unidos_parciales': [],
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

    # 2. Indexar notas de crédito
    print(f"Indexando notas de crédito en: {carpeta_notas}")
    notas_disponibles = {}
    try:
        for f in os.listdir(carpeta_notas):
            if f.lower().endswith('.pdf'):
                codigo = extraer_codigo_nota_credito(f)
                if codigo:
                    notas_disponibles[codigo] = os.path.join(carpeta_notas, f)
        print(f"-> Se encontraron {len(notas_disponibles)} notas de crédito.\n")
    except FileNotFoundError:
        print(f"❌ Error: Carpeta de notas no existe: {carpeta_notas}\n")
        return

    # 3. Indexar oficios
    print(f"Indexando oficios en: {carpeta_oficios}")
    oficios_disponibles = {}
    try:
        for f in os.listdir(carpeta_oficios):
            if f.lower().endswith('.pdf'):
                codigo = extraer_codigo_oficio(f)
                if codigo:
                    oficios_disponibles[codigo] = os.path.join(carpeta_oficios, f)
        print(f"-> Se encontraron {len(oficios_disponibles)} oficios.\n")
    except FileNotFoundError:
        print(f"❌ Error: Carpeta de oficios no existe: {carpeta_oficios}\n")
        return

    # 4. Iterar sobre subcarpetas en carpeta raíz
    try:
        subcarpetas = [os.path.join(carpeta_raiz, d) for d in os.listdir(carpeta_raiz) 
                      if os.path.isdir(os.path.join(carpeta_raiz, d))]
    except FileNotFoundError:
        print(f"❌ Error: Carpeta raíz no existe: {carpeta_raiz}\n")
        return

    for ruta_subcarpeta in subcarpetas:
        nombre_subcarpeta = os.path.basename(ruta_subcarpeta)
        print(f"\nAnalizando carpeta: '{nombre_subcarpeta}'...")

        # 5. Buscar epicrisis
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

        # 6. Buscar documentos correspondientes
        cert = certificados_disponibles.get(codigo_epicrisis)
        nota = notas_disponibles.get(codigo_epicrisis)
        oficio = oficios_disponibles.get(codigo_epicrisis)

        documentos_encontrados = []
        documentos_faltantes = []

        if cert:
            documentos_encontrados.append(f"Certificado: {os.path.basename(cert)}")
        else:
            documentos_faltantes.append("Certificado")

        if nota:
            documentos_encontrados.append(f"Nota: {os.path.basename(nota)}")
        else:
            documentos_faltantes.append("Nota Crédito")

        if oficio:
            documentos_encontrados.append(f"Oficio: {os.path.basename(oficio)}")
        else:
            documentos_faltantes.append("Oficio")

        print(f"  -> Código: {codigo_epicrisis}")
        for doc in documentos_encontrados:
            print(f"     ✅ {doc}")
        for doc in documentos_faltantes:
            print(f"     🟡 Falta: {doc}")

        # 7. Realizar la fusión
        try:
            print("  -> 🔄 Uniendo documentos...")
            escritor = pypdf.PdfWriter()

            # Orden: Certificado -> Nota -> Oficio -> Epicrisis
            if cert:
                lector = pypdf.PdfReader(cert)
                for pagina in lector.pages:
                    escritor.add_page(pagina)

            if nota:
                lector = pypdf.PdfReader(nota)
                for pagina in lector.pages:
                    escritor.add_page(pagina)

            if oficio:
                lector = pypdf.PdfReader(oficio)
                for pagina in lector.pages:
                    escritor.add_page(pagina)

            # Epicrisis al final
            lector_epicrisis = pypdf.PdfReader(ruta_epicrisis)
            for pagina in lector_epicrisis.pages:
                escritor.add_page(pagina)

            # Sobrescribir epicrisis
            with open(ruta_epicrisis, 'wb') as f_salida:
                escritor.write(f_salida)

            if not documentos_faltantes:
                print("  -> ✅ ÉXITO COMPLETO: Todos los documentos unidos.")
                resultados['unidos_completos'].append({
                    'carpeta': nombre_subcarpeta,
                    'documentos': len(documentos_encontrados) + 1
                })
            else:
                print(f"  -> ✅ ÉXITO PARCIAL: Unidos {len(documentos_encontrados)} de 3 documentos.")
                resultados['unidos_parciales'].append({
                    'carpeta': nombre_subcarpeta,
                    'faltantes': documentos_faltantes
                })

        except Exception as e:
            print(f"  -> ❌ ERROR durante la fusión: {e}")
            resultados['fallidos'].append({'carpeta': nombre_subcarpeta, 'razon': str(e)})

    # 8. Reporte final
    print("\n" + "="*60)
    print("      REPORTE FINAL DE UNIÓN DE DOCUMENTOS")
    print("="*60)
    print(f"✅ Uniones completas (4 docs): {len(resultados['unidos_completos'])}")
    print(f"🟡 Uniones parciales: {len(resultados['unidos_parciales'])}")
    print(f"❌ Errores: {len(resultados['fallidos']) + len(resultados['sin_epicrisis'])}")
    print("="*60 + "\n")

    if resultados['unidos_completos']:
        print("--- DETALLE DE ÉXITOS COMPLETOS ---")
        for exito in resultados['unidos_completos']:
            print(f"  - '{exito['carpeta']}' -> OK (4 documentos)")
        print()

    if resultados['unidos_parciales']:
        print("--- DETALLE DE ÉXITOS PARCIALES ---")
        for parcial in resultados['unidos_parciales']:
            faltantes_str = ", ".join(parcial['faltantes'])
            print(f"  - '{parcial['carpeta']}' -> Falta: {faltantes_str}")
        print()

if __name__ == '__main__':
    print("="*60)
    print("  UNIR DOCUMENTOS DE AGOTAMIENTO A EPICRISIS")
    print("="*60 + "\n")
    
    raiz = input("Ruta a la carpeta con subcarpetas de EPICRISIS:\n> ").strip().strip('"')
    certificados = input("Ruta a la carpeta con CERTIFICADOS AGOTAMIENTO:\n> ").strip().strip('"')
    notas = input("Ruta a la carpeta con NOTAS DE CRÉDITO:\n> ").strip().strip('"')
    oficios = input("Ruta a la carpeta con OFICIOS EXPLICATORIOS:\n> ").strip().strip('"')
    
    if not os.path.isdir(raiz):
        print("❌ Ruta raíz no válida.")
    elif not os.path.isdir(certificados):
        print("❌ Ruta de certificados no válida.")
    elif not os.path.isdir(notas):
        print("❌ Ruta de notas no válida.")
    elif not os.path.isdir(oficios):
        print("❌ Ruta de oficios no válida.")
    else:
        unir_documentos_agotamiento(raiz, certificados, notas, oficios)
    
    input("\nProceso finalizado. Presiona Enter para salir.")
