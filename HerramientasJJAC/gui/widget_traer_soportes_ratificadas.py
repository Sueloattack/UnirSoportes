from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QLabel, QTextEdit, QFileDialog, QTextBrowser
from PySide6.QtCore import Signal, Qt
from logica.logica_traer_soportes_ratificadas import LogicaTraerSoportesRatificadas

class WidgetTraerSoportesRatificadas(QWidget):
    operacion_iniciada = Signal(list, str, str) # invoice_numbers, search_dir, dest_dir

    def __init__(self):
        super().__init__()
        self.logica = LogicaTraerSoportesRatificadas(self.append_log)
        self.init_ui()
        self.operacion_iniciada.connect(self.logica.buscar_y_copiar_soportes)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop)

        # Título
        title_label = QLabel("Traer Soportes Ratificadas")
        title_label.setObjectName("AyudaTitulo") # Reusing style from AyudaTitulo
        main_layout.addWidget(title_label)

        # Sección de Números de Factura
        invoice_section_layout = QVBoxLayout()
        invoice_label = QLabel("Números de Factura (uno por línea):")
        invoice_section_layout.addWidget(invoice_label)
        self.invoice_numbers_textedit = QTextEdit()
        self.invoice_numbers_textedit.setPlaceholderText("Ingrese los números de factura aquí...")
        invoice_section_layout.addWidget(self.invoice_numbers_textedit)
        main_layout.addLayout(invoice_section_layout)

        # Sección de Directorio de Búsqueda
        search_dir_layout = QHBoxLayout()
        search_dir_label = QLabel("Directorio de Búsqueda:")
        search_dir_layout.addWidget(search_dir_label)
        self.search_dir_lineedit = QLineEdit()
        self.search_dir_lineedit.setReadOnly(True)
        search_dir_layout.addWidget(self.search_dir_lineedit)
        self.search_dir_button = QPushButton("Seleccionar")
        self.search_dir_button.clicked.connect(self.select_search_directory)
        search_dir_layout.addWidget(self.search_dir_button)
        main_layout.addLayout(search_dir_layout)

        # Sección de Directorio de Destino
        dest_dir_layout = QHBoxLayout()
        dest_dir_label = QLabel("Directorio de Destino:")
        dest_dir_layout.addWidget(dest_dir_label)
        self.dest_dir_lineedit = QLineEdit()
        self.dest_dir_lineedit.setReadOnly(True)
        dest_dir_layout.addWidget(self.dest_dir_lineedit)
        self.dest_dir_button = QPushButton("Seleccionar")
        self.dest_dir_button.clicked.connect(self.select_dest_directory)
        dest_dir_layout.addWidget(self.dest_dir_button)
        main_layout.addLayout(dest_dir_layout)

        # Botón de Iniciar Operación
        self.start_button = QPushButton("Iniciar Búsqueda y Copia")
        self.start_button.setObjectName("BotonPrincipal") # Reusing style from BotonPrincipal
        self.start_button.clicked.connect(self.start_operation)
        main_layout.addWidget(self.start_button)

        # Área de Logs/Resultados
        log_label = QLabel("Resultados:")
        main_layout.addWidget(log_label)
        self.log_textbrowser = QTextBrowser()
        main_layout.addWidget(self.log_textbrowser)

    def select_search_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Seleccionar Directorio de Búsqueda")
        if directory:
            self.search_dir_lineedit.setText(directory)

    def select_dest_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Seleccionar Directorio de Destino")
        if directory:
            self.dest_dir_lineedit.setText(directory)

    def start_operation(self):
        invoice_numbers_str = self.invoice_numbers_textedit.toPlainText()
        invoice_numbers = [num.strip() for num in invoice_numbers_str.split('\n') if num.strip()]
        search_dir = self.search_dir_lineedit.text()
        dest_dir = self.dest_dir_lineedit.text()

        if not invoice_numbers:
            self.log_textbrowser.append("<p style='color:red;'>Error: Ingrese al menos un número de factura.</p>")
            return
        if not search_dir:
            self.log_textbrowser.append("<p style='color:red;'>Error: Seleccione el directorio de búsqueda.</p>")
            return
        if not dest_dir:
            self.log_textbrowser.append("<p style='color:red;'>Error: Seleccione el directorio de destino.</p>")
            return

        self.log_textbrowser.clear()
        self.log_textbrowser.append("<p style='color:blue;'>Iniciando operación...</p>")
        self.operacion_iniciada.emit(invoice_numbers, search_dir, dest_dir)

    def append_log(self, message):
        self.log_textbrowser.append(message)
