import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from recursos.utils import resource_path
from gui.main_window.ventana_principal import VentanaPrincipal

def main():
    """Punto de entrada principal para la aplicación."""
    app = QApplication(sys.argv)

    # --- Configuración del icono de la aplicación (para la barra de tareas en Windows) ---
    # En Windows, es necesario establecer un "AppUserModelID" para que el icono
    # de la barra de tareas sea consistente. Es una buena práctica.
    if sys.platform == "win32":
        import ctypes
        myappid = u'mycompany.myproduct.subproduct.version' # Cadena única
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    # --- Cargar icono y hoja de estilos usando resource_path ---
    
    # 1. Establecer el ícono de la aplicación/ventana
    icon_path = resource_path("licencias.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"Advertencia: No se encontró el archivo de icono en '{icon_path}'.")

    # 2. Cargar la hoja de estilos
    qss_path = resource_path("estilos.qss")
    try:
        with open(qss_path, "r", encoding='utf-8') as f:
            style_sheet = f.read()
        app.setStyleSheet(style_sheet)
        print(f"Estilos cargados exitosamente desde: {qss_path}")
    except FileNotFoundError:
        print(f"Advertencia: No se encontró el archivo de estilos '{qss_path}'.")
    except Exception as e:
        print(f"Error crítico al cargar la hoja de estilos: {e}")

    # 3. Crear y mostrar la ventana principal
    ventana = VentanaPrincipal()
    ventana.show()
    
    # 4. Iniciar el bucle de eventos de la aplicación
    sys.exit(app.exec())

if __name__ == "__main__":
    main()