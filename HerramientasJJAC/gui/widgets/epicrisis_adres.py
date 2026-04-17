from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLineEdit, QGroupBox, QLabel, QTabWidget, QTextEdit)
from PySide6.QtCore import QThread, Qt

from gui.common.componentes_comunes import crear_selector_carpeta, setup_logging_browser
from logica.workers.epicrisis_adres_logic import EpicrisisAdresWorker
import re

class EpicrisisAdresWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hilo_trabajo = None
        self.worker = None

        self.color_exito = "#2ecc71"
        self.color_error = "#e74c3c"
        self.color_advertencia = "#f39c12"
        self.color_info = "#3498db"

        self.init_ui()

    def init_ui(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)

        label_titulo = QLabel("Gestión de EPICRIS ADRES")
        label_titulo.setAlignment(Qt.AlignCenter)
        label_titulo.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout_principal.addWidget(label_titulo)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { color: black; background: #e0e0e0; padding: 8px 15px; margin: 2px; }
            QTabBar::tab:selected { background: #ffffff; font-weight: bold; }
        """)
        layout_principal.addWidget(self.tabs)

        self.tab_unir = QWidget()
        self.setup_tab_unir()
        self.tabs.addTab(self.tab_unir, "Unir Respuesta / Limpieza Total")

        self.tab_automatica = QWidget()
        self.setup_tab_automatica()
        self.tabs.addTab(self.tab_automatica, "Limpieza Automática")

        # LOGS
        self.log_browser, log_group_box = setup_logging_browser("Resultados del Proceso")
        layout_principal.addWidget(log_group_box)

        self.boton_cancelar = QPushButton("Cancelar Proceso")
        self.boton_cancelar.setEnabled(False)
        self.boton_cancelar.clicked.connect(self.cancelar_proceso)
        layout_principal.addWidget(self.boton_cancelar)

    def setup_tab_unir(self):
        layout = QVBoxLayout(self.tab_unir)
        grupo = QGroupBox("Configuración Manual")
        g_layout = QVBoxLayout(grupo)

        self.ruta_respuestas_le, ly_resp = crear_selector_carpeta("Carpeta Respuestas:", "Seleccionar")
        self.ruta_soportes_le, ly_sop = crear_selector_carpeta("Carpeta Soportes:", "Seleccionar")

        g_layout.addLayout(ly_resp)
        g_layout.addLayout(ly_sop)

        g_layout.addWidget(QLabel("Pegar Lista de Facturas (una por línea o espacio):"))
        self.text_lista_manual = QTextEdit()
        g_layout.addWidget(self.text_lista_manual)

        ly_botones = QHBoxLayout()
        self.btn_unir = QPushButton("1. Unir Respuesta (SOLO EPICRIS)")
        self.btn_unir.clicked.connect(lambda: self.ejecutar_manual("unir"))
        self.btn_limpiar = QPushButton("2. Limpiar TODO (Extrema)")
        self.btn_limpiar.clicked.connect(lambda: self.ejecutar_manual("limpieza_total"))
        ly_botones.addWidget(self.btn_unir)
        ly_botones.addWidget(self.btn_limpiar)
        g_layout.addLayout(ly_botones)

        layout.addWidget(grupo)
        
    def setup_tab_automatica(self):
        layout = QVBoxLayout(self.tab_automatica)
        grupo = QGroupBox("Configuración Automática")
        g_layout = QVBoxLayout(grupo)

        self.ruta_raiz_le, ly_raiz = crear_selector_carpeta("Carpeta Raíz (con subcarpetas 4318, etc.):", "Seleccionar")
        g_layout.addLayout(ly_raiz)
        
        self.btn_auto = QPushButton("3. Limpieza Automática")
        self.btn_auto.clicked.connect(self.ejecutar_automatica)
        g_layout.addWidget(self.btn_auto)

        layout.addWidget(grupo)
        layout.addStretch()

    def ejecutar_manual(self, modo):
        r_resp = self.ruta_respuestas_le.text().strip()
        r_sop = self.ruta_soportes_le.text().strip()
        texto_lista = self.text_lista_manual.toPlainText()

        lista_ids = [g.strip() for g in re.split(r'[,\s\n]+', texto_lista) if g.strip()]

        if not r_resp or not r_sop or not lista_ids:
            self.log_browser.append(f"<font color='{self.color_error}'>Faltan carpetas o lista de facturas.</font>")
            return
            
        params = {
            'ruta_respuestas': r_resp,
            'ruta_soportes': r_sop,
            'lista_ids': lista_ids
        }
        self.lanzar_worker(params, modo)

    def ejecutar_automatica(self):
        ruta_raiz = self.ruta_raiz_le.text().strip()
        if not ruta_raiz:
             self.log_browser.append(f"<font color='{self.color_error}'>Por favor seleccione la carpeta raíz.</font>")
             return
        
        params = {'ruta_raiz': ruta_raiz}
        self.lanzar_worker(params, "limpieza_automatica")

    def lanzar_worker(self, parametros, modo):
        self.boton_cancelar.setEnabled(True)
        self.tabs.setEnabled(False)
        self.log_browser.clear()

        self.hilo_trabajo = QThread()
        self.worker = EpicrisisAdresWorker(parametros, modo)
        self.worker.moveToThread(self.hilo_trabajo)

        self.worker.progreso_actualizado.connect(self.log_browser.append)
        self.worker.proceso_finalizado.connect(self.finalizar_proceso)
        self.hilo_trabajo.started.connect(self.worker.ejecutar)

        self.hilo_trabajo.start()

    def cancelar_proceso(self):
        if self.worker and self.hilo_trabajo.isRunning():
            self.worker.cancelar()
            self.log_browser.append(f"<font color='{self.color_advertencia}'>Cancelando... Espere un momento.</font>")
            self.boton_cancelar.setEnabled(False)

    def finalizar_proceso(self, resultados):
        self.tabs.setEnabled(True)
        self.boton_cancelar.setEnabled(False)
        
        if 'error' in resultados:
            self.log_browser.append(f"<font color='{self.color_error}'><b>Error: {resultados['error']}</b></font>")
        else:
            self.log_browser.append(f"<br><font color='{self.color_exito}'><b>Proceso Finalizado.</b></font>")

        if self.hilo_trabajo:
            self.hilo_trabajo.quit()
            self.hilo_trabajo.wait()
