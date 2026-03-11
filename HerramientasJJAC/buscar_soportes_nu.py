import os
import shutil

def buscar_y_procesar_soportes_nu():
    print("=== BUSCADOR DE SOPORTES NU (3 ARCHIVOS + VERIFICACIÓN TAMAÑO) ===")
    
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

    # Limpiar duplicados y espacios
    facturas = list(set([f.strip() for f in facturas_input if f.strip()]))

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

    for factura in facturas:
        print(f"\nFactura: {factura}")
        encontrado_hc = False
        encontrado_factura = False

        nombre_hc_buscado = f"HC_{factura}".upper()
        nombre_factura_buscado = factura.upper()
        
        # 1. Procesar HC -> EPI_800209891_{ID}.pdf y PDX_800209891_{ID}.pdf
        if nombre_hc_buscado in indice:
            encontrado_hc = True
            rutas = indice[nombre_hc_buscado]
            ruta_src = max(rutas, key=os.path.getmtime)
            
            _, ext = os.path.splitext(ruta_src)
            extension = ext if ext else '.pdf'
            
            # Verificar tamaño
            peso = os.path.getsize(ruta_src)
            if peso > UMBRAL_TAMANO_BYTES:
                print(f"  [!] ADVERTENCIA: Historia Clínica excede 20MB ({round(peso/(1024*1024), 2)} MB)")

            # EPI
            nombre_epi = f"EPI_{NIT}_{factura}{extension}"
            ruta_epi = os.path.join(dir_destino, nombre_epi)
            
            # PDX
            nombre_pdx = f"PDX_{NIT}_{factura}{extension}"
            ruta_pdx = os.path.join(dir_destino, nombre_pdx)
            
            try:
                shutil.copy2(ruta_src, ruta_epi)
                print(f"  [OK] HC -> {nombre_epi}")
                shutil.copy2(ruta_src, ruta_pdx)
                print(f"  [OK] HC -> {nombre_pdx}")
                total_archivos_creados += 2
            except Exception as e:
                print(f"  [ERROR] No se pudo copiar HC/EPI/PDX: {e}")

        # 2. Procesar Factura -> CRC_800209891_{ID}.pdf
        if nombre_factura_buscado in indice:
            encontrado_factura = True
            rutas = indice[nombre_factura_buscado]
            ruta_src = max(rutas, key=os.path.getmtime)
            
            _, ext = os.path.splitext(ruta_src)
            nuevo_nombre_crc = f"CRC_{NIT}_{factura}{ext if ext else '.pdf'}"
            ruta_dst_crc = os.path.join(dir_destino, nuevo_nombre_crc)

            # Verificar tamaño
            peso = os.path.getsize(ruta_src)
            if peso > UMBRAL_TAMANO_BYTES:
                print(f"  [!] ADVERTENCIA: Factura original excede 20MB ({round(peso/(1024*1024), 2)} MB)")
            
            try:
                shutil.copy2(ruta_src, ruta_dst_crc)
                print(f"  [OK] Factura -> {nuevo_nombre_crc}")
                total_archivos_creados += 1
            except Exception as e:
                print(f"  [ERROR] No se pudo copiar Factura/CRC: {e}")

        # Reportar faltantes o éxito
        if not encontrado_hc:
            print(f"  [!] No se encontró HC_{factura}")
        if not encontrado_factura:
            print(f"  [!] No se encontró el archivo de factura {factura}")
            
        if encontrado_hc and encontrado_factura:
            exitos += 1
        else:
            errores += 1

    print("\n" + "="*40)
    print(f"RESUMEN FINAL:")
    print(f"Facturas con lote completo (EPI, PDX, CRC): {exitos}")
    print(f"Facturas incompletas: {errores}")
    print(f"Total de archivos generados en destino: {total_archivos_creados}")
    print("="*40)

if __name__ == "__main__":
    buscar_y_procesar_soportes_nu()
    input("\nPresione Enter para salir...")
