# file_identifier.py
import re
import os

# --- PATRÓN MODIFICADO PARA LA CARTA GLOSA ---
# El grupo (?:...)? hace que toda la sección inicial 'código_' sea opcional.
# ?: significa que es un grupo que no captura, solo agrupa para el cuantificador '?'
PATTERN_CARTA = re.compile(r"(?:[a-zA-Z0-9]+_)?([A-Z]+)_(\d+)_.*\.pdf", re.IGNORECASE)

# Los otros patrones permanecen igual
PATTERN_RESPUESTA_VERIFICABLE = re.compile(r"([A-Z]+)_?(\d+)\.pdf", re.IGNORECASE)
PATTERN_RESPUESTA_GLOSA_REP = re.compile(r"GLOSA_REP\d*\.pdf", re.IGNORECASE)

def identify_documents(pdf_files, folder_path):
    """Clasifica los archivos PDF de una carpeta en Carta, Respuesta y Soportes."""
    results = {
        'carta_glosa': None,
        'respuesta_glosa': None,
        'soportes': []
    }
    
    claimed_files = set()

    # Primera pasada: Identificar Carta y Respuesta Glosa
    for filename in pdf_files:
        # Evitar que se reclame un archivo ya clasificado
        if filename in claimed_files:
            continue

        # Identificar Carta Glosa con el nuevo patrón flexible
        match_carta = PATTERN_CARTA.search(filename)
        if match_carta:
            # Condición para evitar que el patrón de respuesta glosa (FECR_326143.pdf) sea confundido
            # con una carta glosa. Las cartas glosa suelen tener más texto después del número.
            # Verificamos si hay un '_' después del número, que es típico de la carta glosa.
            if f"_{match_carta.group(2)}_" in filename:
                if not results['carta_glosa']: # Tomar solo la primera que encuentre
                    results['carta_glosa'] = {
                        'path': os.path.join(folder_path, filename),
                        'serie': match_carta.group(1).upper(), # El grupo de la SERIE ahora es el 1
                        'numero': match_carta.group(2)         # El grupo del NÚMERO ahora es el 2
                    }
                    claimed_files.add(filename)
                    continue

    # Ahora buscamos la respuesta, para no confundir con carta.
    for filename in pdf_files:
        if filename in claimed_files:
            continue
            
        # Identificar Respuesta Glosa (Tipo Verificable)
        match_resp_verificable = PATTERN_RESPUESTA_VERIFICABLE.match(filename)
        if match_resp_verificable:
            if not results['respuesta_glosa']: # Tomar solo la primera
                results['respuesta_glosa'] = {
                    'path': os.path.join(folder_path, filename),
                    'type': 'VERIFICABLE',
                    'serie': match_resp_verificable.group(1).upper(),
                    'numero': match_resp_verificable.group(2)
                }
                claimed_files.add(filename)
                continue

        # Identificar Respuesta Glosa (Tipo GLOSA_REP)
        match_resp_glosa_rep = PATTERN_RESPUESTA_GLOSA_REP.match(filename)
        if match_resp_glosa_rep:
            if not results['respuesta_glosa']: # Tomar solo la primera
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