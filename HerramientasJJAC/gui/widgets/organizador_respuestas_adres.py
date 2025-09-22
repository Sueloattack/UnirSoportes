# gui/widget_adres.py
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QLabel, QLineEdit, 
                               QPushButton, QFileDialog, QMessageBox, QProgressBar, 
                               QDialog, QScrollArea, QHBoxLayout)
from PySide6.QtCore import QThread, Qt

# Asegúrate de que el nombre del worker que importas es correcto
from logica.workers.organizador_respuestas_adres_logic import OrganizadorRespuestasAdresWorker

class ResultadosAdresDialog(QDialog):
    """
    Ventana de resultados que muestra el resultado del procesamiento ADRES.
    (Tu código original para esta clase)
    """
    def __init__(self, resultados, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resultados del Procesamiento ADRES")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        label_titulo = QLabel("Resultados del Procesamiento")
        label_titulo.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(label_titulo)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        widget_contenido = QWidget()
        scroll_area.setWidget(widget_contenido)
        layout_resultados = QVBoxLayout(widget_contenido)

        if resultados['exitosos']:
            label = QLabel(f"ÉXITO ({len(resultados['exitosos'])})")
            label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2ecc71;")
            layout_resultados.addWidget(label)
            for item in resultados['exitosos']:
                layout_resultados.addWidget(QLabel(f"✔ Carpeta: {item['carpeta']} -> Se añadió '{item['respuesta_procesada']}'"))

        if resultados['ya_tenian_respuesta']:
            label = QLabel(f"YA TENÍAN RESPUESTA ({len(resultados['ya_tenian_respuesta'])})")
            label.setStyleSheet("font-size: 16px; font-weight: bold; color: #3498db;")
            layout_resultados.addWidget(label)
            for item in resultados['ya_tenian_respuesta']:
                layout_resultados.addWidget(QLabel(f"- Carpeta: {item['carpeta']}"))

        if resultados['sin_respuesta_encontrada']:
            label = QLabel(f"SIN RESPUESTA ENCONTRADA ({len(resultados['sin_respuesta_encontrada'])})")
            label.setStyleSheet("font-size: 16px; font-weight: bold; color: #f39c12;")
            layout_resultados.addWidget(label)
            for item in resultados['sin_respuesta_encontrada']:
                layout_resultados.addWidget(QLabel(f"- Carpeta: {item['carpeta']}"))

        if resultados['fallidos']:
            label = QLabel(f"ERRORES ({len(resultados['fallidos'])})")
            label.setStyleSheet("font-size: 16px; font-weight: bold; color: #e74c3c;")
            layout_resultados.addWidget(label)
            for item in resultados['fallidos']:
                layout_resultados.addWidget(QLabel(f"✖ Carpeta: {item['carpeta']} | Razón: {item['razon']}"))

        if 'sobrantes' in resultados and resultados['sobrantes']: # Verificación de existencia de la clave
            label = QLabel(f"RESPUESTAS SOBRANTES ({len(resultados['sobrantes'])})")
            label.setStyleSheet("font-size: 16px; font-weight: bold; color: #9b59b6;")
            layout_resultados.addWidget(label)
            for codigo, archivo in resultados['sobrantes'].items():
                layout_resultados.addWidget(QLabel(f"- {archivo} (código: {codigo})"))

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.accept)
        layout.addWidget(boton_cerrar)

