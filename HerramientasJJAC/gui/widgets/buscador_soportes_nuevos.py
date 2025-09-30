# gui/widgets/buscador_soportes_nuevos.py
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QLabel, QLineEdit, 
                               QPushButton, QTextEdit, QMessageBox, QTextBrowser, QFileDialog, QHBoxLayout)
from PySide6.QtCore import QThread, Qt

from logica.workers.buscador_soportes_nuevos_logic import BuscadorSoportesNuevosWorker

class BuscadorSoportesNuevosWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.thread = None
        
        self.crear_widgets()

    def crear_widgets(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)

        label_titulo = QLabel("Buscador de Soportes Nuevos (NU)")
        label_titulo.setObjectName("AyudaTitulo")
        label_titulo.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(label_titulo)
        
        group_inputs = QGroupBox("1. Entradas de Datos")
        layout_inputs = QVBoxLayout(group_inputs)
        layout_inputs.setSpacing(10)

        self.editor_facturas = QTextEdit()
        self.editor_facturas.setPlaceholderText("Pega aquí la lista de facturas con su serie (una por línea).\nEjemplo:\ncoex12345\nfecr67890")
        layout_inputs.addWidget(self.editor_facturas)
        
        selector_busqueda_layout = QHBoxLayout()
        self.line_busqueda = QLineEdit()
        self.line_busqueda.setPlaceholderText("Seleccione la carpeta de búsqueda...")
        self.line_busqueda.setReadOnly(True)
        btn_busqueda = QPushButton("Seleccionar...")
        btn_busqueda.clicked.connect(lambda: self._seleccionar_carpeta(self.line_busqueda))
        selector_busqueda_layout.addWidget(self.line_busqueda)
        selector_busqueda_layout.addWidget(btn_busqueda)
        layout_inputs.addLayout(selector_busqueda_layout)
        
        selector_destino_layout = QHBoxLayout()
        self.line_destino = QLineEdit()
        self.line_destino.setPlaceholderText("Selecciona la carpeta de destino para los soportes...")
        self.line_destino.setReadOnly(True)
        btn_destino = QPushButton("Seleccionar...")
        btn_destino.clicked.connect(lambda: self._seleccionar_carpeta(self.line_destino))
        selector_destino_layout.addWidget(self.line_destino)
        selector_destino_layout.addWidget(btn_destino)
        layout_inputs.addLayout(selector_destino_layout)
        
        layout_principal.addWidget(group_inputs)

        self.btn_iniciar = QPushButton("Iniciar Búsqueda y Copia")
        self.btn_iniciar.setObjectName("BotonPrincipal")
        self.btn_iniciar.setFixedHeight(40)
        self.btn_iniciar.clicked.connect(self.iniciar_proceso)
        layout_principal.addWidget(self.btn_iniciar)

        group_results = QGroupBox("2. Resultados")
        layout_results = QVBoxLayout(group_results)
        self.log_viewer = QTextBrowser()
        layout_results.addWidget(self.log_viewer)
        layout_principal.addWidget(group_results)

    def _seleccionar_carpeta(self, line_edit_widget):
        directory = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        if directory:
            line_edit_widget.setText(directory)
            
    def iniciar_proceso(self):
        facturas_raw = self.editor_facturas.toPlainText().strip()
        dir_busqueda = self.line_busqueda.text()
        dir_destino = self.line_destino.text()

        if not facturas_raw or not dir_busqueda or not dir_destino:
            QMessageBox.warning(self, "Datos incompletos", "Por favor, complete todos los campos.")
            return

        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "Proceso en curso", "Espere a que termine el proceso actual.")
            return

        facturas_con_serie = [line.strip() for line in facturas_raw.splitlines() if line.strip()]

        self.btn_iniciar.setText("Procesando...")
        self.btn_iniciar.setEnabled(False)
        self.log_viewer.clear()
        self.log_viewer.append("Iniciando proceso...")
        
        self.thread = QThread()
        self.worker = BuscadorSoportesNuevosWorker(facturas_con_serie, dir_busqueda, dir_destino)
        self.worker.moveToThread(self.thread)
        
        self.worker.log_generado.connect(self.actualizar_log)
        self.worker.proceso_finalizado.connect(self.finalizar_proceso)
        self.thread.started.connect(self.worker.ejecutar)
        
        self.thread.start()

    def actualizar_log(self, mensaje_html: str):
        self.log_viewer.append(mensaje_html)

    def finalizar_proceso(self):
        self.log_viewer.append("<b>Proceso finalizado.</b>")
        self.btn_iniciar.setText("Iniciar Búsqueda y Copia")
        self.btn_iniciar.setEnabled(True)
        self.thread.quit()
        self.thread.wait()
        self.thread = None
        self.worker = None
        QMessageBox.information(self, "Proceso Finalizado", "La búsqueda de soportes para facturas NUEVAS (NU) ha terminado.")
