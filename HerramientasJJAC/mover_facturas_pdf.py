import os
import shutil
import logging
import sys

# Configuración de logs para ver qué está pasando
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def obtener_input_multilinea(mensaje):
    """Permite al usuario pegar varias líneas de texto."""
    print(mensaje)
    print("(Presiona Enter dos veces seguidas o Ctrl+Z/Ctrl+D para finalizar)")
    lineas = []
    while True:
        try:
            linea = input()
            if not linea:
                break
            lineas.append(linea.strip())
        except EOFError:
            break
    return lineas

def mover_archivos_por_factura(lista_facturas, origen, destino):
    """
    Busca archivos PDF en la carpeta de origen que contengan en su nombre 
    alguna de las facturas de la lista y los mueve al destino.
    """
    
    # Normalizar rutas
    origen = os.path.normpath(origen.strip().replace('"', ''))
    destino = os.path.normpath(destino.strip().replace('"', ''))

    # Asegurarse de que las rutas existen
    if not os.path.exists(origen):
        logging.error(f"La carpeta de origen no existe: {origen}")
        return

    if not os.path.exists(destino):
        logging.info(f"Creando carpeta de destino: {destino}")
        try:
            os.makedirs(destino)
        except Exception as e:
            logging.error(f"No se pudo crear la carpeta de destino: {e}")
            return

    # Contador de archivos movidos
    total_movidos = 0
    facturas_encontradas = set()

    # Listar archivos en la carpeta de origen
    try:
        archivos = [f for f in os.listdir(origen) if os.path.isfile(os.path.join(origen, f))]
    except Exception as e:
        logging.error(f"Error al leer la carpeta de origen: {e}")
        return

    logging.info(f"Escaneando {len(archivos)} archivos en {origen}...")

    for factura in lista_facturas:
        factura = factura.strip()
        if not factura:
            continue
            
        logging.info(f"Buscando archivos para la factura: {factura}")
        encontrados_para_esta_factura = 0

        for nombre_archivo in archivos:
            # Comprobar si es PDF o TXT (ignora mayúsculas/minúsculas en extensión)
            if not nombre_archivo.lower().endswith((".pdf", ".txt")):
                continue

            # Comprobar si la factura está en el nombre (ignora mayúsculas/minúsculas)
            if factura.upper() in nombre_archivo.upper():
                ruta_completa_origen = os.path.join(origen, nombre_archivo)
                ruta_completa_destino = os.path.join(destino, nombre_archivo)

                try:
                    # Mover el archivo
                    shutil.move(ruta_completa_origen, ruta_completa_destino)
                    logging.info(f" -> MOVIDO: {nombre_archivo}")
                    total_movidos += 1
                    encontrados_para_esta_factura += 1
                    facturas_encontradas.add(factura)
                except Exception as e:
                    logging.error(f" -> ERROR al mover {nombre_archivo}: {e}")

        if encontrados_para_esta_factura == 0:
            logging.warning(f" -> No se encontraron archivos para la factura: {factura}")
        else:
            logging.info(f" -> Se movieron {encontrados_para_esta_factura} archivos para esta factura.")

    # Resumen final
    logging.info("-" * 40)
    logging.info(f"PROCESO FINALIZADO")
    logging.info(f"Total de archivos movidos: {total_movidos}")
    logging.info(f"Facturas con archivos encontrados: {len(facturas_encontradas)} de {len(lista_facturas)}")
    
    facturas_no_encontradas = set(lista_facturas) - facturas_encontradas
    if facturas_no_encontradas:
        print("\n[ALERTA] Facturas sin ningún archivo encontrado:")
        for f in facturas_no_encontradas:
            print(f" - {f}")

if __name__ == "__main__":
    print("=== SCRIPT PARA MOVER PDFS/TXTS POR LISTADO DE FACTURAS ===\n")
    
    # 1. Obtener listado de facturas
    facturas = obtener_input_multilinea("Introduce (o pega) el listado de facturas:")
    
    if not facturas:
        print("Error: No se ingresaron facturas.")
        sys.exit(1)
        
    # 2. Obtener rutas
    print("\nIntroduce la ruta de la CARPETA DE ORIGEN (donde están los archivos):")
    origen = input("> ").strip()
    
    print("\nIntroduce la ruta de la CARPETA DE DESTINO (a donde se moverán):")
    destino = input("> ").strip()
    
    if not origen or not destino:
        print("Error: Las rutas de origen y destino son obligatorias.")
        sys.exit(1)

    # Ejecutar la función
    print("\nIniciando proceso...")
    mover_archivos_por_factura(facturas, origen, destino)
    
    print("\nPresiona Enter para cerrar...")
    input()
