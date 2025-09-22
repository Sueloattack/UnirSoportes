# gui/widget_auditor_facturas.py
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QLabel, QLineEdit, QPushButton, 
                               QFileDialog, QMessageBox, QProgressBar, QDialog, QScrollArea, 
                               QGridLayout, QTextEdit, QHBoxLayout)
from PySide6.QtCore import QThread, Qt

from logica.logica_auditor_facturas import WorkerAuditorFacturas

class ResultadosAuditorDialog(QDialog):
    def __init__(self, resultados, worker, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resultados de la Auditoría")
        self.setMinimumSize(800, 600)
        self.resultados = resultados
        self.worker = worker

        layout = QVBoxLayout(self)
        
        label_titulo = QLabel("Resumen Final de la Auditoría")
        label_titulo.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(label_titulo)

        # Resumen
        resumen = self.resultados['resumen']
        for key, value in resumen.items():
            layout.addWidget(QLabel(f"{key.replace('_', ' ').capitalize()}: {value}"))

        # Pestañas para detalles
        from PySide6.QtWidgets import QTabWidget
        pestanas = QTabWidget()
        layout.addWidget(pestanas)

        # Faltantes
        texto_faltantes = "\n".join(self.resultados['facturas_faltantes'])
        editor_faltantes = QTextEdit(texto_faltantes)
        editor_faltantes.setReadOnly(True)
        pestanas.addTab(editor_faltantes, f"Facturas Faltantes ({len(self.resultados['facturas_faltantes'])})")

        # Sobrantes
        texto_sobrantes = "\n".join([f"{num}: {nombre}" for num, nombre in self.resultados['carpetas_sobrantes'].items()])
        self.editor_sobrantes = QTextEdit(texto_sobrantes)
        self.editor_sobrantes.setReadOnly(True)
        pestanas.addTab(self.editor_sobrantes, f"Carpetas Sobrantes ({len(self.resultados['carpetas_sobrantes'])})")

        if self.resultados['carpetas_sobrantes']:
            self.boton_eliminar = QPushButton("Eliminar Carpetas Sobrantes")
            self.boton_eliminar.clicked.connect(self.eliminar_sobrantes)
            layout.addWidget(self.boton_eliminar)

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.accept)
        layout.addWidget(boton_cerrar)

    def eliminar_sobrantes(self):
        confirmacion = QMessageBox.warning(self, "Confirmar Eliminación", 
                                           f"¿Estás seguro de que deseas eliminar {len(self.resultados['carpetas_sobrantes'])} carpetas de forma permanente?",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirmacion == QMessageBox.Yes:
            eliminados, fallidos = self.worker.eliminar_carpetas_sobrantes(self.resultados['carpetas_sobrantes'])
            QMessageBox.information(self, "Resultado de la Eliminación", 
                                    f"Se eliminaron {eliminados} carpetas.\nFallaron {len(fallidos)} eliminaciones.")
            self.editor_sobrantes.clear()
            self.boton_eliminar.setEnabled(False)

class WidgetAuditorFacturas(QWidget):
    def __init__(self):
        super().__init__()
        self.pdf_path = ""
        self.folders_path = ""
        self.worker_thread = None
        self.worker = None

        self.crear_widgets()

    def crear_widgets(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)

        # 1. Título principal de la pestaña
        label_titulo = QLabel("Revisor de facturas y carpetas en la cuenta de cobro")
        label_titulo.setObjectName("AyudaTitulo")
        label_titulo.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(label_titulo)

        # 2. Grupo de Selección de Archivos
        group_seleccion = QGroupBox("1. Archivos de Entrada")
        layout_seleccion = QVBoxLayout(group_seleccion)
        layout_seleccion.setSpacing(10)

        # Selector de archivo PDF
        selector_pdf_layout = QHBoxLayout()
        self.entry_pdf = QLineEdit()
        self.entry_pdf.setPlaceholderText("Seleccione el archivo .PDF de la cuenta de cobro a revisar...")
        self.entry_pdf.setReadOnly(True)
        boton_examinar_pdf = QPushButton("Seleccionar...")
        boton_examinar_pdf.clicked.connect(self.seleccionar_pdf)
        selector_pdf_layout.addWidget(self.entry_pdf)
        selector_pdf_layout.addWidget(boton_examinar_pdf)

        # Selector de carpeta de facturas
        selector_carpetas_layout = QHBoxLayout()
        self.entry_carpetas = QLineEdit()
        self.entry_carpetas.setPlaceholderText("Seleccione la carpeta que contiene las subcarpetas con las facturas...")
        self.entry_carpetas.setReadOnly(True)
        boton_examinar_carpetas = QPushButton("Seleccionar...")
        boton_examinar_carpetas.clicked.connect(self.seleccionar_carpetas)
        selector_carpetas_layout.addWidget(self.entry_carpetas)
        selector_carpetas_layout.addWidget(boton_examinar_carpetas)

        layout_seleccion.addLayout(selector_pdf_layout)
        layout_seleccion.addLayout(selector_carpetas_layout)
        layout_principal.addWidget(group_seleccion)

        # 3. Botón de Acción Principal
        self.boton_procesar = QPushButton("Iniciar Auditoría")
        self.boton_procesar.setObjectName("BotonPrincipal")
        self.boton_procesar.setFixedHeight(40)
        self.boton_procesar.clicked.connect(self.iniciar_procesamiento)
        layout_principal.addWidget(self.boton_procesar)

        # 4. Grupo de Progreso
        frame_progreso = QGroupBox("2. Progreso")
        layout_progreso = QVBoxLayout(frame_progreso)
        self.label_progreso = QLabel("Esperando para iniciar...")
        self.barra_progreso = QProgressBar()
        self.barra_progreso.setValue(0)
        layout_progreso.addWidget(self.label_progreso)
        layout_progreso.addWidget(self.barra_progreso)
        layout_principal.addWidget(frame_progreso)

        layout_principal.addStretch()

    def seleccionar_pdf(self):
        # Usamos QFileDialog.getOpenFileName para seleccionar un solo archivo
        ruta, _ = QFileDialog.getOpenFileName(self, "Selecciona el archivo PDF", "", "PDF Files (*.pdf)")
        if ruta:
            self.pdf_path = ruta
            self.entry_pdf.setText(self.pdf_path)

    def seleccionar_carpetas(self):
        # Usamos QFileDialog.getExistingDirectory para seleccionar una carpeta
        ruta = QFileDialog.getExistingDirectory(self, "Selecciona la carpeta de facturas")
        if ruta:
            self.folders_path = ruta
            self.entry_carpetas.setText(self.folders_path)

    def iniciar_procesamiento(self):
        # (El resto del código de la clase permanece igual, es funcional y robusto)
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "Proceso en curso", "Ya hay un proceso en ejecución.")
            return
        # Usamos self.pdf_path y self.folders_path directamente, ya que se actualizan
        if not self.pdf_path or not self.folders_path:
            QMessageBox.critical(self, "Error", "Por favor, selecciona el archivo PDF y la carpeta de facturas.")
            return

        self.boton_procesar.setEnabled(False)
        self.boton_procesar.setText("Procesando...")
        self.barra_progreso.setValue(0)

        self.worker_thread = QThread()
        self.worker = WorkerAuditorFacturas(self.pdf_path, self.folders_path)
        self.worker.moveToThread(self.worker_thread)

        self.worker.progreso_actualizado.connect(self.actualizar_progreso)
        self.worker.proceso_finalizado.connect(self.proceso_finalizado)
        self.worker_thread.started.connect(self.worker.ejecutar)

        self.worker_thread.start()

    def actualizar_progreso(self, mensaje, porcentaje):
        self.label_progreso.setText(mensaje)
        self.barra_progreso.setValue(int(porcentaje))

    def proceso_finalizado(self, resultados):
        self.label_progreso.setText("Proceso finalizado. Listo para empezar de nuevo.")
        self.boton_procesar.setEnabled(True)
        self.boton_procesar.setText("Iniciar Auditoría")

        self.worker_thread.quit()
        self.worker_thread.wait()

        if 'error' in resultados['resumen']:
            QMessageBox.critical(self, "Error en la Auditoría", resultados['resumen']['error'])
        else:
            dialogo_resultados = ResultadosAuditorDialog(resultados, self.worker, self)
            dialogo_resultados.exec()