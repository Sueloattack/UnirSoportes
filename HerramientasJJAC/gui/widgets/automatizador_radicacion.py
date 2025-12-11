# gui/widgets/automatizador_radicacion.py

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                                QLineEdit, QGroupBox, QLabel, QDateEdit, QCheckBox,
                                QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar)
from PySide6.QtCore import QThread, Qt, Signal, QDate
from PySide6.QtGui import QColor
from gui.common.componentes_comunes import crear_selector_carpeta
import os


class AutomatizadorRadicacionWorker(QThread):
    """Worker thread para ejecutar la automatización en segundo plano"""
    progreso_actualizado = Signal(str, int)  # mensaje, porcentaje
    proceso_finalizado = Signal(dict)  # resultados
    error_ocurrido = Signal(str)  # mensaje de error
    
    def __init__(self, carpeta_pdfs, fecha_notificacion, username, password, headless):
        super().__init__()
        self.carpeta_pdfs = carpeta_pdfs
        self.fecha_notificacion = fecha_notificacion
        self.username = username
        self.password = password
        self.headless = headless
        self._cancelado = False
    
    def run(self):
        """Ejecuta la automatización"""
        print("\n" + "="*70)
        print("WORKER THREAD INICIADO")
        print("="*70)
        try:
            print("Importando módulo de lógica...")
            from logica.workers.automatizador_radicacion_logic import automatizar_radicacion_logic
            print("Módulo importado exitosamente")
            
            print(f"Parámetros:")
            print(f"  - Carpeta: {self.carpeta_pdfs}")
            print(f"  - Fecha: {self.fecha_notificacion}")
            print(f"  - Usuario: {self.username}")
            print(f"  - Headless: {self.headless}")
            
            print("\nLlamando a automatizar_radicacion_logic...")
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
            print("automatizar_radicacion_logic completado")
        except Exception as e:
            print(f"ERROR CRÍTICO en worker: {e}")
            import traceback
            traceback.print_exc()
            self.error_ocurrido.emit(f"Error crítico: {str(e)}")
    
    def cancelar(self):
        """Marca el worker para cancelación"""
        self._cancelado = True


