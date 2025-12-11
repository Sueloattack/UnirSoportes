# logica/workers/automatizador_radicacion_logic.py

import os
import re
import pypdf
import pytesseract
from pdf2image import convert_from_path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Configuración de ruta Tesseract si no está en PATH (opcional, ajustar según entorno)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

import io
from PIL import Image

def extraer_texto_ocr(ruta_pdf):
    """
    Intenta extraer texto usando OCR.
    Estrategia 1: pdf2image (requiere Poppler).
    Estrategia 2: pypdf (extraer imágenes incrustadas).
    """
    texto_ocr = ""
    try:
        # Estrategia 1: pdf2image
        try:
            # Check si poppler está disponible intentando una conversión simple o verificando
            # print(f"  → Intentando OCR con pdf2image para: {os.path.basename(ruta_pdf)}")
            imagenes = convert_from_path(ruta_pdf)
            for imagen in imagenes:
                texto_ocr += pytesseract.image_to_string(imagen)
            return texto_ocr
        except Exception as e_poppler:
            # print(f"  ⚠ Fallo pdf2image (¿Falta Poppler?): {e_poppler}")
            # print("  → Intentando extracción directa de imágenes con pypdf...")
            pass

        # Estrategia 2: Extracción directa con pypdf
        with open(ruta_pdf, 'rb') as f:
            reader = pypdf.PdfReader(f)
            for page in reader.pages:
                for image_file in page.images:
                    try:
                        image_data = image_file.data
                        image = Image.open(io.BytesIO(image_data))
                        texto_ocr += pytesseract.image_to_string(image)
                    except Exception as e_img:
                        print(f"    ⚠ Error procesando imagen interna: {e_img}")
        
        return texto_ocr

    except Exception as e:
        print(f"  ⚠ Fallo OCR General: {e}")
        return ""

def extraer_serie_numero_de_nombre(nombre_archivo):
    """
    Extrae serie y número del nombre del archivo.
    Ej: 'FECR340375.pdf' → ('FECR', '340375')
        'COEX13088.pdf' → ('COEX', '13088')
    
    Returns:
        tuple: (serie, numero) o (None, None) si no se puede extraer
    """
    # Remover extensión
    nombre_sin_ext = os.path.splitext(nombre_archivo)[0]
    
    # Patrón: letras seguidas de números
    match = re.match(r'^([A-Z]+)(\d+)$', nombre_sin_ext, re.IGNORECASE)
    if match:
        return match.group(1).upper(), match.group(2)
    
    return None, None


