# gui/widget_unir_soportes.py
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFrame, QLabel, QLineEdit, QPushButton, QHBoxLayout, 
                               QFileDialog, QMessageBox, QProgressBar, QDialog, QScrollArea, QGridLayout, QGroupBox)
from PySide6.QtCore import Qt, QThread
from logica.workers.unir_soportes_logic import UnirSoportesWorker
from gui.common.componentes_comunes import SelectorCarpeta

class ResultadosDialog(QDialog):
    """
    Ventana de resultados que muestra los éxitos y fallos del proceso.
    """
    def __init__(self, resultados, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resultados del Procesamiento")
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

        # Sección de Éxitos
        if resultados['exitosos']:
            label_exitos = QLabel(f"ÉXITO ({len(resultados['exitosos'])})")
            label_exitos.setStyleSheet("font-size: 16px; font-weight: bold; color: #2ecc71;") # Verde brillante
            layout_resultados.addWidget(label_exitos)
            for item in resultados['exitosos']:
                label_item = QLabel(f"✔ {item['carpeta']}: {item['razon']}")
                label_item.setStyleSheet("color: #ecf0f1;") # Blanco roto
                layout_resultados.addWidget(label_item)

        # Sección de Errores
        if resultados['fallidos']:
            label_fallos = QLabel(f"ERRORES ({len(resultados['fallidos'])})")
            label_fallos.setStyleSheet("font-size: 16px; font-weight: bold; color: #e74c3c;") # Rojo brillante
            layout_resultados.addWidget(label_fallos)
            for item in resultados['fallidos']:
                label_item = QLabel(f"✖ {item['carpeta']}: {item['razon']}")
                label_item.setStyleSheet("color: #ecf0f1;") # Blanco roto
                layout_resultados.addWidget(label_item)

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.accept)
        layout.addWidget(boton_cerrar)

class UnirSoportesWidget(QWidget):
    """
    Widget principal para la herramienta "Unir Soportes", con layout actualizado.
    """
    def __init__(self):
        super().__init__()
        self.ruta_seleccionada = ""
        self.modo_procesamiento = "Aseguradoras"
        self.worker_thread = None
        self.worker = None

        self.crear_widgets()

    def crear_widgets(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)

        # 1. Título principal de la pestaña
        label_titulo = QLabel("Unir Soportes para radicar")
        label_titulo.setObjectName("AyudaTitulo")
        label_titulo.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(label_titulo)

        # 2. Grupo de Selección de Carpetas
        group_seleccion = QGroupBox("1. Selección de Carpetas")
        layout_seleccion = QHBoxLayout(group_seleccion)
        
        self.entry_carpeta = QLineEdit()
        self.entry_carpeta.setPlaceholderText("Seleccione la carpeta de la cuenta de cobro...")
        self.entry_carpeta.setReadOnly(True)
        boton_examinar = QPushButton("Seleccionar...")
        boton_examinar.clicked.connect(self.seleccionar_carpeta)

        layout_seleccion.addWidget(self.entry_carpeta)
        layout_seleccion.addWidget(boton_examinar)
        layout_principal.addWidget(group_seleccion)
        
        # 3. Grupo de Modo de Operación
        group_modo = QGroupBox("2. Modo de Operación")
        layout_modo = QHBoxLayout(group_modo)

        self.boton_aseguradoras = QPushButton("Aseguradoras")
        self.boton_aseguradoras.setCheckable(True)
        self.boton_aseguradoras.setChecked(True)
        self.boton_adres = QPushButton("ADRES")
        self.boton_adres.setCheckable(True)

        self.boton_aseguradoras.clicked.connect(lambda: self.seleccionar_modo("Aseguradoras"))
        self.boton_adres.clicked.connect(lambda: self.seleccionar_modo("ADRES"))
        
        # Los botones se expandirán para llenar el espacio
        layout_modo.addWidget(self.boton_aseguradoras)
        layout_modo.addWidget(self.boton_adres)
        layout_principal.addWidget(group_modo)
        
        # 4. Botón de Proceso
        self.boton_procesar = QPushButton("Iniciar Proceso de Unión")
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

    def seleccionar_carpeta(self):
        ruta = QFileDialog.getExistingDirectory(self, "Selecciona la carpeta raíz de la Cuenta de Cobro")
        if ruta:
            self.ruta_seleccionada = ruta
            self.entry_carpeta.setText(self.ruta_seleccionada)

    def seleccionar_modo(self, modo):
        self.modo_procesamiento = modo
        if modo == "Aseguradoras":
            self.boton_aseguradoras.setChecked(True)
            self.boton_adres.setChecked(False)
        else: # ADRES
            self.boton_adres.setChecked(True)
            self.boton_aseguradoras.setChecked(False)

    def iniciar_procesamiento(self):
        if self.worker_thread and self.worker_thread.isRunning():
            QMessageBox.warning(self, "Proceso en curso", "Ya hay un proceso en ejecución.")
            return
        if not self.ruta_seleccionada:
            QMessageBox.critical(self, "Error", "Por favor, selecciona una carpeta primero.")
            return

        self.boton_procesar.setEnabled(False)
        self.boton_procesar.setText("Procesando...")
        self.barra_progreso.setValue(0)

        self.worker_thread = QThread()
        self.worker = UnirSoportesWorker(self.ruta_seleccionada, self.modo_procesamiento)
        self.worker.moveToThread(self.worker_thread)

        self.worker.progreso_actualizado.connect(self.actualizar_progreso)
        self.worker.proceso_finalizado.connect(self.proceso_finalizado)
        self.worker_thread.started.connect(self.worker.ejecutar)

        self.worker_thread.start()

    def actualizar_progreso(self, nombre_carpeta, porcentaje):
        self.label_progreso.setText(f"Procesando: {nombre_carpeta}...")
        self.barra_progreso.setValue(int(porcentaje))

    def proceso_finalizado(self, resultados):
        self.label_progreso.setText("Proceso finalizado. Listo para empezar de nuevo.")
        self.boton_procesar.setEnabled(True)
        self.boton_procesar.setText("Iniciar Proceso de Unión")

        self.worker_thread.quit()
        self.worker_thread.wait()

        dialogo_resultados = ResultadosDialog(resultados, self)
        dialogo_resultados.exec()