class OrganizadorRespuestasAdresWidget(QWidget):
    """
    Widget principal para la herramienta ADRES, con layout unificado.
    """
    def __init__(self):
        super().__init__()
        self.ruta_raiz = ""
        self.ruta_respuestas = ""
        self.mover_archivos = True
        self.worker_thread = None
        self.worker = None

        self.crear_widgets()

    def crear_widgets(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)

        # 1. Título principal de la pestaña
        label_titulo = QLabel("Organizador de respuestas glosas ADRES")
        label_titulo.setObjectName("AyudaTitulo")
        label_titulo.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(label_titulo)

        # 2. Grupo de Selección de Carpetas
        group_seleccion = QGroupBox("1. Selección de Carpetas")
        layout_seleccion = QVBoxLayout(group_seleccion)
        layout_seleccion.setSpacing(10)
        
        selector_raiz_layout = QHBoxLayout()
        self.entry_raiz = QLineEdit()
        self.entry_raiz.setPlaceholderText("Seleccione la carpeta con las subcarpetas de las FACTURAS...")
        self.entry_raiz.setReadOnly(True)
        boton_examinar_raiz = QPushButton("Seleccionar...")
        boton_examinar_raiz.clicked.connect(self.seleccionar_carpeta_raiz)
        selector_raiz_layout.addWidget(self.entry_raiz)
        selector_raiz_layout.addWidget(boton_examinar_raiz)

        selector_respuestas_layout = QHBoxLayout()
        self.entry_respuestas = QLineEdit()
        self.entry_respuestas.setPlaceholderText("Seleccione la carpeta con las RESPUESTAS glosas...")
        self.entry_respuestas.setReadOnly(True)
        boton_examinar_respuestas = QPushButton("Seleccionar...")
        boton_examinar_respuestas.clicked.connect(self.seleccionar_carpeta_respuestas)
        selector_respuestas_layout.addWidget(self.entry_respuestas)
        selector_respuestas_layout.addWidget(boton_examinar_respuestas)

        layout_seleccion.addLayout(selector_raiz_layout)
        layout_seleccion.addLayout(selector_respuestas_layout)
        layout_principal.addWidget(group_seleccion)

        # 3. Grupo de Acción a Realizar
        group_accion = QGroupBox("2. Acción a Realizar")
        layout_accion_interno = QHBoxLayout(group_accion)

        self.boton_mover = QPushButton("Mover archivos")
        self.boton_mover.setCheckable(True)
        self.boton_mover.setChecked(True)
        self.boton_mover.clicked.connect(lambda: self.seleccionar_accion("mover"))

        self.boton_copiar = QPushButton("Copiar archivos")
        self.boton_copiar.setCheckable(True)
        self.boton_copiar.clicked.connect(lambda: self.seleccionar_accion("copiar"))
        
        layout_accion_interno.addWidget(self.boton_mover)
        layout_accion_interno.addWidget(self.boton_copiar)
        layout_principal.addWidget(group_accion)
        
        # 4. Botón de Proceso
        self.boton_procesar = QPushButton("Iniciar Procesamiento ADRES")
        self.boton_procesar.setObjectName("BotonPrincipal")
        self.boton_procesar.setFixedHeight(40)
        self.boton_procesar.clicked.connect(self.iniciar_procesamiento)
        layout_principal.addWidget(self.boton_procesar)
        
        # 5. Grupo de Progreso
        frame_progreso = QGroupBox("3. Progreso")
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
            self.ruta_raiz = ruta
            self.entry_raiz.setText(self.ruta_raiz)

    def seleccionar_carpeta_respuestas(self):
        ruta = QFileDialog.getExistingDirectory(self, "Selecciona la carpeta de respuestas")
        if ruta:
            self.ruta_respuestas = ruta
            self.entry_respuestas.setText(self.ruta_respuestas)

    def seleccionar_accion(self, modo):
        if modo == "mover":
            self.mover_archivos = True
            self.boton_mover.setChecked(True)
            self.boton_copiar.setChecked(False)
        elif modo == "copiar":
            self.mover_archivos = False
            self.boton_copiar.setChecked(True)
            self.boton_mover.setChecked(False)

    def iniciar_procesamiento(self):
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "Proceso en curso", "Ya hay un proceso en ejecución.")
            return
        if not self.ruta_raiz or not self.ruta_respuestas:
            QMessageBox.critical(self, "Error", "Por favor, selecciona ambas carpetas primero.")
            return

        self.boton_procesar.setEnabled(False)
        self.boton_procesar.setText("Procesando...")
        self.barra_progreso.setValue(0)

        self.worker_thread = QThread()
        self.worker = OrganizadorRespuestasAdresWorker(self.ruta_raiz, self.ruta_respuestas, self.mover_archivos)
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
        self.boton_procesar.setText("Iniciar Procesamiento ADRES")

        self.worker_thread.quit()
        self.worker_thread.wait()

        dialogo_resultados = ResultadosAdresDialog(resultados, self)
        dialogo_resultados.exec()