import os
import shutil
from datetime import datetime

class LogicaTraerSoportesRatificadas:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback

    def _log(self, message):
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def buscar_y_copiar_soportes(
        self, invoice_numbers: list[str], search_dir: str, dest_dir: str
    ):
        if not os.path.isdir(search_dir):
            self._log(f"<p style='color:red;'>Error: El directorio de búsqueda no existe: {search_dir}</p>")
            return
        if not os.path.isdir(dest_dir):
            self._log(f"<p style='color:red;'>Error: El directorio de destino no existe: {dest_dir}</p>")
            return

        self._log("<p style='color:green;'>Iniciando búsqueda y copia de soportes...</p>")
        self._log(f"Números de factura a buscar: {', '.join(invoice_numbers)}")
        self._log(f"Directorio de búsqueda: {search_dir}")
        self._log(f"Directorio de destino: {dest_dir}")

        for invoice_number in invoice_numbers:
            self._log(f"<p style='color:blue;'>Buscando soportes para factura: {invoice_number}</p>")
            found_folders = self._find_invoice_folders(invoice_number, search_dir)

            if not found_folders:
                self._log(f"<p style='color:orange;'>No se encontraron carpetas para la factura {invoice_number}.</p>")
                continue

            # Seleccionar la última carpeta encontrada (por fecha de modificación)
            found_folders.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            target_folder = found_folders[0]
            self._log(f"<p>Carpeta encontrada (última modificación): {target_folder}</p>")

            try:
                self._copy_folder_contents(target_folder, dest_dir, invoice_number)
                self._log(f"<p style='color:green;'>Contenido de la factura {invoice_number} copiado exitosamente.</p>")
            except Exception as e:
                self._log(f"<p style='color:red;'>Error al copiar contenido para la factura {invoice_number}: {e}</p>")

        self._log("<p style='color:green;'>Operación completada.</p>")

    def _find_invoice_folders(self, invoice_number: str, root_dir: str) -> list[str]:
        found_paths = []
        for dirpath, dirnames, filenames in os.walk(root_dir):
            # Buscar carpetas que contengan el número de factura
            # Y que estén en una estructura que sugiera una 'carta glosa' (e.g., subcarpeta de una raíz)
            # La lógica de 'cartas glosa' es un poco ambigua, asumo que significa que la carpeta de la factura
            # está dentro de una carpeta que a su vez está dentro de la carpeta raíz de búsqueda.
            # O que la carpeta de la factura contiene un archivo 'carta glosa' (no implementado aquí, solo la estructura)

            # Simplificación: buscar cualquier carpeta cuyo nombre contenga el número de factura
            # y que no sea la carpeta raíz de búsqueda directamente.
            for dirname in dirnames:
                if invoice_number in dirname and dirpath != root_dir:
                    full_path = os.path.join(dirpath, dirname)
                    # Opcional: verificar si contiene 'carta glosa' si es un archivo específico
                    # if 'carta glosa' in [f.lower() for f in os.listdir(full_path)]:
                    found_paths.append(full_path)
        return found_paths

    def _copy_folder_contents(self, source_folder: str, destination_root: str, invoice_number: str):
        # Crear una carpeta de destino específica para esta factura dentro del destino raíz
        # para evitar mezclar contenidos si los nombres de archivo son idénticos entre facturas.
        # El usuario quiere que se pegue en 'mi carpeta determinada', asumo que es la carpeta raíz de destino
        # y que los contenidos se pegan directamente allí, pero con el sufijo '-copia'.
        # Si se quiere una subcarpeta por factura, se debería crear aquí.

        # Para pegar directamente en destination_root con -copia
        for item_name in os.listdir(source_folder):
            source_item_path = os.path.join(source_folder, item_name)
            
            # Construir el nuevo nombre con '-copia'
            name, ext = os.path.splitext(item_name)
            new_item_name = f"{name}-copia{ext}"
            destination_item_path = os.path.join(destination_root, new_item_name)

            if os.path.isfile(source_item_path):
                shutil.copy2(source_item_path, destination_item_path)
            elif os.path.isdir(source_item_path):
                # Si es un directorio, copiar recursivamente con el sufijo
                # Esto es más complejo si se quiere que cada archivo dentro del subdirectorio también tenga '-copia'
                # Por simplicidad, copiaré el directorio tal cual con el nuevo nombre.
                # Si el usuario quiere '-copia' en cada archivo dentro de los subdirectorios, la lógica debe ser más profunda.
                shutil.copytree(source_item_path, destination_item_path, dirs_exist_ok=True)

