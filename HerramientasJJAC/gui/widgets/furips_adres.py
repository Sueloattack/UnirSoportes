from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QLineEdit, QGroupBox, QLabel, QTabWidget, QTextEdit,
                               QCheckBox,
                               QFileDialog)
from PySide6.QtCore import QThread, Qt

from gui.common.componentes_comunes import crear_selector_carpeta, setup_logging_browser
from logica.workers.furips_adres_logic import FuripsAdresWorker

class FuripsAdresWidget(QWidget):
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

        label_titulo = QLabel("Gestión de FURIPS ADRES")
        label_titulo.setAlignment(Qt.AlignCenter)
        label_titulo.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout_principal.addWidget(label_titulo)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab { color: black; background: #e0e0e0; padding: 8px 15px; margin: 2px; }
            QTabBar::tab:selected { background: #ffffff; font-weight: bold; }
        """)
        layout_principal.addWidget(self.tabs)

        # TAB 1: Unir FURIPS
        self.tab_unir = QWidget()
        self.setup_tab_unir()
        self.tabs.addTab(self.tab_unir, "Unir FURIPS")

        # TAB 2: Filtrar Dual FURIPS
        self.tab_filtrar = QWidget()
        self.setup_tab_filtrar()
        self.tabs.addTab(self.tab_filtrar, "Filtrado Dual FURIPS")

        # LOGS
        self.log_browser, log_group_box = setup_logging_browser("Resultados del Proceso")
        layout_principal.addWidget(log_group_box)

        self.boton_cancelar = QPushButton("Cancelar Proceso")
        self.boton_cancelar.setEnabled(False)
        self.boton_cancelar.clicked.connect(self.cancelar_proceso)
        layout_principal.addWidget(self.boton_cancelar)

    def setup_tab_unir(self):
        layout = QVBoxLayout(self.tab_unir)

        self.ruta_entrada_unir_le, ly_entrada = crear_selector_carpeta("Carpeta FURIPS origen:", "Seleccionar")
        self.ruta_salida_unir_le, ly_salida = crear_selector_carpeta("Carpeta Destino:", "Seleccionar")

        grupo = QGroupBox("Configuración de Unión")
        g_layout = QVBoxLayout(grupo)
        
        ly_num = QHBoxLayout()
        ly_num.addWidget(QLabel("Número de Cuenta:"))
        self.numero_cuenta_le = QLineEdit()
        ly_num.addWidget(self.numero_cuenta_le)

        g_layout.addLayout(ly_entrada)
        g_layout.addLayout(ly_salida)
        g_layout.addLayout(ly_num)

        self.boton_ejecutar_unir = QPushButton("Unir FURIPS")
        self.boton_ejecutar_unir.clicked.connect(self.ejecutar_unir)
        g_layout.addWidget(self.boton_ejecutar_unir)

        layout.addWidget(grupo)
        layout.addStretch()

    def setup_tab_filtrar(self):
        layout = QVBoxLayout(self.tab_filtrar)

        grupo = QGroupBox("Configuración de Filtrado Dual")
        g_layout = QVBoxLayout(grupo)

        # Selectores archivo manuales (para variar del selector de carpeta)
        ly_f1 = QHBoxLayout()
        ly_f1.addWidget(QLabel("Archivo FURIPS 1:"))
        self.ruta_f1_le = QLineEdit()
        btn_f1 = QPushButton("Buscar")
        btn_f1.clicked.connect(lambda: self.seleccionar_archivo(self.ruta_f1_le))
        ly_f1.addWidget(self.ruta_f1_le)
        ly_f1.addWidget(btn_f1)

        ly_f2 = QHBoxLayout()
        ly_f2.addWidget(QLabel("Archivo FURIPS 2:"))
        self.ruta_f2_le = QLineEdit()
        btn_f2 = QPushButton("Buscar")
        btn_f2.clicked.connect(lambda: self.seleccionar_archivo(self.ruta_f2_le))
        ly_f2.addWidget(self.ruta_f2_le)
        ly_f2.addWidget(btn_f2)

        self.ruta_salida_filtrar_le, ly_salida = crear_selector_carpeta("Carpeta Destino:", "Seleccionar")

        g_layout.addLayout(ly_f1)
        g_layout.addLayout(ly_f2)
        g_layout.addLayout(ly_salida)

        self.checkbox_factura_individual = QCheckBox("Factura X individual")
        g_layout.addWidget(self.checkbox_factura_individual)

        g_layout.addWidget(QLabel("Pegar Lista de Facturas (una por línea o espacio):"))
        self.text_lista_filtrar = QTextEdit()
        g_layout.addWidget(self.text_lista_filtrar)

        self.boton_ejecutar_filtrar = QPushButton("Filtrar FURIPS")
        self.boton_ejecutar_filtrar.clicked.connect(self.ejecutar_filtrar)
        g_layout.addWidget(self.boton_ejecutar_filtrar)

        layout.addWidget(grupo)

    def seleccionar_archivo(self, line_edit):
        ruta, _ = QFileDialog.getOpenFileName(self, "Seleccionar archivo", "", "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)")
        if ruta:
            line_edit.setText(ruta)

    def ejecutar_unir(self):
        import traceback
        carpeta_entrada = self.ruta_entrada_unir_le.text().strip()
        carpeta_salida = self.ruta_salida_unir_le.text().strip()
        numero_cuenta = self.numero_cuenta_le.text().strip()

        if not carpeta_entrada or not carpeta_salida or not numero_cuenta:
            self.log_browser.append(f"<font color='{self.color_error}'>Faltan datos por llenar.</font>")
            return

        params = {
            'carpeta_entrada': carpeta_entrada,
            'carpeta_salida': carpeta_salida,
            'numero_cuenta': numero_cuenta
        }
        self.lanzar_worker(params, "unir")

    def ejecutar_filtrar(self):
        f1 = self.ruta_f1_le.text().strip()
        f2 = self.ruta_f2_le.text().strip()
        carpeta_salida = self.ruta_salida_filtrar_le.text().strip()
        texto_glosas = self.text_lista_filtrar.toPlainText()

        import re
        glosas = [g.strip() for g in re.split(r'[,\s\n]+', texto_glosas) if g.strip()]

        if not f1 or not f2 or not carpeta_salida or not glosas:
            self.log_browser.append(f"<font color='{self.color_error}'>Faltan datos o lista de facturas vacía.</font>")
            return

        params = {
            'archivo_f1': f1,
            'archivo_f2': f2,
            'carpeta_salida': carpeta_salida,
            'glosas': glosas,
            'factura_x_individual': self.checkbox_factura_individual.isChecked()
        }
        self.lanzar_worker(params, "filtrar")

    def lanzar_worker(self, parametros, modo):
        self.boton_cancelar.setEnabled(True)
        self.tabs.setEnabled(False)
        self.log_browser.clear()

        self.hilo_trabajo = QThread()
        self.worker = FuripsAdresWorker(parametros, modo)
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