def extraer_datos_carta_glosa(ruta_pdf):
    """
    Extrae datos del PDF de carta glosa.
    
    Returns:
        dict: {
            'valor_objecion': float o None,
            'clasificacion': str o None,
            'tiene_valor': bool
        }
    """
    try:
        with open(ruta_pdf, 'rb') as f:
            lector = pypdf.PdfReader(f)
            texto_completo = ""
            
            # Extraer texto de todas las páginas
            for pagina in lector.pages:
                texto_completo += pagina.extract_text()
            
            # Verificar si el PDF tiene texto extraíble
            texto_limpio = texto_completo.strip()
            
            # Si hay poco texto, probar OCR pero NO detenerse
            if len(texto_limpio) < 100:
                print(f"  ⚠️  ADVERTENCIA: PDF con poco texto extraíble ({len(texto_limpio)} caracteres). Intentando OCR...")
                texto_ocr = extraer_texto_ocr(ruta_pdf)
                if len(texto_ocr) > len(texto_limpio):
                    texto_completo += "\n" + texto_ocr
                    print(f"  → Texto recuperado con OCR: {len(texto_ocr)} caracteres")
                else:
                    print("  → OCR no mejoró el resultado.")

            
            # Buscar valor de objeción total
            valor_objecion = None
            tiene_valor = False
            
            # Patrón 1: "Objeción    $ 73.500,00" o "Objecion: $ 27.400,00"
            match_objecion = re.search(r'Objeci[oó]n\s*:?\s*\$?\s*&?nbsp;?\s*([\d,.]+)', texto_completo, re.IGNORECASE)
            if match_objecion:
                # Formato colombiano: punto = separador de miles, coma = decimal
                # Ejemplo: 54.400,00 = 54400
                valor_str = match_objecion.group(1)
                # Eliminar puntos (separador de miles) y reemplazar coma por punto (decimal)
                valor_str = valor_str.replace('.', '').replace(',', '.')
                try:
                    valor_objecion = float(valor_str)
                    tiene_valor = True
                except ValueError:
                    pass
            
            # Patrón 2: Buscar "1002" seguido de "Objeción" (pueden estar en líneas separadas)
            # Formato: "1002\nObjeción\n   $ 54.400,00"
            if not tiene_valor:
                # Buscar 1002, luego Objeción, luego $ y valor (con espacios y saltos de línea)
                match_1002 = re.search(r'1002[\s\n]+Objeci[oó]n[\s\n]+\$?[\s&nbsp;]*([ \s]*[\d,.]+)', texto_completo, re.IGNORECASE)
                if match_1002:
                    # Formato colombiano: punto = separador de miles, coma = decimal
                    valor_str = match_1002.group(1).strip().replace('\xa0', '')
                    # Eliminar puntos (miles) y reemplazar coma por punto (decimal)
                    valor_str = valor_str.replace('.', '').replace(',', '.')
                    try:
                        valor_objecion = float(valor_str)
                        tiene_valor = True
                    except ValueError:
                        pass
            
            # Patrón 3: Buscar "VTC    Valor total cobrado    $ X" como alternativa
            if not tiene_valor:
                match_vtc = re.search(r'VTC\s+Valor total cobrado\s+\$\s*&?nbsp;?\s*([\d,.]+)', texto_completo, re.IGNORECASE)
                if match_vtc:
                    # Formato colombiano
                    valor_str = match_vtc.group(1).replace('.', '').replace(',', '.')
                    try:
                        valor_objecion = float(valor_str)
                        tiene_valor = True
                    except ValueError:
                        pass
            
            # Patrón 4: Buscar "Total:" seguido de valor (para PDFs tipo GT con (8) Devoluciones)
            # Formato: "Total:\n$   524.500"
            if not tiene_valor:
                match_total = re.search(r'Total:\s*\$?\s*([\d,.]+)', texto_completo, re.IGNORECASE)
                if match_total:
                    # Formato colombiano
                    valor_str = match_total.group(1).replace('.', '').replace(',', '.')
                    try:
                        valor_objecion = float(valor_str)
                        tiene_valor = True
                    except ValueError:
                        pass
            
            # Analizar ítems para determinar tipo de glosa
            es_devolucion_total = False
            es_glosa_parcial = False
            es_gt = False  # Glosa Total (cuando dice "(8) Devoluciones" Y tiene ítems con objeción)
            tiene_rubro_devoluciones = False
            
            # Buscar si dice "(8) Devoluciones" en el rubro
            if re.search(r'\(8\)\s*Devoluciones', texto_completo, re.IGNORECASE):
                tiene_rubro_devoluciones = True
            
            if tiene_valor:
                # Buscar todos los ítems con sus porcentajes
                # Patrón: "100.00%" o "0.00%"
                # Mejorado: Buscar también valores asociados para detectar $0.00
                porcentajes_raw = re.findall(r'(\d+\.\d+)%', texto_completo)
                
                if porcentajes_raw:
                    porcentajes_float = [float(p) for p in porcentajes_raw]
                    
                    # Contar cuántos tienen 100% y cuántos tienen 0%
                    items_100 = sum(1 for p in porcentajes_float if p == 100.0)
                    items_0 = sum(1 for p in porcentajes_float if p == 0.0)
                    total_items = len(porcentajes_float)
                    
                    # Búsqueda heurística de valores cero asociados a ítems
                    # Si encontramos "$ 0,00" o "$ 0" cerca de un ítem, podría ser Glosa Parcial aunque sea 100%
                    # Esto es difícil con regex simple, así que usamos heurística:
                    # Si hay presencia de "$ 0,00" o "$ 0.00" o "$ 0 " en el documento
                    hay_valores_cero = bool(re.search(r'\$\s*0[,.]00', texto_completo) or re.search(r'\$\s*0\s', texto_completo))

                    # Lógica de clasificación
                    
                    # 1. Glosa Total (GT): Rubro (8) Devoluciones Y hay ítems objetados
                    # Se diferencia de Devolución simple (oficio) porque el oficio no suele tener porcentajes desglosados
                    if tiene_rubro_devoluciones and items_100 > 0:
                        es_gt = True
                        
                    # 2. Glosa Parcial (Mezcla real):
                    # - Mezcla de porcentajes 100% y 0% explicita
                    # - O todos 100% PERO hay valores de $0 detectados (caso FECR343879)
                    elif (items_100 > 0 and items_0 > 0) or (items_100 == total_items and hay_valores_cero):
                         es_glosa_parcial = True
                         
                    # 3. Devolución Total:
                    # - Todos los ítems al 100%
                    # - NO debe haber mezcla con 0%
                    # - NO debe haber valores monetarios de $0 (implícito por el `elif` anterior)
                    elif items_100 > 0 and items_0 == 0 and items_100 == total_items:
                        es_devolucion_total = True
                        
                    # 4. Caso raro (solo 0%), probablemente parcial
                    elif items_0 > 0 and items_100 == 0:
                        es_glosa_parcial = True
                else:
                    # No hay porcentajes en el PDF (es un oficio o formato diferente)
                    pass
            
            # Revaluar si es simple Oficio de Devolución (sin ítems porcentuales)
            # Si tiene rubro (8) Devoluciones y NO se detectó GT (porque no halló ítems), es Devolución simple
            es_devolucion_simple = False
            if tiene_rubro_devoluciones and not es_gt and not es_glosa_parcial and not es_devolucion_total:
                es_devolucion_simple = True
            
            # Busqueda heuristica: Si dice "DEVOLUCION" explícitamente y no hay items
            if not es_devolucion_simple and not es_gt and not es_glosa_parcial and not es_devolucion_total:
                 if re.search(r'DEVOLUCI[OÓ]N', texto_completo, re.IGNORECASE) and items_100 == 0:
                      es_devolucion_simple = True

            # Manejo especial: Si no se encontró valor (tiene_valor=False) pero es una Devolución/Oficio
            # Automáticamente clasificaremos como 'Devolución' en el llenado y usaremos Saldo Cartera

            
            # Buscar clasificación
            clasificacion = None
            
            # Patrón 1: "Clasificación: R3"
            match_clasif = re.search(r'Clasificaci[oó]n\s*:?\s*([A-Z0-9]+)', texto_completo, re.IGNORECASE)
            if match_clasif:
                clasificacion = match_clasif.group(1).upper()
            
            # Patrón 2: Buscar código "NU" específicamente
            if not clasificacion and re.search(r'\bNU\b', texto_completo):
                clasificacion = 'NU'
            
            return {
                'valor_objecion': valor_objecion,
                'clasificacion': clasificacion,
                'tiene_valor': tiene_valor,
                'es_devolucion_total': es_devolucion_total,
                'es_glosa_parcial': es_glosa_parcial,
                'es_gt': es_gt,
                'es_devolucion_simple': es_devolucion_simple,
                'es_pdf_escaneado': False,
                'error': None
            }
    
    except Exception as e:
        print(f"Error extrayendo datos de {ruta_pdf}: {e}")
        return {
            'valor_objecion': None,
            'clasificacion': None,
            'tiene_valor': False,
            'es_devolucion_total': False,
            'es_glosa_parcial': False,
            'es_gt': False,
            'es_devolucion_simple': False,
            'es_pdf_escaneado': False,
            'error': str(e)
        }


