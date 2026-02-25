from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                                QLineEdit, QGroupBox, QLabel, QDateEdit, QCheckBox,
                                QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar, QMessageBox)
from PySide6.QtCore import QThread, Qt, Signal, QDate
from PySide6.QtGui import QColor
from gui.common.componentes_comunes import crear_selector_carpeta
import os

class AutomatizadorRadicacionWorker(QThread):
    """Worker thread para ejecutar la automatización en segundo plano"""
    progreso_actualizado = Signal(str, int)
    proceso_finalizado = Signal(dict)
    error_ocurrido = Signal(str)
    
    def __init__(self, carpeta_pdfs, fecha_notificacion, username, password, headless):
        super().__init__()
        self.carpeta_pdfs = carpeta_pdfs
        self.fecha_notificacion = fecha_notificacion
        self.username = username
        self.password = password
        self.headless = headless
        self._cancelado = False
    
    def run(self):
        print("\n" + "="*70)
        print("WORKER THREAD INICIADO")
        try:
            from logica.workers.automatizador_radicacion_logic import automatizar_radicacion_logic
            
            automatizar_radicacion_logic(
                self.carpeta_pdfs,
                self.fecha_notificacion,
                self.username,
                self.password,
                self.headless,
                self.progreso_actualizado,
                self.proceso_finalizado,
                self.error_ocurrido
            )
        except Exception as e:
            print(f"ERROR CRÍTICO en worker: {e}")
            import traceback
            traceback.print_exc()
            self.error_ocurrido.emit(f"Error crítico: {str(e)}")
    
    def cancelar(self):
        self._cancelado = True

