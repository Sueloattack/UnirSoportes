# gui/widgets/renombrador.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QGroupBox
from PySide6.QtCore import QThread
from gui.common.componentes_comunes import crear_selector_carpeta, setup_logging_browser
from logica.workers.renombrador_logic import RenombradorWorker

class RenombradorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hilo_trabajo = None
        self.worker = None
        
        # Paleta de colores para logs
        self.color_exito = "#2ecc71"
        self.color_error = "#e74c3c"
        self.color_advertencia = "#f39c12"
        self.color_info = "#3498db"

        self.init_ui()

    def init_ui(self):
        layout_principal = QVBoxLayout(self)

        # --- Selector de Carpeta --- #
        self.ruta_carpeta_line_edit, selector_carpeta_layout = crear_selector_carpeta(
            "Carpeta Raíz:", 
            "Seleccionar Carpeta Raíz",
            self.habilitar_botones
        )
        layout_principal.addLayout(selector_carpeta_layout)

        # --- Grupo de Acciones --- #
        grupo_acciones = QGroupBox("Acciones de Renombrado")
        layout_acciones = QHBoxLayout()
        
        self.boton_escolar = QPushButton("Escolar")
        self.boton_devolucion = QPushButton("Devolución")
        self.boton_glosa = QPushButton("Glosa")
        self.boton_revertir_escolar = QPushButton("Revertir Renombrado Escolar")

        self.botones_modo = {
            'escolar': self.boton_escolar,
            'devolucion': self.boton_devolucion,
            'glosa': self.boton_glosa,
            'revertir_escolar': self.boton_revertir_escolar
        }

        self.boton_escolar.clicked.connect(lambda: self.iniciar_proceso('escolar'))
        self.boton_devolucion.clicked.connect(lambda: self.iniciar_proceso('devolucion'))
        self.boton_glosa.clicked.connect(lambda: self.iniciar_proceso('glosa'))
        self.boton_revertir_escolar.clicked.connect(lambda: self.iniciar_proceso('revertir_escolar'))

        self.boton_revertir_escolar.setStyleSheet(f"background-color: {self.color_error}; color: white;")

        layout_acciones.addWidget(self.boton_escolar)
        layout_acciones.addWidget(self.boton_devolucion)
        layout_acciones.addWidget(self.boton_glosa)
        layout_acciones.addWidget(self.boton_revertir_escolar)
        grupo_acciones.setLayout(layout_acciones)
        layout_principal.addWidget(grupo_acciones)

        # --- Botón de Cancelar --- #
        self.boton_cancelar = QPushButton("Cancelar Proceso")
        self.boton_cancelar.clicked.connect(self.cancelar_proceso)
        layout_principal.addWidget(self.boton_cancelar)

        # --- Log de Resultados --- #
        self.log_browser, log_group_box = setup_logging_browser("Resultados del Renombrado")
        layout_principal.addWidget(log_group_box)

        self.habilitar_botones() # Llamada inicial para establecer el estado correcto

    def habilitar_botones(self):
        hay_ruta = bool(self.ruta_carpeta_line_edit.text())
        for boton in self.botones_modo.values():
            boton.setEnabled(hay_ruta)
        self.boton_cancelar.setEnabled(False)

    def iniciar_proceso(self, modo):
        ruta_carpeta = self.ruta_carpeta_line_edit.text()
        if not ruta_carpeta:
            self.log_browser.append(f"<font color='{self.color_advertencia}'>Por favor, selecciona una carpeta raíz primero.</font>")
            return

        self.log_browser.clear()
        self.log_browser.append(f"<font color='{self.color_info}'>Iniciando proceso de renombrado modo '{modo}'...</font>")
        
        self.set_controles_habilitados(False, modo_activo=modo)

        self.hilo_trabajo = QThread()
        self.worker = RenombradorWorker(ruta_carpeta, modo)
        self.worker.moveToThread(self.hilo_trabajo)

        self.worker.progreso_actualizado.connect(self.actualizar_progreso)
        self.worker.proceso_finalizado.connect(self.finalizar_proceso)
        self.hilo_trabajo.started.connect(self.worker.ejecutar)
        
        self.hilo_trabajo.start()

    def actualizar_progreso(self, nombre_carpeta, porcentaje):
        self.log_browser.append(f"Procesando: {nombre_carpeta}...")

    def finalizar_proceso(self, resultados):
        num_exitosos = len(resultados.get('exitosos', []))
        num_fallidos = len(resultados.get('fallidos', []))

        self.log_browser.append("<br><b>--- Proceso Finalizado ---</b>")
        resumen = f"<b>Resumen: <font color='{self.color_exito}'>{num_exitosos} exitosos</font>, <font color='{self.color_error}'>{num_fallidos} fallidos</font></b>"
        self.log_browser.append(resumen)
        self.log_browser.append("<br>")

        if num_exitosos > 0:
            self.log_browser.append(f"<font color='{self.color_exito}'><b>Detalles exitosos:</b></font>")
            for item in resultados['exitosos']:
                self.log_browser.append(f"- Carpeta: {item['carpeta']}, Detalle: {item['razon']}")
        
        if num_fallidos > 0:
            self.log_browser.append(f"<font color='{self.color_error}'><b>Detalles de fallos o advertencias:</b></font>")
            for item in resultados['fallidos']:
                self.log_browser.append(f"- Carpeta: {item['carpeta']}, Razón: {item['razon']}")

        self.set_controles_habilitados(True)
        if self.hilo_trabajo:
            self.hilo_trabajo.quit()
            self.hilo_trabajo.wait()

    def set_controles_habilitados(self, habilitado, modo_activo=None):
        self.ruta_carpeta_line_edit.parent().parent().setEnabled(habilitado)

        for modo, boton in self.botones_modo.items():
            boton.setEnabled(habilitado)
            
            if habilitado:
                if modo == 'revertir_escolar':
                    boton.setStyleSheet(f"background-color: {self.color_error}; color: white;")
                else:
                    boton.setStyleSheet("")
            else:
                if modo == modo_activo:
                    boton.setStyleSheet(f"background-color: {self.color_exito}; color: white;")
                else:
                    boton.setEnabled(False)

        self.boton_cancelar.setEnabled(not habilitado)

    def cancelar_proceso(self):
        if self.worker and self.hilo_trabajo.isRunning():
            self.worker.cancelar()
            self.log_browser.append(f"<font color='{self.color_advertencia}'><b>Cancelando proceso... por favor espere.</b></font>")
            self.boton_cancelar.setEnabled(False)