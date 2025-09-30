# gui/componentes_comunes.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog, QTextBrowser, QVBoxLayout, QGroupBox

class SelectorCarpeta(QWidget):
    def __init__(self, etiqueta_texto: str, placeholder: str = "Ninguna carpeta seleccionada..."):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel(etiqueta_texto)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText(placeholder)
        self.entry.setReadOnly(True)
        button = QPushButton("Seleccionar...")
        button.clicked.connect(self.seleccionar_carpeta)

        layout.addWidget(label)
        layout.addWidget(self.entry)
        layout.addWidget(button)

    def seleccionar_carpeta(self):
        ruta = QFileDialog.getExistingDirectory(self)
        if ruta:
            self.entry.setText(ruta)
    
    def path(self) -> str:
        return self.entry.text()

def crear_selector_carpeta(label_text, dialog_title, on_path_selected=None):
    """
    Crea un layout con un label, un QLineEdit para la ruta y un botón para seleccionar carpeta.
    """
    layout = QHBoxLayout()
    label = QLabel(label_text)
    line_edit = QLineEdit()
    line_edit.setReadOnly(True)
    
    def select_folder():
        ruta = QFileDialog.getExistingDirectory(None, dialog_title)
        if ruta:
            line_edit.setText(ruta)
            if on_path_selected:
                on_path_selected()

    button = QPushButton("...")
    button.clicked.connect(select_folder)

    layout.addWidget(label)
    layout.addWidget(line_edit)
    layout.addWidget(button)
    
    return line_edit, layout

def setup_logging_browser(group_box_title):
    """
    Crea un GroupBox con un QTextBrowser para mostrar logs.
    """
    group_box = QGroupBox(group_box_title)
    log_browser = QTextBrowser()
    log_browser.setReadOnly(True)
    log_browser.setOpenExternalLinks(True)
    
    layout = QVBoxLayout(group_box)
    layout.addWidget(log_browser)
    
    return log_browser, group_box
