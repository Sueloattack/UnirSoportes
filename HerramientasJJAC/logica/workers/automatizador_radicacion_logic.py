import os
import re
import pdfplumber
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ========================================================
# 1. UTILIDADES Y LÓGICA DE EXTRACCIÓN (PDFPLUMBER)
# ========================================================

def limpiar_valor(valor_str):
    """Convierte '$ 5.542.250,00' -> 5542250.0"""
    if not valor_str: return 0.0
    try:
        limpio = re.sub(r'[^\d.,]', '', valor_str)
        # Formato Colombia: Puntos son miles, comas son decimales
        limpio = limpio.replace('.', '').replace(',', '.')
        return float(limpio)
    except ValueError: return 0.0

def extraer_serie_numero_de_nombre(nombre_archivo):
    """Extrae FECR y 336664 del nombre"""
    nombre_sin_ext = os.path.splitext(nombre_archivo)[0]
    match = re.search(r'([A-Za-z]+)(\d+)', nombre_sin_ext)
    if match:
        return match.group(1).upper(), match.group(2)
    return None, None

def _crear_respuesta_error(msg, es_imagen=False):
    return {
        'valor_objecion': 0, 'clasificacion': None, 'tiene_valor': False,
        'es_devolucion_total': False, 'es_glosa_parcial': False, 
        'es_gt': False, 'es_devolucion_simple': False, 
        'es_pdf_escaneado': es_imagen, 'error': msg,
        'items_detectados': [] 
    }

def analizar_items_porcentajes(texto):
    """Busca porcentajes (ej. 0.00% o 100.00%) para la lógica de items"""
    matches = re.findall(r'(\d+[.,]\d+)\s*%', texto)
    porcentajes = []
    for m in matches:
        try:
            val = float(m.replace(',', '.'))
            porcentajes.append(val)
        except: pass
    return porcentajes

def analizar_filas_items(texto):
    """
    Busca líneas que contengan porcentajes, asumiendo que corresponden a items tabulados.
    Retorna una lista de strings (las líneas completas).
    """
    lines = texto.split('\n')
    items = []
    # Regex para detectar porcentajes típicos: 100.00%, 0%, 50,00 %
    pct_re = re.compile(r'\d+[.,]?\d*\s*%')
    
    for line in lines:
        if pct_re.search(line):
            # Limpieza básica
            items.append(line.strip())
    return items

def analizar_liquidacion_tabular(texto):
    """Estrategia para las tablas de liquidación FECR estándar"""
    datos = {
        'valor_objecion': 0.0, 'valor_pagar': 0.0, 'encontrado': False,
        'hay_porcentaje_cero': False, 'todos_son_cien': False
    }
    # Buscar códigos financieros al pie
    m_obj = re.search(r'1002\s*(?:Objeci[oó]n)?\s*\$?\s*([\d\.,]+)', texto)
    m_pag = re.search(r'9023\s*(?:Pago neto)?\s*\$?\s*([\d\.,]+)', texto)
    
    if m_obj or m_pag:
        datos['encontrado'] = True
        if m_obj: datos['valor_objecion'] = limpiar_valor(m_obj.group(1))
        if m_pag: datos['valor_pagar'] = limpiar_valor(m_pag.group(1))

    # Analizar porcentajes de los items para clasificar
    porcentajes = analizar_items_porcentajes(texto)
    if porcentajes:
        # Si hay items < 99.9%, significa que hay items aceptados
        datos['hay_porcentaje_cero'] = any(p < 99.9 for p in porcentajes)
        # Si todos son > 99%, es glosa total
        datos['todos_son_cien'] = all(p > 99.0 for p in porcentajes)
    
    return datos

def analizar_formato_devolucion_simple(texto):
    """Estrategia para formatos tipo RGC Activa / Oficios"""
    claves = ["objeción de factura", "gestiones de servicios", "motivo objeción"]
    if not any(x in texto.lower() for x in claves):
        return {'valor': 0.0, 'encontrado': False}

    m = re.search(r'Total:\s*\$?\s*([\d\.,]+)', texto, re.IGNORECASE)
    return {'valor': limpiar_valor(m.group(1)) if m else 0.0, 'encontrado': bool(m)}

