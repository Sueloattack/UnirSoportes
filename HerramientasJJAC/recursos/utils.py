# HerramientasJJAC/recursos/utils.py

import sys
import os

def resource_path(relative_path):
    """
    Obtiene la ruta absoluta a un recurso, funciona para el desarrollo
    y para el ejecutable de PyInstaller.
    """
    try:
        # PyInstaller crea una carpeta temporal y almacena su ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Si no se está ejecutando como un .exe, usa la ruta del directorio del proyecto
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # Construye la ruta al recurso dentro de la carpeta 'recursos'
    return os.path.join(base_path, "recursos", relative_path)