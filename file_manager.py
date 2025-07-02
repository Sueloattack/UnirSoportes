# file_manager.py
import os

def list_subdirectories(root_path):
    """Devuelve una lista de rutas completas a subdirectorios."""
    if not os.path.isdir(root_path):
        return []
    return [os.path.join(root_path, d) for d in os.listdir(root_path) if os.path.isdir(os.path.join(root_path, d))]

def get_pdf_files_in_directory(dir_path):
    """Devuelve una lista de nombres de archivos PDF en un directorio."""
    if not os.path.isdir(dir_path):
        return []
    return [f for f in os.listdir(dir_path) if f.lower().endswith('.pdf')]