def analizar_carta_narrativa(texto):
    """Estrategia para cartas de texto corrido (COEX)"""
    m = re.search(r'por\s+valor\s+de\s*\$?\s*([\d\.,]+)', texto, re.IGNORECASE)
    return {'valor': limpiar_valor(m.group(1)) if m else 0.0, 'encontrado': bool(m)}

def extraer_datos_carta_glosa(ruta_pdf):
    texto_parts = []
    try:
        with pdfplumber.open(ruta_pdf) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if txt: texto_parts.append(str(txt))
    except Exception as e:
        return _crear_respuesta_error(f"Error lectura PDF: {e}")
    texto_completo = "\n".join(texto_parts)

    # Verificar si es imagen (Scaneado)
    if len(str(texto_completo).strip()) < 50:
        return _crear_respuesta_error("PDF es imagen/escaneado", es_imagen=True)

    res = {
        'valor_objecion': 0.0, 'clasificacion': "", 'tiene_valor': False,
        'es_devolucion_total': False, 'es_glosa_parcial': False, 
        'es_gt': False, 'es_devolucion_simple': False,
        'es_pdf_escaneado': False, 'error': "",
        'items_detectados': []
    }
    
    # Extraer items potenciales (filas con porcentajes)
    res['items_detectados'] = analizar_filas_items(texto_completo)
    
    # --- ESTRATEGIA 1: TABLA LIQUIDACIÓN (Mayoría de FECR) ---
    lectura_tabla = analizar_liquidacion_tabular(texto_completo)
    
    if lectura_tabla['encontrado']:
        res['valor_objecion'] = lectura_tabla['valor_objecion']
        res['tiene_valor'] = True
        
        pagar = lectura_tabla['valor_pagar']
        hay_ceros = lectura_tabla['hay_porcentaje_cero']
        todos_cien = lectura_tabla['todos_son_cien']
        
        v_obj = res.get('valor_objecion', 0.0)
        v_obj_float = float(v_obj) if isinstance(v_obj, (int, float, str)) else 0.0
        
        # Clasificación
        if pagar > 100: 
            res['es_glosa_parcial'] = True
        elif hay_ceros:
            # Caso crítico: Paga $0 pero hay items al 0.00% aceptados
            res['es_glosa_parcial'] = True
        elif todos_cien and v_obj_float > 0:
            res['es_gt'] = True
        else:
            if v_obj_float > 0: res['es_gt'] = True

    # --- ESTRATEGIA 2: FORMATO DEVOLUCIÓN ---
    elif True: 
        lectura_dev = analizar_formato_devolucion_simple(texto_completo)
        if lectura_dev['encontrado']:
            res['valor_objecion'] = float(lectura_dev.get('valor', 0.0))
            res['tiene_valor'] = True
            if "devolucion" in str(texto_completo).lower() or "vigencia" in str(texto_completo).lower():
                res['es_devolucion_total'] = True
            else: res['es_gt'] = True
        else:
            # --- ESTRATEGIA 3: CARTA NARRATIVA (COEX) ---
            lectura_narr = analizar_carta_narrativa(texto_completo)
            if lectura_narr['encontrado']:
                res['valor_objecion'] = float(lectura_narr.get('valor', 0.0))
                res['tiene_valor'] = True
                res['es_devolucion_simple'] = True
            elif "devolucion" in str(texto_completo).lower() and not res['tiene_valor']:
                res['es_devolucion_simple'] = True # Asume saldo cartera

    match_clasif = re.search(r'Clasificaci[oó]n\s*:?\s*([A-Z0-9]+)', str(texto_completo), re.IGNORECASE)
    if match_clasif: res['clasificacion'] = match_clasif.group(1).upper()
        
    return res

# ========================================================
# 2. AUTOMATIZACIÓN (PLAYWRIGHT)
# ========================================================