def automatizar_radicacion_logic(carpeta_pdfs, fecha_notificacion, username, password, 
                                  headless, progress_callback, completion_callback, 
                                  error_callback):
    """
    Función principal de orquestación para automatizar la radicación.
    
    Args:
        carpeta_pdfs: Ruta a la carpeta con los PDFs de carta glosa
        fecha_notificacion: Fecha en formato YYYY-MM-DD o DD/MM/YYYY
        username: Usuario para login
        password: Contraseña para login
        headless: bool, True para modo sin interfaz gráfica
        progress_callback: Signal(str, int) para reportar progreso
        completion_callback: Signal(dict) para reportar finalización
        error_callback: Signal(str) para reportar errores
    """
    try:
        # 1. Validar carpeta y encontrar PDFs
        if not os.path.isdir(carpeta_pdfs):
            raise ValueError(f"La carpeta no existe: {carpeta_pdfs}")
        
        archivos = os.listdir(carpeta_pdfs)
        pdfs = [f for f in archivos if f.lower().endswith('.pdf')]
        
        if not pdfs:
            raise ValueError("No se encontraron archivos PDF en la carpeta seleccionada")
        
        total_pdfs = len(pdfs)
        progress_callback.emit(f"Encontrados {total_pdfs} archivos PDF", 5)
        
        resultados = {
            'exitosos': [],
            'fallidos': [],
            'advertencias': []
        }
        
        # 2. Lanzar navegador con Playwright
        progress_callback.emit("Iniciando navegador...", 10)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()
            
            try:
                # 3. Login
                progress_callback.emit("Iniciando sesión...", 15)
                page.goto('https://asotrauma.ngrok.app/441_v2/pages/radicacion.php', timeout=30000)
                
                # Esperar a que cargue la página
                page.wait_for_load_state('networkidle', timeout=30000)
                
                # Verificar si ya está en la página de radicación o si necesita login
                try:
                    # Intentar encontrar el campo de usuario (indica que está en login)
                    page.wait_for_selector('input[name="user"]', timeout=5000)
                    
                    # Llenar credenciales
                    print(f"  → Llenando usuario: {username}")
                    page.fill('input[name="user"]', username)
                    page.fill('input[name="password"]', password)
                    
                    # Buscar y hacer clic en el botón de login
                    # El botón es: <input type="submit" class="btn btn-outline-primary d-block w-100" value="Ingresar">
                    print("  → Buscando botón de login...")
                    
                    try:
                        # Buscar input type submit
                        login_button = page.locator('input[type="submit"]').first
                        login_button.wait_for(timeout=2000)
                        print("  → Haciendo clic en botón de login (input submit)...")
                        login_button.click()
                        page.wait_for_load_state('networkidle', timeout=30000)
                        print("  → Login exitoso")
                    except:
                        # Si no encuentra input submit, intentar presionar Enter
                        print("  → No se encontró botón, presionando Enter...")
                        page.press('input[name="password"]', 'Enter')
                        page.wait_for_load_state('networkidle', timeout=30000)
                        print("  → Login exitoso (Enter)")
                    
                except Exception as e:
                    # Ya está logueado o error
                    print(f"  → Ya está en la página de radicación o error: {e}")
                
                progress_callback.emit("Sesión iniciada correctamente", 20)
                
                # 4. Procesar cada PDF
                for i, pdf_nombre in enumerate(pdfs):
                    porcentaje_base = 20
                    porcentaje_por_pdf = 70 / total_pdfs
                    porcentaje_actual = int(porcentaje_base + (i * porcentaje_por_pdf))
                    
                    progress_callback.emit(f"Procesando {pdf_nombre} ({i+1}/{total_pdfs})...", porcentaje_actual)
                    
                    try:
                        ruta_pdf = os.path.join(carpeta_pdfs, pdf_nombre)
                        
                        # Extraer serie y número del nombre
                        serie, numero = extraer_serie_numero_de_nombre(pdf_nombre)
                        if not serie or not numero:
                            raise ValueError(f"No se pudo extraer serie/número del nombre: {pdf_nombre}")
                        
                        # Extraer datos del PDF
                        datos_pdf = extraer_datos_carta_glosa(ruta_pdf)
                        
                        # Verificar si es un PDF escaneado
                        if datos_pdf.get('es_pdf_escaneado', False):
                            raise ValueError(f"PDF escaneado o sin texto extraíble. {datos_pdf.get('error', '')}")
                        
                        # Llenar formulario
                        llenar_formulario_radicacion_sync(
                            page, serie, numero, datos_pdf, 
                            fecha_notificacion, ruta_pdf
                        )
                        
                        resultados['exitosos'].append({
                            'archivo': pdf_nombre,
                            'serie': serie,
                            'numero': numero,
                            'valor_glosa': datos_pdf.get('valor_objecion'),
                            'clasificacion': datos_pdf.get('clasificacion')
                        })
                        
                        print(f"✓ Procesado exitosamente: {pdf_nombre}")
                    
                    except Exception as e:
                        resultados['fallidos'].append({
                            'archivo': pdf_nombre,
                            'error': str(e)
                        })
                        print(f"✗ Error procesando {pdf_nombre}: {e}")
                
                progress_callback.emit("Finalizando...", 95)
            
            finally:
                browser.close()
        
        # 5. Reportar finalización
        progress_callback.emit("Proceso completado", 100)
        completion_callback.emit(resultados)
    
    except Exception as e:
        error_callback.emit(f"Error general: {str(e)}")
        print(f"Error en automatizar_radicacion_logic: {e}")


