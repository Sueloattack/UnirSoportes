# main.py
import sys
import os
from PySide6.QtWidgets import QApplication
from gui.ventana_principal import VentanaPrincipal

def main():
    app = QApplication(sys.argv)
    
    # Cargar y aplicar la hoja de estilo
    from PySide6.QtGui import QIcon
    project_root = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(project_root, "licencias.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    else:
        print(f"Advertencia: No se encontró el archivo de icono en '{icon_path}'.")
    try:
        # Construir la ruta absoluta al archivo estilos.qss en la raíz del proyecto
        # Asumiendo que main.py está en HerramientasJJAC/main.py y estilos.qss en la raíz
        qss_path = os.path.join(project_root, "estilos.qss")
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except FileNotFoundError:
        print(f"Advertencia: No se encontró el archivo de estilos en '{qss_path}'.")
    except Exception as e:
        print(f"Error al cargar estilos.qss: {e}")

    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()