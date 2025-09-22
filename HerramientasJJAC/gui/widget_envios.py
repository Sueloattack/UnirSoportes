# gui/widget_envios.py
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFrame, QLabel, QLineEdit, QPushButton, 
                               QFileDialog, QMessageBox, QProgressBar, QDialog, QScrollArea, 
                               QGridLayout)
from PySide6.QtCore import QThread
from logica.logica_envios import WorkerEnvios

class ResultadosEnviosDialog(QDialog):
    def __init__(self, resultados, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resultados de la Reorganización de Sedes")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        label_titulo = QLabel("Resultados de la Reorganización")
        label_titulo.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(label_titulo)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        widget_contenido = QWidget()
        scroll_area.setWidget(widget_contenido)
        layout_resultados = QVBoxLayout(widget_contenido)

        if resultados['movimientos']:
            label = QLabel(f"MOVIMIENTOS ({len(resultados['movimientos'])})")
            label.setStyleSheet("font-size: 16px; font-weight: bold; color: green;")
            layout_resultados.addWidget(label)
            for item in resultados['movimientos']:
                layout_resultados.addWidget(QLabel(f"✔ Carpeta: '{item['carpeta']}' (Serie: {item['serie']}) movida de '{item['origen']}' a '{item['destino']}'"))

        if resultados['errores']:
            label = QLabel(f"ERRORES ({len(resultados['errores'])})")
            label.setStyleSheet("font-size: 16px; font-weight: bold; color: red;")
            layout_resultados.addWidget(label)
            for item in resultados['errores']:
                layout_resultados.addWidget(QLabel(f"✖ Carpeta: '{item['carpeta']}' | Razón: {item['razon']}"))

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.accept)
        layout.addWidget(boton_cerrar)

class WidgetEnvios(QWidget):
    def __init__(self):
        super().__init__()
        self.worker_thread = None
        self.worker = None

        self.crear_widgets()

    def crear_widgets(self):
        layout_principal = QVBoxLayout(self)

        frame_seleccion = QFrame()
        frame_seleccion.setFrameShape(QFrame.StyledPanel)
        layout_seleccion = QGridLayout(frame_seleccion)
        
        label_raiz = QLabel("Carpeta que contiene 'sede 1' y 'sede 2':")
        self.entry_raiz = QLineEdit()
        self.entry_raiz.setReadOnly(True)
        boton_examinar_raiz = QPushButton("Seleccionar...")
        boton_examinar_raiz.clicked.connect(self.seleccionar_carpeta_raiz)

        layout_seleccion.addWidget(label_raiz, 0, 0)
        layout_seleccion.addWidget(self.entry_raiz, 0, 1)
        layout_seleccion.addWidget(boton_examinar_raiz, 0, 2)
        layout_principal.addWidget(frame_seleccion)

        self.boton_procesar = QPushButton("Iniciar Reorganización de Sedes")
        self.boton_procesar.setFixedHeight(40)
        self.boton_procesar.clicked.connect(self.iniciar_procesamiento)
        layout_principal.addWidget(self.boton_procesar)

        frame_progreso = QFrame()
        layout_progreso = QVBoxLayout(frame_progreso)
        self.label_progreso = QLabel("Esperando para iniciar...")
        self.barra_progreso = QProgressBar()
        self.barra_progreso.setValue(0)
        layout_progreso.addWidget(self.label_progreso)
        layout_progreso.addWidget(self.barra_progreso)
        layout_principal.addWidget(frame_progreso)

        layout_principal.addStretch()

    def seleccionar_carpeta_raiz(self):
        ruta = QFileDialog.getExistingDirectory(self, "Selecciona la carpeta raíz")
        if ruta:
            self.entry_raiz.setText(ruta)

    def iniciar_procesamiento(self):
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "Proceso en curso", "Ya hay un proceso en ejecución.")
            return
        
        carpeta_raiz = self.entry_raiz.text()
        if not carpeta_raiz:
            QMessageBox.critical(self, "Error", "Por favor, selecciona la carpeta raíz.")
            return

        self.boton_procesar.setEnabled(False)
        self.boton_procesar.setText("Procesando...")
        self.barra_progreso.setValue(0)

        self.worker_thread = QThread()
        self.worker = WorkerEnvios(carpeta_raiz)
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
        self.boton_procesar.setText("Iniciar Reorganización de Sedes")

        self.worker_thread.quit()
        self.worker_thread.wait()

        dialogo_resultados = ResultadosEnviosDialog(resultados, self)
        dialogo_resultados.exec()
