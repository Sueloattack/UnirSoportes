# gui/ventana_principal.py
import sys
import os
# --- Bloque de importación unificado y limpio ---
from PySide6.QtWidgets import (QMainWindow, QApplication, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QStackedWidget, QLabel, 
                               QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Herramientas JJAC")
        self.setGeometry(100, 100, 1200, 700)
        self.sidebar_collapsed = True # Empezamos con el estado "colapsado"

        # Contenedor central y layout principal horizontal
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Contenedor del Sidebar para agrupar el botón y la lista
        self.sidebar_container = QWidget()
        self.sidebar_container.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(5, 5, 5, 5)
        sidebar_layout.setSpacing(10)
        main_layout.addWidget(self.sidebar_container)

        # Botón de Toggle
        # Iniciamos con el texto '>' ya que empieza expandido
        self.toggle_button = QPushButton() 
        self.toggle_button.setObjectName("ToggleButton")
        self.toggle_button.setFixedSize(QSize(40, 40))
        self.toggle_button.clicked.connect(self.toggle_sidebar)
        sidebar_layout.addWidget(self.toggle_button, 0, Qt.AlignCenter)

        # Establecer una fuente compatible para los símbolos
        font = self.toggle_button.font()
        font.setFamily("Segoe UI Symbol") 
        font.setPointSize(16)
        self.toggle_button.setFont(font)
        
        # Lista de Widgets (Menú)
        self.sidebar_list = QListWidget()
        self.sidebar_list.setObjectName("SidebarList")
        sidebar_layout.addWidget(self.sidebar_list)

        # Contenido principal apilado
        self.stacked_widget = QStackedWidget()
        # Puedes darle un ID para un fondo de contenido por defecto, si quieres
        # self.stacked_widget.setObjectName("ContentArea") 
        main_layout.addWidget(self.stacked_widget)

        # Guardamos la info de los botones/widgets
        self.button_info = []

        # Inicializar y añadir todas las pestañas
        self._add_widget("Unir Soportes", "US", "widget_unir_soportes", "WidgetUnirSoportes")
        self._add_widget("Organizar PDFs", "PDF", "widget_organizar_pdfs", "WidgetOrganizarPDFs")
        self._add_widget("Organizar XMLs", "XML", "widget_organizar_xmls", "WidgetOrganizarXMLs")
        self._add_widget("Traer Soportes ADRES", "TSA", "widget_traer_soportes_adres", "WidgetTraerSoportesAdres")
        self._add_widget("Traer Soportes Ratificadas", "TSR", "widget_traer_soportes_ratificadas", "WidgetTraerSoportesRatificadas")
        self._add_widget("Auditor de Facturas", "AF", "widget_auditor_facturas", "WidgetAuditorFacturas")
        self._add_widget("Procesamiento ADRES", "PA", "widget_adres", "WidgetAdres")
        self._add_widget("Buscador de Carpetas", "BC", "widget_buscador", "WidgetBuscador")
        self._add_widget("Reorganizar Sedes (Envios)", "ENV", "widget_envios", "WidgetEnvios")
        self._add_widget("Ayuda", "?", "widget_ayuda", "WidgetAyuda")

        # Conectar la selección del menú con el cambio de pestaña
        self.sidebar_list.currentRowChanged.connect(self.stacked_widget.setCurrentIndex)

        # Seleccionar la primera pestaña por defecto
        if self.sidebar_list.count() > 0:
            self.sidebar_list.setCurrentRow(0)
        
        # Aplicar el estado inicial (expandido)
        self.update_sidebar_state()

    def _add_widget(self, name, abbr, module_name, class_name):
        try:
            # Importación dinámica del módulo del widget
            module = __import__(f"gui.{module_name}", fromlist=[class_name])
            widget_class = getattr(module, class_name)
            widget_instance = widget_class()
            self.stacked_widget.addWidget(widget_instance)
            
            # Crear y añadir el ítem a la lista del sidebar
            item = QListWidgetItem()
            item.setTextAlignment(Qt.AlignCenter) # El texto se alineará al centro en el QListWidget
            self.sidebar_list.addItem(item)
            self.button_info.append({"name": name, "abbr": abbr})

        except (ImportError, AttributeError) as e:
            print(f"Error al cargar el widget {name}: {e}")
            # Crear un widget de error como placeholder
            placeholder = QLabel(f"Error: No se pudo cargar el widget '{name}'.\n\n{e}")
            placeholder.setAlignment(Qt.AlignCenter)
            self.stacked_widget.addWidget(placeholder)
            self.sidebar_list.addItem(f"ERROR: {name}")

    def toggle_sidebar(self):
        """Invierte el estado colapsado/expandido y actualiza la UI."""
        self.sidebar_collapsed = not self.sidebar_collapsed
        self.update_sidebar_state()

    def update_sidebar_state(self):
        """Aplica los cambios visuales según el estado del sidebar."""
        if self.sidebar_collapsed:
            self.sidebar_container.setFixedWidth(80)
            self.toggle_button.setText("☰")
            for i in range(self.sidebar_list.count()):
                item = self.sidebar_list.item(i)
                item.setText(self.button_info[i]["abbr"]) # Usar abreviatura
        else:
            self.sidebar_container.setFixedWidth(220)
            self.toggle_button.setText("☰")
            for i in range(self.sidebar_list.count()):
                item = self.sidebar_list.item(i)
                item.setText(self.button_info[i]["name"]) # Usar nombre completo

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ventana = VentanaPrincipal()
    ventana.show()
    sys.exit(app.exec())