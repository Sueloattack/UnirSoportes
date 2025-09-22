import os
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QStackedWidget, QLabel, 
                               QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator, QAbstractItemView)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

class VentanaPrincipal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Herramientas JJAC")
        self.setGeometry(100, 100, 1200, 700)
        self.sidebar_collapsed = True
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar_container = QWidget()
        self.sidebar_container.setObjectName("Sidebar")
        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(5, 5, 5, 5)
        sidebar_layout.setSpacing(10)
        main_layout.addWidget(self.sidebar_container)
        

        self.toggle_button = QPushButton()
        self.toggle_button.setObjectName("ToggleButton")
        self.toggle_button.setFixedSize(QSize(40, 40))
        self.toggle_button.clicked.connect(self.toggle_sidebar)
        sidebar_layout.addWidget(self.toggle_button, 0, Qt.AlignLeft)

        # Ruta al icono chevrons-right.svg
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Sube tres niveles para llegar a HerramientasJJAC
        self.chevrons_icon_path = os.path.join(project_root, "chevrons-right.svg")
        self.category_icon_path = os.path.join(project_root, "chevron-right.svg")
        self.widget_icon_path = os.path.join(project_root, "chevrons-down.svg")
        
        self.sidebar_tree = QTreeWidget()
        self.sidebar_tree.setObjectName("SidebarTree")
        self.sidebar_tree.setIndentation(15)
        self.sidebar_tree.setHeaderHidden(True)
        self.sidebar_tree.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.sidebar_tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.sidebar_tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        sidebar_layout.addWidget(self.sidebar_tree)
        self.sidebar_tree.installEventFilter(self)

        self.stacked_widget = QStackedWidget()
        main_layout.addWidget(self.stacked_widget)
        
        self.item_to_widget_map = {} # Mapea id(QTreeWidgetItem) a índice de stacked_widget
        self.full_text_map = {}     # Mapea id(QTreeWidgetItem) a {'name': 'Full Name', 'abbr': 'ABBR'}

        self.poblar_menu() # Llama al nuevo método para llenar el menú

        self.sidebar_tree.currentItemChanged.connect(self.on_menu_item_changed)
        # self.sidebar_tree.itemClicked.connect(self.on_item_clicked_debug) # Nueva conexión para depuración
        self.sidebar_tree.expandAll()
        
        primer_item_seleccionable = self.sidebar_tree.topLevelItem(0).child(0)
        if primer_item_seleccionable:
            self.sidebar_tree.setCurrentItem(primer_item_seleccionable)
        
        self.update_sidebar_state()

    def poblar_menu(self):
        # 1. Categoría Procesamiento y Unión
        cat_procesamiento = self._add_category("PROCESAMIENTO")
        self._add_widget(cat_procesamiento, "Unir Soportes", "US", "widgets.unir_soportes", "UnirSoportesWidget")
        self._add_widget(cat_procesamiento, "Procesamiento ADRES", "PA", "widgets.organizador_respuestas_adres", "OrganizadorRespuestasAdresWidget")

        # 2. Categoría Organización de Archivos
        cat_organizacion = self._add_category("ORGANIZACIÓN")
        self._add_widget(cat_organizacion, "Organizar PDFs", "ORG", "widgets.organizador_respuestas", "OrganizadorRespuestasWidget")
        self._add_widget(cat_organizacion, "Organizar XMLs", "XML", "widgets.organizador_xml", "OrganizadorXMLWidget")
        self._add_widget(cat_organizacion, "Reorganizar Sedes", "ENV", "widgets.reorganizador_sedes", "ReorganizadorSedesWidget")

        # 3. Categoría Búsqueda y Extracción
        cat_busqueda = self._add_category("BÚSQUEDA")
        self._add_widget(cat_busqueda, "Traer Soportes ADRES", "TSA", "widgets.traer_soportes_adres", "TraerSoportesAdresWidget")
        self._add_widget(cat_busqueda, "Buscador Soportes Ratificadas", "BSR", "widgets.buscador_soportes_ratificados", "BuscadorSoportesRatificadosWidget")
        self._add_widget(cat_busqueda, "Buscador de Carpetas", "BC", "widgets.buscador_carpetas_ratificadas", "BuscadorCarpetasRatificadasWidget")

        # 4. Categoría Auditoría
        cat_auditoria = self._add_category("AUDITORÍA")
        self._add_widget(cat_auditoria, "Auditor de Facturas", "AUD", "widgets.auditor_cuentas_cobro", "AuditorCuentasCobroWidget")
        
        # 5. Categoría Sistema
        cat_sistema = self._add_category("SISTEMA")
        self._add_widget(cat_sistema, "Ayuda y Recomendaciones", "AYU", "widgets.panel_ayuda", "PanelAyudaWidget")

    def _add_category(self, name: str) -> QTreeWidgetItem:
        category_item = QTreeWidgetItem(self.sidebar_tree, [name.upper()])
        category_item.setFlags(category_item.flags() & ~Qt.ItemIsSelectable)
        category_item.setData(0, Qt.UserRole, "category")
        category_item.setTextAlignment(0, Qt.AlignTop | Qt.AlignLeft) # Alineación para categorías
        if os.path.exists(self.category_icon_path):
            icon = QIcon(self.category_icon_path)
            # if icon.isNull():
                # print(f"DEBUG: Failed to load category icon from {self.category_icon_path}")
            category_item.setIcon(0, icon)
            category_item.setSizeHint(0, QSize(32, 32)) # Ajustar tamaño del icono
        self.full_text_map[id(category_item)] = {"name": name.upper(), "abbr": ""} # Store full name for categories
        return category_item

    def _add_widget(self, parent_item: QTreeWidgetItem, name, abbr, module_name, class_name):
        try:
            module = __import__(f"gui.{module_name}", fromlist=[class_name])
            widget_class = getattr(module, class_name)
            widget_instance = widget_class()
            widget_index = self.stacked_widget.addWidget(widget_instance)
            
            item = QTreeWidgetItem(parent_item)
            item.setText(0, name)
            item.setTextAlignment(0, Qt.AlignTop | Qt.AlignLeft) # Alineación para ítems de widget
            if os.path.exists(self.widget_icon_path):
                icon = QIcon(self.widget_icon_path)
                # if icon.isNull():
                    # print(f"DEBUG: Failed to load widget icon from {self.widget_icon_path}")
                item.setIcon(0, icon)
                item.setSizeHint(0, QSize(32, 32)) # Ajustar tamaño del icono
            
            self.item_to_widget_map[id(item)] = widget_index
            self.full_text_map[id(item)] = {"name": name, "abbr": abbr}

        except (ImportError, AttributeError, ModuleNotFoundError) as e:
            print(f"Error al cargar el widget '{name}': {e}")
            error_label = QLabel(f"Error al cargar:\n{name}\n\n({e})")
            error_label.setAlignment(Qt.AlignCenter)
            error_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.stacked_widget.addWidget(error_label)
            item = QTreeWidgetItem(parent_item, [f"Error: {abbr}"])
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(0, Qt.red)
            item.setTextAlignment(0, Qt.AlignTop | Qt.AlignLeft) # Alineación para ítems de error
            

    def on_menu_item_changed(self, current_item: QTreeWidgetItem, previous_item: QTreeWidgetItem):
        if current_item and current_item.flags() & Qt.ItemIsSelectable:
            widget_index = self.item_to_widget_map.get(id(current_item))
            if widget_index is not None:
                self.stacked_widget.setCurrentIndex(widget_index)
        # else:
            # print("  Item no seleccionable o nulo.")

    def toggle_sidebar(self):
        """Invierte el estado colapsado/expandido y actualiza la UI."""
        self.sidebar_collapsed = not self.sidebar_collapsed
        self.update_sidebar_state()

    def update_sidebar_state(self):
        """Aplica los cambios visuales según el estado del sidebar."""
        if self.sidebar_collapsed:
            self.sidebar_container.setFixedWidth(80) # Ancho para abreviaturas
            # Usar el icono SVG
            if os.path.exists(self.chevrons_icon_path):
                self.toggle_button.setIcon(QIcon(self.chevrons_icon_path))
                self.toggle_button.setText("") # Limpiar texto si hay icono
                self.toggle_button.setIconSize(QSize(32, 32)) # Ajustar tamaño del icono
            else:
                self.toggle_button.setText(">>") # Fallback si no se encuentra el icono
            
            # Actualizar texto de los ítems del árbol
            iterator = QTreeWidgetItemIterator(self.sidebar_tree)
            while iterator.value():
                item = iterator.value()
                if item.data(0, Qt.UserRole) == "category": # Si es categoría
                    item.setText(0, "") 
                    item.setToolTip(0, self.full_text_map.get(id(item), {}).get("name", "")) # Guardar texto original en tooltip
                else: # Si es un ítem de widget
                    item_id = id(item)
                    if item_id in self.full_text_map:
                        item.setText(0, "")
                iterator += 1
            self.sidebar_tree.expandAll() # Asegurar que las categorías estén expandidas

        else:
            self.sidebar_container.setFixedWidth(240)
            self.toggle_button.setIcon(QIcon()) # Limpiar icono
            self.toggle_button.setText("MENU") # Texto 'MENU'
            
            # Restaurar texto de los ítems del árbol
            iterator = QTreeWidgetItemIterator(self.sidebar_tree)
            while iterator.value():
                item = iterator.value()
                if item.data(0, Qt.UserRole) == "category": # Si es categoría
                    item.setText(0, self.full_text_map.get(id(item), {}).get("name", "")) # Restaurar desde tooltip
                else: # Si es un ítem de widget
                    item_id = id(item)
                    if item_id in self.full_text_map:
                        item.setText(0, self.full_text_map[item_id]["name"])
                iterator += 1
            self.sidebar_tree.expandAll() # Asegurar que las categorías estén expandidas
