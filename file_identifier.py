# file_identifier.py
import re
import os

# --- PATRONES DE BÚSQUEDA PARA AMBOS MODOS ---
# (Estos patrones son utilizados por una o ambas lógicas)

# Patrones para Modo Aseguradoras
PATTERN_CARTA = re.compile(r"(?:[a-zA-Z0-9]+[_-])?([A-Z]+)[_-](\d+)[_-].*\.pdf", re.IGNORECASE)

# Patrones compartidos por ambos modos (Respuesta)
PATTERN_RESPUESTA_VERIFICABLE = re.compile(r"([A-Z]+)_?(\d+)\.pdf", re.IGNORECASE)
PATTERN_RESPUESTA_GLOSA_REP = re.compile(r"GLOSA_REP\d*\.pdf", re.IGNORECASE)
PATTERN_RESPUESTA_GLOSA_NUEVO = re.compile(r"resp_glosa\.pdf", re.IGNORECASE)

# Patrones específicos para Modo ADRES
PATTERN_ADRES_EPICRISIS = re.compile(r"\d+_[A-Z]+\d+_EPICRIS(?:IS)?\.pdf", re.IGNORECASE)
PATTERN_ADRES_FACOSTE = re.compile(r"\d+_[A-Z]+\d+_FACOSTE\.pdf", re.IGNORECASE)
PATTERN_ADRES_FACTURA = re.compile(r"\d+_[A-Z]+\d+_FACTURA\.pdf", re.IGNORECASE)


# --- FUNCIÓN 1: Lógica para el Modo Aseguradoras ---
# **AQUÍ ESTÁ LA CORRECCIÓN: RENOMBRAMOS LA FUNCIÓN**
def identify_documents_aseguradoras(pdf_files, folder_path):
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
            numero = match_carta.group(2)
            if f"_{numero}_" in filename or f"-{numero}-" in filename:
                if not results['carta_glosa']:
                    results['carta_glosa'] = {
                        'path': os.path.join(folder_path, filename),
                        'serie': match_carta.group(1).upper(),
                        'numero': numero
                    }
                    claimed_files.add(filename)
                    continue

    # Ahora buscamos la respuesta, para no confundir con carta
    for filename in pdf_files:
        if filename in claimed_files:
            continue
            
        if PATTERN_RESPUESTA_GLOSA_NUEVO.match(filename):
            if not results['respuesta_glosa']:
                results['respuesta_glosa'] = {'path': os.path.join(folder_path, filename), 'type': 'RESP_GLOSA'}
                claimed_files.add(filename)
                continue

        match_resp_verificable = PATTERN_RESPUESTA_VERIFICABLE.match(filename)
        if match_resp_verificable:
            if not results['respuesta_glosa']:
                results['respuesta_glosa'] = {
                    'path': os.path.join(folder_path, filename), 'type': 'VERIFICABLE',
                    'serie': match_resp_verificable.group(1).upper(),
                    'numero': match_resp_verificable.group(2)
                }
                claimed_files.add(filename)
                continue

        if PATTERN_RESPUESTA_GLOSA_REP.match(filename):
            if not results['respuesta_glosa']:
                results['respuesta_glosa'] = {'path': os.path.join(folder_path, filename), 'type': 'GLOSA_REP'}
                claimed_files.add(filename)
                continue
    
    # Lo que no fue reclamado es un soporte
    for filename in pdf_files:
        if filename not in claimed_files and filename.lower().endswith('.pdf'):
            results['soportes'].append(os.path.join(folder_path, filename))

    return results


# --- FUNCIÓN 2: Lógica para el Modo ADRES ---
def identify_documents_adres(pdf_files, folder_path):
    """Nueva lógica de identificación para el modo ADRES."""
    results = {
        'epicrisis': None,
        'respuesta_glosa': None,
        'soportes': [],
        'ignorados': [] # Para facturas y facostes
    }
    
    claimed_files = set()

    # PASO 1: Identificar archivos clave y los que se deben ignorar/dejar quietos
    for filename in pdf_files:
        if PATTERN_ADRES_EPICRISIS.match(filename) and not results['epicrisis']:
            results['epicrisis'] = {'path': os.path.join(folder_path, filename)}
            claimed_files.add(filename)

        elif (PATTERN_RESPUESTA_VERIFICABLE.match(filename) or 
              PATTERN_RESPUESTA_GLOSA_REP.match(filename)) and not results['respuesta_glosa']:
            results['respuesta_glosa'] = {'path': os.path.join(folder_path, filename)}
            claimed_files.add(filename)
            
        elif PATTERN_ADRES_FACOSTE.match(filename) or PATTERN_ADRES_FACTURA.match(filename):
            results['ignorados'].append(os.path.join(folder_path, filename))
            # Importante: los añadimos a claimed_files para que no se consideren "soportes"
            claimed_files.add(filename)
    
    # PASO 2: Todo lo demás que sea PDF y no haya sido reclamado es un soporte
    for filename in pdf_files:
        if filename.lower().endswith('.pdf') and filename not in claimed_files:
            results['soportes'].append(os.path.join(folder_path, filename))
            
    return results