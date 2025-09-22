# gui/widget_traer_soportes_ratificadas.py
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QLabel, QLineEdit, 
                               QPushButton, QTextEdit, QMessageBox, QTextBrowser, QFileDialog, QHBoxLayout)
from PySide6.QtCore import QThread, Qt

from logica.workers.buscador_soportes_ratificados_logic import BuscadorSoportesRatificadosWorker

class BuscadorSoportesRatificadosWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.thread = None
        
        # Renombramos init_ui a crear_widgets por consistencia
        self.crear_widgets()

    def crear_widgets(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)

        # 1. Título principal
        label_titulo = QLabel("Buscador de soportes ratificados para aseguradoras")
        label_titulo.setObjectName("AyudaTitulo")
        label_titulo.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(label_titulo)
        
        # 2. Grupo para Entradas de Datos
        group_inputs = QGroupBox("1. Entradas de Datos")
        layout_inputs = QVBoxLayout(group_inputs) # Layout vertical para organizar secciones
        layout_inputs.setSpacing(10)

        # Sección para pegar los números de factura
        self.editor_facturas = QTextEdit()
        self.editor_facturas.setPlaceholderText("Pega aquí la lista de códigos de factura (uno por línea y solo números)...\n336304\n336519\n... ")
        layout_inputs.addWidget(self.editor_facturas)
        
        # Sección para el directorio de búsqueda
        selector_busqueda_layout = QHBoxLayout()
        self.line_busqueda = QLineEdit()
        self.line_busqueda.setPlaceholderText("Seleccione la carpeta de búsqueda...")
        self.line_busqueda.setReadOnly(True)
        btn_busqueda = QPushButton("Seleccionar...")
        btn_busqueda.clicked.connect(lambda: self._seleccionar_carpeta(self.line_busqueda))
        selector_busqueda_layout.addWidget(self.line_busqueda)
        selector_busqueda_layout.addWidget(btn_busqueda)
        layout_inputs.addLayout(selector_busqueda_layout)
        
        # Sección para el directorio de destino
        selector_destino_layout = QHBoxLayout()
        self.line_destino = QLineEdit()
        self.line_destino.setPlaceholderText("Selecciona la carpeta con subcarpetas de FACTURAS de destino...")
        self.line_destino.setReadOnly(True)
        btn_destino = QPushButton("Seleccionar...")
        btn_destino.clicked.connect(lambda: self._seleccionar_carpeta(self.line_destino))
        selector_destino_layout.addWidget(self.line_destino)
        selector_destino_layout.addWidget(btn_destino)
        layout_inputs.addLayout(selector_destino_layout)
        
        layout_principal.addWidget(group_inputs)

        # 3. Botón de Acción Principal
        self.btn_iniciar = QPushButton("Iniciar Búsqueda y Copia")
        self.btn_iniciar.setObjectName("BotonPrincipal")
        self.btn_iniciar.setFixedHeight(40)
        self.btn_iniciar.clicked.connect(self.iniciar_proceso)
        layout_principal.addWidget(self.btn_iniciar)
        
        # 4. Grupo para Resultados (Log)
        group_results = QGroupBox("2. Resultados")
        layout_results = QVBoxLayout(group_results)
        self.log_viewer = QTextBrowser()
        layout_results.addWidget(self.log_viewer)
        layout_principal.addWidget(group_results)

    def _seleccionar_carpeta(self, line_edit_widget):
        """Función genérica para seleccionar una carpeta y ponerla en un QLineEdit."""
        directory = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta")
        if directory:
            line_edit_widget.setText(directory)
            
    def iniciar_proceso(self):
        """Prepara y lanza el hilo de trabajo."""
        numeros_raw = self.editor_facturas.toPlainText().strip()
        dir_busqueda = self.line_busqueda.text()
        dir_destino = self.line_destino.text()

        if not numeros_raw or not dir_busqueda or not dir_destino:
            QMessageBox.warning(self, "Datos incompletos", "Por favor, complete todos los campos.")
            return

        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "Proceso en curso", "Espere a que termine el proceso actual.")
            return

        numeros_factura = [line.strip() for line in numeros_raw.splitlines() if line.strip()]

        self.btn_iniciar.setText("Procesando...")
        self.btn_iniciar.setEnabled(False)
        self.log_viewer.clear()
        
        self.thread = QThread()
        self.worker = BuscadorSoportesRatificadosWorker(numeros_factura, dir_busqueda, dir_destino)
        self.worker.moveToThread(self.thread)
        
        self.worker.log_generado.connect(self.actualizar_log)
        self.worker.proceso_finalizado.connect(self.finalizar_proceso)
        self.thread.started.connect(self.worker.ejecutar)
        
        self.thread.start()

    def actualizar_log(self, mensaje_html: str):
        """Slot que recibe mensajes del worker y los añade al log."""
        self.log_viewer.append(mensaje_html)

    def finalizar_proceso(self):
        """Slot que se ejecuta cuando el worker emite la señal de finalización."""
        self.btn_iniciar.setText("Iniciar Búsqueda y Copia")
        self.btn_iniciar.setEnabled(True)
        self.thread.quit()
        self.thread.wait()
        self.thread = None
        self.worker = None