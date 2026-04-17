# gui/widgets/respuesta_glosas_salud_total.py
import re

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit,
    QGroupBox, QLabel, QTabWidget, QTextEdit, QFileDialog
)
from PySide6.QtCore import QThread, Qt

from gui.common.componentes_comunes import crear_selector_carpeta, setup_logging_browser
from logica.workers.respuesta_glosas_salud_total_logic import (
    AjustarTXTWorker, ConvertirCSVWorker, COLUMNAS_REQUERIDAS
)


class RespuestaGlosasSaludTotalWidget(QWidget):
    """
    Widget con dos funcionalidades para responder glosas de Salud Total:

    TAB 1 – Ajustar TXT:
        Toma el TXT original (delimitado por |) que envía Salud Total,
        conserva sólo las columnas requeridas y agrega vacías las columnas
        nuevas que el usuario debe diligenciar en Excel.

    TAB 2 – CSV → TXT(s):
        Toma el CSV (delimitado por comas) diligenciado por el usuario en
        Excel, filtra por radicados indicados y genera un TXT por radicado
        delimitado por | con el nombre RTAGLOSA_NIT_ddMMAAAA_N.txt.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.hilo_trabajo = None
        self.worker = None

        self.color_exito = "#2ecc71"
        self.color_error = "#e74c3c"
        self.color_advertencia = "#f39c12"
        self.color_info = "#3498db"

        self._init_ui()

    # ------------------------------------------------------------------
    # Construcción de la interfaz
    # ------------------------------------------------------------------

    def _init_ui(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)

        titulo = QLabel("Respuesta a Glosas – Salud Total EPS")
        titulo.setAlignment(Qt.AlignCenter)
        titulo.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout_principal.addWidget(titulo)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(
            "QTabBar::tab { color: black; background: #e0e0e0; padding: 8px 15px; margin: 2px; }"
            "QTabBar::tab:selected { background: #ffffff; font-weight: bold; }"
        )
        layout_principal.addWidget(self.tabs)

        self.tab_ajustar = QWidget()
        self._setup_tab_ajustar()
        self.tabs.addTab(self.tab_ajustar, "1. Ajustar TXT")

        self.tab_csv = QWidget()
        self._setup_tab_csv()
        self.tabs.addTab(self.tab_csv, "2. CSV → TXT(s)")

        self.log_browser, log_group = setup_logging_browser("Resultados del Proceso")
        layout_principal.addWidget(log_group)

        self.boton_cancelar = QPushButton("Cancelar Proceso")
        self.boton_cancelar.setEnabled(False)
        layout_principal.addWidget(self.boton_cancelar)

    # --- TAB 1: Ajustar TXT ---

    def _setup_tab_ajustar(self):
        layout = QVBoxLayout(self.tab_ajustar)

        grupo = QGroupBox("Ajustar TXT de Salud Total")
        g_layout = QVBoxLayout(grupo)
        g_layout.setSpacing(10)

        # Selector de archivo TXT
        ly_txt = QHBoxLayout()
        ly_txt.addWidget(QLabel("Archivo TXT original:"))
        self.ruta_txt_le = QLineEdit()
        self.ruta_txt_le.setReadOnly(True)
        self.ruta_txt_le.setPlaceholderText("Seleccione el TXT enviado por Salud Total…")
        btn_txt = QPushButton("Buscar…")
        btn_txt.clicked.connect(self._seleccionar_txt)
        ly_txt.addWidget(self.ruta_txt_le)
        ly_txt.addWidget(btn_txt)

        # Selector de carpeta de salida
        self.ruta_salida_ajustar_le, ly_salida = crear_selector_carpeta(
            "Carpeta de salida:", "Seleccionar carpeta de salida"
        )

        # Información sobre columnas de salida
        info_cols = QLabel(
            f"Columnas del archivo ajustado: {' | '.join(COLUMNAS_REQUERIDAS)}"
        )
        info_cols.setWordWrap(True)
        info_cols.setStyleSheet("color: #888; font-size: 11px;")

        btn_ajustar = QPushButton("Ajustar TXT")
        btn_ajustar.clicked.connect(self._ejecutar_ajustar)

        g_layout.addLayout(ly_txt)
        g_layout.addLayout(ly_salida)
        g_layout.addWidget(info_cols)
        g_layout.addWidget(btn_ajustar)

        layout.addWidget(grupo)
        layout.addStretch()

    # --- TAB 2: CSV → TXTs ---

    def _setup_tab_csv(self):
        layout = QVBoxLayout(self.tab_csv)

        grupo = QGroupBox("Convertir CSV diligenciado → TXT(s) para Filezilla")
        g_layout = QVBoxLayout(grupo)
        g_layout.setSpacing(10)

        # Selector de archivo CSV
        ly_csv = QHBoxLayout()
        ly_csv.addWidget(QLabel("Archivo CSV:"))
        self.ruta_csv_le = QLineEdit()
        self.ruta_csv_le.setReadOnly(True)
        self.ruta_csv_le.setPlaceholderText("Seleccione el CSV guardado desde Excel…")
        btn_csv = QPushButton("Buscar…")
        btn_csv.clicked.connect(self._seleccionar_csv)
        ly_csv.addWidget(self.ruta_csv_le)
        ly_csv.addWidget(btn_csv)



        # NIT del prestador (fijo)
        ly_nit = QHBoxLayout()
        ly_nit.addWidget(QLabel("NIT del prestador:"))
        self.nit_label = QLabel("800209891")
        self.nit_label.setStyleSheet("font-weight: bold; color: #e0e0e0;")
        ly_nit.addWidget(self.nit_label)
        ly_nit.addStretch()

        # Selector de carpeta de salida
        self.ruta_salida_csv_le, ly_salida = crear_selector_carpeta(
            "Carpeta de salida:", "Seleccionar carpeta de salida"
        )
        info_busqueda = QLabel(
            "Si hay subcarpetas con cartas glosas coincidentes, los TXT se guardarán automáticamente en ellas. "
            "Si no, se guardarán en esta carpeta."
        )
        info_busqueda.setWordWrap(True)
        info_busqueda.setStyleSheet("color: #888; font-size: 10px;")

        # Lista de facturas
        lbl_rad = QLabel(
            "Facturas a separar (una por línea o separadas por coma/espacio). "
            "Formato: PREFIJOnumero, ej: FECR363035"
        )
        self.text_radicados = QTextEdit()
        self.text_radicados.setPlaceholderText(
            "FECR363035\nCOEX38678\nCOEX38677\nFECR363449"
        )
        self.text_radicados.setFixedHeight(110)

        # Nombre de archivo resultante (info)
        info_nombre = QLabel(
            "Los archivos se nombrarán: RTAGLOSA_<NIT>_<ddMMAAAA>_<consecutivo>.txt\n"
            "El consecutivo se reinicia cada día y se guarda en la carpeta de salida."
        )
        info_nombre.setWordWrap(True)
        info_nombre.setStyleSheet("color: #888; font-size: 11px;")

        btn_convertir = QPushButton("Generar TXT(s)")
        btn_convertir.clicked.connect(self._ejecutar_convertir)

        g_layout.addLayout(ly_csv)
        g_layout.addLayout(ly_nit)
        g_layout.addLayout(ly_salida)
        g_layout.addWidget(info_busqueda)
        g_layout.addWidget(lbl_rad)
        g_layout.addWidget(self.text_radicados)
        g_layout.addWidget(info_nombre)
        g_layout.addWidget(btn_convertir)

        layout.addWidget(grupo)
        layout.addStretch()

    # ------------------------------------------------------------------
    # Selección de archivos
    # ------------------------------------------------------------------

    def _seleccionar_txt(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo TXT", "",
            "Archivos de texto (*.txt);;Todos los archivos (*)"
        )
        if ruta:
            self.ruta_txt_le.setText(ruta)

    def _seleccionar_csv(self):
        ruta, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo CSV", "",
            "Archivos CSV (*.csv);;Todos los archivos (*)"
        )
        if ruta:
            self.ruta_csv_le.setText(ruta)

    # ------------------------------------------------------------------
    # Ejecución de procesos
    # ------------------------------------------------------------------

    def _ejecutar_ajustar(self):
        ruta_txt = self.ruta_txt_le.text().strip()
        carpeta_salida = self.ruta_salida_ajustar_le.text().strip()

        if not ruta_txt:
            self.log_browser.append(
                f"<font color='{self.color_error}'>Seleccione el archivo TXT original.</font>"
            )
            return
        if not carpeta_salida:
            self.log_browser.append(
                f"<font color='{self.color_error}'>Seleccione la carpeta de salida.</font>"
            )
            return

        worker = AjustarTXTWorker(ruta_txt, carpeta_salida)
        self._lanzar_worker(worker)

    def _ejecutar_convertir(self):
        ruta_csv = self.ruta_csv_le.text().strip()
        nit = "800209891"  # NIT fijo
        carpeta_salida = self.ruta_salida_csv_le.text().strip()
        texto_facturas = self.text_radicados.toPlainText()

        facturas = [r.strip() for r in re.split(r'[,\s\n]+', texto_facturas) if r.strip()]

        if not ruta_csv:
            self.log_browser.append(
                f"<font color='{self.color_error}'>Seleccione el archivo CSV.</font>"
            )
            return
        if not carpeta_salida:
            self.log_browser.append(
                f"<font color='{self.color_error}'>Seleccione la carpeta de salida.</font>"
            )
            return
        if not facturas:
            self.log_browser.append(
                f"<font color='{self.color_error}'>Ingrese al menos una factura (ej: FECR363035).</font>"
            )
            return

        worker = ConvertirCSVWorker(ruta_csv, nit, facturas, carpeta_salida)
        self._lanzar_worker(worker)

    # ------------------------------------------------------------------
    # Gestión de hilos
    # ------------------------------------------------------------------

    def _lanzar_worker(self, worker):
        self.boton_cancelar.setEnabled(False)  # no cancelable en este flujo
        self.tabs.setEnabled(False)
        self.log_browser.clear()

        self.hilo_trabajo = QThread()
        self.worker = worker
        self.worker.moveToThread(self.hilo_trabajo)

        self.worker.progreso_actualizado.connect(self.log_browser.append)
        self.worker.proceso_finalizado.connect(self._finalizar_proceso)
        self.hilo_trabajo.started.connect(self.worker.ejecutar)

        self.hilo_trabajo.start()

    def _finalizar_proceso(self, resultados: dict):
        self.tabs.setEnabled(True)
        self.boton_cancelar.setEnabled(False)

        exitosos = resultados.get('exitosos', [])
        fallidos = resultados.get('fallidos', [])

        if exitosos:
            self.log_browser.append(
                f"<br><font color='{self.color_exito}'>"
                f"<b>Proceso completado: {len(exitosos)} archivo(s) generado(s).</b>"
                f"</font>"
            )
        if fallidos:
            self.log_browser.append(
                f"<font color='{self.color_error}'>"
                f"<b>{len(fallidos)} error(es):</b></font>"
            )
            for f in fallidos:
                self.log_browser.append(
                    f"<font color='{self.color_error}'>"
                    f"  ✖ {f.get('archivo', '')} — {f.get('razon', '')}</font>"
                )

        if self.hilo_trabajo:
            self.hilo_trabajo.quit()
            self.hilo_trabajo.wait()
