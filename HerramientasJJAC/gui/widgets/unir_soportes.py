# gui/widget_unir_soportes.py
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFrame, QLabel, QLineEdit, QPushButton, QHBoxLayout, 
                               QFileDialog, QMessageBox, QProgressBar, QDialog, QScrollArea, QGridLayout, QGroupBox, QTextEdit)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from logica.workers.unir_soportes_logic import UnirSoportesWorker
from logica.workers.mover_respuesta_raiz_logic import MoverRespuestaRaizWorker
from logica.workers.unir_axa_calixto_logic import unir_axa_calixto_logic
from gui.common.componentes_comunes import SelectorCarpeta

# Worker para la nueva funcionalidad de AXA Calixto
class UnirAxaCalixtoWorker(QObject):
    progreso_actualizado = Signal(str, int)
    proceso_finalizado = Signal(str)
    error_ocurrido = Signal(str)

    def __init__(self, dir_origen, dir_destino):
        super().__init__()
        self.dir_origen = dir_origen
        self.dir_destino = dir_destino
        self.running = True

    def ejecutar(self):
        try:
            # Conectamos las señales del worker a los métodos de la lógica
            unir_axa_calixto_logic(
                self.dir_origen,
                self.dir_destino,
                self.progreso_actualizado,
                self.proceso_finalizado,
                self.error_ocurrido
            )
        except Exception as e:
            self.error_ocurrido.emit(str(e))

    def stop(self):
        self.running = False

