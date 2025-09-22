import sys
from PySide6.QtWidgets import QApplication
from gui.main_window.ventana_principal import VentanaPrincipal

def main():
    app = QApplication(sys.argv)

    # Cargar la hoja de estilos
    try:
        with open("estilos.qss", "r", encoding='utf-8') as f:
            style_sheet = f.read()
        app.setStyleSheet(style_sheet)
    except FileNotFoundError:
        print("Advertencia: No se encontró el archivo 'estilos.qss'. La aplicación se ejecutará sin estilos personalizados.")

    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
