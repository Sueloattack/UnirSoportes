import os
import shutil
import zipfile
import re

def comprimir_en_lotes():
    print("\n--- COMPRESIÓN DE ARCHIVOS EN LOTES (ZIP < 500MB) ---")
    
    # 1. Carpeta de origen
    while True:
        dir_origen = input("\nIngrese la ruta de la carpeta con los PDFs a comprimir: ").strip()
        if os.path.isdir(dir_origen):
            break
        print(f"Error: La ruta '{dir_origen}' no es un directorio válido.")

    # 2. Carpeta de destino
    while True:
        dir_destino = input("Ingrese la ruta donde se guardarán los archivos .ZIP: ").strip()
        if not os.path.exists(dir_destino):
            try:
                os.makedirs(dir_destino)
                break
            except Exception as e:
                print(f"Error al crear el directorio: {e}")
        elif os.path.isdir(dir_destino):
            break
        else:
            print("La ruta de destino no es válida.")

    MAX_BATCH_SIZE_BYTES = 500 * 1024 * 1024  # 500MB
    
    print("\n[1/2] Analizando archivos y agrupando por factura...")
    
    # Agrupar archivos por código de factura
    # Formato esperado: TIPO_NIT_ID.pdf (ID es lo que nos interesa)
    grupos = {}
    for filename in os.listdir(dir_origen):
        if filename.lower().endswith('.pdf'):
            partes = filename.replace('.pdf', '').split('_')
            if len(partes) >= 3:
                factura_id = partes[-1] # El último elemento suele ser el ID
                if factura_id not in grupos:
                    grupos[factura_id] = []
                grupos[factura_id].append(os.path.join(dir_origen, filename))

    # Filtrar solo facturas completas (4 archivos)
    facturas_completas = []
    facturas_incompletas = []
    
    for factura_id, archivos in grupos.items():
        if len(archivos) == 4:
            # Calcular tamaño total de la factura
            size_total = sum(os.path.getsize(f) for f in archivos)
            facturas_completas.append({'id': factura_id, 'archivos': archivos, 'size': size_total})
        else:
            facturas_incompletas.append(factura_id)

    if not facturas_completas:
        print("No se encontraron facturas completas (con 4 archivos cada una).")
        if facturas_incompletas:
            print(f"Facturas incompletas detectadas: {len(facturas_incompletas)}")
        return

    print(f"Total de facturas completas encontradas: {len(facturas_completas)}")
    if facturas_incompletas:
        print(f"Aviso: Se omitirán {len(facturas_incompletas)} facturas por estar incompletas.")

    print("\n[2/2] Creando lotes ZIP...")
    
    lote_actual = []
    size_lote_actual = 0
    numero_lote = 1
    total_zips = 0

    def crear_zip(lote, num):
        nombre_zip = f"SUBIDA {num}.zip"
        ruta_zip = os.path.join(dir_destino, nombre_zip)
        print(f"  > Generando {nombre_zip} (Invoices: {len(lote)})")
        with zipfile.ZipFile(ruta_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for f_data in lote:
                for archivo_path in f_data['archivos']:
                    zipf.write(archivo_path, os.path.basename(archivo_path))
        return 1

    for f_data in facturas_completas:
        # Si agregar esta factura supera los 500MB, cerramos el lote anterior
        if size_lote_actual + f_data['size'] > MAX_BATCH_SIZE_BYTES and lote_actual:
            total_zips += crear_zip(lote_actual, numero_lote)
            numero_lote += 1
            lote_actual = []
            size_lote_actual = 0
        
        lote_actual.append(f_data)
        size_lote_actual += f_data['size']

    # Procesar el último lote si quedó algo
    if lote_actual:
        total_zips += crear_zip(lote_actual, numero_lote)

    print("\n" + "="*40)
    print(f"PROCESO DE COMPRESIÓN FINALIZADO")
    print(f"Total de archivos .ZIP creados: {total_zips}")
    print(f"Total de facturas comprimidas: {len(facturas_completas)}")
    print("="*40)

def validar_soportes_existentes():
    print("\n--- VALIDADORA DE SOPORTES ---")
    
    # 1. Carpeta a validar
    while True:
        dir_val = input("\nIngrese la ruta de la carpeta que desea validar: ").strip()
        if os.path.isdir(dir_val):
            break
        print(f"Error: La ruta '{dir_val}' no es un directorio válido.")

    # 2. Listado de facturas
    print("\nIngrese el listado de facturas a validar (una por línea, deje en blanco para terminar):")
    facturas_check = []
    while True:
        entrada = input("> ").strip()
        if not entrada: break
        facturas_check.append(entrada)
    
    if not facturas_check:
        print("No se ingresaron facturas.")
        return

    # 3. Modalidad
    print("\n¿Qué modalidad desea validar?")
    print("1. Estándar (3 archivos: EPI, PDX, CRC)")
    print("2. Completa (4 archivos: EPI, PDX, CRC, FURIPS)")
    while True:
        modo_val = input("Seleccione (1 o 2): ").strip()
        if modo_val in ['1', '2']: break
        print("Opción no válida.")

    NIT = "800209891"
    tipos_requeridos = ['EPI', 'PDX', 'CRC']
    if modo_val == '2':
        tipos_requeridos.append('FURIPS')

    print(f"\n[1/1] Validando {len(facturas_check)} facturas...")
    
    completas = 0
    incompletas = 0
    reporte_validacion = []

    for factura in facturas_check:
        faltantes = []
        for tipo in tipos_requeridos:
            nombre_archivo = f"{tipo}_{NIT}_{factura}.pdf"
            ruta_archivo = os.path.join(dir_val, nombre_archivo)
            if not os.path.exists(ruta_archivo):
                faltantes.append(tipo)
        
        if not faltantes:
            print(f"  [OK] Factura {factura}: Completa")
            completas += 1
        else:
            msg_error = f"  [X] Factura {factura}: Faltan {', '.join(faltantes)}"
            print(msg_error)
            incompletas += 1
            reporte_validacion.append(msg_error)

    print("\n" + "="*40)
    print(f"RESULTADO DE VALIDACIÓN:")
    print(f"Total revisadas: {len(facturas_check)}")
    print(f"Completas: {completas}")
    print(f"Incompletas: {incompletas}")
    print("="*40)

def buscar_y_procesar_soportes_nu():
    print("=== BUSCADOR DE SOPORTES NU (SOPORTES + COMPRESIÓN + VALIDACIÓN) ===")
    
    # 0. Seleccionar modalidad
    print("\nSeleccione la operación a realizar:")
    print("1. Buscar y Organizar Soportes - Modalidad Estándar (3 archivos: HC, CRC)")
    print("2. Buscar y Organizar Soportes - Modalidad Completa (4 archivos: HC, CRC, FURIPS)")
    print("3. Comprimir Archivos en Lotes (ZIP < 500MB)")
    print("4. Buscar y Organizar Soportes - Solo HC y FURIPS (3 archivos: HC, FURIPS)")
    print("5. Validar Soportes Existentes en Carpeta")
    
    while True:
        choice = input("Seleccione una opción (1, 2, 3, 4 o 5): ").strip()
        if choice in ['1', '2', '3', '4', '5']:
            break
        print("Opción no válida.")

    if choice == '3':
        comprimir_en_lotes()
        return
    if choice == '5':
        validar_soportes_existentes()
        return

    # A partir de aquí, lógica de búsqueda (choice 1, 2 o 4)
    modo = choice # Reutilizamos modo para el resto del script
    
    # 1. Ingresar listado de facturas
    print("\nIngrese el listado de facturas (una por línea, deje en blanco y presione Enter para terminar):")
    facturas_input = []
    while True:
        entrada = input("> ").strip()
        if not entrada:
            break
        facturas_input.append(entrada)
    
    if not facturas_input:
        print("No se ingresaron facturas. Saliendo.")
        return

    # Limpiar duplicados y espacios, manteniendo el orden de ingreso
    facturas = []
    vistos = set()
    for f in facturas_input:
        f_clean = f.strip()
        if f_clean and f_clean not in vistos:
            facturas.append(f_clean)
            vistos.add(f_clean)

    # 2. Lugar de origen
    while True:
        dir_origen = input("\nIngrese la ruta de la carpeta de ORIGEN (donde buscará): ").strip()
        if os.path.isdir(dir_origen):
            break
        print(f"Error: La ruta '{dir_origen}' no es un directorio válido.")

    # 3. Lugar de destino
    while True:
        dir_destino = input("Ingrese la ruta de la carpeta de DESTINO: ").strip()
        if not os.path.exists(dir_destino):
            try:
                os.makedirs(dir_destino)
                break
            except Exception as e:
                print(f"Error al crear el directorio de destino: {e}")
        elif os.path.isdir(dir_destino):
            break
        else:
            print("La ruta de destino no es válida.")

    # NIT fijo según requerimiento
    NIT = "800209891"
    UMBRAL_TAMANO_BYTES = 20 * 1024 * 1024  # 20MB
    
    print("\n[1/2] Indexando archivos... (esto puede tardar si hay miles de carpetas)")
    
    # Indexar archivos por nombre (sin extensión) para búsqueda instantánea
    indice = {}
    total_indexados = 0
    
    try:
        for root, dirs, files in os.walk(dir_origen):
            for filename in files:
                nombre_sin_ext = os.path.splitext(filename)[0].upper()
                if nombre_sin_ext not in indice:
                    indice[nombre_sin_ext] = []
                indice[nombre_sin_ext].append(os.path.join(root, filename))
                total_indexados += 1
    except Exception as e:
        print(f"Error crítico indexando archivos: {e}")
        return

    print(f"Indexación completada. {total_indexados} archivos encontrados en total.")
    print("\n[2/2] Procesando facturas...")
    
    exitos = 0
    errores = 0
    total_archivos_creados = 0
    fallas = []

    for factura in facturas:
        print(f"\nFactura: {factura}")
        motivos_falla = []
        
        # Archivos obligatorios para ambos modos
        encontrado_hc = False
        encontrado_factura = False if modo in ['1', '2'] else True # Solo mod 1 y 2 necesitan CRC
        encontrado_furips = False if modo in ['2', '4'] else True # Mod 2 y 4 necesitan FURIPS
        
        nombre_hc_buscado = f"HC_{factura}".upper()
        nombre_factura_buscado = factura.upper()
        nombre_furips_buscado = f"FURIPS_{factura}".upper()
        nombre_soporte_unido = f"{factura}-SOPORTE".upper()

        # 1. Procesar HC -> EPI y PDX
        ruta_hc = None
        if nombre_hc_buscado in indice:
            ruta_hc = max(indice[nombre_hc_buscado], key=os.path.getmtime)
        elif nombre_soporte_unido in indice:
            ruta_hc = max(indice[nombre_soporte_unido], key=os.path.getmtime)
            print(f"  [!] Usando archivo UNIDO para HC: {os.path.basename(ruta_hc)}")

        if ruta_hc:
            encontrado_hc = True
            _, ext = os.path.splitext(ruta_hc)
            extension = ext if ext else '.pdf'
            
            if os.path.getsize(ruta_hc) > UMBRAL_TAMANO_BYTES:
                print(f"  [!] ADVERTENCIA: Historia Clínica excede 20MB")

            try:
                # EPI
                nombre_epi = f"EPI_{NIT}_{factura}{extension}"
                shutil.copy2(ruta_hc, os.path.join(dir_destino, nombre_epi))
                # PDX
                nombre_pdx = f"PDX_{NIT}_{factura}{extension}"
                shutil.copy2(ruta_hc, os.path.join(dir_destino, nombre_pdx))
                print(f"  [OK] HC -> {nombre_epi} y {nombre_pdx}")
                total_archivos_creados += 2
            except Exception as e:
                motivos_falla.append(f"Error al copiar HC (EPI/PDX): {e}")
        else:
            motivos_falla.append(f"No se encontró archivo HC_{factura} ni {factura}-SOPORTE")

        # 2. Procesar Factura -> CRC (Solo si modo es 1 o 2)
        if modo in ['1', '2']:
            if nombre_factura_buscado in indice:
                encontrado_factura = True
                rutas = indice[nombre_factura_buscado]
                ruta_src = max(rutas, key=os.path.getmtime)
                
                _, ext = os.path.splitext(ruta_src)
                extension = ext if ext else '.pdf'
                
                if os.path.getsize(ruta_src) > UMBRAL_TAMANO_BYTES:
                    print(f"  [!] ADVERTENCIA: Factura original excede 20MB")
                
                try:
                    nombre_crc = f"CRC_{NIT}_{factura}{extension}"
                    shutil.copy2(ruta_src, os.path.join(dir_destino, nombre_crc))
                    print(f"  [OK] Factura -> {nombre_crc}")
                    total_archivos_creados += 1
                except Exception as e:
                    motivos_falla.append(f"Error al copiar Factura (CRC): {e}")
            else:
                motivos_falla.append(f"No se encontró archivo de factura {factura}")

        # 3. Procesar FURIPS (Solo si modo es 2 o 4)
        if modo in ['2', '4']:
            ruta_furips = None
            if nombre_furips_buscado in indice:
                ruta_furips = max(indice[nombre_furips_buscado], key=os.path.getmtime)
            elif nombre_soporte_unido in indice:
                ruta_furips = max(indice[nombre_soporte_unido], key=os.path.getmtime)
                print(f"  [!] Usando archivo UNIDO para FURIPS: {os.path.basename(ruta_furips)}")

            if ruta_furips:
                encontrado_furips = True
                _, ext = os.path.splitext(ruta_furips)
                extension = ext if ext else '.pdf'
                
                try:
                    nombre_furips_dst = f"FURIPS_{NIT}_{factura}{extension}"
                    shutil.copy2(ruta_furips, os.path.join(dir_destino, nombre_furips_dst))
                    print(f"  [OK] FURIPS -> {nombre_furips_dst}")
                    total_archivos_creados += 1
                except Exception as e:
                    motivos_falla.append(f"Error al copiar FURIPS: {e}")
            else:
                motivos_falla.append(f"No se encontró archivo FURIPS_{factura} ni {factura}-SOPORTE")

        # Finalizar Factura
        if encontrado_hc and encontrado_factura and encontrado_furips and not motivos_falla:
            exitos += 1
        else:
            errores += 1
            print(f"  [!] Factura {factura} INCOMPLETA: {', '.join(motivos_falla)}")
            fallas.append(f"Factura: {factura} | Fallos: {', '.join(motivos_falla)}")

    # Generar reporte de fallas
    if fallas:
        ruta_reporte = os.path.join(dir_destino, "facturas_fallidas.txt")
        try:
            with open(ruta_reporte, "w", encoding="utf-8") as f:
                f.write("REPORTE DE FACTURAS FALLIDAS O INCOMPLETAS\n")
                f.write("="*50 + "\n")
                if modo == '1': tag = "Estándar (HC+CRC)"
                elif modo == '2': tag = "Completa (HC+CRC+FURIPS)"
                elif modo == '4': tag = "Solo HC y FURIPS"
                else: tag = "Desconocida"
                
                f.write(f"Modalidad: {tag}\n\n")
                for falla in fallas:
                    f.write(f"- {falla}\n")
            print(f"\n[!] Se ha generado el reporte de fallas en: {ruta_reporte}")
        except Exception as e:
            print(f"Error al crear el reporte de fallas: {e}")

    print("\n" + "="*40)
    print(f"RESUMEN FINAL (Modo {modo}):")
    print(f"Facturas completas: {exitos}")
    print(f"Facturas incompletas/fallidas: {errores}")
    print(f"Total de archivos generados: {total_archivos_creados}")
    print("="*40)

if __name__ == "__main__":
    buscar_y_procesar_soportes_nu()
    input("\nPresione Enter para salir...")
