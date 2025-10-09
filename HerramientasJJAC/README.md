# Herramientas JJAC para Gestión de Glosas

Esta es una aplicación de escritorio desarrollada en Python con PySide6, diseñada para automatizar y facilitar diversas tareas relacionadas con el procesamiento de glosas y soportes de facturación en el sector salud.

## Arquitectura del Proyecto

El proyecto sigue una arquitectura limpia y organizada, separando claramente la lógica de negocio de la interfaz de usuario.

-   **`main.py`**: Es el punto de entrada de la aplicación. Se encarga de inicializar el entorno de Qt, cargar la hoja de estilos y mostrar la ventana principal.
-   **`gui/`**: Contiene todo el código relacionado con la interfaz gráfica.
    -   **`main_window/`**: Define la ventana principal (`VentanaPrincipal`), que incluye la barra lateral de navegación y el contenedor para los diferentes módulos.
    -   **`widgets/`**: Cada archivo `.py` en esta carpeta corresponde a un módulo o "herramienta" individual que el usuario ve en pantalla.
    -   **`common/`**: Contiene componentes de interfaz reutilizables, como selectores de carpetas.
-   **`logica/`**: Contiene la lógica de negocio de la aplicación.
    -   **`core/`**: Módulos centrales con funciones reutilizables para tareas como la manipulación de archivos (`gestor_archivos.py`), identificación de documentos por patrones (`identificador_archivos.py`) y procesamiento de PDFs (`procesador_pdf.py`).
    -   **`workers/`**: Cada archivo `_logic.py` aquí es un "trabajador" que corresponde a un widget de la `gui`. Estos workers se ejecutan en hilos separados (`QThread`) para no congelar la interfaz de usuario durante operaciones largas.
-   **`recursos/`**: Almacena recursos estáticos como íconos (`.svg`, `.png`) y la hoja de estilos de la aplicación (`estilos.qss`).

## Dependencias

El proyecto utiliza las siguientes librerías principales, definidas en `requirements.txt`:

-   **PySide6**: El framework para la construcción de la interfaz gráfica.
-   **pypdf**: Para la manipulación y unión de documentos PDF.
-   **PyMuPDF**: Para la lectura y extracción de texto e información de archivos PDF.
-   **pandas**: Utilizado en algunos scripts para la manipulación de datos tabulares.
-   **openpyxl**: Para la exportación de datos a formato Excel (`.xlsx`).

## Funcionalidades

La aplicación se organiza en categorías dentro de una barra de navegación lateral. A continuación se describen las funcionalidades de cada módulo.

---

### Categoría: PROCESAMIENTO

#### 1. Unir Soportes (`unir_soportes.py`)

-   **Propósito**: Unificar en un solo PDF la respuesta a una glosa, la carta de glosa original y todos los soportes adicionales.
-   **Lógica (`unir_soportes_logic.py`):**
    1.  Recorre las subcarpetas de la ruta seleccionada.
    2.  Utiliza `identificador_archivos.py` para clasificar los PDFs de cada subcarpeta en "carta glosa", "respuesta glosa" y "soportes".
    3.  Verifica que la carta y la respuesta existan y que sus series y números coincidan.
    4.  Comprueba si el contenido de la carta ya está dentro de la respuesta para evitar duplicar la unión.
    5.  Si no está unido, fusiona la carta y los soportes al final del archivo de respuesta, sobrescribiéndolo.
    6.  Tiene un modo "ADRES" que sigue una lógica ligeramente diferente, uniendo la respuesta y los soportes a un archivo "Epicrisis".

#### 2. Revisor de Facturas (`auditor_cuentas_cobro.py`)

-   **Propósito**: Auditar una carpeta de cuentas de cobro, comparando las facturas listadas en un PDF de "relación de glosas" contra las carpetas existentes en el disco.
-   **Lógica (`auditor_cuentas_cobro_logic.py`):**
    1.  Extrae todas las facturas del PDF principal usando `PyMuPDF`, identificando para cada una: número de factura, serie, fecha y estatus. La extracción se basa en coordenadas verticales para asegurar la correcta asociación de los datos en cada fila.
    2.  Escanea la carpeta de trabajo para obtener una lista de todas las subcarpetas que empiezan con un número.
    3.  Compara la lista de facturas del PDF con las carpetas encontradas.
    4.  Genera un reporte que incluye:
        -   **Facturas Faltantes**: Facturas que están en el PDF pero no tienen una carpeta correspondiente.
        -   **Carpetas Sobrantes**: Carpetas que existen en el disco pero no corresponden a ninguna factura del PDF.
    5.  Crea una copia del PDF de entrada llamada `..._auditado.pdf`, resaltando en verde las facturas encontradas y en amarillo las repetidas.
    6.  Permite exportar la lista de facturas faltantes a un archivo Excel.

#### 3. Renombrar Archivos (`renombrador.py`)

