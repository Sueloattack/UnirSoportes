#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para probar la extracción de datos de PDFs de carta glosa.
Permite ingresar la ruta de un PDF y muestra toda la información extraída.
"""

import os
import sys

# Agregar el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logica.workers.automatizador_radicacion_logic import extraer_serie_numero_de_nombre, extraer_datos_carta_glosa


def diagnosticar_pdf(ruta_pdf):
    """
    Diagnostica un PDF y muestra toda la información extraída.
    """
    print("=" * 80)
    print("DIAGNÓSTICO DE PDF - AUTOMATIZADOR DE RADICACIÓN")
    print("=" * 80)
    print()
    
    # Verificar que el archivo existe
    if not os.path.exists(ruta_pdf):
        print(f"❌ ERROR: El archivo no existe: {ruta_pdf}")
        return
    
    if not ruta_pdf.lower().endswith('.pdf'):
        print(f"❌ ERROR: El archivo no es un PDF: {ruta_pdf}")
        return
    
    nombre_archivo = os.path.basename(ruta_pdf)
    print(f"📄 Archivo: {nombre_archivo}")
    print(f"📁 Ruta completa: {ruta_pdf}")
    print()
    
    # 1. Extraer serie y número del nombre
    print("-" * 80)
    print("1️⃣  EXTRACCIÓN DEL NOMBRE DEL ARCHIVO")
    print("-" * 80)
    
    serie, numero = extraer_serie_numero_de_nombre(nombre_archivo)
    
    if serie and numero:
        print(f"✅ Serie: {serie}")
        print(f"✅ Número: {numero}")
    else:
        print(f"❌ No se pudo extraer serie/número del nombre")
    print()
    
    # 2. Extraer datos del PDF
    print("-" * 80)
    print("2️⃣  EXTRACCIÓN DE DATOS DEL PDF")
    print("-" * 80)
    
    datos = extraer_datos_carta_glosa(ruta_pdf)
    
    print(f"Tiene valor: {datos['tiene_valor']}")
    
    if datos['valor_objecion']:
        print(f"✅ Valor de objeción: ${datos['valor_objecion']:,.0f}")
    else:
        print(f"❌ Valor de objeción: No encontrado")
    
    if datos['clasificacion']:
        print(f"✅ Clasificación: {datos['clasificacion']}")
    else:
        print(f"⚠️  Clasificación: No encontrada")
    
    print(f"Es devolución total: {datos['es_devolucion_total']}")
    print(f"Es glosa parcial: {datos['es_glosa_parcial']}")
    print()
    
    # 3. Determinar tipo de glosa
    print("-" * 80)
    print("3️⃣  DETERMINACIÓN DE TIPO DE GLOSA")
    print("-" * 80)
    
    if not datos['tiene_valor']:
        tipo_glosa = "DEVOLUCIÓN"
        valor_glosa = "Saldo en Cartera del sistema"
        razon = "El PDF no contiene valor de objeción (carta/oficio)"
    elif datos['es_gt']:
        tipo_glosa = "GT (Glosa Total)"
        valor_glosa = f"${datos['valor_objecion']:,.0f}"
        razon = "El PDF tiene rubro '(8) Devoluciones'"
    elif datos['es_devolucion_total']:
        tipo_glosa = "DEVOLUCIÓN TOTAL"
        valor_glosa = f"${datos['valor_objecion']:,.0f}"
        razon = "TODOS los ítems tienen 100% de objeción"
    elif datos['es_glosa_parcial']:
        tipo_glosa = "GLOSA PARCIAL"
        valor_glosa = f"${datos['valor_objecion']:,.0f}"
        razon = "Hay mezcla de ítems (algunos con objeción, otros sin)"
    else:
        tipo_glosa = "GLOSA PARCIAL (por defecto)"
        valor_glosa = f"${datos['valor_objecion']:,.0f}" if datos['valor_objecion'] else "$0"
        razon = "No se pudo determinar tipo específico"
    
    print(f"📋 Tipo de Glosa: {tipo_glosa}")
    print(f"💰 Valor Glosa: {valor_glosa}")
    print(f"📝 Razón: {razon}")
    print()
    
    # 4. Resumen final
    print("=" * 80)
    print("📊 RESUMEN PARA RADICACIÓN")
    print("=" * 80)
    print(f"Serie: {serie if serie else 'N/A'}")
    print(f"Número: {numero if numero else 'N/A'}")
    print(f"Tipo de Glosa: {tipo_glosa}")
    print(f"Valor Glosa: {valor_glosa}")
    print("=" * 80)
    print()


def main():
    """
    Función principal del script.
    """
    print()
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "DIAGNÓSTICO DE PDF - RADICACIÓN" + " " * 27 + "║")
    print("╚" + "═" * 78 + "╝")
    print()
    
    # Solicitar ruta del PDF
    if len(sys.argv) > 1:
        # Si se pasó como argumento
        ruta_pdf = sys.argv[1]
    else:
        # Solicitar interactivamente
        print("Ingresa la ruta completa del PDF a diagnosticar:")
        print("(Puedes arrastrar el archivo aquí o pegar la ruta)")
        print()
        ruta_pdf = input("Ruta del PDF: ").strip().strip('"').strip("'")
    
    print()
    
    if not ruta_pdf:
        print("❌ No se ingresó ninguna ruta.")
        return
    
    # Diagnosticar el PDF
    diagnosticar_pdf(ruta_pdf)
    
    # Preguntar si quiere diagnosticar otro
    if len(sys.argv) <= 1:  # Solo si es interactivo
        print()
        respuesta = input("¿Quieres diagnosticar otro PDF? (s/n): ").strip().lower()
        if respuesta == 's':
            print()
            main()
        else:
            print()
            print("👋 ¡Hasta luego!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print()
        print("👋 Proceso cancelado por el usuario.")
    except Exception as e:
        print()
        print(f"❌ ERROR CRÍTICO: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print()
        input("Presiona Enter para salir...")
