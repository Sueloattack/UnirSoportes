# gui/widget_auditor_facturas.py
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QLabel, QLineEdit, QPushButton, 
                               QFileDialog, QMessageBox, QProgressBar, QDialog, QScrollArea, 
                               QGridLayout, QTextEdit, QHBoxLayout)
from PySide6.QtCore import QThread, Qt

from logica.workers.auditor_cuentas_cobro_logic import AuditorCuentasCobroWorker

class ResultadosAuditorDialog(QDialog):
    def __init__(self, resultados, worker, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resultados de la Auditoría")
        self.setMinimumSize(800, 600)
        self.resultados = resultados
        self.worker = worker

        # Layout principal
        layout = QVBoxLayout(self)
        
        # Título
        label_titulo = QLabel("Resumen Final de la Auditoría")
        label_titulo.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(label_titulo)

        # Área de scroll para los resultados
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        widget_contenido = QWidget()
        scroll_area.setWidget(widget_contenido)
        layout_resultados = QVBoxLayout(widget_contenido)

        # --- Sección de Resumen ---
        resumen = self.resultados.get('resumen', {})
        if resumen:
            label_resumen_titulo = QLabel("RESUMEN GENERAL")
            label_resumen_titulo.setStyleSheet("font-size: 16px; font-weight: bold; color: #2ecc71;") # Verde
            layout_resultados.addWidget(label_resumen_titulo)

            # Sub-sección: Datos del PDF
            label_sub_pdf = QLabel("Datos del PDF")
            label_sub_pdf.setStyleSheet("font-weight: bold; color: #3498db;") # Azul
            layout_resultados.addWidget(label_sub_pdf)
            
            pdf_items = {
                'informe': "Informe PDF",
                'total_glosas': "Total de glosas en PDF",
                'total_facturas_unicas': "Facturas únicas en PDF"
            }
            for key, text in pdf_items.items():
                if key in resumen:
                    label_item = QLabel(f"  - {text}: {resumen[key]}")
                    label_item.setStyleSheet("color: #ecf0f1;")
                    layout_resultados.addWidget(label_item)

            # Sub-sección: Análisis de Carpetas
            label_sub_carpetas = QLabel("Análisis de Carpetas")
            label_sub_carpetas.setStyleSheet("font-weight: bold; color: #3498db;") # Azul
            layout_resultados.addWidget(label_sub_carpetas)

            carpetas_items = {
                'carpetas_en_disco': "Carpetas encontradas",
                'facturas_con_carpeta': "Facturas con carpeta",
                'facturas_faltantes': "Facturas sin carpeta",
                'carpetas_sobrantes': "Carpetas sobrantes"
            }
            for key, text in carpetas_items.items():
                if key in resumen:
                    label_item = QLabel(f"  - {text}: {resumen[key]}")
                    label_item.setStyleSheet("color: #ecf0f1;")
                    layout_resultados.addWidget(label_item)

        # --- Sección de Facturas Faltantes ---
        facturas_faltantes = self.resultados.get('facturas_faltantes', [])
        if facturas_faltantes:
            label_faltantes = QLabel(f"FACTURAS FALTANTES EN CARPETAS ({len(facturas_faltantes)})")
            label_faltantes.setStyleSheet("font-size: 16px; font-weight: bold; color: #e74c3c;") # Rojo
            layout_resultados.addWidget(label_faltantes)
            for item in facturas_faltantes:
                label_item = QLabel(f"✖ {item}")
                label_item.setStyleSheet("color: #ecf0f1;")
                layout_resultados.addWidget(label_item)

        # --- Sección de Carpetas Sobrantes ---
        carpetas_sobrantes = self.resultados.get('carpetas_sobrantes', {})
        if carpetas_sobrantes:
            label_sobrantes = QLabel(f"CARPETAS SOBRANTES ({len(carpetas_sobrantes)})")
            label_sobrantes.setStyleSheet("font-size: 16px; font-weight: bold; color: #f39c12;") # Naranja
            layout_resultados.addWidget(label_sobrantes)
            
            self.labels_sobrantes = {}
            for num, nombre in carpetas_sobrantes.items():
                label_item = QLabel(f"✖ {num}: {nombre}")
                label_item.setStyleSheet("color: #ecf0f1;")
                layout_resultados.addWidget(label_item)
                self.labels_sobrantes[num] = label_item

        layout_resultados.addStretch()

        # --- Botones de Acción ---
        layout_botones = QHBoxLayout()
        
        if self.resultados.get('carpetas_sobrantes'):
            self.boton_eliminar = QPushButton("Eliminar Sobrantes")
            self.boton_eliminar.setObjectName("BotonPeligro") # Asignar nombre de objeto para QSS
            self.boton_eliminar.clicked.connect(self.eliminar_sobrantes)
            layout_botones.addWidget(self.boton_eliminar)

        layout_botones.addStretch()
        
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.setObjectName("BotonNeutral") # Asignar nombre de objeto para QSS
        boton_cerrar.clicked.connect(self.accept)
        layout_botones.addWidget(boton_cerrar)
        
        layout.addLayout(layout_botones)

    def eliminar_sobrantes(self):
        carpetas_a_eliminar = self.resultados.get('carpetas_sobrantes', {})
        if not carpetas_a_eliminar:
            QMessageBox.information(self, "Información", "No hay carpetas sobrantes para eliminar.")
            return

        confirmacion = QMessageBox.warning(self, "Confirmar Eliminación", 
                                           f"¿Estás seguro de que deseas eliminar {len(carpetas_a_eliminar)} carpetas de forma permanente?",
                                           QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if confirmacion == QMessageBox.Yes:
            eliminados, fallidos = self.worker.eliminar_carpetas_sobrantes(carpetas_a_eliminar)
            
            # Actualizar la UI
            if eliminados:
                # Eliminar las etiquetas de las carpetas que se borraron con éxito
                for num_factura in eliminados:
                    if num_factura in self.labels_sobrantes:
                        self.labels_sobrantes[num_factura].setText(f"✔ {self.labels_sobrantes[num_factura].text().strip('✖ ')} (Eliminada)")
                        self.labels_sobrantes[num_factura].setStyleSheet("color: #2ecc71;") # Verde
            
            self.boton_eliminar.setEnabled(False)
            self.boton_eliminar.setText("Sobrantes Eliminados")

            # Mensaje final
            QMessageBox.information(self, "Resultado de la Eliminación", 
                                    f"Se eliminaron {len(eliminados)} carpetas.\nFallaron {len(fallidos)} eliminaciones.")

class AuditorCuentasCobroWidget(QWidget):
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
        self.worker = AuditorCuentasCobroWorker(self.pdf_path, self.folders_path)
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