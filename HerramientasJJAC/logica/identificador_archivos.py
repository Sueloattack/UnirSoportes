# logica/identificador_archivos.py
import re
import os

# --- PATRONES DE BÚSQUEDA PARA AMBOS MODOS ---

# Patrones para Modo Aseguradoras
PATRON_CARTA = re.compile(r"(?:[a-zA-Z0-9]+[_-])?([A-Z]+)[_-](\d+)[_-].*\.pdf", re.IGNORECASE)

# Patrones compartidos (Respuesta)
PATRON_RESPUESTA_VERIFICABLE = re.compile(r"([A-Z]+)_?(\d+)\.pdf", re.IGNORECASE)
PATRON_RESPUESTA_GLOSA_REP = re.compile(r"GLOSA_REP\d*\.pdf", re.IGNORECASE)
PATRON_RESPUESTA_GLOSA_NUEVO = re.compile(r"resp_glosa\.pdf", re.IGNORECASE)

# Patrones específicos para Modo ADRES
PATRON_ADRES_EPICRISIS = re.compile(r"\d+_[A-Z]+\d+_EPICRIS(?:IS)?\.pdf", re.IGNORECASE)
PATRON_ADRES_FACOSTE = re.compile(r"\d+_[A-Z]+\d+_FACOSTE\.pdf", re.IGNORECASE)
PATRON_ADRES_FACTURA = re.compile(r"\d+_[A-Z]+\d+_FACTURA\.pdf", re.IGNORECASE)


def identificar_documentos_aseguradoras(archivos_pdf, ruta_carpeta):
    """Clasifica los archivos PDF de una carpeta en Carta, Respuesta y Soportes."""
    resultados = {
        'carta_glosa': None,
        'respuesta_glosa': None,
        'soportes': []
    }
    
    archivos_reclamados = set()

    # Primera pasada: Identificar Carta Glosa
    for nombre_archivo in archivos_pdf:
        if nombre_archivo in archivos_reclamados:
            continue

        match_carta = PATRON_CARTA.search(nombre_archivo)
        if match_carta:
            numero = match_carta.group(2)
            if f"_{numero}_" in nombre_archivo or f"-{numero}-" in nombre_archivo:
                if not resultados['carta_glosa']:
                    resultados['carta_glosa'] = {
                        'path': os.path.join(ruta_carpeta, nombre_archivo),
                        'serie': match_carta.group(1).upper(),
                        'numero': numero
                    }
                    archivos_reclamados.add(nombre_archivo)
                    continue

    # Ahora buscamos la respuesta, para no confundir con carta
    for nombre_archivo in archivos_pdf:
        if nombre_archivo in archivos_reclamados:
            continue
            
        if PATRON_RESPUESTA_GLOSA_NUEVO.match(nombre_archivo):
            if not resultados['respuesta_glosa']:
                resultados['respuesta_glosa'] = {'path': os.path.join(ruta_carpeta, nombre_archivo), 'type': 'RESP_GLOSA'}
                archivos_reclamados.add(nombre_archivo)
                continue

        match_resp_verificable = PATRON_RESPUESTA_VERIFICABLE.match(nombre_archivo)
        if match_resp_verificable:
            if not resultados['respuesta_glosa']:
                resultados['respuesta_glosa'] = {
                    'path': os.path.join(ruta_carpeta, nombre_archivo), 'type': 'VERIFICABLE',
                    'serie': match_resp_verificable.group(1).upper(),
                    'numero': match_resp_verificable.group(2)
                }
                archivos_reclamados.add(nombre_archivo)
                continue

        if PATRON_RESPUESTA_GLOSA_REP.match(nombre_archivo):
            if not resultados['respuesta_glosa']:
                resultados['respuesta_glosa'] = {'path': os.path.join(ruta_carpeta, nombre_archivo), 'type': 'GLOSA_REP'}
                archivos_reclamados.add(nombre_archivo)
                continue
    
    # Lo que no fue reclamado es un soporte
    for nombre_archivo in archivos_pdf:
        if nombre_archivo not in archivos_reclamados and nombre_archivo.lower().endswith('.pdf'):
            resultados['soportes'].append(os.path.join(ruta_carpeta, nombre_archivo))

    return resultados


def identificar_documentos_adres(archivos_pdf, ruta_carpeta):
    """Nueva lógica de identificación para el modo ADRES."""
    resultados = {
        'epicrisis': None,
        'respuesta_glosa': None,
        'soportes': [],
        'ignorados': [] # Para facturas y facostes
    }
    
    archivos_reclamados = set()

    # PASO 1: Identificar archivos clave y los que se deben ignorar/dejar quietos
    for nombre_archivo in archivos_pdf:
        if PATRON_ADRES_EPICRISIS.match(nombre_archivo) and not resultados['epicrisis']:
            resultados['epicrisis'] = {'path': os.path.join(ruta_carpeta, nombre_archivo)}
            archivos_reclamados.add(nombre_archivo)

        elif (PATRON_RESPUESTA_VERIFICABLE.match(nombre_archivo) or 
              PATRON_RESPUESTA_GLOSA_REP.match(nombre_archivo)) and not resultados['respuesta_glosa']:
            resultados['respuesta_glosa'] = {'path': os.path.join(ruta_carpeta, nombre_archivo)}
            archivos_reclamados.add(nombre_archivo)
            
        elif PATRON_ADRES_FACOSTE.match(nombre_archivo) or PATRON_ADRES_FACTURA.match(nombre_archivo):
            resultados['ignorados'].append(os.path.join(ruta_carpeta, nombre_archivo))
            # Importante: los añadimos a archivos_reclamados para que no se consideren "soportes"
            archivos_reclamados.add(nombre_archivo)
    
    # PASO 2: Todo lo demás que sea PDF y no haya sido reclamado es un soporte
    for nombre_archivo in archivos_pdf:
        if nombre_archivo.lower().endswith('.pdf') and nombre_archivo not in archivos_reclamados:
            resultados['soportes'].append(os.path.join(ruta_carpeta, nombre_archivo))
            
    return resultados