def llenar_formulario_radicacion_sync(page, serie, numero, datos_pdf, 
                                      fecha_notificacion, ruta_pdf):
    """
    Llena el formulario de radicación de forma sincrónica.
    
    Args:
        page: Página de Playwright
        serie: Serie de la factura (ej. 'FECR')
        numero: Número de la factura (ej. '340375')
        datos_pdf: Diccionario con datos extraídos del PDF
        fecha_notificacion: Fecha de notificación
        ruta_pdf: Ruta al archivo PDF para subir
    """
    # 1. Llenar Serie
    page.fill('#serie', serie)
    
    # 2. Llenar Número de Factura
    page.fill('#num_factura', numero)
    
    # 3. Presionar Enter o Tab para trigger de carga de datos
    page.press('#num_factura', 'Tab')
    
    # 4. Esperar que carguen los datos (esperar un momento)
    page.wait_for_timeout(2000)
    
    # 5. Manejar popup de duplicado si aparece
    try:
        boton_aceptar = page.locator('#awn-confirm-ok')
        boton_aceptar.wait_for(timeout=3000)
        boton_aceptar.click()
        print("  → Popup de duplicado detectado y aceptado")
        page.wait_for_timeout(1000)
    except PlaywrightTimeout:
        # No apareció el popup, continuar normalmente
        pass
    
    # 6. Esperar a que aparezca el saldo en cartera
    try:
        page.wait_for_selector('span:has-text("Saldo en Cartera")', timeout=5000)
    except PlaywrightTimeout:
        print("  ⚠ Advertencia: No se encontró el saldo en cartera")
    
    # 7. Obtener saldo de cartera del sistema
    saldo_cartera = None
    try:
        saldo_element = page.locator('span:has-text("Saldo en Cartera")').first
        saldo_text = saldo_element.text_content()
        
        # Extraer el valor numérico: "Saldo en Cartera: $ 27.400" → 27400
        match = re.search(r'\$\s*&nbsp;\s*([\d,.]+)', saldo_text)
        if not match:
            match = re.search(r'\$\s*([\d,.]+)', saldo_text)
        
        if match:
            valor_str = match.group(1).replace(',', '').replace('.', '')
            saldo_cartera = float(valor_str)
            print(f"  → Saldo en cartera: ${saldo_cartera:,.0f}")
    except Exception as e:
        print(f"  ⚠ No se pudo obtener saldo en cartera: {e}")
    
    # 8. Determinar Tipo de Glosa y Valor Glosa según lógica de negocio
    if not datos_pdf['tiene_valor']:
        # Caso 1a: Devolución (PDF sin valor de objeción - carta/oficio)
        tipo_glosa = 'Devolución'
        valor_glosa = saldo_cartera if saldo_cartera else 0
        print(f"  → Tipo: Devolución (sin valor en PDF), Valor: ${valor_glosa:,.0f}")
    elif datos_pdf.get('es_devolucion_simple', False):
        # Caso 1b: Devolución Simple (Oficio con valor detectado o rubro (8))
        tipo_glosa = 'Devolución'
        valor_glosa = datos_pdf['valor_objecion']
        print(f"  → Tipo: Devolución (Oficio), Valor: ${valor_glosa:,.0f}")
    elif datos_pdf['es_gt']:
        # Caso 2: GT - Glosa Total (cuando dice "(8) Devoluciones" en el rubro)
        tipo_glosa = 'GT'
        valor_glosa = datos_pdf['valor_objecion']
        print(f"  → Tipo: GT (rubro '(8) Devoluciones'), Valor: ${valor_glosa:,.0f}")
    elif datos_pdf['es_devolucion_total']:
        # Caso 3: Devolución Total (TODOS los ítems al 100% de objeción)
        tipo_glosa = 'Devolución'
        valor_glosa = datos_pdf['valor_objecion']
        print(f"  → Tipo: Devolución Total (todos los ítems al 100%), Valor: ${valor_glosa:,.0f}")
    elif datos_pdf['es_glosa_parcial']:
        # Caso 4: Glosa Parcial (mezcla de ítems con y sin objeción)
        tipo_glosa = 'Glosa Parcial'
        valor_glosa = datos_pdf['valor_objecion']
        print(f"  → Tipo: Glosa Parcial (mezcla de ítems), Valor: ${valor_glosa:,.0f}")
    else:
        # Caso por defecto: Glosa Parcial
        tipo_glosa = 'Glosa Parcial'
        valor_glosa = datos_pdf['valor_objecion'] if datos_pdf['valor_objecion'] else 0
        print(f"  → Tipo: Glosa Parcial (por defecto), Valor: ${valor_glosa:,.0f}")
    
    # 9. Llenar Valor Glosa
    page.fill('#vr_glosa', str(int(valor_glosa)))
    
    # 10. Seleccionar Tipo de Glosa
    page.select_option('#gl_tipo', label=tipo_glosa)
    
    # 11. Seleccionar Medio de Ingreso = "Correo Electrónico" (value="1")
    page.select_option('#reporte', value='1')
    
    # 12. Llenar Fecha Notificación
    # Convertir formato si es necesario (DD/MM/YYYY → YYYY-MM-DD)
    if '/' in fecha_notificacion:
        partes = fecha_notificacion.split('/')
        if len(partes) == 3:
            fecha_formateada = f"{partes[2]}-{partes[1]}-{partes[0]}"
        else:
            fecha_formateada = fecha_notificacion
    else:
        fecha_formateada = fecha_notificacion
    
    page.fill('#f_ingreso', fecha_formateada)
    
    # 13. Llenar Observación si aplica
    observacion = ""
    if saldo_cartera and datos_pdf['valor_objecion']:
        if saldo_cartera < datos_pdf['valor_objecion']:
            observacion = "Carta glosa por mayor valor"
            print(f"  → Observación: {observacion}")
    
    if observacion:
        page.fill('#message', observacion)
    
    # 14. Subir archivo PDF
    page.set_input_files('#file_input', ruta_pdf)
    print(f"  → Archivo subido: {os.path.basename(ruta_pdf)}")
    
    # 15. Esperar un momento antes de guardar
    page.wait_for_timeout(1000)
    
    # 16. Hacer clic en Guardar
    print("  → Haciendo clic en Guardar...")
    page.click('#buttonSaveObject')
    
    # 17. Esperar y verificar confirmación del sistema
    print("  → Esperando confirmación del sistema...")
    try:
        # Esperar mensaje de éxito (ajustar selector según el sistema)
        # Puede ser un alert, un mensaje en pantalla, o redirección
        page.wait_for_timeout(2000)
        
        # Verificar si hay algún mensaje de error
        try:
            error_msg = page.locator('.error, .alert-danger, [class*="error"]').first
            if error_msg.is_visible(timeout=1000):
                error_text = error_msg.text_content()
                raise Exception(f"Error del sistema: {error_text}")
        except PlaywrightTimeout:
            # No hay mensaje de error, continuar
            pass
        
        # Esperar un poco más para asegurar que se procesó
        page.wait_for_timeout(2000)
        
        print(f"  ✓ Formulario guardado exitosamente")
        
    except Exception as e:
        print(f"  ⚠ Advertencia al verificar guardado: {e}")
        # Esperar un poco más por si acaso
        page.wait_for_timeout(2000)