class AutomatizadorRadicacionWidget(QWidget):
    """Widget para automatizar la radicación de cartas glosas"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        
        # Colores
        self.color_exito = QColor(46, 204, 113)      # Verde
        self.color_error = QColor(231, 76, 60)       # Rojo
        self.color_advertencia = QColor(243, 156, 18) # Naranja/Amarillo
        
        self.init_ui()
    
    def init_ui(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)
        
        # --- Título ---
        label_titulo = QLabel("Automatizador de Radicación Previsora")
        label_titulo.setObjectName("AyudaTitulo")
        label_titulo.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(label_titulo)
        
        # --- Configuración ---
        grupo_config = QGroupBox("Configuración")
        layout_config = QVBoxLayout()
        
        self.ruta_carpeta_line_edit, selector_carpeta_layout = crear_selector_carpeta(
            "Carpeta con PDFs:", "Seleccionar Carpeta", self.validar_formulario
        )
        layout_config.addLayout(selector_carpeta_layout)
        
        # Fecha
        layout_fecha = QHBoxLayout()
        label_fecha = QLabel("Fecha de Notificación:")
        label_fecha.setMinimumWidth(150)
        self.fecha_edit = QDateEdit()
        self.fecha_edit.setCalendarPopup(True)
        self.fecha_edit.setDate(QDate.currentDate())
        self.fecha_edit.setMaximumDate(QDate.currentDate())
        self.fecha_edit.setDisplayFormat("dd/MM/yyyy")
        layout_fecha.addWidget(label_fecha)
        layout_fecha.addWidget(self.fecha_edit)
        layout_fecha.addStretch()
        layout_config.addLayout(layout_fecha)
        
        # Credenciales
        layout_usuario = QHBoxLayout()
        label_usuario = QLabel("Usuario:")
        label_usuario.setMinimumWidth(150)
        self.usuario_edit = QLineEdit()
        self.usuario_edit.setText("AJ.JOSE") # Default
        layout_usuario.addWidget(label_usuario)
        layout_usuario.addWidget(self.usuario_edit)
        layout_config.addLayout(layout_usuario)
        
        layout_pass = QHBoxLayout()
        label_pass = QLabel("Contraseña:")
        label_pass.setMinimumWidth(150)
        self.password_edit = QLineEdit()
        self.password_edit.setText("1005911366") # Default
        self.password_edit.setEchoMode(QLineEdit.Password)
        layout_pass.addWidget(label_pass)
        layout_pass.addWidget(self.password_edit)
        layout_config.addLayout(layout_pass)
        
        self.headless_checkbox = QCheckBox("Modo invisible (Headless)")
        self.headless_checkbox.setChecked(False)
        layout_config.addWidget(self.headless_checkbox)
        
        grupo_config.setLayout(layout_config)
        layout_principal.addWidget(grupo_config)
        
        # --- Botones ---
        layout_botones = QHBoxLayout()
        self.boton_iniciar = QPushButton("Iniciar Radicación")
        self.boton_iniciar.setObjectName("BotonPrimario")
        self.boton_iniciar.clicked.connect(self.iniciar_automatizacion)
        self.boton_iniciar.setEnabled(False)
        
        self.boton_cancelar = QPushButton("Detener")
        self.boton_cancelar.setObjectName("BotonSecundario")
        self.boton_cancelar.clicked.connect(self.cancelar_automatizacion)
        self.boton_cancelar.setEnabled(False)
        
        layout_botones.addWidget(self.boton_iniciar)
        layout_botones.addWidget(self.boton_cancelar)
        layout_principal.addLayout(layout_botones)
        
        # --- Progreso ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout_principal.addWidget(self.progress_bar)
        
        self.label_estado = QLabel("Esperando configuración...")
        self.label_estado.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(self.label_estado)
        
        # --- Resultados ---
        grupo_resultados = QGroupBox("Resultados de la Ejecución")
        layout_res = QVBoxLayout()
        
        self.tabla_resultados = QTableWidget()
        self.tabla_resultados.setColumnCount(4)
        self.tabla_resultados.setHorizontalHeaderLabels(["Nombre", "Factura", "Tipo Glosa", "Estado / Valor"])
        
        header = self.tabla_resultados.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch) 
        
        layout_res.addWidget(self.tabla_resultados)
        grupo_resultados.setLayout(layout_res)
        layout_principal.addWidget(grupo_resultados)
    
    def validar_formulario(self):
        carpeta = self.ruta_carpeta_line_edit.text()
        ok = bool(carpeta and os.path.isdir(carpeta) and 
                  any(f.lower().endswith('.pdf') for f in os.listdir(carpeta)))
        self.boton_iniciar.setEnabled(ok)
        self.label_estado.setText("✓ Carpeta lista" if ok else "Seleccione una carpeta válida")

    def iniciar_automatizacion(self):
        carpeta = self.ruta_carpeta_line_edit.text()
        fecha_str = self.fecha_edit.date().toString("dd/MM/yyyy")
        user = self.usuario_edit.text()
        pwd = self.password_edit.text()
        headless = self.headless_checkbox.isChecked()
        
        # Reset UI
        self.tabla_resultados.setRowCount(0)
        self.progress_bar.setValue(0)
        self.set_controles_habilitados(False)
        
        self.worker = AutomatizadorRadicacionWorker(carpeta, fecha_str, user, pwd, headless)
        self.worker.progreso_actualizado.connect(self.actualizar_progreso)
        self.worker.proceso_finalizado.connect(self.finalizar_proceso)
        self.worker.error_ocurrido.connect(self.mostrar_error)
        self.worker.start()
        
        self.label_estado.setText("Iniciando motor de radicación...")

    def actualizar_progreso(self, msj, val):
        self.progress_bar.setValue(val)
        self.label_estado.setText(msj)

    def finalizar_proceso(self, resultados):
        """Maneja el fin del proceso: llena tabla y muestra popup"""
        
        # Contadores
        exitosos = resultados.get('exitosos', [])
        fallidos = resultados.get('fallidos', [])
        advertencias = resultados.get('advertencias', [])
        
        count_ok = len(exitosos)
        count_err = len(fallidos)
        count_warn = len(advertencias)
        total = count_ok + count_err + count_warn

        # --- Llenar Tabla (Éxitos) ---
        for item in exitosos:
            self._agregar_fila_tabla(item, "OK")

        # --- Llenar Tabla (Advertencias/Saltados) ---
        for item in advertencias:
             self._agregar_fila_tabla(item, "WARN")
             
        # --- Llenar Tabla (Fallidos) ---
        for item in fallidos:
            self._agregar_fila_tabla(item, "ERR")

        # Restaurar UI
        self.progress_bar.setValue(100)
        self.label_estado.setText(f"Fin: {count_ok} radicados, {count_warn} saltados, {count_err} errores.")
        self.set_controles_habilitados(True)
        
        # --- Mostrar Mensaje Emergente (QMessageBox) ---
        msj = f"""
        <b>Resumen del Proceso</b>
        <br><br>
        <b>Total procesados:</b> {total}<br>
        <hr>
        ✅ <b>Exitosos:</b> {count_ok}<br>
        ⚠️ <b>Saltados (Imágenes):</b> {count_warn}<br>
        ❌ <b>Errores:</b> {count_err}<br>
        """
        QMessageBox.information(self, "Proceso Finalizado", msj)

    def _agregar_fila_tabla(self, item, estado_code):
        fila = self.tabla_resultados.rowCount()
        self.tabla_resultados.insertRow(fila)
        
        # 1. Nombre sin extensión
        nombre_full = item['archivo']
        nombre_clean = nombre_full.lower().replace('.pdf', '').upper()
        
        self.tabla_resultados.setItem(fila, 0, QTableWidgetItem(nombre_clean))
        
        # 2. Numero Factura / Serie
        # Si es un error/adv a veces no trae serie/num, manejamos con get
        factura_str = f"{item.get('serie', '')} {item.get('numero', '')}" if 'numero' in item else "-"
        self.tabla_resultados.setItem(fila, 1, QTableWidgetItem(factura_str))
        
        if estado_code == "OK":
            # 3. Tipo y Valor
            tipo_txt = f"{item.get('clasif') or 'Glosa Parcial'}" # 'GT' o 'Parcial'
            valor = item.get('valor', 0)
            if valor is None: valor = 0
            
            self.tabla_resultados.setItem(fila, 2, QTableWidgetItem(tipo_txt))
            
            # 4. Estado Verde
            item_st = QTableWidgetItem(f"OK | ${valor:,.0f}")
            item_st.setBackground(self.color_exito)
            self.tabla_resultados.setItem(fila, 3, item_st)
            
        elif estado_code == "WARN":
            # Advertencia (Imágenes)
            self.tabla_resultados.setItem(fila, 2, QTableWidgetItem("N/A"))
            
            razon = item.get('razon', 'Saltado')
            item_st = QTableWidgetItem(f"⚠️ {razon}")
            item_st.setBackground(self.color_advertencia)
            self.tabla_resultados.setItem(fila, 3, item_st)
            
        else:
            # Error Rojo
            self.tabla_resultados.setItem(fila, 2, QTableWidgetItem("-"))
            
            err_msg = item.get('error', 'Desconocido')
            item_st = QTableWidgetItem(f"Error: {err_msg}")
            item_st.setBackground(self.color_error)
            self.tabla_resultados.setItem(fila, 3, item_st)

    def mostrar_error(self, msj):
        self.label_estado.setText(f"❌ {msj}")
        QMessageBox.critical(self, "Error de Ejecución", f"Ocurrió un error:\n{msj}")
        self.set_controles_habilitados(True)

    def cancelar_automatizacion(self):
        if self.worker and self.worker.isRunning():
            self.worker.cancelar()
            self.worker.terminate()
            self.label_estado.setText("Cancelado por usuario.")
            self.set_controles_habilitados(True)

    def set_controles_habilitados(self, enable):
        self.ruta_carpeta_line_edit.setEnabled(enable)
        self.boton_iniciar.setEnabled(enable)
        self.boton_cancelar.setEnabled(not enable)