class AutomatizadorRadicacionWidget(QWidget):
    """Widget para automatizar la radicación de cartas glosas"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        
        # Colores para la tabla de resultados
        self.color_exito = QColor(46, 204, 113)  # Verde
        self.color_error = QColor(231, 76, 60)   # Rojo
        self.color_advertencia = QColor(243, 156, 18)  # Naranja
        
        self.init_ui()
    
    def init_ui(self):
        """Inicializa la interfaz de usuario"""
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)
        
        # --- Título Principal ---
        label_titulo = QLabel("Automatizador de Radicación")
        label_titulo.setObjectName("AyudaTitulo")
        label_titulo.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(label_titulo)
        
        # --- Grupo de Configuración ---
        grupo_config = QGroupBox("Configuración")
        layout_config = QVBoxLayout()
        
        # Selector de carpeta con PDFs
        self.ruta_carpeta_line_edit, selector_carpeta_layout = crear_selector_carpeta(
            "Carpeta con PDFs:",
            "Seleccionar Carpeta",
            self.validar_formulario
        )
        layout_config.addLayout(selector_carpeta_layout)
        
        # Fecha de notificación
        layout_fecha = QHBoxLayout()
        label_fecha = QLabel("Fecha de Notificación:")
        label_fecha.setMinimumWidth(150)
        self.fecha_edit = QDateEdit()
        self.fecha_edit.setCalendarPopup(True)
        self.fecha_edit.setDate(QDate.currentDate())
        self.fecha_edit.setMaximumDate(QDate.currentDate())  # No permitir fechas futuras
        self.fecha_edit.setDisplayFormat("dd/MM/yyyy")
        layout_fecha.addWidget(label_fecha)
        layout_fecha.addWidget(self.fecha_edit)
        layout_fecha.addStretch()
        layout_config.addLayout(layout_fecha)
        
        # Credenciales de login
        layout_usuario = QHBoxLayout()
        label_usuario = QLabel("Usuario:")
        label_usuario.setMinimumWidth(150)
        self.usuario_edit = QLineEdit()
        self.usuario_edit.setText("AJ.JOSE")
        layout_usuario.addWidget(label_usuario)
        layout_usuario.addWidget(self.usuario_edit)
        layout_config.addLayout(layout_usuario)
        
        layout_password = QHBoxLayout()
        label_password = QLabel("Contraseña:")
        label_password.setMinimumWidth(150)
        self.password_edit = QLineEdit()
        self.password_edit.setText("1005911366")
        self.password_edit.setEchoMode(QLineEdit.Password)
        layout_password.addWidget(label_password)
        layout_password.addWidget(self.password_edit)
        layout_config.addLayout(layout_password)
        
        # Checkbox para modo headless
        self.headless_checkbox = QCheckBox("Modo headless (navegador invisible)")
        self.headless_checkbox.setChecked(False)
        layout_config.addWidget(self.headless_checkbox)
        
        grupo_config.setLayout(layout_config)
        layout_principal.addWidget(grupo_config)
        
        # --- Botones de Acción ---
        layout_botones = QHBoxLayout()
        
        self.boton_iniciar = QPushButton("Iniciar Automatización")
        self.boton_iniciar.setObjectName("BotonPrimario")
        self.boton_iniciar.clicked.connect(self.iniciar_automatizacion)
        self.boton_iniciar.setEnabled(False)
        
        self.boton_cancelar = QPushButton("Cancelar")
        self.boton_cancelar.setObjectName("BotonSecundario")
        self.boton_cancelar.clicked.connect(self.cancelar_automatizacion)
        self.boton_cancelar.setEnabled(False)
        
        layout_botones.addWidget(self.boton_iniciar)
        layout_botones.addWidget(self.boton_cancelar)
        layout_botones.addStretch()
        
        layout_principal.addLayout(layout_botones)
        
        # --- Barra de Progreso ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout_principal.addWidget(self.progress_bar)
        
        # --- Label de Estado ---
        self.label_estado = QLabel("Esperando para iniciar...")
        self.label_estado.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(self.label_estado)
        
        # --- Tabla de Resultados ---
        grupo_resultados = QGroupBox("Resultados")
        layout_resultados = QVBoxLayout()
        
        self.tabla_resultados = QTableWidget()
        self.tabla_resultados.setColumnCount(4)
        self.tabla_resultados.setHorizontalHeaderLabels(["Archivo", "Serie", "Número", "Estado"])
        
        # Configurar el ancho de las columnas
        header = self.tabla_resultados.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        
        layout_resultados.addWidget(self.tabla_resultados)
        grupo_resultados.setLayout(layout_resultados)
        layout_principal.addWidget(grupo_resultados)
        
        layout_principal.addStretch()
    
    def validar_formulario(self):
        """Valida que todos los campos estén completos"""
        carpeta = self.ruta_carpeta_line_edit.text()
        usuario = self.usuario_edit.text()
        password = self.password_edit.text()
        
        # Verificar que la carpeta existe y tiene PDFs
        tiene_pdfs = False
        if carpeta and os.path.isdir(carpeta):
            archivos = os.listdir(carpeta)
            tiene_pdfs = any(f.lower().endswith('.pdf') for f in archivos)
        
        # Habilitar botón solo si todo está completo
        formulario_valido = bool(carpeta and usuario and password and tiene_pdfs)
        self.boton_iniciar.setEnabled(formulario_valido)
        
        if carpeta and not tiene_pdfs:
            self.label_estado.setText("⚠ No se encontraron archivos PDF en la carpeta")
        elif formulario_valido:
            self.label_estado.setText("✓ Listo para iniciar")
        else:
            self.label_estado.setText("Esperando para iniciar...")
    
    def iniciar_automatizacion(self):
        """Inicia el proceso de automatización"""
        print("="*70)
        print("INICIANDO AUTOMATIZACIÓN")
        print("="*70)
        
        # Validar campos
        carpeta = self.ruta_carpeta_line_edit.text()
        print(f"Carpeta seleccionada: {carpeta}")
        
        if not carpeta or not os.path.isdir(carpeta):
            self.label_estado.setText("❌ Carpeta no válida")
            print("ERROR: Carpeta no válida")
            return
        
        # Obtener fecha en formato DD/MM/YYYY
        fecha = self.fecha_edit.date()
        fecha_str = fecha.toString("dd/MM/yyyy")
        print(f"Fecha de notificación: {fecha_str}")
        
        # Obtener credenciales
        username = self.usuario_edit.text()
        password = self.password_edit.text()
        print(f"Usuario: {username}")
        print(f"Contraseña: {'*' * len(password)}")
        
        # Obtener modo headless
        headless = self.headless_checkbox.isChecked()
        print(f"Modo headless: {headless}")
        
        # Limpiar tabla de resultados
        self.tabla_resultados.setRowCount(0)
        self.progress_bar.setValue(0)
        
        # Deshabilitar controles
        print("Deshabilitando controles...")
        self.set_controles_habilitados(False)
        
        # Crear y configurar worker
        print("Creando worker...")
        try:
            self.worker = AutomatizadorRadicacionWorker(
                carpeta, fecha_str, username, password, headless
            )
            print("Worker creado exitosamente")
        except Exception as e:
            print(f"ERROR al crear worker: {e}")
            self.label_estado.setText(f"❌ Error al crear worker: {e}")
            self.set_controles_habilitados(True)
            return
        
        # Conectar señales
        print("Conectando señales...")
        self.worker.progreso_actualizado.connect(self.actualizar_progreso)
        self.worker.proceso_finalizado.connect(self.finalizar_proceso)
        self.worker.error_ocurrido.connect(self.mostrar_error)
        print("Señales conectadas")
        
        # Iniciar worker
        print("Iniciando worker thread...")
        try:
            self.worker.start()
            print("Worker thread iniciado")
        except Exception as e:
            print(f"ERROR al iniciar worker: {e}")
            self.label_estado.setText(f"❌ Error al iniciar: {e}")
            self.set_controles_habilitados(True)
            return
        
        self.label_estado.setText("🔄 Procesando...")
        print("Automatización iniciada correctamente")
        print("="*70)
    
    def actualizar_progreso(self, mensaje, porcentaje):
        """Actualiza la barra de progreso y el mensaje de estado"""
        self.progress_bar.setValue(porcentaje)
        self.label_estado.setText(mensaje)
    
    def finalizar_proceso(self, resultados):
        """Maneja la finalización del proceso"""
        # Mostrar resultados exitosos
        for item in resultados.get('exitosos', []):
            fila = self.tabla_resultados.rowCount()
            self.tabla_resultados.insertRow(fila)
            
            self.tabla_resultados.setItem(fila, 0, QTableWidgetItem(item['archivo']))
            self.tabla_resultados.setItem(fila, 1, QTableWidgetItem(item['serie']))
            self.tabla_resultados.setItem(fila, 2, QTableWidgetItem(item['numero']))
            
            item_estado = QTableWidgetItem("✓ Exitoso")
            item_estado.setBackground(self.color_exito)
            self.tabla_resultados.setItem(fila, 3, item_estado)
        
        # Mostrar resultados fallidos
        for item in resultados.get('fallidos', []):
            fila = self.tabla_resultados.rowCount()
            self.tabla_resultados.insertRow(fila)
            
            self.tabla_resultados.setItem(fila, 0, QTableWidgetItem(item['archivo']))
            self.tabla_resultados.setItem(fila, 1, QTableWidgetItem("-"))
            self.tabla_resultados.setItem(fila, 2, QTableWidgetItem("-"))
            
            item_estado = QTableWidgetItem(f"✗ Error: {item['error']}")
            item_estado.setBackground(self.color_error)
            self.tabla_resultados.setItem(fila, 3, item_estado)
        
        # Actualizar estado
        num_exitosos = len(resultados.get('exitosos', []))
        num_fallidos = len(resultados.get('fallidos', []))
        
        self.label_estado.setText(
            f"✓ Completado: {num_exitosos} exitosos, {num_fallidos} fallidos"
        )
        self.progress_bar.setValue(100)
        
        # Habilitar controles
        self.set_controles_habilitados(True)
    
    def mostrar_error(self, mensaje):
        """Muestra un error crítico"""
        self.label_estado.setText(f"❌ Error: {mensaje}")
        self.progress_bar.setValue(0)
        self.set_controles_habilitados(True)
    
    def cancelar_automatizacion(self):
        """Cancela el proceso de automatización"""
        if self.worker and self.worker.isRunning():
            self.worker.cancelar()
            self.worker.quit()
            self.worker.wait()
            self.label_estado.setText("⚠ Proceso cancelado")
            self.set_controles_habilitados(True)
    
    def set_controles_habilitados(self, habilitado):
        """Habilita o deshabilita los controles de la interfaz"""
        self.ruta_carpeta_line_edit.setEnabled(habilitado)
        self.fecha_edit.setEnabled(habilitado)
        self.usuario_edit.setEnabled(habilitado)
        self.password_edit.setEnabled(habilitado)
        self.headless_checkbox.setEnabled(habilitado)
        self.boton_iniciar.setEnabled(habilitado)
        self.boton_cancelar.setEnabled(not habilitado)
        
        if habilitado:
            self.validar_formulario()
