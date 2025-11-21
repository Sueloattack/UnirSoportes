# logica/gestor_archivos.py
import os
import shutil

def listar_subdirectorios(ruta_raiz):
    """Devuelve una lista de rutas completas a subdirectorios."""
    if not os.path.isdir(ruta_raiz):
        return []
    return [os.path.join(ruta_raiz, d) for d in os.listdir(ruta_raiz) if os.path.isdir(os.path.join(ruta_raiz, d))]

def obtener_archivos_pdf(ruta_directorio):
    """Devuelve una lista de nombres de archivos PDF en un directorio."""
    if not os.path.isdir(ruta_directorio):
        return []
    return [f for f in os.listdir(ruta_directorio) if f.lower().endswith('.pdf')]

def buscar_carpetas_por_nombre(ruta_raiz, nombres_a_buscar):
    """
    Busca recursivamente carpetas por nombre y las agrupa por su directorio padre.
    Devuelve: {'ruta_padre_1': {'envios': 'ruta_a_envios', 'furips': 'ruta_a_furips'}, ...}
    """
    carpetas_agrupadas = {}
    nombres_set = set(nombres_a_buscar)

    for dirpath, dirnames, _ in os.walk(ruta_raiz):
        # Optimización: si no hay carpetas con los nombres buscados en este nivel, seguir.
        if not nombres_set.intersection(set(d.lower() for d in dirnames)):
            continue

        for dirname in dirnames:
            if dirname.lower() in nombres_set:
                ruta_padre = os.path.dirname(os.path.join(dirpath, dirname))
                if ruta_padre not in carpetas_agrupadas:
                    carpetas_agrupadas[ruta_padre] = {}
                
                carpetas_agrupadas[ruta_padre][dirname.lower()] = os.path.join(dirpath, dirname)
    
    return carpetas_agrupadas

def copiar_contenido_carpeta(origen, destino, patron_nombre=None, extensiones_permitidas=None, extensiones_excluidas=None):
    """
    Copia archivos de una carpeta a otra con filtros opcionales.
    Crea la carpeta de destino si no existe.
    """
    if not os.path.exists(origen):
        return
        
    os.makedirs(destino, exist_ok=True)
    
    for item in os.listdir(origen):
        origen_path = os.path.join(origen, item)
        if not os.path.isfile(origen_path):
            continue

        # Filtrar por patrón en el nombre
        if patron_nombre and patron_nombre.lower() not in item.lower():
            continue

        # Filtrar por extensiones excluidas
        if extensiones_excluidas and any(item.lower().endswith(ext) for ext in extensiones_excluidas):
            continue

        # Filtrar por extensiones permitidas
        if extensiones_permitidas and not any(item.lower().endswith(ext) for ext in extensiones_permitidas):
            continue
            
        shutil.copy2(origen_path, destino)

