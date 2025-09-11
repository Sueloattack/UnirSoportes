# gui.py
import customtkinter
from tkinter import filedialog, messagebox
import threading
import core_logic

class ResultsWindow(customtkinter.CTkToplevel):
    """
    Ventana de resultados que muestra los éxitos y fallos del proceso.
    """
    def __init__(self, master, results):
        super().__init__(master)
        self.title("Resultados del Procesamiento")
        self.geometry("800x600")
        
        # Estilos y colores
        font_title = customtkinter.CTkFont(size=20, weight="bold")
        font_section = customtkinter.CTkFont(size=16, weight="bold")
        COLOR_SUCCESS = ("#2B8B2B", "#32A932") # Verde
        COLOR_FAILURE = ("#9E2A2B", "#C04A4B") # Rojo
        COLOR_INFO_TEXT = ("#000000", "#FFFFFF") # Negro/Blanco para el texto

        # Título de la ventana
        label_title = customtkinter.CTkLabel(self, text="Resultados del Procesamiento", font=font_title)
        label_title.pack(pady=(20, 10))

        # Crear un frame con scroll para contener todos los resultados
        scrollable_frame = customtkinter.CTkScrollableFrame(self)
        scrollable_frame.pack(fill="both", expand=True, padx=20, pady=10)
        scrollable_frame.grid_columnconfigure(0, weight=1)
        
        def add_result_entry(parent, icon, folder, reason, icon_color):
            """Función auxiliar para añadir una línea de resultado."""
            item_frame = customtkinter.CTkFrame(parent, fg_color="transparent")
            item_frame.pack(fill="x", padx=10, pady=2)
            item_frame.grid_columnconfigure(1, weight=1)

            label_folder = customtkinter.CTkLabel(item_frame, text=f"{icon} {folder}:", text_color=icon_color, font=customtkinter.CTkFont(weight="bold"))
            label_folder.grid(row=0, column=0, sticky="w")

            label_reason = customtkinter.CTkLabel(item_frame, text=reason, wraplength=600, justify="left", text_color=COLOR_INFO_TEXT)
            label_reason.grid(row=0, column=1, sticky="w", padx=(10, 0))

        # Sección de Éxitos
        if results['successful']:
            label_success = customtkinter.CTkLabel(scrollable_frame, text=f"ÉXITO ({len(results['successful'])})", font=font_section, text_color=COLOR_SUCCESS)
            label_success.pack(anchor="w", pady=(10, 5), padx=5)
            
            for item in results['successful']:
                add_result_entry(scrollable_frame, "✔", item['folder'], item['reason'], COLOR_SUCCESS)

        # Sección de Errores
        if results['failed']:
            label_failure = customtkinter.CTkLabel(scrollable_frame, text=f"ERRORES ({len(results['failed'])})", font=font_section, text_color=COLOR_FAILURE)
            label_failure.pack(anchor="w", pady=(20, 5), padx=5)

            for item in results['failed']:
                add_result_entry(scrollable_frame, "✖", item['folder'], item['reason'], COLOR_FAILURE)
                
        # Botón de cerrar
        close_button = customtkinter.CTkButton(self, text="Cerrar", command=self.destroy, width=120)
        close_button.pack(pady=20)