-   **Propósito**: Renombrar masivamente archivos de respuesta de glosa según diferentes prefijos o sufijos.
-   **Lógica (`renombrador_logic.py`):**
    -   **Modo "Glosa" y "Devolución"**:
        1.  Escanea solo la carpeta raíz seleccionada en busca de archivos PDF.
        2.  Identifica los que son "respuestas de glosa" por su nombre (ej. `resp_glosa.pdf`).
        3.  Añade el prefijo `R-8002098917-` (para Glosa) o `8002098917-` (para Devolución).
    -   **Modo "Escolar"**:
        1.  Recorre las **subcarpetas** de la ruta seleccionada.
        2.  Dentro de cada subcarpeta, busca el par `carta_glosa` y `respuesta_glosa`.
        3.  Si encuentra ambos, renombra el archivo de respuesta añadiendo el sufijo `_PRG_1`.

---

### Categoría: ORGANIZACIÓN

#### 4. Mover Carpetas (`movedor_carpetas.py`)

-   **Propósito**: Mover un conjunto de carpetas de una ubicación a otra, especificándolas por su número de factura.
-   **Lógica (`movedor_carpetas_logic.py`):**
    1.  Recibe una lista de números de factura.
    2.  Escanea la carpeta de origen en busca de subcarpetas que **comiencen con** esos números.
    3.  Mueve las carpetas encontradas a la carpeta de destino.
    4.  Reporta cuáles se movieron, cuáles no se encontraron y cuáles ya existían en el destino.

#### 5. Mover Respuestas (`organizador_respuestas.py`)

-   **Propósito**: Organizar archivos de respuesta de glosa sueltos, moviéndolos a sus respectivas carpetas de factura.
-   **Lógica (`organizador_respuestas_logic.py`):**
    1.  Escanea una carpeta de "respuestas" para indexar todos los PDFs y extraer su serie y número.
    2.  Escanea una carpeta "raíz" que contiene las subcarpetas de destino.
    3.  Para cada respuesta, busca una subcarpeta en la raíz cuyo nombre coincida o comience con el número de la respuesta.
    4.  Mueve o copia el archivo de respuesta a la carpeta de destino encontrada.
    5.  Reporta los movimientos exitosos, los fallos por ambigüedad (múltiples carpetas de destino) y los archivos de respuesta que no encontraron destino.

#### 6. Mover Respuestas ADRES (`organizador_respuestas_adres.py`)

-   **Propósito**: Similar al anterior, pero específico para el flujo de trabajo de ADRES.
-   **Lógica (`organizador_respuestas_adres_logic.py`):**
    1.  Indexa los archivos de respuesta disponibles.
    2.  Recorre las subcarpetas de destino y busca un archivo de "Factura" para identificar el código de la carpeta.
    3.  Si la carpeta no tiene ya una respuesta, busca una respuesta coincidente en el índice y la mueve/copia.

#### 7. Mover XMLs (`organizador_xml.py`)

-   **Propósito**: Organizar archivos XML sueltos, moviéndolos a la carpeta de la factura correspondiente.
-   **Lógica (`organizador_xml_logic.py`):**
    1.  Funciona de manera muy similar a "Mover Respuestas ADRES".
    2.  Indexa los archivos XML por serie y número.
    3.  Recorre las subcarpetas, identifica la factura principal, y si no hay un XML, mueve el correspondiente desde la carpeta de origen.

#### 8. Reorganizar Sedes (`reorganizador_sedes.py`)

-   **Propósito**: Clasificar carpetas de facturas en "sede 1" o "sede 2" según la serie de la factura.
-   **Lógica (`reorganizador_sedes_logic.py`):**
    1.  Espera una estructura con carpetas `sede 1` y `sede 2`.
    2.  Analiza las subcarpetas dentro de cada una.
    3.  Lee un archivo de referencia dentro de cada subcarpeta para identificar la serie (`COEX` u otra).
    4.  Determina la sede correcta (ej. `COEX` va a `sede 2`, el resto a `sede 1`).
    5.  Si una carpeta está en la sede incorrecta, la mueve a la correcta.

---

### Categoría: BÚSQUEDA

Esta categoría contiene herramientas para encontrar y copiar soportes o carpetas basados en una lista de facturas.

-   **Traer Soportes ADRES**: Busca soportes específicos para facturas ADRES y los agrupa.
-   **Buscar Soportes NU (Nuevos)**: Busca soportes para facturas nuevas. Usa una doble estrategia: primero busca por carpetas que coincidan con el número de factura y luego, si falla, busca archivos PDF individuales que coincidan con el nombre completo (serie + número).
-   **Buscar Soportes R2 (Ratificados)**: Similar al anterior, pero con una lógica de selección diferente, pensada para facturas ratificadas (tiende a buscar la penúltima carpeta más reciente si hay duplicados).
-   **Buscar Carpetas ADRES**: Busca y copia carpetas completas basadas en una lista de códigos de factura.

---

### Scripts Adicionales en la Raíz

-   **`unir_retail.py`**, **`separador_respuestas_adres.py`**, **`procesador.py`**: Parecen ser versiones anteriores o scripts de línea de comandos que contienen parte de la lógica que luego fue integrada en la aplicación principal.
