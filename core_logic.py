# core_logic.py
import os
import re
import file_manager
import file_identifier
import pdf_processor

def _extract_number_from_string(s):
    """Extrae el primer número de una cadena. Usado para ordenar carpetas."""
    match = re.search(r'\d+', s)
    return int(match.group()) if match else 99999999

def process_folders(root_folder_path, gui_instance):
    """
    Función principal que orquesta el proceso. Se ejecuta en un hilo.
    """
    results = {"successful": [], "failed": []}
    
    sub_folders = file_manager.list_subdirectories(root_folder_path)
    sub_folders.sort(key=lambda path: _extract_number_from_string(os.path.basename(path)))

    if not sub_folders:
        results["failed"].append({"folder": "Raíz", "reason": "No se encontraron subcarpetas para procesar."})
        gui_instance.after(0, gui_instance.process_finished, results)
        return

    total_folders = len(sub_folders)
    for i, folder_path in enumerate(sub_folders):
        folder_name = os.path.basename(folder_path)
        percentage = (i + 1) / total_folders * 100
        
        gui_instance.after(0, gui_instance.update_progress, folder_name, percentage)
        
        try:
            process_single_invoice(folder_path, folder_name, results)
        except Exception as e:
            reason = f"Error inesperado en la carpeta: {e}"
            results['failed'].append({"folder": folder_name, "reason": reason})

    gui_instance.after(0, gui_instance.process_finished, results)

def process_single_invoice(folder_path, folder_name, results):
    """Procesa una única carpeta de factura."""
    pdf_files = file_manager.get_pdf_files_in_directory(folder_path)
    if not pdf_files:
        return

    identified_docs = file_identifier.identify_documents(pdf_files, folder_path)
    
    carta_glosa = identified_docs['carta_glosa']
    respuesta_glosa = identified_docs['respuesta_glosa']
    soportes = identified_docs['soportes']

    if not carta_glosa:
        results['failed'].append({"folder": folder_name, "reason": "No se encontró la Carta Glosa."})
        return

    if not respuesta_glosa:
        results['failed'].append({"folder": folder_name, "reason": "No se encontró la Respuesta Glosa."})
        return
        
    if respuesta_glosa['type'] == 'VERIFICABLE':
        if (carta_glosa['serie'] != respuesta_glosa['serie'] or
            carta_glosa['numero'] != respuesta_glosa['numero']):
            reason = f"Discrepancia Serie/Número. Carta: {carta_glosa['serie']}-{carta_glosa['numero']}, Respuesta: {respuesta_glosa['serie']}-{respuesta_glosa['numero']}"
            results['failed'].append({"folder": folder_name, "reason": reason})
            return
            
    try:
        # --- LLAMADA A LA NUEVA FUNCIÓN DE VERIFICACIÓN ---
        is_already_processed = pdf_processor.check_if_merged_by_content(
            target_pdf_path=respuesta_glosa['path'],
            source_pdf_path=carta_glosa['path']
        )
        if is_already_processed:
            message = "Validación de contenido correcta. La Carta Glosa ya está unida."
            results['successful'].append({"folder": folder_name, "reason": message})
            return
    except Exception as e:
        reason = f"Error al verificar el contenido del archivo: {e}"
        results['failed'].append({"folder": folder_name, "reason": reason})
        return
        
    # Unimos Carta Glosa y los soportes.
    files_to_merge = [carta_glosa['path']] + soportes
    soportes.sort() # Ordenar soportes alfabéticamente

    try:
        pdf_processor.merge_pdfs_into_target(
            target_pdf_path=respuesta_glosa['path'],
            source_pdf_paths=files_to_merge
        )
        message = f"¡Unión exitosa! Se anexó la Carta Glosa y {len(soportes)} soporte(s)."
        results['successful'].append({"folder": folder_name, "reason": message})
    except Exception as e:
        reason = f"Error crítico al intentar unir los PDFs: {e}"
        results['failed'].append({"folder": folder_name, "reason": reason})