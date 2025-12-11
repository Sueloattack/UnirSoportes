# logica/workers/renombrar_previsora_logic.py

import os
import re
import tempfile
import pyzipper
import pypdf
from collections import defaultdict

def extraer_codigo_factura_previsora(ruta_pdf):
    """
    Extrae el código de factura de un PDF de Previsora.
    Maneja 3 formatos diferentes:
    1. Carta/Oficio: "Factura / Radicado: FECR344616"
    2. Devolución (tabla): "Número factura ... FERD618"
    3. Liquidación: En encabezado "Nro Factura ... FECR344540"
    
    Returns:
        str: Código de factura (ej: FECR344616) o None si no se encuentra
    """
    try:
        with open(ruta_pdf, 'rb') as f:
            lector = pypdf.PdfReader(f)
            if len(lector.pages) > 0:
                texto_pagina = lector.pages[0].extract_text()
                
                # Patrón 1: Carta/Oficio - "Factura / Radicado: FECR344616"
                match_carta = re.search(r'Factura\s*/\s*Radicado:\s*([A-Z]{2,}\d+)', texto_pagina, re.IGNORECASE)
                if match_carta:
                    return match_carta.group(1)
                
                # Patrón 2: Devolución - "Número factura ... FERD618"
                # Buscar línea que contenga "Número factura" y extraer código en esa zona
                match_devolucion = re.search(r'Número\s+factura.*?([A-Z]{2,}\d+)', texto_pagina, re.IGNORECASE | re.DOTALL)
                if match_devolucion:
                    return match_devolucion.group(1)
                
                # Patrón 3: Liquidación - "Nro Factura ... FECR344540"
                match_liquidacion = re.search(r'Nro\s+Factura.*?([A-Z]{2,}\d+)', texto_pagina, re.IGNORECASE | re.DOTALL)
                if match_liquidacion:
                    return match_liquidacion.group(1)
                
                # Patrón genérico: Buscar cualquier código FECR/FERD/COEX seguido de números
                match_generico = re.search(r'\b(FE[CR][RD]\d{4,}|COEX\d{4,})\b', texto_pagina)
                if match_generico:
                    return match_generico.group(1)
                
    except Exception as e:
        print(f"Error extrayendo código de factura de {ruta_pdf}: {e}")
    
    return None


def renombrar_previsora_logic(directorio_origen, progress_callback, completion_callback, error_callback):
    """
    Lógica principal para descomprimir ZIPs de Previsora y renombrar los PDFs 
    con el código de factura extraído.
    
    Args:
        directorio_origen: Carpeta que contiene los archivos .zip de Previsora
        progress_callback: Signal(str, int) para actualizar progreso
        completion_callback: Signal(str) para notificar finalización
        error_callback: Signal(str) para notificar errores
    """
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            # Paso 1: Encontrar todos los archivos .zip
            zip_files = []
            for root, dirs, files in os.walk(directorio_origen):
                for file in files:
                    if file.lower().endswith('.zip'):
                        zip_files.append(os.path.join(root, file))
            
            if not zip_files:
                raise ValueError("No se encontraron archivos .zip en el directorio seleccionado.")
            
            total_zips = len(zip_files)
            archivos_renombrados = []
            archivos_sin_codigo = []
            errores_procesamiento = []
            
            # Paso 2: Descomprimir cada ZIP
            for i, zip_path in enumerate(zip_files):
                porcentaje = int(((i + 1) / total_zips) * 40)
                progress_callback.emit(f"Descomprimiendo {os.path.basename(zip_path)}...", porcentaje)
                
                try:
                    # Intentar descomprimir sin contraseña
                    with pyzipper.ZipFile(zip_path, 'r') as zf:
                        zf.extractall(path=temp_dir)
                except Exception as e:
                    errores_procesamiento.append({
                        'archivo': os.path.basename(zip_path),
                        'error': f"Error al descomprimir: {str(e)}"
                    })
                    print(f"Error al descomprimir {zip_path}: {e}")
                    continue
            
            progress_callback.emit("Procesando y renombrando archivos...", 45)
            
            # Paso 3: Procesar todos los PDFs descomprimidos
            pdf_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.lower().endswith('.pdf'):
                        pdf_files.append(os.path.join(root, file))
            
            if not pdf_files:
                raise ValueError("No se encontraron archivos PDF dentro de los ZIPs.")
            
            total_pdfs = len(pdf_files)
            
            for i, pdf_path in enumerate(pdf_files):
                porcentaje = 45 + int(((i + 1) / total_pdfs) * 55)
                nombre_original = os.path.basename(pdf_path)
                progress_callback.emit(f"Procesando {nombre_original}...", porcentaje)
                
                try:
                    # Extraer código de factura
                    codigo_factura = extraer_codigo_factura_previsora(pdf_path)
                    
                    if codigo_factura:
                        # Renombrar y mover al directorio de origen
                        nuevo_nombre = f"{codigo_factura}.pdf"
                        ruta_destino = os.path.join(directorio_origen, nuevo_nombre)
                        
                        # Si ya existe, agregar sufijo numérico
                        contador = 1
                        while os.path.exists(ruta_destino):
                            nuevo_nombre = f"{codigo_factura}_{contador}.pdf"
                            ruta_destino = os.path.join(directorio_origen, nuevo_nombre)
                            contador += 1
                        
                        # Copiar el archivo renombrado
                        import shutil
                        shutil.copy2(pdf_path, ruta_destino)
                        
                        archivos_renombrados.append({
                            'original': nombre_original,
                            'nuevo': nuevo_nombre,
                            'codigo': codigo_factura
                        })
                        print(f"✓ Renombrado: {nombre_original} → {nuevo_nombre}")
                    else:
                        # No se pudo extraer código - registrar como fallo
                        archivos_sin_codigo.append(nombre_original)
                        print(f"✗ No se pudo extraer código de: {nombre_original}")
                
                except Exception as e:
                    errores_procesamiento.append({
                        'archivo': nombre_original,
                        'error': str(e)
                    })
                    print(f"✗ Error procesando {nombre_original}: {e}")
            
            # Paso 4: Generar estructura de resultados
            resultados_finales = {
                'total_zips': total_zips,
                'total_pdfs': total_pdfs,
                'renombrados': archivos_renombrados,
                'sin_codigo': archivos_sin_codigo,
                'errores': errores_procesamiento
            }
            
            completion_callback.emit(resultados_finales)
    
    except ValueError as ve:
        error_callback.emit(str(ve))
    except Exception as e:
        error_callback.emit(f"Error inesperado: {str(e)}")