class ResultadosDialog(QDialog):
    """
    Ventana de resultados que muestra los éxitos y fallos del proceso en un formato que permite copiar.
    """
    def __init__(self, resultados, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resultados del Procesamiento")
        self.setMinimumSize(800, 600)

        layout = QVBoxLayout(self)
        
        label_titulo = QLabel("Resultados del Procesamiento")
        label_titulo.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(label_titulo)

        resultados_texto = QTextEdit()
        resultados_texto.setReadOnly(True)
        
        html_content = ""

        # Sección de Éxitos
        if resultados.get('exitosos'):
            html_content += f'<h2 style="font-size: 16px; font-weight: bold; color: #2ecc71;">ÉXITO ({len(resultados["exitosos"])})</h2>'
            html_content += '<div style="color: #ecf0f1;">'
            for item in resultados['exitosos']:
                html_content += f"✔ {item['carpeta']}: {item['razon']}<br>"
            html_content += '</div>'

        # Sección de Errores
        if resultados.get('fallidos'):
            html_content += f'<h2 style="font-size: 16px; font-weight: bold; color: #e74c3c;">ERRORES ({len(resultados["fallidos"])})</h2>'
            html_content += '<div style="color: #ecf0f1;">'
            for item in resultados['fallidos']:
                html_content += f"✖ {item['carpeta']}: {item['razon']}<br>"
            html_content += '</div>'
        
        resultados_texto.setStyleSheet("background-color: #2c3e50; color: #ecf0f1; border: 1px solid #34495e;")
        resultados_texto.setHtml(html_content)
        layout.addWidget(resultados_texto)

        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.clicked.connect(self.accept)
        layout.addWidget(boton_cerrar)

class UnirSoportesWidget(QWidget):
    """
    Widget principal para la herramienta "Unir Soportes", con layout actualizado.
    """
    def __init__(self):
        super().__init__()
        self.worker_thread = None
        self.worker = None
        self.mover_worker_thread = None
        self.mover_worker = None
        self.axa_worker_thread = None
        self.axa_worker = None
        self.modo_procesamiento = "Aseguradoras"

        self.crear_widgets()

    def crear_widgets(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)

        label_titulo = QLabel("Unir Soportes y Acciones Adicionales")
        label_titulo.setObjectName("AyudaTitulo")
        label_titulo.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(label_titulo)

        group_seleccion = QGroupBox("1. Selección de Carpeta de Origen")
        layout_seleccion = QVBoxLayout(group_seleccion)
        
        self.selector_origen = SelectorCarpeta("Carpeta de Origen")
        
        layout_seleccion.addWidget(self.selector_origen)
        layout_principal.addWidget(group_seleccion)

        group_acciones = QGroupBox("2. Acciones")
        layout_acciones_grid = QGridLayout(group_acciones)
        
        self.boton_unir_axa = QPushButton("Unir AXA Calixto")
        self.boton_unir_axa.clicked.connect(self.iniciar_union_axa)
        
        self.boton_mover_respuestas = QPushButton("Mover Respuestas a Raíz")
        self.boton_mover_respuestas.clicked.connect(self.iniciar_movimiento_respuestas)

        self.boton_procesar = QPushButton("Iniciar Unión Estándar")
        self.boton_procesar.setObjectName("BotonPrincipal")
        self.boton_procesar.setFixedHeight(40)
        self.boton_procesar.clicked.connect(self.iniciar_procesamiento)
        
        self.boton_aseguradoras = QPushButton("Modo Aseguradoras")
        self.boton_aseguradoras.setCheckable(True)
        self.boton_aseguradoras.setChecked(True)
        
        self.boton_adres = QPushButton("Modo ADRES")
        self.boton_adres.setCheckable(True)

        self.boton_aseguradoras.clicked.connect(lambda: self.seleccionar_modo("Aseguradoras"))
        self.boton_adres.clicked.connect(lambda: self.seleccionar_modo("ADRES"))

        layout_acciones_grid.addWidget(self.boton_unir_axa, 0, 0)
        layout_acciones_grid.addWidget(self.boton_mover_respuestas, 0, 1)
        layout_acciones_grid.addWidget(self.boton_procesar, 1, 0, 1, 2)
        layout_acciones_grid.addWidget(self.boton_aseguradoras, 2, 0)
        layout_acciones_grid.addWidget(self.boton_adres, 2, 1)
        
        layout_principal.addWidget(group_acciones)
        
        frame_progreso = QGroupBox("3. Progreso")
        layout_progreso = QVBoxLayout(frame_progreso)
        self.label_progreso = QLabel("Esperando para iniciar...")
        self.barra_progreso = QProgressBar()
        self.barra_progreso.setValue(0)
        layout_progreso.addWidget(self.label_progreso)
        layout_progreso.addWidget(self.barra_progreso)
        layout_principal.addWidget(frame_progreso)

        layout_principal.addStretch()

    def seleccionar_modo(self, modo):
        self.modo_procesamiento = modo
        if modo == "Aseguradoras":
            self.boton_aseguradoras.setChecked(True)
            self.boton_adres.setChecked(False)
        else:
            self.boton_adres.setChecked(True)
            self.boton_aseguradoras.setChecked(False)

    def es_proceso_en_ejecucion(self):
        if (self.worker_thread and self.worker_thread.isRunning()) or \
           (self.mover_worker_thread and self.mover_worker_thread.isRunning()) or \
           (self.axa_worker_thread and self.axa_worker_thread.isRunning()):
            QMessageBox.warning(self, "Proceso en curso", "Ya hay un proceso en ejecución. Por favor, espere a que termine.")
            return True
        return False

    def iniciar_procesamiento(self):
        if self.es_proceso_en_ejecucion(): return
        
        ruta_origen = self.selector_origen.path()
        if not ruta_origen:
            QMessageBox.critical(self, "Error", "Por favor, selecciona una carpeta de origen para la unión estándar.")
            return

        self.deshabilitar_botones()
        self.boton_procesar.setText("Procesando...")
        
        self.worker_thread = QThread()
        self.worker = UnirSoportesWorker(ruta_origen, self.modo_procesamiento)
        self.worker.moveToThread(self.worker_thread)
        self.worker.progreso_actualizado.connect(self.actualizar_progreso_simple)
        self.worker.proceso_finalizado.connect(self.proceso_finalizado_estandar)
        self.worker_thread.started.connect(self.worker.ejecutar)
        self.worker_thread.start()

    def iniciar_movimiento_respuestas(self):
        if self.es_proceso_en_ejecucion(): return

        ruta_origen = self.selector_origen.path()
        if not ruta_origen:
            QMessageBox.critical(self, "Error", "Por favor, selecciona una carpeta de origen para mover las respuestas.")
            return

        self.deshabilitar_botones()
        self.boton_mover_respuestas.setText("Moviendo...")

        self.mover_worker_thread = QThread()
        self.mover_worker = MoverRespuestaRaizWorker(ruta_origen)
        self.mover_worker.moveToThread(self.mover_worker_thread)
        self.mover_worker.progreso_actualizado.connect(self.actualizar_progreso_simple)
        self.mover_worker.proceso_finalizado.connect(self.proceso_movimiento_finalizado)
        self.mover_worker_thread.started.connect(self.mover_worker.ejecutar)
        self.mover_worker_thread.start()

    def iniciar_union_axa(self):
        if self.es_proceso_en_ejecucion(): return

        dir_origen = self.selector_origen.path()
        if not dir_origen:
            QMessageBox.critical(self, "Error", "Debe seleccionar la carpeta de origen que contiene los archivos .zip.")
            return

        # Preguntar por la carpeta de destino justo antes de empezar
        dir_destino = QFileDialog.getExistingDirectory(self, "Seleccione la carpeta donde se guardarán los PDFs unidos")
        if not dir_destino:
            # El usuario canceló la selección de carpeta
            return

        self.deshabilitar_botones()
        self.boton_unir_axa.setText("Procesando AXA...")

        self.axa_worker_thread = QThread()
        self.axa_worker = UnirAxaCalixtoWorker(dir_origen, dir_destino)
        self.axa_worker.moveToThread(self.axa_worker_thread)
        self.axa_worker.progreso_actualizado.connect(self.actualizar_progreso_axa)
        self.axa_worker.proceso_finalizado.connect(self.proceso_axa_finalizado)
        self.axa_worker.error_ocurrido.connect(self.proceso_axa_error)
        self.axa_worker_thread.started.connect(self.axa_worker.ejecutar)
        self.axa_worker_thread.start()


    def actualizar_progreso_simple(self, nombre_carpeta, porcentaje):
        self.label_progreso.setText(f"Procesando: {nombre_carpeta}...")
        self.barra_progreso.setValue(int(porcentaje))

    def actualizar_progreso_axa(self, mensaje, porcentaje):
        self.label_progreso.setText(mensaje)
        self.barra_progreso.setValue(int(porcentaje))
        
    def proceso_finalizado_estandar(self, resultados):
        self.habilitar_botones()
        self.label_progreso.setText("Proceso finalizado. Listo para empezar de nuevo.")
        self.worker_thread.quit()
        self.worker_thread.wait()
        dialogo_resultados = ResultadosDialog(resultados, self)
        dialogo_resultados.exec()

    def proceso_movimiento_finalizado(self, resultados):
        self.habilitar_botones()
        self.label_progreso.setText("Movimiento de respuestas finalizado.")
        self.mover_worker_thread.quit()
        self.mover_worker_thread.wait()
        QMessageBox.information(self, "Resultado del Movimiento", f"Se movieron {len(resultados.get('movidos', []))} archivos y fallaron {len(resultados.get('errores', []))}.")

    def proceso_axa_finalizado(self, mensaje):
        self.habilitar_botones()
        self.label_progreso.setText("Proceso de AXA Calixto finalizado.")
        self.barra_progreso.setValue(100)
        QMessageBox.information(self, "Éxito", mensaje)
        self.axa_worker_thread.quit()
        self.axa_worker_thread.wait()

    def proceso_axa_error(self, error_msg):
        self.habilitar_botones()
        self.label_progreso.setText("Error en el proceso de AXA Calixto.")
        QMessageBox.critical(self, "Error en Proceso AXA", error_msg)
        if self.axa_worker_thread:
            self.axa_worker_thread.quit()
            self.axa_worker_thread.wait()
            
    def deshabilitar_botones(self):
        self.boton_unir_axa.setEnabled(False)
        self.boton_mover_respuestas.setEnabled(False)
        self.boton_procesar.setEnabled(False)

    def habilitar_botones(self):
        self.boton_unir_axa.setEnabled(True)
        self.boton_mover_respuestas.setEnabled(True)
        self.boton_procesar.setEnabled(True)
        self.boton_unir_axa.setText("Unir AXA Calixto")
        self.boton_mover_respuestas.setText("Mover Respuestas a Raíz")
        self.boton_procesar.setText("Iniciar Unión Estándar")