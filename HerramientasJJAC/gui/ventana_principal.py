# gui/ventana_principal.py
import sys
import os # Added import os
from PySide6.QtWidgets import QMainWindow, QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QStackedWidget, QLabel, QListWidgetItem
from PySide6.QtCore import Qt

class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Herramientas JJAC")
        self.setGeometry(100, 100, 1000, 700) # Aumentar tamaño para sidebar

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Sidebar de navegación (QListWidget)
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(200)
        self.sidebar.setObjectName("Sidebar") # Para aplicar estilos QSS
        main_layout.addWidget(self.sidebar)

        # Contenido principal (QStackedWidget)
        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)

        # Diccionario para almacenar widgets y sus nombres
        self.widgets = {}

        # Inicializar y añadir widgets al stacked_widget y sidebar
        self._add_widget( "Unir Soportes", "widget_unir_soportes", "WidgetUnirSoportes")
        self._add_widget( "Organizar PDFs", "widget_organizar_pdfs", "WidgetOrganizarPDFs")
        self._add_widget( "Organizar XMLs", "widget_organizar_xmls", "WidgetOrganizarXMLs")
        self._add_widget( "Traer Soportes ADRES", "widget_traer_soportes_adres", "WidgetTraerSoportesAdres")
        self._add_widget( "Traer Soportes Ratificadas", "widget_traer_soportes_ratificadas", "WidgetTraerSoportesRatificadas")
        self._add_widget( "Auditor de Facturas", "widget_auditor_facturas", "WidgetAuditorFacturas")
        self._add_widget( "Procesamiento ADRES", "widget_adres", "WidgetAdres")
        self._add_widget( "Buscador de Carpetas", "widget_buscador", "WidgetBuscador")
        self._add_widget( "Reorganizar Sedes (Envios)", "widget_envios", "WidgetEnvios")
        self._add_widget( "Ayuda y Recomendaciones", "widget_ayuda", "WidgetAyuda")

        # Conectar la selección del sidebar al stacked_widget
        self.sidebar.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)

        # Seleccionar el primer elemento por defecto
        if self.sidebar.count() > 0:
            self.sidebar.setCurrentRow(0)

    def _add_widget(self, name, module_name, class_name):
        try:
            # Corrected import logic
            module = __import__(f"gui.{module_name}", fromlist=[class_name])
            widget_class = getattr(module, class_name)
            widget_instance = widget_class()
            self.stacked_widget.addWidget(widget_instance)
            item = QListWidgetItem(name)
            self.sidebar.addItem(item)
            self.widgets[name] = widget_instance
        except ImportError as e:
            print(f"Error al cargar el widget {name}: {e}")
            # Añadir un widget de placeholder si falla la carga
            placeholder_widget = QWidget()
            placeholder_layout = QVBoxLayout(placeholder_widget)
            placeholder_layout.addWidget(QLabel(f"Error: No se pudo cargar {name}"))
            self.stacked_widget.addWidget(placeholder_widget)
            self.sidebar.addItem(name)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())
