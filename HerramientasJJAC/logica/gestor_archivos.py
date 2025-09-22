# logica/gestor_archivos.py
import os

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