def automatizar_radicacion_logic(carpeta_pdfs, fecha_notificacion, username, password, 
                                  headless, progress_callback, completion_callback, 
                                  error_callback):
    """
    Función orquestadora que abre el navegador y procesa la lista de PDFs.
    """
    try:
        # 1. Validaciones previas
        if not os.path.isdir(carpeta_pdfs):
            raise ValueError(f"La carpeta no existe: {carpeta_pdfs}")
        
        archivos = os.listdir(carpeta_pdfs)
        pdfs = [f for f in archivos if f.lower().endswith('.pdf')]
        
        if not pdfs: raise ValueError("No se encontraron archivos PDF en la carpeta seleccionada")
        
        total_pdfs = len(pdfs)
        progress_callback.emit(f"Encontrados {total_pdfs} archivos PDF", 5)
        
        # Estructura de resultados
        resultados = {'exitosos': [], 'fallidos': [], 'advertencias': []}
        
        # 2. Iniciar Browser
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page()
            
            try:
                # 3. Login
                progress_callback.emit("Iniciando sesión en la plataforma...", 10)
                try:
                    page.goto('https://asotrauma.ngrok.app/441_v2/pages/radicacion.php', timeout=30000)
                    
                    # Verificamos si pide login o ya entró
                    if page.locator('input[name="user"]').count() > 0:
                        page.fill('input[name="user"]', username)
                        page.fill('input[name="password"]', password)
                        
                        # Click botón ingresar o Enter
                        try:
                            page.click('input[type="submit"]', timeout=2000)
                        except:
                            page.press('input[name="password"]', 'Enter')
                        
                        page.wait_for_load_state('networkidle')
                except Exception as e:
                    print(f"Nota Login (no crítico): {e}")

                # 4. Procesar Archivos
                for i, pdf_nombre in enumerate(pdfs):
                    pct = int(15 + (i * 80 / total_pdfs))
                    progress_callback.emit(f"Procesando {pdf_nombre}...", pct)
                    
                    try:
                        ruta_pdf = os.path.join(carpeta_pdfs, pdf_nombre)
                        serie, numero = extraer_serie_numero_de_nombre(pdf_nombre)
                        
                        if not serie or not numero:
                            raise ValueError(f"El nombre del archivo no cumple formato (SERIE+NUMERO.pdf)")

                        # -- PASO A: EXTRAER DATOS (Usa la lógica de arriba) --
                        datos_pdf = extraer_datos_carta_glosa(ruta_pdf)
                        
                        # -- PASO B: FILTRAR SI ES IMAGEN --
                        if datos_pdf['es_pdf_escaneado']:
                            resultados['advertencias'].append({'archivo': pdf_nombre, 'razon': 'PDF es Imagen/Escaneado (Saltado)'})
                            print(f"Advertencia: {pdf_nombre} saltado por ser imagen.")
                            continue
                            
                        # -- PASO C: LLENAR FORMULARIO WEB --
                        llenar_formulario_radicacion_sync(page, serie, numero, datos_pdf, fecha_notificacion, ruta_pdf)
                        
                        # -- PASO D: REGISTRAR ÉXITO --
                        tipo_final = 'DV' if (datos_pdf['es_devolucion_total'] or datos_pdf['es_devolucion_simple']) \
                                     else ('GT' if datos_pdf['es_gt'] else 'GP')
                        resultados['exitosos'].append({
                            'archivo': pdf_nombre,
                            'valor': datos_pdf.get('valor_objecion'),
                            'clasif': datos_pdf.get('clasificacion'),
                            'tipo': tipo_final
                        })
                        print(f"✓ Éxito: {pdf_nombre}")
                        
                    except Exception as e:
                        print(f"✗ Error en {pdf_nombre}: {e}")
                        resultados['fallidos'].append({'archivo': pdf_nombre, 'error': str(e)})

            finally:
                browser.close()
                
        # 5. Finalizar
        progress_callback.emit("Proceso finalizado", 100)
        completion_callback.emit(resultados)

    except Exception as e:
        error_callback.emit(f"Error General: {str(e)}")

