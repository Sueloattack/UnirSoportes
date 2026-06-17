# gui/widgets/duplicador_archivos.py
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QGroupBox, QLabel, QFileDialog, QMessageBox, QProgressBar, QTextBrowser)
from PySide6.QtCore import QThread, Qt
from logica.workers.duplicador_archivos_logic import DuplicadorArchivosWorker

class DuplicadorArchivosWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hilo_trabajo = None
        self.worker = None
        self.crear_widgets()

    def crear_widgets(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)

        label_titulo = QLabel("Duplicar archivo en todas las subcarpetas")
        label_titulo.setObjectName("AyudaTitulo")
        label_titulo.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(label_titulo)

        group_inputs = QGroupBox("1. Archivo y Carpeta Raíz Destino")
        layout_inputs = QVBoxLayout(group_inputs)
        layout_inputs.setSpacing(10)

        # Selector de archivo origen
        layout_archivo = QHBoxLayout()
        self.line_archivo = QLineEdit()
        self.line_archivo.setPlaceholderText("Seleccione el archivo que desea duplicar...")
        self.line_archivo.setReadOnly(True)
        btn_archivo = QPushButton("Seleccionar Archivo...")
        btn_archivo.clicked.connect(self._seleccionar_archivo)
        layout_archivo.addWidget(self.line_archivo)
        layout_archivo.addWidget(btn_archivo)
        layout_inputs.addLayout(layout_archivo)

        # Selector de carpeta destino
        layout_destino = QHBoxLayout()
        self.line_destino = QLineEdit()
        self.line_destino.setPlaceholderText("Seleccione la carpeta raíz que contiene las subcarpetas...")
        self.line_destino.setReadOnly(True)
        btn_destino = QPushButton("Seleccionar Carpeta...")
        btn_destino.clicked.connect(self._seleccionar_carpeta)
        layout_destino.addWidget(self.line_destino)
        layout_destino.addWidget(btn_destino)
        layout_inputs.addLayout(layout_destino)

        layout_principal.addWidget(group_inputs)

        layout_botones = QHBoxLayout()
        self.btn_iniciar = QPushButton("Iniciar Duplicación")
        self.btn_iniciar.setObjectName("BotonPrincipal")
        self.btn_iniciar.setFixedHeight(40)
        self.btn_iniciar.clicked.connect(self.iniciar_proceso)
        layout_botones.addWidget(self.btn_iniciar)

        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.setFixedHeight(40)
        self.btn_cancelar.setEnabled(False)
        self.btn_cancelar.clicked.connect(self.cancelar_proceso)
        layout_botones.addWidget(self.btn_cancelar)
        layout_principal.addLayout(layout_botones)

        group_progreso = QGroupBox("2. Progreso")
        layout_progreso = QVBoxLayout(group_progreso)
        self.label_progreso = QLabel("Esperando para iniciar...")
        self.barra_progreso = QProgressBar()
        self.barra_progreso.setValue(0)
        layout_progreso.addWidget(self.label_progreso)
        layout_progreso.addWidget(self.barra_progreso)
        layout_principal.addWidget(group_progreso)

        group_results = QGroupBox("3. Resultados")
        layout_results = QVBoxLayout(group_results)
        self.log_viewer = QTextBrowser()
        layout_results.addWidget(self.log_viewer)
        layout_principal.addWidget(group_results)

        layout_principal.addStretch()

    def _seleccionar_archivo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo a duplicar")
        if file_path:
            self.line_archivo.setText(file_path)

    def _seleccionar_carpeta(self):
        directory = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta raíz de destino")
        if directory:
            self.line_destino.setText(directory)

    def iniciar_proceso(self):
        ruta_archivo = self.line_archivo.text().strip()
        ruta_destino = self.line_destino.text().strip()

        if not ruta_archivo or not ruta_destino:
            QMessageBox.warning(self, "Datos incompletos", "Por favor, complete todos los campos.")
            return

        if self.hilo_trabajo and self.hilo_trabajo.isRunning():
            QMessageBox.warning(self, "Proceso en curso", "Espere a que termine el proceso actual.")
            return

        self.btn_iniciar.setEnabled(False)
        self.btn_cancelar.setEnabled(True)
        self.log_viewer.clear()
        self.barra_progreso.setValue(0)

        self.hilo_trabajo = QThread()
        self.worker = DuplicadorArchivosWorker(ruta_archivo, ruta_destino)
        self.worker.moveToThread(self.hilo_trabajo)

        self.worker.log_generado.connect(self.log_viewer.append)
        self.worker.progreso_actualizado.connect(self.actualizar_progreso)
        self.worker.proceso_finalizado.connect(self.finalizar_proceso)
        self.hilo_trabajo.started.connect(self.worker.ejecutar)

        self.hilo_trabajo.start()

    def actualizar_progreso(self, mensaje, porcentaje):
        self.label_progreso.setText(mensaje)
        self.barra_progreso.setValue(int(porcentaje))

    def finalizar_proceso(self, resultados):
        self.btn_iniciar.setEnabled(True)
        self.btn_cancelar.setEnabled(False)

        num_exitos = len(resultados.get('exitosos', []))
        num_fallidos = len(resultados.get('fallidos', []))

        QMessageBox.information(
            self,
            "Proceso finalizado",
            f"Duplicación completada.\n\nÉxitos: {num_exitos}\nFallos: {num_fallidos}"
        )

        if self.hilo_trabajo:
            self.hilo_trabajo.quit()
            self.hilo_trabajo.wait()
        self.hilo_trabajo = None
        self.worker = None

    def cancelar_proceso(self):
        if self.worker:
            self.worker.cancelar()
            self.log_viewer.append("<b>Cancelación solicitada...</b>")
