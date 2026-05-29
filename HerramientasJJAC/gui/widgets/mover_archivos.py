import re

from PySide6.QtCore import QThread, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from logica.workers.mover_archivos_logic import MoverArchivosWorker


class MoverArchivosWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.thread = None

        self.crear_widgets()

    def crear_widgets(self):
        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(20, 20, 20, 20)
        layout_principal.setSpacing(15)

        label_titulo = QLabel("Mover PDFs por factura")
        label_titulo.setObjectName("AyudaTitulo")
        label_titulo.setAlignment(Qt.AlignCenter)
        layout_principal.addWidget(label_titulo)

        group_inputs = QGroupBox("1. Entradas de datos")
        layout_inputs = QVBoxLayout(group_inputs)
        layout_inputs.setSpacing(10)

        label_info = QLabel(
            "Pega las facturas una por línea o separadas por espacios/comas. "
            "Se moverán o copiarán todos los PDFs cuyo nombre contenga la factura."
        )
        label_info.setWordWrap(True)
        layout_inputs.addWidget(label_info)

        self.editor_facturas = QTextEdit()
        self.editor_facturas.setPlaceholderText(
            "COEX28446\nCOEX33972\nCOEX36137\n\nTambién acepta: COEX28446, COEX33972 COEX36137"
        )
        layout_inputs.addWidget(self.editor_facturas)

        layout_origen = QHBoxLayout()
        self.line_origen = QLineEdit()
        self.line_origen.setPlaceholderText("Seleccione la carpeta de origen...")
        self.line_origen.setReadOnly(True)
        btn_origen = QPushButton("Seleccionar...")
        btn_origen.clicked.connect(lambda: self._seleccionar_carpeta(self.line_origen))
        layout_origen.addWidget(self.line_origen)
        layout_origen.addWidget(btn_origen)
        layout_inputs.addLayout(layout_origen)

        layout_destino = QHBoxLayout()
        self.line_destino = QLineEdit()
        self.line_destino.setPlaceholderText("Seleccione la carpeta de destino...")
        self.line_destino.setReadOnly(True)
        btn_destino = QPushButton("Seleccionar...")
        btn_destino.clicked.connect(lambda: self._seleccionar_carpeta(self.line_destino))
        layout_destino.addWidget(self.line_destino)
        layout_destino.addWidget(btn_destino)
        layout_inputs.addLayout(layout_destino)

        layout_principal.addWidget(group_inputs)

        layout_botones = QHBoxLayout()
        self.btn_iniciar_mover = QPushButton("Iniciar proceso de mover")
        self.btn_iniciar_mover.setObjectName("BotonPrincipal")
        self.btn_iniciar_mover.setFixedHeight(40)
        self.btn_iniciar_mover.clicked.connect(lambda: self.iniciar_proceso("mover"))
        layout_botones.addWidget(self.btn_iniciar_mover)

        self.btn_iniciar_copiar = QPushButton("Iniciar proceso de copiar")
        self.btn_iniciar_copiar.setObjectName("BotonPrincipal")
        self.btn_iniciar_copiar.setFixedHeight(40)
        self.btn_iniciar_copiar.clicked.connect(lambda: self.iniciar_proceso("copiar"))
        layout_botones.addWidget(self.btn_iniciar_copiar)

        layout_principal.addLayout(layout_botones)

        group_progreso = QGroupBox("2. Progreso")
        layout_progreso = QVBoxLayout(group_progreso)
        self.label_progreso = QLabel("Esperando para iniciar...")
        self.barra_progreso = QProgressBar()
        self.barra_progreso.setValue(0)
        layout_progreso.addWidget(self.label_progreso)
        layout_progreso.addWidget(self.barra_progreso)
        layout_principal.addWidget(group_progreso)

        group_results = QGroupBox("3. Resultados")
        layout_results = QVBoxLayout(group_results)
        self.log_viewer = QTextBrowser()
        layout_results.addWidget(self.log_viewer)
        layout_principal.addWidget(group_results)

    def _seleccionar_carpeta(self, line_edit_widget):
        directory = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta")
        if directory:
            line_edit_widget.setText(directory)

    def _obtener_facturas(self) -> list[str]:
        facturas_raw = self.editor_facturas.toPlainText().strip()
        tokens = [token.strip().upper() for token in re.split(r"[\s,;]+", facturas_raw) if token.strip()]
        facturas_unicas = list(dict.fromkeys(tokens))
        return facturas_unicas

    def iniciar_proceso(self, accion: str):
        facturas = self._obtener_facturas()
        dir_origen = self.line_origen.text().strip()
        dir_destino = self.line_destino.text().strip()

        if not facturas or not dir_origen or not dir_destino:
            QMessageBox.warning(self, "Datos incompletos", "Por favor, complete todos los campos.")
            return

        if dir_origen == dir_destino:
            QMessageBox.warning(self, "Rutas no válidas", "La carpeta de origen y destino no pueden ser la misma.")
            return

        if self.thread and self.thread.isRunning():
            QMessageBox.warning(self, "Proceso en curso", "Espere a que termine el proceso actual.")
            return

        self._actualizar_estado_ejecucion(True)
        self.barra_progreso.setValue(0)
        self.label_progreso.setText("Preparando proceso...")
        self.log_viewer.clear()
        self.log_viewer.append(f"Iniciando proceso de {accion} para {len(facturas)} facturas...")

        self.thread = QThread()
        self.worker = MoverArchivosWorker(facturas, dir_origen, dir_destino, accion)
        self.worker.moveToThread(self.thread)

        self.worker.log_generado.connect(self.actualizar_log)
        self.worker.progreso_actualizado.connect(self.actualizar_progreso)
        self.worker.proceso_finalizado.connect(self.finalizar_proceso)
        self.thread.started.connect(self.worker.ejecutar)

        self.thread.start()

    def _actualizar_estado_ejecucion(self, ejecutando: bool):
        self.btn_iniciar_mover.setEnabled(not ejecutando)
        self.btn_iniciar_copiar.setEnabled(not ejecutando)
        if ejecutando:
            self.btn_iniciar_mover.setText("Procesando...")
            self.btn_iniciar_copiar.setText("Procesando...")
        else:
            self.btn_iniciar_mover.setText("Iniciar proceso de mover")
            self.btn_iniciar_copiar.setText("Iniciar proceso de copiar")

    def actualizar_log(self, mensaje_html: str):
        self.log_viewer.append(mensaje_html)

    def actualizar_progreso(self, mensaje: str, porcentaje: float):
        self.label_progreso.setText(mensaje)
        self.barra_progreso.setValue(int(porcentaje))

    def finalizar_proceso(self, resumen: dict):
        self.actualizar_progreso("Proceso finalizado.", 100)
        self._actualizar_estado_ejecucion(False)

        if self.thread:
            self.thread.quit()
            self.thread.wait()

        self.thread = None
        self.worker = None

        QMessageBox.information(
            self,
            "Proceso finalizado",
            (
                "Proceso finalizado.\n\n"
                f"Facturas con coincidencias: {resumen.get('facturas_con_coincidencias', 0)}\n"
                f"Facturas sin coincidencias: {resumen.get('facturas_sin_coincidencias', 0)}\n"
                f"Archivos procesados: {resumen.get('archivos_procesados', 0)}\n"
                f"Archivos omitidos: {resumen.get('archivos_omitidos', 0)}\n"
                f"Errores: {resumen.get('errores', 0)}"
            ),
        )