class App(customtkinter.CTk):
    """
    Ventana principal de la aplicación.
    """
    def __init__(self):
        super().__init__()
        self.title("Unificador de Soportes")
        # Aumentamos la altura para el nuevo widget
        self.geometry("700x400")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # Aumentado de 2 a 3 para el nuevo widget

        self.selected_folder_path = ""
        self.processing_mode = "Aseguradoras" # Modo por defecto
        self.is_processing = False
        self.results_window = None
        self.create_widgets()

    def create_widgets(self):
        # Frame de selección de carpeta (en la fila 0)
        frame_select = customtkinter.CTkFrame(self)
        frame_select.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        frame_select.grid_columnconfigure(1, weight=1)
        
        label_folder = customtkinter.CTkLabel(frame_select, text="Carpeta de Cuenta de Cobro:")
        label_folder.grid(row=0, column=0, padx=10, pady=10)
        
        self.entry_folder = customtkinter.CTkEntry(frame_select, placeholder_text="Ninguna carpeta seleccionada...", state="readonly")
        self.entry_folder.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        button_browse = customtkinter.CTkButton(frame_select, text="Seleccionar...", command=self.browse_folder)
        button_browse.grid(row=0, column=2, padx=10, pady=10)

        # --- NUEVO FRAME PARA SELECCIÓN DE MODO --- (en la fila 1)
        frame_mode = customtkinter.CTkFrame(self)
        frame_mode.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        frame_mode.grid_columnconfigure(1, weight=1)
        
        label_mode = customtkinter.CTkLabel(frame_mode, text="Modo de Operación:")
        label_mode.grid(row=0, column=0, padx=10, pady=10)

        self.mode_selector = customtkinter.CTkSegmentedButton(
            frame_mode,
            values=["Aseguradoras", "ADRES"],
            command=self.set_processing_mode
        )
        self.mode_selector.set("Aseguradoras") # Establecer el valor inicial
        self.mode_selector.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        
        # Botón de proceso (en la fila 2)
        self.button_process = customtkinter.CTkButton(self, text="Iniciar Proceso de Unión", command=self.start_processing_thread, height=40)
        self.button_process.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        # Frame de progreso (en la fila 3)
        frame_progress = customtkinter.CTkFrame(self, fg_color="transparent")
        frame_progress.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        frame_progress.grid_columnconfigure(0, weight=1)
        
        self.progress_label = customtkinter.CTkLabel(frame_progress, text="Esperando para iniciar...")
        self.progress_label.grid(row=0, column=0, sticky="w", padx=5)
        
        self.progress_bar = customtkinter.CTkProgressBar(frame_progress, orientation="horizontal", mode="determinate")
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, padx=5, pady=(0, 10), sticky="ew")

    def set_processing_mode(self, value):
        """Callback que se activa al cambiar de modo para guardar el estado."""
        self.processing_mode = value

    def browse_folder(self):
        """Abre un diálogo para seleccionar la carpeta raíz."""
        path = filedialog.askdirectory(title="Selecciona la carpeta raíz de la Cuenta de Cobro")
        if path:
            self.selected_folder_path = path
            self.entry_folder.configure(state="normal")
            self.entry_folder.delete(0, "end")
            self.entry_folder.insert(0, self.selected_folder_path)
            self.entry_folder.configure(state="readonly")

    def start_processing_thread(self):
        """Inicia el proceso de lógica de negocio en un hilo separado."""
        if self.is_processing:
            messagebox.showwarning("Proceso en curso", "Ya hay un proceso en ejecución.")
            return
        if not self.selected_folder_path:
            messagebox.showerror("Error", "Por favor, selecciona una carpeta primero.")
            return
            
        self.is_processing = True
        self.button_process.configure(state="disabled", text="Procesando...")
        self.progress_bar.set(0)
        
        # Pasa el modo seleccionado al hilo de trabajo
        thread = threading.Thread(target=core_logic.process_folders, 
                                  args=(self.selected_folder_path, self, self.processing_mode))
        thread.daemon = True
        thread.start()

    def update_progress(self, current_folder_name, percentage):
        """Actualiza la barra y el texto de progreso desde el hilo de trabajo."""
        self.progress_label.configure(text=f"Procesando: {current_folder_name}...")
        self.progress_bar.set(percentage / 100)

    def process_finished(self, results):
        """Se ejecuta cuando el hilo de trabajo ha terminado."""
        if self.results_window is not None and self.results_window.winfo_exists():
            self.results_window.destroy()
        
        self.results_window = ResultsWindow(self, results)
        self.progress_label.configure(text="Proceso finalizado. Listo para empezar de nuevo.")
        self.button_process.configure(state="normal", text="Iniciar Proceso de Unión")
        self.is_processing = False