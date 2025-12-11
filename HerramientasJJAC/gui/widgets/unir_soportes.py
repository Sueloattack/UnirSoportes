# gui/widget_unir_soportes.py
import sys
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFrame, QLabel, QLineEdit, QPushButton, QHBoxLayout, 
                               QFileDialog, QMessageBox, QProgressBar, QDialog, QScrollArea, QGridLayout, QGroupBox, QTextEdit)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from logica.workers.unir_soportes_logic import UnirSoportesWorker
from logica.workers.mover_respuesta_raiz_logic import MoverRespuestaRaizWorker
from logica.workers.unir_axa_calixto_logic import unir_axa_calixto_logic
from logica.workers.renombrar_previsora_logic import renombrar_previsora_logic
from gui.common.componentes_comunes import SelectorCarpeta

# Worker para la nueva funcionalidad de AXA Calixto
class UnirAxaCalixtoWorker(QObject):
    progreso_actualizado = Signal(str, int)
    proceso_finalizado = Signal(dict)
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

# Worker para Previsora
class RenombrarPrevisoraWorker(QObject):
    progreso_actualizado = Signal(str, int)
    proceso_finalizado = Signal(dict)  # Cambiado a dict para enviar datos estructurados
    error_ocurrido = Signal(str)

    def __init__(self, dir_origen):
        super().__init__()
        self.dir_origen = dir_origen
        self.running = True

    def ejecutar(self):
        try:
            renombrar_previsora_logic(
                self.dir_origen,
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

class ResultadosProcesamientoDialog(QDialog):
    """
    Ventana de resultados genérica para procesos de unión/renombrado.
    Muestra éxitos y errores en un formato visual y permite copiar el texto.
    """
    def __init__(self, resultados, parent=None):
        super().__init__(parent)
        tipo = resultados.get('tipo_proceso', 'Previsora')
        titulo = "Renombrar Previsora" if tipo == 'Previsora' else "Unir AXA Calixto"
        color_tema = "#9b59b6" if tipo == 'Previsora' else "#3498db"
        
        self.setWindowTitle(f"Resultados - {titulo}")
        self.setMinimumSize(900, 650)

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Título principal
        label_titulo = QLabel(f"📊 Reporte de {titulo}")
        label_titulo.setStyleSheet(f"""
            font-size: 22px;
            font-weight: bold;
            color: {color_tema};
            padding: 10px;
            background-color: #34495e;
            border-radius: 5px;
        """)
        label_titulo.setAlignment(Qt.AlignCenter)
        layout.addWidget(label_titulo)

        # Resumen en tarjetas (Más compactas)
        layout_resumen = QHBoxLayout()
        layout_resumen.setSpacing(10)
        layout_resumen.addStretch() # Centrar tarjetas
        
        # Tarjeta: Total procesados
        card_total = self._crear_tarjeta(
            "📦 ZIPs",
            str(resultados.get('total_zips', 0)),
            "#3498db"
        )
        layout_resumen.addWidget(card_total)
        
        # Tarjeta: Éxitos
        card_exitos = self._crear_tarjeta(
            "✅ Éxitos",
            str(len(resultados.get('renombrados', []))),
            "#27ae60"
        )
        layout_resumen.addWidget(card_exitos)
        
        # Tarjeta: Sin código (Solo Previsora)
        if resultados.get('sin_codigo'):
            card_sin_codigo = self._crear_tarjeta(
                "⚠️ Sin Código",
                str(len(resultados.get('sin_codigo', []))),
                "#f39c12"
            )
            layout_resumen.addWidget(card_sin_codigo)
        
        # Tarjeta: Errores
        if resultados.get('errores'):
            card_errores = self._crear_tarjeta(
                "❌ Errores",
                str(len(resultados.get('errores', []))),
                "#e74c3c"
            )
            layout_resumen.addWidget(card_errores)
        
        layout_resumen.addStretch() # Centrar tarjetas
        layout.addLayout(layout_resumen)

        # Área de texto con resultados detallados
        resultados_texto = QTextEdit()
        resultados_texto.setReadOnly(True)
        resultados_texto.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 2px solid #34495e;
                border-radius: 5px;
                padding: 10px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
            }
        """)
        
        html_content = ""

        # Sección de Éxitos (Simplificada y en una línea)
        if resultados.get('renombrados'):
            html_content += f'<h2 style="color: #27ae60; font-size: 16px; margin-top: 5px; margin-bottom: 10px;">✅ ARCHIVOS GENERADOS ({len(resultados["renombrados"])})</h2>'
            html_content += '<div style="color: #ecf0f1;">'
            for item in resultados['renombrados']:
                html_content += f'<div style="margin-bottom: 4px; padding: 4px 8px; background-color: #34495e; border-radius: 3px;">'
                html_content += f'{item["original"]} <span style="color: #27ae60; font-weight: bold;">→</span> <span style="color: #2ecc71; font-weight: bold;">{item["nuevo"]}</span>'
                html_content += '</div>'
            html_content += '</div><br>'

        # Sección de archivos sin código
        if resultados.get('sin_codigo'):
            html_content += f'<h2 style="color: #f39c12; font-size: 16px; margin-top: 10px;">⚠️ ARCHIVOS SIN CÓDIGO DETECTADO ({len(resultados["sin_codigo"])})</h2>'
            html_content += '<div style="color: #ecf0f1;">'
            for nombre in resultados['sin_codigo']:
                html_content += f'<div style="margin-bottom: 2px;">• {nombre}</div>'
            html_content += '</div><br>'
        
        # Sección de errores
        if resultados.get('errores'):
            html_content += f'<h2 style="color: #e74c3c; font-size: 16px; margin-top: 10px;">❌ ERRORES DE PROCESAMIENTO ({len(resultados["errores"])})</h2>'
            html_content += '<div style="color: #ecf0f1;">'
            for error in resultados['errores']:
                html_content += f'<div style="margin-bottom: 5px;">'
                html_content += f'<span style="color: #e74c3c; font-weight: bold;">{error["archivo"]}</span>: {error["error"]}'
                html_content += '</div>'
            html_content += '</div>'
        
        resultados_texto.setHtml(html_content)
        layout.addWidget(resultados_texto)

        # Botones
        layout_botones = QHBoxLayout()
        
        boton_copiar = QPushButton("📋 Copiar Todo")
        boton_copiar.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        boton_copiar.clicked.connect(lambda: self._copiar_texto(resultados_texto))
        
        boton_cerrar = QPushButton("✖ Cerrar")
        boton_cerrar.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        boton_cerrar.clicked.connect(self.accept)
        
        layout_botones.addStretch()
        layout_botones.addWidget(boton_copiar)
        layout_botones.addWidget(boton_cerrar)
        layout.addLayout(layout_botones)

    def _crear_tarjeta(self, titulo, valor, color):
        """Crea una tarjeta de resumen compacta"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 6px;
                padding: 5px;
            }}
        """)
        frame.setFixedWidth(100) # Ancho aún más pequeño
        frame.setFixedHeight(60) # Altura fija pequeña
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(0)
        layout.setContentsMargins(2, 2, 2, 2)
        
        label_titulo = QLabel(titulo)
        label_titulo.setStyleSheet("""
            color: white;
            font-size: 10px;
            font-weight: bold;
        """)
        label_titulo.setAlignment(Qt.AlignCenter)
        
        label_valor = QLabel(valor)
        label_valor.setStyleSheet("""
            color: white;
            font-size: 18px;
            font-weight: bold;
        """)
        label_valor.setAlignment(Qt.AlignCenter)
        
        layout.addWidget(label_titulo)
        layout.addWidget(label_valor)
        
        return frame
    
    def _copiar_texto(self, text_edit):
        """Copia el texto plano al portapapeles"""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(text_edit.toPlainText())
        
        # Feedback visual
        QMessageBox.information(self, "Copiado", "El texto ha sido copiado al portapapeles.")

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
        self.previsora_worker_thread = None
        self.previsora_worker = None
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
        layout_acciones_principal = QVBoxLayout(group_acciones)
        layout_acciones_principal.setSpacing(15)
        
        # === SECCIÓN: PROCESAMIENTO ESPECIALIZADO ===
        label_especializado = QLabel("📦 Procesamiento Especializado")
        label_especializado.setStyleSheet("font-weight: bold; font-size: 13px; color: #3498db; margin-top: 5px;")
        layout_acciones_principal.addWidget(label_especializado)
        
        layout_especializado = QGridLayout()
        layout_especializado.setSpacing(10)
        
        # Botón AXA
        self.boton_unir_axa = QPushButton("🔗 Unir AXA Calixto")
        self.boton_unir_axa.setMinimumHeight(45)
        self.boton_unir_axa.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #21618c;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.boton_unir_axa.clicked.connect(self.iniciar_union_axa)
        
        # Botón Previsora
        self.boton_renombrar_previsora = QPushButton("📝 Renombrar Previsora")
        self.boton_renombrar_previsora.setMinimumHeight(45)
        self.boton_renombrar_previsora.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
            QPushButton:pressed {
                background-color: #7d3c98;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.boton_renombrar_previsora.clicked.connect(self.iniciar_renombrar_previsora)
        
        layout_especializado.addWidget(self.boton_unir_axa, 0, 0)
        layout_especializado.addWidget(self.boton_renombrar_previsora, 0, 1)
        layout_acciones_principal.addLayout(layout_especializado)
        
        # Separador
        linea_separador = QFrame()
        linea_separador.setFrameShape(QFrame.HLine)
        linea_separador.setFrameShadow(QFrame.Sunken)
        linea_separador.setStyleSheet("background-color: #34495e; margin: 10px 0px;")
        layout_acciones_principal.addWidget(linea_separador)
        
        # === SECCIÓN: ORGANIZACIÓN ===
        label_organizacion = QLabel("📁 Organización")
        label_organizacion.setStyleSheet("font-weight: bold; font-size: 13px; color: #e67e22; margin-top: 5px;")
        layout_acciones_principal.addWidget(label_organizacion)
        
        self.boton_mover_respuestas = QPushButton("📤 Mover Respuestas a Raíz")
        self.boton_mover_respuestas.setMinimumHeight(45)
        self.boton_mover_respuestas.setStyleSheet("""
            QPushButton {
                background-color: #e67e22;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #d35400;
            }
            QPushButton:pressed {
                background-color: #ba4a00;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.boton_mover_respuestas.clicked.connect(self.iniciar_movimiento_respuestas)
        layout_acciones_principal.addWidget(self.boton_mover_respuestas)
        
        # Separador
        linea_separador2 = QFrame()
        linea_separador2.setFrameShape(QFrame.HLine)
        linea_separador2.setFrameShadow(QFrame.Sunken)
        linea_separador2.setStyleSheet("background-color: #34495e; margin: 10px 0px;")
        layout_acciones_principal.addWidget(linea_separador2)
        
        # === SECCIÓN: UNIÓN ESTÁNDAR ===
        label_estandar = QLabel("⚙️ Unión Estándar")
        label_estandar.setStyleSheet("font-weight: bold; font-size: 13px; color: #27ae60; margin-top: 5px;")
        layout_acciones_principal.addWidget(label_estandar)

        self.boton_procesar = QPushButton("▶ Unión")
        self.boton_procesar.setMinimumHeight(50)
        self.boton_procesar.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #229954;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.boton_procesar.clicked.connect(self.iniciar_procesamiento)
        layout_acciones_principal.addWidget(self.boton_procesar)
        
        # Botones de modo
        layout_modo = QHBoxLayout()
        layout_modo.setSpacing(10)
        
        self.boton_aseguradoras = QPushButton("🏥 Aseguradoras")
        self.boton_aseguradoras.setCheckable(True)
        self.boton_aseguradoras.setChecked(True)
        self.boton_aseguradoras.setMinimumHeight(35)
        self.boton_aseguradoras.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                color: white;
                border: 2px solid #2c3e50;
                border-radius: 5px;
                padding: 5px;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #27ae60;
                border: 2px solid #229954;
            }
            QPushButton:hover {
                background-color: #2c3e50;
            }
        """)
        
        self.boton_adres = QPushButton("🏛️ ADRES")
        self.boton_adres.setCheckable(True)
        self.boton_adres.setMinimumHeight(35)
        self.boton_adres.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                color: white;
                border: 2px solid #2c3e50;
                border-radius: 5px;
                padding: 5px;
                font-size: 11px;
            }
            QPushButton:checked {
                background-color: #27ae60;
                border: 2px solid #229954;
            }
            QPushButton:hover {
                background-color: #2c3e50;
            }
        """)

        self.boton_aseguradoras.clicked.connect(lambda: self.seleccionar_modo("Aseguradoras"))
        self.boton_adres.clicked.connect(lambda: self.seleccionar_modo("ADRES"))
        
        layout_modo.addWidget(self.boton_aseguradoras)
        layout_modo.addWidget(self.boton_adres)
        layout_acciones_principal.addLayout(layout_modo)
        
        # Checkbox para Modo Solo Soportes
        from PySide6.QtWidgets import QCheckBox
        self.checkbox_solo_soportes = QCheckBox("🔧 Modo Solo Soportes (sin Carta/Respuesta Glosa)")
        self.checkbox_solo_soportes.setStyleSheet("""
            QCheckBox {
                color: #ecf0f1;
                font-size: 11px;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.checkbox_solo_soportes.setToolTip(
            "Activa este modo para verificar y unir solo los archivos de soporte,\n"
            "sin requerir la Carta Glosa (Aseguradoras) o Respuesta Glosa (ADRES)."
        )
        layout_acciones_principal.addWidget(self.checkbox_solo_soportes)
        
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
           (self.axa_worker_thread and self.axa_worker_thread.isRunning()) or \
           (self.previsora_worker_thread and self.previsora_worker_thread.isRunning()):
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
        
        # Obtener estado del checkbox
        solo_soportes = self.checkbox_solo_soportes.isChecked()
        
        self.worker_thread = QThread()
        self.worker = UnirSoportesWorker(ruta_origen, self.modo_procesamiento, solo_soportes)
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

    def iniciar_renombrar_previsora(self):
        if self.es_proceso_en_ejecucion(): return

        dir_origen = self.selector_origen.path()
        if not dir_origen:
            QMessageBox.critical(self, "Error", "Debe seleccionar la carpeta que contiene los archivos .zip de Previsora.")
            return

        self.deshabilitar_botones()
        self.boton_renombrar_previsora.setText("Procesando Previsora...")

        self.previsora_worker_thread = QThread()
        self.previsora_worker = RenombrarPrevisoraWorker(dir_origen)
        self.previsora_worker.moveToThread(self.previsora_worker_thread)
        self.previsora_worker.progreso_actualizado.connect(self.actualizar_progreso_axa)
        self.previsora_worker.proceso_finalizado.connect(self.proceso_previsora_finalizado)
        self.previsora_worker.error_ocurrido.connect(self.proceso_previsora_error)
        self.previsora_worker_thread.started.connect(self.previsora_worker.ejecutar)
        self.previsora_worker_thread.start()


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

    def proceso_axa_finalizado(self, resultados):
        self.habilitar_botones()
        self.label_progreso.setText("Proceso de AXA Calixto finalizado.")
        self.barra_progreso.setValue(100)
        self.axa_worker_thread.quit()
        self.axa_worker_thread.wait()
        
        # Mostrar diálogo de resultados
        dialogo_resultados = ResultadosProcesamientoDialog(resultados, self)
        dialogo_resultados.exec()

    def proceso_axa_error(self, error_msg):
        self.habilitar_botones()
        self.label_progreso.setText("Error en el proceso de AXA Calixto.")
        QMessageBox.critical(self, "Error en Proceso AXA", error_msg)
        if self.axa_worker_thread:
            self.axa_worker_thread.quit()
            self.axa_worker_thread.wait()

    def proceso_previsora_finalizado(self, resultados):
        self.habilitar_botones()
        self.label_progreso.setText("Proceso de Previsora finalizado.")
        self.barra_progreso.setValue(100)
        self.previsora_worker_thread.quit()
        self.previsora_worker_thread.wait()
        
        # Mostrar diálogo de resultados
        dialogo_resultados = ResultadosProcesamientoDialog(resultados, self)
        dialogo_resultados.exec()

    def proceso_previsora_error(self, error_msg):
        self.habilitar_botones()
        self.label_progreso.setText("Error en el proceso de Previsora.")
        QMessageBox.critical(self, "Error en Proceso Previsora", error_msg)
        if self.previsora_worker_thread:
            self.previsora_worker_thread.quit()
            self.previsora_worker_thread.wait()
            
    def deshabilitar_botones(self):
        self.boton_unir_axa.setEnabled(False)
        self.boton_renombrar_previsora.setEnabled(False)
        self.boton_mover_respuestas.setEnabled(False)
        self.boton_procesar.setEnabled(False)

    def habilitar_botones(self):
        self.boton_unir_axa.setEnabled(True)
        self.boton_renombrar_previsora.setEnabled(True)
        self.boton_mover_respuestas.setEnabled(True)
        self.boton_procesar.setEnabled(True)
        self.boton_unir_axa.setText("Unir AXA Calixto")
        self.boton_renombrar_previsora.setText("Renombrar Previsora Calixto")
        self.boton_mover_respuestas.setText("Mover Respuestas a Raíz")
        self.boton_procesar.setText("Iniciar Unión Estándar")