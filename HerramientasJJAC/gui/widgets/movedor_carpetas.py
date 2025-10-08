# gui/widgets/movedor_carpetas.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QLabel, 
                               QPushButton, QTextEdit, QMessageBox, QTextBrowser, QFileDialog, QHBoxLayout, QLineEdit)
from PySide6.QtCore import QThread, Qt

from logica.workers.movedor_carpetas_logic import MovedorCarpetasWorker

class MovedorCarpetasWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.thread = None
        
        self.crear_widgets()

    def crear_widgets(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)

        label_titulo = QLabel("Mover Carpetas por Número de Factura")
        label_titulo.setObjectName("AyudaTitulo")
        label_titulo.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(label_titulo)
        
        group_inputs = QGroupBox("1. Entradas de Datos")
        layout_inputs = QVBoxLayout(group_inputs)
        layout_inputs.setSpacing(10)

        self.editor_facturas = QTextEdit()
        self.editor_facturas.setPlaceholderText("Pega aquí la lista de números de factura (uno por línea, sin series).\nEjemplo:\n12345\n67890")
        layout_inputs.addWidget(self.editor_facturas)
        
        # Selector de carpeta de origen
        layout_origen = QHBoxLayout()
        self.line_origen = QLineEdit()
        self.line_origen.setPlaceholderText("Seleccione la carpeta de origen...")
        self.line_origen.setReadOnly(True)
        btn_origen = QPushButton("Seleccionar...")
        btn_origen.clicked.connect(lambda: self._seleccionar_carpeta(self.line_origen))
        layout_origen.addWidget(self.line_origen)
        layout_origen.addWidget(btn_origen)
        layout_inputs.addLayout(layout_origen)
        
        # Selector de carpeta de destino
        layout_destino = QHBoxLayout()
        self.line_destino = QLineEdit()
        self.line_destino.setPlaceholderText("Selecciona la carpeta de destino...")
        self.line_destino.setReadOnly(True)
        btn_destino = QPushButton("Seleccionar...")
        btn_destino.clicked.connect(lambda: self._seleccionar_carpeta(self.line_destino))
        layout_destino.addWidget(self.line_destino)
        layout_destino.addWidget(btn_destino)
        layout_inputs.addLayout(layout_destino)
        
        layout_principal.addWidget(group_inputs)

        self.btn_iniciar = QPushButton("Iniciar Proceso de Mover")
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
        numeros_factura_raw = self.editor_facturas.toPlainText().strip()
        dir_origen = self.line_origen.text()
        dir_destino = self.line_destino.text()

        if not numeros_factura_raw or not dir_origen or not dir_destino:
            QMessageBox.warning(self, "Datos incompletos", "Por favor, complete todos los campos.")
            return

        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "Proceso en curso", "Espere a que termine el proceso actual.")
            return

        numeros_factura = [line.strip() for line in numeros_factura_raw.splitlines() if line.strip()]

        self.btn_iniciar.setText("Procesando...")
        self.btn_iniciar.setEnabled(False)
        self.log_viewer.clear()
        self.log_viewer.append("Iniciando proceso...")
        
        self.thread = QThread()
        self.worker = MovedorCarpetasWorker(numeros_factura, dir_origen, dir_destino)
        self.worker.moveToThread(self.thread)
        
        self.worker.log_generado.connect(self.actualizar_log)
        self.worker.proceso_finalizado.connect(self.finalizar_proceso)
        self.thread.started.connect(self.worker.ejecutar)
        
        self.thread.start()

    def actualizar_log(self, mensaje_html: str):
        self.log_viewer.append(mensaje_html)

    def finalizar_proceso(self):
        self.log_viewer.append("<b>Proceso finalizado.</b>")
        self.btn_iniciar.setText("Iniciar Proceso de Mover")
        self.btn_iniciar.setEnabled(True)
        self.thread.quit()
        self.thread.wait()
        self.thread = None
        self.worker = None
        QMessageBox.information(self, "Proceso Finalizado", "El proceso de mover carpetas ha terminado.")
