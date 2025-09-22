# gui/componentes_comunes.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QLineEdit, QPushButton, QFileDialog

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
