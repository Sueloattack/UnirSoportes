# logica/logica_auditor_facturas.py
import fitz  # PyMuPDF
import os
import re
from collections import Counter
import shutil
from PySide6.QtCore import QObject, Signal

HIGHLIGHT_COLOR_UNIQUE_FOUND = (0.7, 1, 0.7)  # Verde claro
HIGHLIGHT_COLOR_REPETED_FOUND = (1, 1, 0.6)  # Amarillo claro

class WorkerAuditorFacturas(QObject):
    progreso_actualizado = Signal(str, float)
    proceso_finalizado = Signal(dict)

    def __init__(self, pdf_path, folders_path):
        super().__init__()
        self.pdf_path = pdf_path
        self.folders_path = folders_path
        self.esta_cancelado = False

    def ejecutar(self):
        resultados = {
            'resumen': {},
            'facturas_faltantes': [],
            'carpetas_sobrantes': {},
            'output_path': ''
        }

        try:
            self.progreso_actualizado.emit("Iniciando auditoría...", 0)
            
            folders_info_map = self._get_folders_info(self.folders_path)
            if folders_info_map is None:
                raise ValueError(f"La ruta de carpetas no se encontró o es inválida: {self.folders_path}")

            folder_numbers = set(folders_info_map.keys())
            
            doc = fitz.open(self.pdf_path)
            all_occurrences = self._find_invoices_from_words(doc)

            if not all_occurrences:
                resultados['resumen']['error'] = "No se encontró ninguna factura con el formato esperado en el PDF."
                self.proceso_finalizado.emit(resultados)
                doc.close()
                return

            unique_invoices_map = {item['id']: item for item in reversed(all_occurrences)}.values()
            unique_invoices_dict = {item['id']: item for item in unique_invoices_map}

            invoice_ids_list = [item['id'] for item in all_occurrences]
            invoice_counts = Counter(invoice_ids_list)
            unique_invoice_ids_in_pdf = set(unique_invoices_dict.keys())
            unique_pdf_invoice_numbers = {item['number'] for item in unique_invoices_dict.values()}
            repeated_invoice_ids = {invoice_id for invoice_id, count in invoice_counts.items() if count > 1}

            self.progreso_actualizado.emit("Auditando contra carpetas y resaltando...", 50)
            highlighted_unique_ids = set()
            for item in all_occurrences:
                if self.esta_cancelado: break
                if item['number'] in folder_numbers:
                    highlighted_unique_ids.add(item['id'])
                    page = doc[item['page_num']]
                    color = HIGHLIGHT_COLOR_REPETED_FOUND if item['id'] in repeated_invoice_ids else HIGHLIGHT_COLOR_UNIQUE_FOUND
                    highlight = page.add_highlight_annot(item['rect'])
                    highlight.set_colors(stroke=color)
                    highlight.update()
            
            if self.esta_cancelado: 
                doc.close()
                return

            output_path = self.pdf_path.replace(".pdf", "_auditado.pdf")
            missing_ids_set = unique_invoice_ids_in_pdf - highlighted_unique_ids
            surplus_folder_numbers = folder_numbers - unique_pdf_invoice_numbers

            doc.save(output_path, garbage=4, deflate=True)
            doc.close()

            resultados['output_path'] = output_path
            resultados['resumen'] = {
                'informe': os.path.basename(self.pdf_path),
                'total_glosas': len(all_occurrences),
                'total_facturas_unicas': len(unique_invoice_ids_in_pdf),
                'carpetas_en_disco': len(folder_numbers),
                'facturas_con_carpeta': len(highlighted_unique_ids),
                'facturas_faltantes': len(missing_ids_set),
                'carpetas_sobrantes': len(surplus_folder_numbers)
            }
            resultados['facturas_faltantes'] = sorted([f"{missing_id.replace('240-', '').replace('-', '').upper()} | {unique_invoices_dict.get(missing_id, {}).get('status', 'N/A')}" for missing_id in missing_ids_set])
            resultados['carpetas_sobrantes'] = {num: folders_info_map[num] for num in sorted(list(surplus_folder_numbers)) if num in folders_info_map}

            self.progreso_actualizado.emit("Auditoría completada.", 100)

        except Exception as e:
            resultados['resumen']['error'] = str(e)
        
        self.proceso_finalizado.emit(resultados)

    def eliminar_carpetas_sobrantes(self, carpetas_a_eliminar):
        eliminados = 0
        fallidos = []
        for number, full_name in carpetas_a_eliminar.items():
            ruta_a_eliminar = os.path.join(self.folders_path, full_name)
            try:
                shutil.rmtree(ruta_a_eliminar)
                eliminados += 1
            except Exception as e:
                fallidos.append(f"'{full_name}': {e}")
        return eliminados, fallidos

    def cancelar(self):
        self.esta_cancelado = True

    def _get_folders_info(self, path):
        folders_info = {}
        if not os.path.isdir(path): return None
        for item_name in os.listdir(path):
            full_path = os.path.join(path, item_name)
            if os.path.isdir(full_path):
                match = re.match(r"^\d+", item_name)
                if match:
                    folders_info[match.group(0)] = item_name
        return folders_info

    def _find_invoices_from_words(self, doc):
        invoice_pattern = r"240-[A-Z]+-\d+"
        status_pattern = r"C[O12]"
        all_invoice_occurrences = []

        for page_num, page in enumerate(doc):
            word_list = page.get_text("words", sort=True)
            for i, word_data in enumerate(word_list):
                word_text = word_data[4]
                if re.match(r"240-", word_text):
                    potential_invoice = word_text
                    rect = fitz.Rect(word_data[:4])
                    invoice_line_num = word_data[6]

                    if not re.fullmatch(invoice_pattern, potential_invoice, re.IGNORECASE) and i + 1 < len(word_list):
                        next_word_data = word_list[i+1]
                        if next_word_data[6] == invoice_line_num:
                           potential_invoice += next_word_data[4]
                           rect.include_rect(fitz.Rect(next_word_data[:4]))
                    
                    match = re.search(invoice_pattern, potential_invoice, re.IGNORECASE)
                    if match:
                        clean_id = match.group(0)
                        status_text = "N/A"
                        for j in range(i + 1, min(i + 8, len(word_list))):
                            next_word = word_list[j]
                            if next_word[6] == invoice_line_num and re.fullmatch(status_pattern, next_word[4], re.IGNORECASE):
                                status_text = next_word[4]
                                break
                        all_invoice_occurrences.append({"id": clean_id, "number": clean_id.split('-')[-1], "status": status_text, "page_num": page_num, "rect": rect})

        unique_occurrences = []
        seen_positions = set()
        for item in all_invoice_occurrences:
            pos_signature = (item['page_num'], int(item['rect'].x0), int(item['rect'].y0))
            if pos_signature not in seen_positions:
                unique_occurrences.append(item)
                seen_positions.add(pos_signature)
        return unique_occurrences
