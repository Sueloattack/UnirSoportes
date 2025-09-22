# gui/widget_buscador.py
import sys
import re
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFrame, QLabel, QLineEdit, QPushButton, 
                               QFileDialog, QMessageBox, QProgressBar, QDialog, QScrollArea, 
                               QGridLayout, QTextEdit)
from PySide6.QtCore import QThread
from logica.logica_buscador import WorkerBuscador

class ResultadosBuscadorDialog(QDialog):
    def __init__(self, resultados, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resultados de la Búsqueda")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        label_titulo = QLabel("Resultados de la Búsqueda y Recopilación")
        label_titulo.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(label_titulo)

        # Resumen
        layout.addWidget(QLabel(f"Códigos buscados: {len(resultados['copiados']) + len(resultados['no_encontrados'])}"))
        layout.addWidget(QLabel(f"Carpetas encontradas y procesadas: {len(resultados['copiados'])}"))
        layout.addWidget(QLabel(f"Códigos sin ninguna carpeta encontrada: {len(resultados['no_encontrados'])}"))
        layout.addWidget(QLabel(f"Códigos con múltiples carpetas encontradas: {len(resultados['duplicados'])}"))

        # Pestañas
        from PySide6.QtWidgets import QTabWidget
        pestanas = QTabWidget()
        layout.addWidget(pestanas)

        # Copiados
        texto_copiados = "\n".join(sorted(list(resultados['copiados'])))
        editor_copiados = QTextEdit(texto_copiados)
        editor_copiados.setReadOnly(True)
        pestanas.addTab(editor_copiados, f"Encontrados y Procesados ({len(resultados['copiados'])})")

        # No Encontrados
        texto_no_encontrados = "\n".join(sorted(list(resultados['no_encontrados'])))
        editor_no_encontrados = QTextEdit(texto_no_encontrados)
        editor_no_encontrados.setReadOnly(True)
        pestanas.addTab(editor_no_encontrados, f"No Encontrados ({len(resultados['no_encontrados'])})")

        # Duplicados
        texto_duplicados = ""
        for codigo, rutas in resultados['duplicados'].items():
            texto_duplicados += f"Código: {codigo}\n"
            for ruta in rutas:
                texto_duplicados += f"  - {ruta}\n"
        editor_duplicados = QTextEdit(texto_duplicados)
        editor_duplicados.setReadOnly(True)
        pestanas.addTab(editor_duplicados, f"Duplicados ({len(resultados['duplicados'])})")

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.accept)
        layout.addWidget(boton_cerrar)

class WidgetBuscador(QWidget):
    def __init__(self):
        super().__init__()
        self.worker_thread = None
        self.worker = None

        self.crear_widgets()

    def crear_widgets(self):
        layout_principal = QVBoxLayout(self)

        # Codigos
        frame_codigos = QFrame()
        frame_codigos.setFrameShape(QFrame.StyledPanel)
        layout_codigos = QVBoxLayout(frame_codigos)
        label_codigos = QLabel("Pega la lista de códigos a buscar:")
        self.text_codigos = QTextEdit()
        layout_codigos.addWidget(label_codigos)
        layout_codigos.addWidget(self.text_codigos)
        layout_principal.addWidget(frame_codigos)

        # Carpetas
        frame_carpetas = QFrame()
        frame_carpetas.setFrameShape(QFrame.StyledPanel)
        layout_carpetas = QGridLayout(frame_carpetas)
        label_busqueda = QLabel("Ruta de búsqueda:")
        self.entry_busqueda = QLineEdit()
        self.entry_busqueda.setReadOnly(True)
        boton_busqueda = QPushButton("Seleccionar...")
        boton_busqueda.clicked.connect(self.seleccionar_carpeta_busqueda)
        label_destino = QLabel("Ruta de destino:")
        self.entry_destino = QLineEdit()
        self.entry_destino.setReadOnly(True)
        boton_destino = QPushButton("Seleccionar...")
        boton_destino.clicked.connect(self.seleccionar_carpeta_destino)
        layout_carpetas.addWidget(label_busqueda, 0, 0)
        layout_carpetas.addWidget(self.entry_busqueda, 0, 1)
        layout_carpetas.addWidget(boton_busqueda, 0, 2)
        layout_carpetas.addWidget(label_destino, 1, 0)
        layout_carpetas.addWidget(self.entry_destino, 1, 1)
        layout_carpetas.addWidget(boton_destino, 1, 2)
        layout_principal.addWidget(frame_carpetas)

        self.boton_procesar = QPushButton("Iniciar Búsqueda")
        self.boton_procesar.setFixedHeight(40)
        self.boton_procesar.clicked.connect(self.iniciar_procesamiento)
        layout_principal.addWidget(self.boton_procesar)

        # Progreso
        frame_progreso = QFrame()
        layout_progreso = QVBoxLayout(frame_progreso)
        self.label_progreso = QLabel("Esperando para iniciar...")
        self.barra_progreso = QProgressBar()
        self.barra_progreso.setValue(0)
        layout_progreso.addWidget(self.label_progreso)
        layout_progreso.addWidget(self.barra_progreso)
        layout_principal.addWidget(frame_progreso)

        layout_principal.addStretch()

    def seleccionar_carpeta_busqueda(self):
        ruta = QFileDialog.getExistingDirectory(self, "Selecciona la carpeta de búsqueda")
        if ruta:
            self.entry_busqueda.setText(ruta)

    def seleccionar_carpeta_destino(self):
        ruta = QFileDialog.getExistingDirectory(self, "Selecciona la carpeta de destino")
        if ruta:
            self.entry_destino.setText(ruta)

    def iniciar_procesamiento(self):
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "Proceso en curso", "Ya hay un proceso en ejecución.")
            return
        
        codigos_texto = self.text_codigos.toPlainText()
        codigos = set(re.findall(r'\d+', codigos_texto))
        carpeta_busqueda = self.entry_busqueda.text()
        carpeta_destino = self.entry_destino.text()

        if not codigos or not carpeta_busqueda or not carpeta_destino:
            QMessageBox.critical(self, "Error", "Por favor, introduce los códigos y selecciona las carpetas.")
            return

        self.boton_procesar.setEnabled(False)
        self.boton_procesar.setText("Procesando...")
        self.barra_progreso.setValue(0)

        self.worker_thread = QThread()
        self.worker = WorkerBuscador(codigos, carpeta_busqueda, carpeta_destino)
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
        self.boton_procesar.setText("Iniciar Búsqueda")

        self.worker_thread.quit()
        self.worker_thread.wait()

        dialogo_resultados = ResultadosBuscadorDialog(resultados, self)
        dialogo_resultados.exec()
