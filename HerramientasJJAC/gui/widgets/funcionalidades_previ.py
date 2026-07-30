import re

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QGroupBox,
    QLabel,
    QTabWidget,
    QTextEdit,
    QComboBox,
    QLineEdit,
    QCheckBox,
)

from gui.common.componentes_comunes import crear_selector_carpeta, setup_logging_browser
from logica.workers.funcionalidades_previ_logic import FuncionalidadesPreviWorker


class FuncionalidadesPreviWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hilo_trabajo = None
        self.worker = None
        self.modo_activo = None

        self.color_exito = "#2ecc71"
        self.color_error = "#e74c3c"
        self.color_advertencia = "#f39c12"

        self.init_ui()

    def init_ui(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)

        label_titulo = QLabel("Funcionalidades Previ")
        label_titulo.setAlignment(Qt.AlignCenter)
        label_titulo.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout_principal.addWidget(label_titulo)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            """
            QTabBar::tab { color: black; background: #e0e0e0; padding: 8px 15px; margin: 2px; }
            QTabBar::tab:selected { background: #ffffff; font-weight: bold; }
            """
        )
        layout_principal.addWidget(self.tabs)

        self.tab_busqueda = QWidget()
        self.setup_tab_busqueda()
        self.tabs.addTab(self.tab_busqueda, "Buscar Soportes")

        self.tab_compresion = QWidget()
        self.setup_tab_compresion()
        self.tabs.addTab(self.tab_compresion, "Compresión por Lotes")

        self.tab_validacion = QWidget()
        self.setup_tab_validacion()
        self.tabs.addTab(self.tab_validacion, "Validación")

        self.tab_excels = QWidget()
        self.setup_tab_excels()
        self.tabs.addTab(self.tab_excels, "Unir Excels")

        self.log_browser, log_group_box = setup_logging_browser("Resultados del Proceso")
        layout_principal.addWidget(log_group_box)

        self.boton_cancelar = QPushButton("Cancelar Proceso")
        self.boton_cancelar.setEnabled(False)
        self.boton_cancelar.clicked.connect(self.cancelar_proceso)
        layout_principal.addWidget(self.boton_cancelar)

    def setup_tab_busqueda(self):
        layout = QVBoxLayout(self.tab_busqueda)
        grupo = QGroupBox("Búsqueda y organización de soportes")
        grupo_layout = QVBoxLayout(grupo)

        modo_layout = QHBoxLayout()
        modo_layout.addWidget(QLabel("Modalidad:"))
        self.combo_modo_busqueda = QComboBox()
        self.combo_modo_busqueda.addItem("Estándar (HC + CRC)", "1")
        self.combo_modo_busqueda.addItem("Completa (HC + CRC + FURIPS)", "2")
        self.combo_modo_busqueda.addItem("Solo HC y FURIPS", "4")
        self.combo_modo_busqueda.addItem("Aceptadas (Rta Glosa + Nota Crédito)", "6")
        modo_layout.addWidget(self.combo_modo_busqueda)

        self.ruta_origen_busqueda_le, ly_origen = crear_selector_carpeta("Carpeta Origen:", "Seleccionar carpeta de origen")
        self.ruta_destino_busqueda_le, ly_destino = crear_selector_carpeta("Carpeta Destino:", "Seleccionar carpeta de destino")

        grupo_layout.addLayout(modo_layout)
        grupo_layout.addLayout(ly_origen)
        grupo_layout.addLayout(ly_destino)
        grupo_layout.addWidget(QLabel("Listado de facturas (una por línea, espacio o coma):"))

        self.text_facturas_busqueda = QTextEdit()
        grupo_layout.addWidget(self.text_facturas_busqueda)

        self.boton_busqueda = QPushButton("Buscar Soportes")
        self.boton_busqueda.clicked.connect(self.ejecutar_busqueda)
        grupo_layout.addWidget(self.boton_busqueda)

        layout.addWidget(grupo)
        layout.addStretch()

    def setup_tab_compresion(self):
        layout = QVBoxLayout(self.tab_compresion)
        grupo = QGroupBox("Compresión en lotes")
        grupo_layout = QVBoxLayout(grupo)

        modo_layout = QHBoxLayout()
        modo_layout.addWidget(QLabel("Modalidad:"))
        self.combo_modo_compresion = QComboBox()
        self.combo_modo_compresion.addItem("Estándar (EPI, PDX, CRC)", "1")
        self.combo_modo_compresion.addItem("Completa (EPI, PDX, CRC, FURIPS)", "2")
        self.combo_modo_compresion.addItem("Solo FURIPS (FURIPS)", "3")
        self.combo_modo_compresion.addItem("Simultánea Soportes + FURIPS (Doble carpeta)", "4")
        self.combo_modo_compresion.currentIndexChanged.connect(self._actualizar_visibilidad_compresion)
        modo_layout.addWidget(self.combo_modo_compresion)

        self.ruta_origen_compresion_le, ly_origen = crear_selector_carpeta("Carpeta Soportes origen:", "Seleccionar carpeta origen de soportes")
        self.ruta_destino_compresion_le, ly_destino = crear_selector_carpeta("Carpeta DESTINO ZIP Soportes (opcional / misma origen):", "Seleccionar carpeta destino de soportes")

        self.widget_furips_compresion = QWidget()
        ly_furips = QVBoxLayout(self.widget_furips_compresion)
        ly_furips.setContentsMargins(0, 0, 0, 0)

        self.ruta_origen_furips_compresion_le, ly_origen_furips = crear_selector_carpeta("Carpeta FURIPS origen:", "Seleccionar carpeta origen de FURIPS")
        self.ruta_destino_furips_compresion_le, ly_destino_furips = crear_selector_carpeta("Carpeta DESTINO ZIP FURIPS (opcional / misma origen):", "Seleccionar carpeta destino de FURIPS")

        ly_furips.addLayout(ly_origen_furips)
        ly_furips.addLayout(ly_destino_furips)

        grupo_layout.addLayout(modo_layout)
        grupo_layout.addLayout(ly_origen)
        grupo_layout.addLayout(ly_destino)
        grupo_layout.addWidget(self.widget_furips_compresion)

        self.widget_furips_compresion.setVisible(False)

        self.boton_compresion = QPushButton("Comprimir en Lotes")
        self.boton_compresion.clicked.connect(self.ejecutar_compresion)
        grupo_layout.addWidget(self.boton_compresion)

        layout.addWidget(grupo)
        layout.addStretch()

    def _actualizar_visibilidad_compresion(self):
        modo = self.combo_modo_compresion.currentData()
        es_simultaneo = (modo == "4")
        self.widget_furips_compresion.setVisible(es_simultaneo)

    def ejecutar_compresion(self):
        modo = self.combo_modo_compresion.currentData()
        carpeta_origen = self.ruta_origen_compresion_le.text().strip()
        carpeta_destino = self.ruta_destino_compresion_le.text().strip() or carpeta_origen

        if modo == "4":
            origen_furips = self.ruta_origen_furips_compresion_le.text().strip()
            destino_furips = self.ruta_destino_furips_compresion_le.text().strip() or origen_furips

            if not carpeta_origen or not origen_furips:
                self.log_browser.append(
                    f"<font color='{self.color_error}'>Debe seleccionar la carpeta origen de Soportes y la carpeta origen de FURIPS.</font>"
                )
                return

            parametros = {
                'modo_compresion': modo,
                'carpeta_origen': [carpeta_origen, origen_furips],
                'carpeta_destino': [carpeta_destino, destino_furips],
            }
        else:
            if not carpeta_origen:
                self.log_browser.append(f"<font color='{self.color_error}'>Seleccione la carpeta origen para la compresión.</font>")
                return

            parametros = {
                'modo_compresion': modo,
                'carpeta_origen': carpeta_origen,
                'carpeta_destino': carpeta_destino,
            }
        self.lanzar_worker(parametros, "comprimir")

    def setup_tab_validacion(self):
        layout = QVBoxLayout(self.tab_validacion)
        grupo = QGroupBox("Validación de soportes existentes")
        grupo_layout = QVBoxLayout(grupo)

        modo_layout = QHBoxLayout()
        modo_layout.addWidget(QLabel("Modalidad:"))
        self.combo_modo_validacion = QComboBox()
        self.combo_modo_validacion.addItem("Estándar (EPI, PDX, CRC)", "1")
        self.combo_modo_validacion.addItem("Completa (EPI, PDX, CRC, FURIPS)", "2")
        modo_layout.addWidget(self.combo_modo_validacion)

        self.ruta_validacion_le, ly_validacion = crear_selector_carpeta("Carpeta a validar:", "Seleccionar carpeta a validar")

        grupo_layout.addLayout(modo_layout)
        grupo_layout.addLayout(ly_validacion)
        grupo_layout.addWidget(QLabel("Listado de facturas (una por línea, espacio o coma):"))

        self.text_facturas_validacion = QTextEdit()
        grupo_layout.addWidget(self.text_facturas_validacion)

        self.boton_validacion = QPushButton("Validar Soportes")
        self.boton_validacion.clicked.connect(self.ejecutar_validacion)
        grupo_layout.addWidget(self.boton_validacion)

        layout.addWidget(grupo)
        layout.addStretch()

    def setup_tab_excels(self):
        layout = QVBoxLayout(self.tab_excels)
        grupo = QGroupBox("Consolidación automática de Excel")
        grupo_layout = QVBoxLayout(grupo)

        self.ruta_origen_excel_le, ly_origen = crear_selector_carpeta("Carpeta con Excels:", "Seleccionar carpeta con Excel")
        self.ruta_destino_excel_le, ly_destino = crear_selector_carpeta("Carpeta de salida:", "Seleccionar carpeta de salida")

        grupo_layout.addLayout(ly_origen)
        grupo_layout.addLayout(ly_destino)

        nombre_layout = QHBoxLayout()
        nombre_layout.addWidget(QLabel("Nombre archivo salida:"))
        self.nombre_salida_excel_le = QLineEdit("consolidado_excel.xlsx")
        nombre_layout.addWidget(self.nombre_salida_excel_le)
        grupo_layout.addLayout(nombre_layout)

        self.checkbox_excel_subcarpetas = QCheckBox("Incluir subcarpetas")
        grupo_layout.addWidget(self.checkbox_excel_subcarpetas)

        grupo_layout.addWidget(
            QLabel(
                "La herramienta detecta archivos con la misma estructura y genera un consolidado con la misma hoja y las mismas columnas del archivo original."
            )
        )

        self.boton_unir_excels = QPushButton("Unir Excels")
        self.boton_unir_excels.clicked.connect(self.ejecutar_union_excels)
        grupo_layout.addWidget(self.boton_unir_excels)

        layout.addWidget(grupo)
        layout.addStretch()

    def ejecutar_busqueda(self):
        facturas = self._obtener_facturas(self.text_facturas_busqueda)
        carpeta_origen = self.ruta_origen_busqueda_le.text().strip()
        carpeta_destino = self.ruta_destino_busqueda_le.text().strip()

        if not carpeta_origen or not carpeta_destino or not facturas:
            self.log_browser.append(f"<font color='{self.color_error}'>Complete origen, destino y listado de facturas.</font>")
            return

        parametros = {
            'modo_busqueda': self.combo_modo_busqueda.currentData(),
            'facturas': facturas,
            'carpeta_origen': carpeta_origen,
            'carpeta_destino': carpeta_destino,
        }
        self.lanzar_worker(parametros, "buscar")




    def ejecutar_validacion(self):
        facturas = self._obtener_facturas(self.text_facturas_validacion)
        carpeta_validacion = self.ruta_validacion_le.text().strip()

        if not carpeta_validacion or not facturas:
            self.log_browser.append(f"<font color='{self.color_error}'>Seleccione la carpeta a validar y cargue facturas.</font>")
            return

        parametros = {
            'modo_validacion': self.combo_modo_validacion.currentData(),
            'facturas': facturas,
            'carpeta_validacion': carpeta_validacion,
        }
        self.lanzar_worker(parametros, "validar")

    def ejecutar_union_excels(self):
        carpeta_origen = self.ruta_origen_excel_le.text().strip()
        carpeta_destino = self.ruta_destino_excel_le.text().strip()
        nombre_salida = self.nombre_salida_excel_le.text().strip()

        if not carpeta_origen or not carpeta_destino:
            self.log_browser.append(
                f"<font color='{self.color_error}'>Seleccione la carpeta origen y la carpeta de salida para consolidar Excel.</font>"
            )
            return

        parametros = {
            'carpeta_origen': carpeta_origen,
            'carpeta_destino': carpeta_destino,
            'nombre_salida': nombre_salida,
            'incluir_subcarpetas': self.checkbox_excel_subcarpetas.isChecked(),
        }
        self.lanzar_worker(parametros, "unir_excels")

    def lanzar_worker(self, parametros, modo):
        if self.hilo_trabajo and self.hilo_trabajo.isRunning():
            return

        self.modo_activo = modo
        self.log_browser.clear()
        self.tabs.setEnabled(False)
        self.boton_cancelar.setEnabled(True)

        self.hilo_trabajo = QThread()
        self.worker = FuncionalidadesPreviWorker(parametros, modo)
        self.worker.moveToThread(self.hilo_trabajo)

        self.hilo_trabajo.started.connect(self.worker.ejecutar)
        self.worker.progreso_actualizado.connect(self.log_browser.append)
        self.worker.proceso_finalizado.connect(self.finalizar_proceso)

        self.hilo_trabajo.start()

    def cancelar_proceso(self):
        if self.worker and self.hilo_trabajo and self.hilo_trabajo.isRunning():
            self.worker.cancelar()
            self.log_browser.append(
                f"<font color='{self.color_advertencia}'>Cancelando... espere a que termine el paso actual.</font>"
            )
            self.boton_cancelar.setEnabled(False)

    def finalizar_proceso(self, resultados):
        self.tabs.setEnabled(True)
        self.boton_cancelar.setEnabled(False)

        if 'error' in resultados:
            self.log_browser.append(f"<font color='{self.color_error}'><b>Error: {resultados['error']}</b></font>")
        elif resultados.get('estado') == 'cancelado':
            self.log_browser.append(
                f"<font color='{self.color_advertencia}'><b>Proceso cancelado por el usuario.</b></font>"
            )
        else:
            self.log_browser.append(f"<font color='{self.color_exito}'><b>Proceso finalizado.</b></font>")
            self._mostrar_resumen(resultados)

        if self.hilo_trabajo:
            self.hilo_trabajo.quit()
            self.hilo_trabajo.wait()
        self.worker = None
        self.hilo_trabajo = None
        self.modo_activo = None

    def _mostrar_resumen(self, resultados):
        if self.modo_activo == "buscar":
            self.log_browser.append(
                f"<font color='{self.color_exito}'>Completas: {resultados.get('exitos', 0)} | "
                f"Incompletas: {resultados.get('errores', 0)} | Archivos: {resultados.get('archivos', 0)}</font>"
            )
        elif self.modo_activo == "comprimir":
            self.log_browser.append(
                f"<font color='{self.color_exito}'>ZIPs: {resultados.get('zips', 0)} | "
                f"Facturas: {resultados.get('facturas', 0)} | Omitidas: {resultados.get('omitidas', 0)}</font>"
            )
        elif self.modo_activo == "validar":
            self.log_browser.append(
                f"<font color='{self.color_exito}'>Total: {resultados.get('total', 0)} | "
                f"Completas: {resultados.get('completas', 0)} | Incompletas: {resultados.get('incompletas', 0)}</font>"
            )
        elif self.modo_activo == "unir_excels":
            self.log_browser.append(
                f"<font color='{self.color_exito}'>Encontrados: {resultados.get('archivos_encontrados', 0)} | "
                f"Consolidados: {resultados.get('archivos_consolidados', 0)} | Filas: {resultados.get('filas_consolidadas', 0)} | "
                f"Omitidos: {resultados.get('omitidos', 0)}</font>"
            )
            self.log_browser.append(
                f"<font color='{self.color_exito}'>Salida: {resultados.get('archivo_salida', '')}</font>"
            )

    def _obtener_facturas(self, text_edit: QTextEdit) -> list[str]:
        texto = text_edit.toPlainText()
        return [factura.strip() for factura in re.split(r'[,\s\n]+', texto) if factura.strip()]