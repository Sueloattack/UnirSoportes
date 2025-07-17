# file_identifier.py
import re
import os

# --- PATRONES DE BÚSQUEDA ---
PATTERN_CARTA = re.compile(r"(?:[a-zA-Z0-9]+_)?([A-Z]+)_(\d+)_.*\.pdf", re.IGNORECASE)
PATTERN_RESPUESTA_VERIFICABLE = re.compile(r"([A-Z]+)_?(\d+)\.pdf", re.IGNORECASE)
PATTERN_RESPUESTA_GLOSA_REP = re.compile(r"GLOSA_REP\d*\.pdf", re.IGNORECASE)

# --- NUEVO PATRÓN AÑADIDO ---
# Este patrón busca exactamente el nombre "resp_glosa.pdf" sin importar mayúsculas/minúsculas.
PATTERN_RESPUESTA_GLOSA_NUEVO = re.compile(r"resp_glosa\.pdf", re.IGNORECASE)
# --- FIN DEL NUEVO PATRÓN ---

def identify_documents(pdf_files, folder_path):
    """Clasifica los archivos PDF de una carpeta en Carta, Respuesta y Soportes."""
    results = {
        'carta_glosa': None,
        'respuesta_glosa': None,
        'soportes': []
    }
    
    claimed_files = set()

    # Primera pasada: Identificar Carta Glosa
    for filename in pdf_files:
        if filename in claimed_files:
            continue

        match_carta = PATTERN_CARTA.search(filename)
        if match_carta:
            if f"_{match_carta.group(2)}_" in filename:
                if not results['carta_glosa']:
                    results['carta_glosa'] = {
                        'path': os.path.join(folder_path, filename),
                        'serie': match_carta.group(1).upper(),
                        'numero': match_carta.group(2)
                    }
                    claimed_files.add(filename)
                    continue

    # Ahora buscamos la respuesta, para no confundir con carta.
    for filename in pdf_files:
        if filename in claimed_files:
            continue
            
        # --- NUEVA CONDICIÓN AÑADIDA ---
        # 1. Primero buscamos el nuevo nombre de archivo "resp_glosa.pdf"
        match_resp_nuevo = PATTERN_RESPUESTA_GLOSA_NUEVO.match(filename)
        if match_resp_nuevo:
            if not results['respuesta_glosa']: # Tomar solo la primera
                results['respuesta_glosa'] = {
                    'path': os.path.join(folder_path, filename),
                    'type': 'RESP_GLOSA' # Nuevo tipo para que no valide serie/número
                }
                claimed_files.add(filename)
                continue
        # --- FIN DE LA NUEVA CONDICIÓN ---

        # 2. Si no se encontró el anterior, se buscan los patrones existentes
        match_resp_verificable = PATTERN_RESPUESTA_VERIFICABLE.match(filename)
        if match_resp_verificable:
            if not results['respuesta_glosa']:
                results['respuesta_glosa'] = {
                    'path': os.path.join(folder_path, filename),
                    'type': 'VERIFICABLE',
                    'serie': match_resp_verificable.group(1).upper(),
                    'numero': match_resp_verificable.group(2)
                }
                claimed_files.add(filename)
                continue

        match_resp_glosa_rep = PATTERN_RESPUESTA_GLOSA_REP.match(filename)
        if match_resp_glosa_rep:
            if not results['respuesta_glosa']:
                results['respuesta_glosa'] = {
                    'path': os.path.join(folder_path, filename),
                    'type': 'GLOSA_REP'
                }
                claimed_files.add(filename)
                continue
    
    # Segunda pasada: Lo que no fue reclamado es un soporte
    for filename in pdf_files:
        if filename not in claimed_files:
            results['soportes'].append(os.path.join(folder_path, filename))

    return results