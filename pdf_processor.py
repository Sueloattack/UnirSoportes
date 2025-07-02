# pdf_processor.py
import pypdf
import os

def _get_text_from_page(page):
    """Extrae y limpia el texto de una página PDF."""
    try:
        text = page.extract_text()
        # Normalizamos el texto para una mejor comparación:
        # eliminamos espacios en blanco extra y saltos de línea.
        return " ".join(text.split())
    except Exception:
        # Si la extracción de texto falla, retornamos una cadena vacía.
        return ""

def check_if_merged_by_content(target_pdf_path, source_pdf_path, pages_to_check=2, min_chars_to_match=50):
    """
    Verifica si el contenido del 'source' ya está en el 'target' comparando texto.
    
    Args:
        target_pdf_path (str): Ruta al PDF de respuesta glosa.
        source_pdf_path (str): Ruta al PDF de carta glosa.
        pages_to_check (int): Cuántas de las primeras páginas del 'source' se verificarán.
        min_chars_to_match (int): Longitud mínima de texto para considerar una coincidencia válida.

    Returns:
        bool: True si el contenido ya parece estar fusionado, False en caso contrario.
    """
    try:
        with open(target_pdf_path, 'rb') as f_target, open(source_pdf_path, 'rb') as f_source:
            reader_target = pypdf.PdfReader(f_target)
            reader_source = pypdf.PdfReader(f_source)
            
            # 1. Extraer el texto de todas las páginas del PDF de destino (Respuesta Glosa).
            # Lo unimos en una sola gran cadena de texto para facilitar la búsqueda.
            target_full_text = " ".join([_get_text_from_page(page) for page in reader_target.pages])

            if not target_full_text.strip():
                # Si el PDF de destino no tiene texto, no puede contener al otro.
                return False

            # 2. Iterar sobre las primeras 'pages_to_check' del PDF fuente (Carta Glosa).
            for i in range(min(pages_to_check, len(reader_source.pages))):
                source_page_text = _get_text_from_page(reader_source.pages[i])

                # Si la página fuente tiene suficiente texto para ser significativa...
                if source_page_text and len(source_page_text) > min_chars_to_match:
                    # 3. ...buscamos si ese texto ya existe dentro del texto completo del PDF de destino.
                    if source_page_text in target_full_text:
                        # Si encontramos una sola página coincidente, es suficiente para confirmar.
                        return True
            
            # Si después de revisar las páginas no encontramos ninguna coincidencia, no está fusionado.
            return False

    except Exception as e:
        # Si ocurre cualquier error de lectura, asumimos que no está fusionado para no saltar un proceso válido.
        print(f"Advertencia: Ocurrió un error durante la verificación de contenido de PDF: {e}. Se procederá a unir por seguridad.")
        return False

def merge_pdfs_into_target(target_pdf_path, source_pdf_paths):
    """
    Une una lista de PDFs (sources) a un PDF existente (target) usando PdfWriter.
    El archivo target es SOBRESCRITO.
    """
    writer = pypdf.PdfWriter()

    # Añadir todas las páginas del PDF de destino (Respuesta Glosa) como base.
    reader_target = pypdf.PdfReader(target_pdf_path)
    for page in reader_target.pages:
        writer.add_page(page)

    # Añadir la Carta Glosa y los soportes
    for path in source_pdf_paths:
        reader_source = pypdf.PdfReader(path)
        for page in reader_source.pages:
            writer.add_page(page)

    # Escribir el resultado sobreescribiendo el archivo de destino
    with open(target_pdf_path, 'wb') as output_file:
        writer.write(output_file)