def llenar_formulario_radicacion_sync(page, serie, numero, datos_pdf, fecha, ruta_pdf):
    
    # 1. Serie
    page.locator('#serie').fill(serie)
    page.locator('#serie').dispatch_event('input')
    
    # 2. Número de factura — dispara onDocnChange() → búsquedas AJAX
    page.locator('#num_factura').fill(numero)
    page.locator('#num_factura').dispatch_event('input')
    page.locator('#num_factura').dispatch_event('change')
    
    # 3. Loop unificado: detectar modal AWN y/o esperar que NIT se pueble
    nit_cargado = False
    for intento in range(40):  # 40 * 0.5s = 20 segundos máximo
        try:
            # A. Intentar aceptar el modal usando JavaScript puro (bypasea overlays)
            modal_aceptado = page.evaluate("""
                () => {
                    const botones = Array.from(document.querySelectorAll('button'));
                    const btn = botones.find(b => b.textContent.trim() === 'Aceptar');
                    if (btn && btn.offsetParent !== null) {  // offsetParent != null = es visible
                        btn.click();
                        return true;
                    }
                    return false;
                }
            """)
            if modal_aceptado:
                print(f"  → Modal de reingreso aceptado (intento {intento})")
                page.wait_for_timeout(800)  # darle tiempo al AJAX post-aceptar

            # B. Revisar si el NIT ya llegó (TAMBIÉN via JS para evitar excepciones)
            nit_val = page.evaluate(
                "() => document.querySelector('#nit_tercero')?.value?.trim() || ''"
            )
            if nit_val != '':
                nit_cargado = True
                print(f"  → Factura encontrada (NIT: {nit_val})")
                break

        except Exception as e:
            print(f"  → Intento {intento}: error ignorado ({e})")

        page.wait_for_timeout(500)

    if not nit_cargado:
        raise Exception(f"Timeout: La factura {serie}-{numero} no se encontró en GEMA")

    # 4. Esperar que saldo de cartera deje de cargar
    page.wait_for_timeout(800)

    # 5. Leer saldo en cartera
    saldo_cartera = 0
    try:
        txt = page.evaluate("""
            () => {
                const spans = Array.from(document.querySelectorAll('span'));
                const s = spans.find(sp => sp.textContent.includes('Saldo en Cartera'));
                return s ? s.textContent : '';
            }
        """)
        if txt:
            m = re.search(r'([\d.,]+)\s*$', txt.replace(' ', ''))
            if m: saldo_cartera = limpiar_valor(m.group(1))
    except:
        pass

    # 6. Calcular tipo y valor
    valor_glosa = datos_pdf['valor_objecion']
    tipo_value = 'GP'

    if datos_pdf['es_devolucion_total'] or datos_pdf['es_devolucion_simple']:
        tipo_value = 'DV'
        if valor_glosa == 0 and saldo_cartera > 0:
            valor_glosa = saldo_cartera
    elif datos_pdf['es_gt']:
        tipo_value = 'GT'
    elif datos_pdf['es_glosa_parcial']:
        tipo_value = 'GP'

    print(f"  → Tipo: {tipo_value}, Valor: {valor_glosa}")

    # 7. Valor glosa
    page.locator('#vr_glosa').fill(str(int(valor_glosa)))
    page.locator('#vr_glosa').dispatch_event('input')

    # 8. Tipo de glosa (GT / GP / DV)
    page.locator('#gl_tipo').select_option(value=tipo_value)
    page.locator('#gl_tipo').dispatch_event('change')

    # 9. Medio de ingreso
    page.locator('#reporte').select_option(value='1')
    page.locator('#reporte').dispatch_event('change')
    page.wait_for_timeout(1000)

    # 10. Fecha
    fecha_formateada = fecha
    if '/' in fecha:
        d_p, m_p, y_p = fecha.split('/')
        fecha_formateada = f"{y_p}-{m_p}-{d_p}"
    page.locator('#f_ingreso').fill(fecha_formateada)
    page.locator('#f_ingreso').dispatch_event('input')

    # 11. Subir PDF
    page.set_input_files('#file_input', ruta_pdf)
    page.wait_for_timeout(500)

    # 12. Guardar e interceptar respuesta AJAX
    with page.expect_response(
        lambda r: 'action=saveData' in r.url,
        timeout=20000
    ) as resp_info:
        page.click('#buttonSaveObject')

    data = resp_info.value.json()

    if not data.get('status'):
        raise Exception(f"Sistema rechazó: {data.get('message', 'Error desconocido')}")

    # 13. Esperar que el formulario se limpie (NIT vuelve a '')
    try:
        page.wait_for_function(
            "document.querySelector('#nit_tercero')?.value === ''",
            timeout=10000
        )
    except:
        page.wait_for_timeout(2000)

    page.wait_for_timeout(300)
