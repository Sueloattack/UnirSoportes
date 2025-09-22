import sys
import os

# --- INICIO DEL CÓDIGO CLAVE PARA LAS IMPORTACIONES ---
# Este bloque asegura que Python pueda encontrar los módulos 'gui' y 'logica'
# sin importar desde dónde se ejecute el script.
try:
    # 1. Obtiene la ruta del directorio que contiene este archivo (main.py)
    # Por ejemplo: C:\Users\...\HerramientasJJAC
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Añade este directorio al path de Python.
    # Ahora Python buscará módulos en C:\Users\...\HerramientasJJAC,
    # permitiendo que 'from gui.ventana_principal' funcione correctamente.
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
        
except NameError:
    # __file__ no está definido si se ejecuta en algunos entornos interactivos.
    # Para la ejecución normal del script, esto no debería ocurrir.
    sys.path.insert(0, os.getcwd())

# --- FIN DEL CÓDIGO CLAVE ---


# Ahora las importaciones deberían funcionar sin problemas
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from gui.ventana_principal import VentanaPrincipal


def main():
    """Punto de entrada principal para la aplicación."""
    app = QApplication(sys.argv)
    
    # Obtener la ruta del directorio donde está main.py
    project_root = os.path.dirname(os.path.abspath(__file__))

    # 1. Cargar el icono de la ventana
    icon_path = os.path.join(project_root, "licencias.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"Advertencia: No se encontró el archivo de icono en '{icon_path}'.")

    # 2. Cargar y aplicar la hoja de estilo (QSS)
    qss_path = os.path.join(project_root, "estilos.qss")
    try:
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
            print(f"Estilos cargados exitosamente desde '{qss_path}'.")
    except FileNotFoundError:
        print(f"Advertencia: No se encontró el archivo de estilos en '{qss_path}'.")
    except Exception as e:
        print(f"Error al cargar estilos.qss: {e}")

    # 3. Creación y ejecución de la ventana principal
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()