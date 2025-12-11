# logica/workers/unir_axa_calixto_logic.py

import os
import glob
import tempfile
import re as regex_module
import pyzipper
from collections import defaultdict
from logica.core.procesador_pdf import unir_pdfs, extraer_codigo_factura

def unir_axa_calixto_logic(directorio_origen, directorio_destino, progress_callback, completion_callback, error_callback):
    """
    Lógica principal para descomprimir, agrupar, ordenar y unir los PDFs de AXA Calixto.
    """
    password = b'8002098917' # Contraseña especificada
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Paso 1: Encontrar y descomprimir todos los archivos .zip
            zip_files = glob.glob(os.path.join(directorio_origen, '**', '*.zip'), recursive=True)
            if not zip_files:
                raise ValueError("No se encontraron archivos .zip en el directorio seleccionado.")

            total_zips = len(zip_files)
            archivos_procesados_count = 0

            for i, zip_path in enumerate(zip_files):
                # Calculamos porcentaje del 0 al 40% para descompresión
                porcentaje = int(((i + 1) / total_zips) * 40)
                progress_callback.emit(f"Descomprimiendo {os.path.basename(zip_path)}...", porcentaje)
                
                try:
                    with pyzipper.AESZipFile(zip_path, 'r') as zf:
                        # Usamos pwd para desencriptar
                        zf.extractall(path=temp_dir, pwd=password)
                except RuntimeError:
                    print(f"Error: Contraseña incorrecta para {zip_path}")
                    continue
                except Exception as e:
                    print(f"Error al descomprimir {zip_path}: {e}")
                    continue
            
            progress_callback.emit("Agrupando archivos...", 45)

            # Paso 2: Agrupar archivos
            archivos_por_codigo = defaultdict(list)
            todos_los_codigos = set()
            archivos_huerfanos = []

            # Primera pasada: Agrupar por patrón __CODIGO
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    # Busca el patrón __numeros al final del nombre base
                    match = regex_module.search(r'__(\d+)', file)
                    
                    if match:
                        codigo = match.group(1)
                        todos_los_codigos.add(codigo)
                        archivos_por_codigo[codigo].append(full_path)
                    else:
                        archivos_huerfanos.append(full_path)

            # Segunda pasada: Asociar huérfanos si contienen el código en el nombre
            for path_huerfano in archivos_huerfanos:
                nombre_huerfano = os.path.basename(path_huerfano)
                asignado = False
                for codigo in todos_los_codigos:
                    if codigo in nombre_huerfano:
                        archivos_por_codigo[codigo].append(path_huerfano)
                        asignado = True
                        break 
                
                # Opcional: si no se asigna, se podría ignorar o agregar a un grupo "sin código"
            
            if not archivos_por_codigo:
                 raise ValueError("No se pudieron agrupar archivos o la descompresión falló.")

            # Paso 3: Ordenar, extraer nombre factura y Unir
            total_grupos = len(archivos_por_codigo)
            archivos_generados_lista = []
            errores_union = []

            for i, (codigo_radicado, lista_archivos) in enumerate(archivos_por_codigo.items()):
                # Actualizar barra progreso del 50 al 100
                porcentaje = 50 + int(((i + 1) / total_grupos) * 50)
                progress_callback.emit(f"Procesando radicado {codigo_radicado}...", porcentaje)

                # Ordenamiento específico solicitado
                def sort_key(filepath):
                    fname = os.path.basename(filepath).lower()
                    if fname.startswith('obj_doc_inc__'): return 0
                    if fname.startswith('liq__'): return 1
                    if fname.startswith('rel_recl_siniestro__'): return 3
                    return 2 # Otros soportes

                lista_archivos.sort(key=sort_key)

                # Intentar extraer el código de la factura (FECR...) del archivo liq__
                nombre_final_archivo = codigo_radicado  # Fallback: usa el número de carpeta temporal (radicado)
                
                # Buscar el archivo de liquidación (el que empieza por liq__)
                archivo_liq = next((f for f in lista_archivos if os.path.basename(f).startswith('liq__')), None)
                
                if archivo_liq:
                    # IMPORTANTE: Llamamos a la función con el nuevo regex
                    codigo_factura = extraer_codigo_factura(archivo_liq)
                    
                    if codigo_factura:
                        nombre_final_archivo = codigo_factura
                
                # Crear la ruta de salida con el nombre obtenido
                nombre_base = f"{nombre_final_archivo}.pdf"
                nombre_salida = os.path.join(directorio_destino, nombre_base)
                
                # Evitar sobrescritura
                contador = 1
                while os.path.exists(nombre_salida):
                    nombre_base = f"{nombre_final_archivo}_{contador}.pdf"
                    nombre_salida = os.path.join(directorio_destino, nombre_base)
                    contador += 1

                try:
                    unir_pdfs(lista_archivos, nombre_salida)
                    archivos_generados_lista.append({
                        'original': f"Radicado: {codigo_radicado}",
                        'nuevo': nombre_base,
                        'codigo': nombre_final_archivo
                    })
                except Exception as e:
                    errores_union.append({'archivo': f"Grupo {codigo_radicado}", 'error': str(e)})
                    print(f"Error al unir grupo {codigo_radicado}: {e}")

        completion_callback.emit({
            'total_zips': total_zips,
            'renombrados': archivos_generados_lista,
            'errores': errores_union,
            'tipo_proceso': 'AXA'
        })

    except ValueError as ve:
        error_callback.emit(str(ve))
    except Exception as e:
        error_callback.emit(f"Error inesperado: {str(e)}")