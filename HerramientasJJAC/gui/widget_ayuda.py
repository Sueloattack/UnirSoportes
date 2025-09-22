# gui/widget_ayuda.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
import os

class WidgetAyuda(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("AyudaScrollArea")
        layout.addWidget(scroll_area)

        container = QWidget()
        container.setObjectName("TabContentWidget")
        scroll_area.setWidget(container)
        
        layout_ayuda = QVBoxLayout(container)
        layout_ayuda.setSpacing(20)

        # Add licencias.png
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        png_path = os.path.join(project_root, "licencias.png")
        if os.path.exists(png_path):
            pixmap = QPixmap(png_path)
            if not pixmap.isNull():
                image_label = QLabel()
                image_label.setPixmap(pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                image_label.setAlignment(Qt.AlignCenter)
                layout_ayuda.addWidget(image_label)
            else:
                print(f"Advertencia: No se pudo cargar la imagen desde '{png_path}'.")
        else:
            print(f"Advertencia: No se encontró el archivo de imagen en '{png_path}'.")

        titulo = QLabel("Recomendaciones de Uso")
        titulo.setObjectName("AyudaTitulo")
        layout_ayuda.addWidget(titulo)

        # Sección de Recomendaciones Generales
        layout_ayuda.addWidget(self.crear_seccion_ayuda(
            "Recomendaciones Generales",
            [
                ("📁 Carpetas", "Para la mayoría de las herramientas, debes seleccionar una carpeta 'raíz' que contenga las subcarpetas a procesar."),
                ("⏳ Procesos", "Una vez iniciado un proceso, espera a que termine. La barra de progreso te indicará el estado actual."),
                ("✅ Resultados", "Al finalizar, se mostrará una ventana con el resumen de los archivos procesados exitosamente y los errores encontrados.")
            ]
        ))

        # Sección para Unir Soportes
        layout_ayuda.addWidget(self.crear_seccion_ayuda(
            "Unir Soportes",
            [
                ("📄 Archivos", "Asegúrate de que cada subcarpeta contenga los PDFs y el XML de la factura que deseas unir."),
                ("🤖 Modos", "Usa el modo 'Aseguradoras' para el formato estándar y 'ADRES' para el formato específico de dicha entidad.")
            ]
        ))
        
        # Sección para Organizar PDFs
        layout_ayuda.addWidget(self.crear_seccion_ayuda(
            "Organizar PDFs",
            [
                ("📂 Estructura", "La carpeta seleccionada debe contener directamente los archivos PDF que quieres organizar en carpetas según su contenido.")
            ]
        ))

        # Agrega aquí más secciones para las otras herramientas...

    def crear_seccion_ayuda(self, titulo, items):
        frame = QFrame()
        frame.setObjectName("AyudaSeccionFrame")
        layout = QVBoxLayout(frame)

        label_titulo = QLabel(titulo)
        label_titulo.setObjectName("AyudaSeccionTitulo")
        layout.addWidget(label_titulo)

        for subtitulo, texto in items:
            label_item = QLabel(f"<b>{subtitulo}:</b> {texto}")
            label_item.setWordWrap(True)
            layout.addWidget(label_item)
        
        return frame
