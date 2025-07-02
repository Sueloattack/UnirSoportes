# main.py
import customtkinter
from gui import App

def main():
    """Punto de entrada principal para la aplicación."""
    # Configuración de la apariencia de la GUI
    customtkinter.set_appearance_mode("Light")  # O "Dark", "System"
    customtkinter.set_default_color_theme("blue")

    # Creación y ejecución de la ventana principal
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()