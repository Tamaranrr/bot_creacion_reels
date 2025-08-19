import os
import re
import json
import random
import time 
from datetime import datetime
from pathlib import Path


from utils.db_connection import obtener_descripcion_contenido
from utils.db_connection import obtener_sonido_contenido

import pygetwindow as gw
import pyautogui
import pyperclip  # Asegura copiar texto con símbolos correctamente
import traceback

# Importaciones de Selenium
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import NoAlertPresentException

# Importaciones locales
from client.SeleniumClient import SeleniumClient
from utils.db_connection import obtener_datos_campania, obtener_datos_video, marcar_como_subido, guardar_video_generado
from utils.drive_upload import subir_video_drive

# Constantes y configuración
flag_path = "estado_generative.txt"
usar_generative = False
DOWNLOADS_PATH = Path.home() / "Downloads"

# Día de hoy
hoy = datetime.today().date()

# Verifica si han pasado al menos 2 días desde el último uso de generative
if os.path.exists(flag_path):
    with open(flag_path, "r") as f:
        contenido = f.read().strip()
        try:
            ultima_fecha = datetime.strptime(contenido, "%Y-%m-%d").date()
            if (hoy - ultima_fecha).days >= 2:
                usar_generative = True
        except:
            usar_generative = True
else:
    usar_generative = True

#---------------------------------------------------------#
#---------------Funciones auxiliares----------------------#


def esperar_loader_y_archivo_descargado(driver, directorio_descargas, timeout_descarga=2000):
    print("⏳ Esperando a que desaparezca el loader de descarga...")

    # Paso 1: Esperar que desaparezca el loader
    while True:
        try:
            driver.find_element("css selector", 'div.c-hPeQtj')
            time.sleep(1)
        except NoSuchElementException:
            print("✅ Loader ha desaparecido.")
            break

    # Paso 2: Registrar archivos antes
    print("⏳ Esperando que se genere un archivo nuevo en la carpeta de descargas...")
    antes = set(p.name for p in Path(directorio_descargas).glob("*"))

    tiempo_esperado = 0
    while tiempo_esperado < timeout_descarga:
        ahora = set(p.name for p in Path(directorio_descargas).glob("*") if not p.name.endswith('.crdownload'))
        nuevos = ahora - antes
        if nuevos:
            archivo_nuevo = list(nuevos)[0]
            print(f"✅ Archivo descargado: {archivo_nuevo}")
            return archivo_nuevo
        time.sleep(1)
        tiempo_esperado += 1

    print("❌ Tiempo de espera agotado. No se detectó archivo descargado.")
    return None

def limpiar_nombre_archivo(nombre, max_length=100):
    nombre_limpio = re.sub(r'[<>:"/\\|?*\n\r]', '', nombre)
    nombre_limpio = re.sub(r'[^\x00-\x7F]+', '', nombre_limpio)
    return nombre_limpio[:max_length].strip()

def esperar_descarga_completa(directorio, timeout=120):
    print("⏳ Esperando que finalice la descarga...")
    tiempo_esperado = 0
    while tiempo_esperado < timeout:
        archivos_crdownload = list(Path(directorio).glob("*.crdownload"))
        if not archivos_crdownload:
            print("✅ Descarga completa detectada.")
            return True
        time.sleep(1)
        tiempo_esperado += 1
    print("❌ Tiempo de espera agotado. La descarga no terminó.")
    return False

def renombrar_archivo_unico(archivo_path, nuevo_nombre):
    tiempo_maximo = 60
    tiempo_esperado = 0
    while not archivo_path.endswith('.mp4') or not os.path.exists(archivo_path):
        print(f"⏳ Esperando archivo .mp4 válido: {archivo_path}")
        time.sleep(1)
        tiempo_esperado += 1
        if tiempo_esperado > tiempo_maximo:
            print("❌ Tiempo de espera agotado. No se encontró archivo válido.")
            return None

    nuevo_archivo_path = os.path.join(DOWNLOADS_PATH, nuevo_nombre)
    contador = 1
    while os.path.exists(nuevo_archivo_path):
        nuevo_nombre = f"{os.path.splitext(nuevo_nombre)[0]}_{contador}.mp4"
        nuevo_archivo_path = os.path.join(DOWNLOADS_PATH, nuevo_nombre)
        contador += 1

    os.rename(archivo_path, nuevo_archivo_path)
    print(f"✅ El archivo ha sido renombrado a: {nuevo_nombre}")
    return nuevo_archivo_path

def esperar_y_ejecutar_click_nuevo_video(driver):
    print("⏳ Esperando que desaparezca el círculo de carga...")

    frame_anterior = driver.execute_script("return window.location.href;")

    while True:
        # 1. Esperar que desaparezca el círculo de carga
        while True:
            try:
                driver.find_element(By.CSS_SELECTOR, 'circle[stroke="#FFFFFF"]')
                print("🔄 Aún cargando video... esperando...")
                time.sleep(1)
            except NoSuchElementException:
                print("✅ Círculo de carga desaparecido.")
                break

        # 2. Ejecutar JS para hacer clic al video con imagen base64
        script_click_video = '''
        (function() {
            const imagenes = document.querySelectorAll('img');
            const imagenObjetivo = Array.from(imagenes).find(img => img.src.startsWith('data:image/jpeg;base64'));
            if (imagenObjetivo) {
                imagenObjetivo.click();
                console.log('✅ Imagen del nuevo video fue clickeada.');
            } else {
                console.warn('⚠️ No se encontró la imagen del nuevo video en base64.');
            }
        })();
        '''
        pyperclip.copy(script_click_video)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
        pyautogui.press('enter')
        print("✅ Script ejecutado para hacer clic al nuevo video.")

        # 3. Verificar si cambió de frame
        time.sleep(3)
        frame_actual = driver.execute_script("return window.location.href;")
        if frame_actual != frame_anterior:
            print("🎉 El frame ha cambiado correctamente.")
            return
        else:
            print("⏳ El frame no ha cambiado aún. Reintentando en 5 segundos...")
            time.sleep(5)

def escribir_texto_en_musica(driver, id_contenido):
    # Esperar a que cargue la caja de música
    print("🎵 Esperando a que cargue el área de música...")
    time.sleep(6)

    WebDriverWait(driver, 40).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    print("✅ Página completamente cargada.")

    # Ruta a la imagen del campo de música
    base_dir = os.path.dirname(__file__)
    ruta_img_musica = os.path.join(base_dir, "img", "tutorial", "musica_box.png")

    # Buscar la caja de texto de música en pantalla
    musica_box = pyautogui.locateOnScreen(ruta_img_musica, confidence=0.8)

    # 🔄 Obtener el sonido desde la base de datos
    sonido = obtener_sonido_contenido(id_contenido)
    print(f"🎶 Sonido desde contenido_semanal: {sonido}")

    texto_musical = sonido or "Ticking Countdown ASMR"

    if musica_box:
        x, y = pyautogui.center(musica_box)
        pyautogui.click(x, y)
        print("✅ Caja de música encontrada y clicada.")

        time.sleep(1)
        pyautogui.write(texto_musical, interval=0.03)
        pyautogui.press("enter")
        print("✅ Texto de música escrito correctamente desde base de datos.")
    else:
        pyautogui.screenshot("error_musica.png")
        print("❌ No se detectó la caja de música. Se guardó una captura como 'error_musica.png'.")

def esperar_y_ejecutar_click_insert(driver):
    print("⏳ Esperando a que desaparezca el círculo de carga...")

    # 1. Esperar a que desaparezca el loader
    while True:
        try:
            driver.find_element(By.CSS_SELECTOR, 'circle[stroke="#FFFFFF"]')
            print("🔄 Aún cargando... esperando...")
            time.sleep(1)
        except:
            print("✅ Círculo de carga desaparecido.")
            break

    print("⏳ Esperando que aparezca el botón Insert...")

    # 2. Esperar hasta que el botón "Insert" esté presente (sin timeout)
    while True:
        try:
            botones = driver.find_elements(By.XPATH, "//button[.//div[normalize-space()='Insert']]")
            if botones:
                print("✅ Botón Insert detectado.")
                break
        except:
            pass
        time.sleep(1)

    # 3. Ejecutar script para hacer clic automáticamente
    script_click_insert = '''
    (function() {
        const insertButton = Array.from(document.querySelectorAll("button")).find(btn =>
            btn.textContent.trim().toLowerCase() === "insert"
        );
        if (insertButton) {
            insertButton.click();
            console.log("✅ Botón 'Insert' clickeado automáticamente.");
        } else {
            console.warn("⚠️ No se encontró el botón 'Insert'.");
        }
    })();
    '''
    pyperclip.copy(script_click_insert)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)
    pyautogui.press('enter')
    print("✅ Script ejecutado correctamente para hacer clic en Insert.")

def mover_slider_a_mitad(driver):
    print("🎚️ Esperando a que cargue el slider...")
    time.sleep(6)

    WebDriverWait(driver, 40).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    print("✅ Página completamente cargada.")

    # Ruta a la imagen del slider
    base_dir = os.path.dirname(__file__)
    ruta_img_slider = os.path.join(base_dir, "img", "tutorial", "slider_box.png")

    # Buscar la imagen del slider en pantalla
    slider_box = pyautogui.locateOnScreen(ruta_img_slider, confidence=0.8)

    if slider_box:
        x_start, y = pyautogui.center(slider_box)
        width = slider_box[2]  # ancho del slider

        # Calcular destino: mitad del recorrido
        x_end = x_start - int(width / 3)  # puedes ajustar esto si el arrastre requiere menos recorrido

        print(f"🎯 Moviendo slider desde ({x_start}, {y}) hasta ({x_end}, {y})")
        pyautogui.moveTo(x_start, y, duration=0.3)
        pyautogui.mouseDown()
        pyautogui.moveTo(x_end, y, duration=0.4)
        pyautogui.mouseUp()
        print("✅ Slider bajado a la mitad.")
    else:
        pyautogui.screenshot("error_slider.png")
        print("❌ No se detectó el slider. Se guardó una captura como 'error_slider.png'.")

def obtener_ultimo_archivo_descargado(directorio_descargas):
    archivos = [os.path.join(directorio_descargas, f) for f in os.listdir(directorio_descargas)]
    archivos = [f for f in archivos if os.path.isfile(f)]
    if not archivos:
        print("⚠️ No se encontraron archivos en el directorio.")
        return None
    archivo_reciente = max(archivos, key=os.path.getctime)
    print(f"📥 Último archivo descargado detectado: {archivo_reciente}")
    return archivo_reciente


def verificar_y_reintentar(driver, tiempo_espera=5):
    """
    Espera un tiempo y verifica si aparece el mensaje de error de generación.
    Si aparece, hace clic en el botón 'Try again', de lo contrario, continúa.
    """
    print(f"⏳ Esperando {tiempo_espera}s antes de verificar error de generación...")
    time.sleep(tiempo_espera)

    try:
        # Buscar el div con "Generation error"
        error_div = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[contains(@class, 'c-bVLGld')]//span[contains(text(),'Generation error')]")
            )
        )
        if error_div:
            print("⚠️ Error de generación detectado. Intentando nuevamente...")

            try_again_btn = driver.find_element(
                By.XPATH,
                "//button[div[contains(text(),'Try again')]]"
            )
            driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", try_again_btn)
            time.sleep(0.5)
            try_again_btn.click()
            print("✅ Botón 'Try again' clickeado.")
        else:
            print("✅ No se detectó error de generación. Continuando ejecución...")

    except TimeoutException:
        print("✅ No se detectó error de generación. Continuando ejecución...")




#--------------------------------------------------------#
#--------------------------------------------------------#


# 👇 Clase principal con Selenium
class BotTutorial:
    def __init__(self, prompt, platform_video=None, tema=None, campaign_key=None, id_contenido=None, lenguaje=None, sonido=None, tipo=None, hashtags=None, id_video=None, titulo=None, servicio=None, main_cta=None,*args, **kwargs             ,):
    
        self.prompt = prompt
        self.platform_video = platform_video
        self.tema = tema
        self.campaign_key = campaign_key
        self.id_contenido = id_contenido
        self.lenguaje = lenguaje
        self.sonido = sonido
        self.tipo = tipo    
        self.hashtags = hashtags
        self.id_video = id_video
        self.titulo = titulo
        
        self.servicio = servicio
        self.main_cta = main_cta

        

    def run(self):
        video_completado_correctamente = False
        self.resultado_video = None               
        
        print("🌐 Iniciando navegador con perfil persistente...")

        cliente = SeleniumClient()
        driver = cliente.start_browser()
        ventana = gw.getWindowsWithTitle("Chrome")[0]
        ventana.activate()
        ventana.maximize()
        if not driver:
            print("❌ El navegador no se pudo iniciar. Abortando ejecución del bot.")
            return

        try:
            
            #-------------------------------------------------------------------------#
            # Abrir la página principal
            #-------------------------------------------------------------------------#
            print("🌐 Abriendo página https://www.captions.ai con PyAutoGUI...")

            # Activar ventana de Chrome
            ventanas = gw.getWindowsWithTitle("Chrome")
            if ventanas:
                ventana = ventanas[0]
                ventana.activate()
                time.sleep(1)

                # Presionar Ctrl+L para ir a la barra de direcciones
                pyautogui.hotkey('ctrl', 'l')
                time.sleep(0.5)

                # Escribir la URL manualmente
                pyautogui.typewrite("https://www.captions.ai", interval=0.03)
                pyautogui.press('enter')
                print("✅ URL abierta manualmente en navegador.")
                time.sleep(5)
            else:
                print("❌ No se encontró ventana de Chrome.")
                return
            
            #-------------------------------------------------------------------------#
            # Esperar a que la página esté completamente cargada
            #-------------------------------------------------------------------------#
            print("⏳ Esperando visualmente que cargue Captions.ai...")
            time.sleep(10)  # o más si es necesario

            #-------------------------------------------------------------------------#
            # Capturar cookies antes de hacer clic
            #-------------------------------------------------------------------------#

            # 🛠️ Eliminar target=_blank del botón para mantener sesión en la misma pagina
            driver.execute_script("""
            const boton = document.querySelector("a.button.w-variant-87c1939c-62e2-1a30-e54d-560ede136892.w-inline-block");
            if (boton) { boton.removeAttribute("target"); }
            """)
            time.sleep(5)  # Esperar a que se aplique el cambio
            
            #-------------------------------------------------------------------------#
            # Esperar y hacer clic con PyAutoGUI sobre el botón "Get Started"
            #-------------------------------------------------------------------------#
            
            print("🖱️ Buscando el botón 'Get Started' en pantalla con PyAutoGUI...")
            base_dir = os.path.dirname(__file__)
            ruta_get_started = os.path.join(base_dir, "img", "get_started.png")
            try:
                time.sleep(2)  # da tiempo a que termine cualquier animación
                boton_pos = pyautogui.locateCenterOnScreen(ruta_get_started, confidence=0.8)
                if boton_pos:
                    pyautogui.click(boton_pos)
                    print("✅ Click en botón 'Get Started' con PyAutoGUI.")
                else:
                    print("❌ No se encontró el botón 'Get Started'.")
                    return
            except Exception as e:
                print(f"❌ Error con PyAutoGUI al hacer clic en 'Get Started': {e}")
                return
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Esperar y escribir en el área de descripción
            #-------------------------------------------------------------------------#
            print("🖊️ Esperando a que cargue el área de descripción...")
            time.sleep(6)
            WebDriverWait(driver, 40).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            print("✅ Página completamente cargada.")

            try:
                # Lista de posibles imágenes de la caja de descripción
                imagenes_posibles = [
                    os.path.join(base_dir, "img", "tutorial", "descripcion_box.png"),
                    os.path.join(base_dir, "img", "tutorial", "descripcion_box_alt1.png")
                ]

                descripcion_box = None
                for ruta_img in imagenes_posibles:
                    print(f"🔍 Buscando campo de descripción con {os.path.basename(ruta_img)}...")
                    try:
                        descripcion_box = pyautogui.locateOnScreen(ruta_img, confidence=0.8)
                    except pyautogui.ImageNotFoundException:
                        descripcion_box = None

                    if descripcion_box:
                        print(f"✅ Campo de descripción encontrado con {os.path.basename(ruta_img)}.")
                        x, y = pyautogui.center(descripcion_box)
                        pyautogui.click(x, y)
                        break
                    else:
                        print(f"⚠️ No se encontró con {os.path.basename(ruta_img)}.")

                if descripcion_box:
                    time.sleep(1)
                    descripcion = obtener_descripcion_contenido(self.id_contenido)
                    if descripcion:
                        pyautogui.write(descripcion, interval=0.03)
                        pyautogui.press("enter")
                    else:
                        pyautogui.write("Descripción por defecto", interval=0.03)
                        pyautogui.press("enter")
                else:
                    raise Exception("No se detectó la caja de descripción con ninguna imagen.")

            except Exception as e:
                print(f"❌ Error al procesar el área de descripción: {e}")
                traceback.print_exc()
                pyautogui.screenshot("error_descripcion.png")
                return

            except Exception as e:
                print(f"❌ Error al procesar el área de descripción: {e}")
                traceback.print_exc()
                pyautogui.screenshot("error_descripcion.png")
                return

            #-------------------------------------------------------------------------#
            # Activar consola con f12
            #-------------------------------------------------------------------------#
            
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            time.sleep(2)
            print("✅ DevTools debería estar abierta ahora.")
            time.sleep(3)

            #-------------------------------------------------------------------------#
            # Click en boton no actor
            #-------------------------------------------------------------------------#
            print("🖱️ Click al botón 'No actor' ...")
            
            script_no_actor = '''
            (function() {
                const botones = document.querySelectorAll('button[role="radio"]');
                for (let boton of botones) {
                    const texto = boton.innerText.trim().toLowerCase();
                    if (texto.includes("no actor")) {
                        boton.focus();
                        boton.click();
                        console.log("✅ Botón 'No actor' clickeado correctamente.");
                        return;
                    }
                }
                console.warn("❌ Botón 'No actor' no encontrado.");
            })();
            '''
            # Copiar el script al portapapeles (más seguro que escribirlo)
            pyperclip.copy(script_no_actor)

            # Pegar el contenido
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
        
            # Ejecutar
            pyautogui.press('enter')
            print("✅ Click al boton No actor correctamente.")
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Click al boton voice para eleccion de voz
            #-------------------------------------------------------------------------#
            print("🖱️ Click al botón 'Voice' ...")
            
            script_voice = ''' 
            (function () {
                const voiceButtons = Array.from(document.querySelectorAll('div[tabindex="0"]'));
                const btn = voiceButtons.find(el => {
                    const text = el.innerText.trim().toLowerCase();
                    return text.includes("voice");
                });

                if (!btn) {
                    console.warn("❌ No se encontró ningún botón de voz disponible.");
                    return;
                }

                btn.scrollIntoView({ behavior: "smooth", block: "center" });
                btn.focus();
                btn.click();
                console.log("✅ Botón de voz detectado y clickeado.");
            })();
            '''
            
            pyperclip.copy(script_voice)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton de voz correctamente.")
            
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Seleccion aleatoria de voz
            #-------------------------------------------------------------------------#
            print("🎤 Seleccionando voz aleatoria...")
            
            script_random_voice = '''
            (function() {
                const botones = Array.from(document.querySelectorAll('button[role="radio"][data-radix-collection-item]'));

                if (botones.length === 0) {
                    console.warn("❌ No se encontraron botones de voz.");
                    return;
                }

                const botonesValidos = botones.filter(btn => {
                    const nombre = btn.innerText.trim().toLowerCase();
                    return nombre.includes("brandon") ||
                        nombre.includes("lea") ||
                        nombre.includes("john") ||
                        nombre.includes("jordan") ||
                        nombre.includes("julie") ||
                        nombre.includes("asher") ||
                        nombre.includes("ashley") ||
                        nombre.includes("sylvia") ||
                        nombre.includes("kayla") ||
                        nombre.includes("alexandra") ||
                        nombre.includes("bradford") ||
                        nombre.includes("samara") ||
                        nombre.includes("hope") ||
                        nombre.includes("eve") ||
                        nombre.includes("blondie") ||
                        nombre.includes("mark") ||
                        nombre.includes("sam") ||
                        nombre.includes("jamal");
                });

                if (botonesValidos.length === 0) {
                    console.warn("❌ No se encontraron botones válidos por nombre.");
                    return;
                }

                const seleccionado = botonesValidos[Math.floor(Math.random() * botonesValidos.length)];
                seleccionado.scrollIntoView({ behavior: "smooth", block: "center" });
                seleccionado.focus();
                seleccionado.click();

                console.log("✅ Voz aleatoria seleccionada:", seleccionado.innerText.trim());
            })();

            '''
            
            pyperclip.copy(script_random_voice)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Voz aleatoria seleccionada correctamente.")
        
            time.sleep(8)
            #-------------------------------------------------------------------------#
            # Desactivar consola con f12
            #-------------------------------------------------------------------------#
            
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            print("✅ DevTools debería estar desactivada ahora.")
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Click al boton de idioma
            #-------------------------------------------------------------------------#
        
            print("🖱️ Buscando el botón 'Idioma' en pantalla con PyAutoGUI...")
            base_dir = os.path.dirname(__file__)
            ruta_globe_button = os.path.join(base_dir, "img","tutorial", "globe_button.png")
            try:
                time.sleep(2)  # da tiempo a que termine cualquier animación
                boton_pos = pyautogui.locateCenterOnScreen(ruta_globe_button, confidence=0.8)
                if boton_pos:
                    pyautogui.click(boton_pos)
                    print("✅ Click en botón 'Idioma' con PyAutoGUI.")
                else:
                    print("❌ No se encontró el botón 'Idioma'.")
                    return
            except Exception as e:
                print(f"❌ Error con PyAutoGUI al hacer clic en 'Idioma': {e}")
                return
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Activar consola con f12
            #-------------------------------------------------------------------------#
            
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            print("✅ DevTools debería estar abierta ahora.")
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Seleccionar el idioma dinámicamente
            #-------------------------------------------------------------------------#
            idioma = (self.lenguaje or "Spanish").lower()
            print(f"⌨️ Escribiendo '{idioma}' en el campo de búsqueda de idiomas...")

            script_select_language = f'''
            (async function () {{
                const input = document.querySelector('input.c-kojsVf[placeholder="Search languages"]');
                if (!input) {{
                    console.warn("⚠️ No se encontró el input.");
                    return;
                }}

                input.focus();
                input.value = "{idioma}";
                input.dispatchEvent(new Event("input", {{ bubbles: true }}));
                input.dispatchEvent(new Event("change", {{ bubbles: true }}));
                console.log("⌨️ Escribiendo '{idioma}'...");

                // Esperar y buscar la opción que diga "{idioma}"
                const maxRetries = 20;
                let retries = 0;
                let option;

                while (retries < maxRetries) {{
                    await new Promise((r) => setTimeout(r, 200));
                    option = Array.from(document.querySelectorAll("div, span, button, li"))
                    .find(el => el.textContent.trim().toLowerCase() === "{idioma}");

                    if (option) break;
                    retries++;
                }}

                if (option) {{
                    option.click();
                    console.log("✅ Opción '{idioma}' seleccionada.");
                }} else {{
                    console.warn("⚠️ No se encontró la opción '{idioma}' después de escribir.");
                }}
            }})();
            '''

            pyperclip.copy(script_select_language)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print(f"✅ Selección de idioma '{idioma}' correctamente.")
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Click al boton de seleccion de estilo de video
            #-------------------------------------------------------------------------#
            print("🖱️ Click al botón de estilo de video ...")
            
            script_style = '''
            (function () {
                const botones = Array.from(document.querySelectorAll('div[tabindex="0"]'));
                const boton = botones.find(div => {
                    const texto = div.innerText.trim().toLowerCase();
                    return texto.includes("edit style");
                });

                if (!boton) {
                    console.warn("❌ No se encontró ningún botón con 'Edit style'.");
                    return;
                }

                boton.scrollIntoView({ behavior: "smooth", block: "center" });
                boton.focus();
                boton.click();
                console.log("✅ Se hizo clic en el botón de estilo detectado.");
            })();
            '''
            
            pyperclip.copy(script_style)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Seleccion de estilo de video clickeada correctamente.")
            
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Seleccion aleatoria de estilo de video
            #-------------------------------------------------------------------------#
            print("🎨 Seleccionando estilo de video aleatorio...")
            
            script_random_style = '''
            (function() {
                // Selecciona todos los estilos disponibles
                const estilos = Array.from(document.querySelectorAll('.c-kcwvRG'));

                if (estilos.length === 0) {
                    console.warn("❌ No se encontraron estilos.");
                    return;
                }

                // Filtra el que ya esté seleccionado
                const disponibles = estilos.filter(el => !el.classList.contains('c-kcwvRG-hJXGzc-selected-true'));

                if (disponibles.length === 0) {
                    console.warn("❌ Todos los estilos están seleccionados o no hay alternativos.");
                    return;
                }

                // Elige uno aleatorio
                const random = disponibles[Math.floor(Math.random() * disponibles.length)];

                // Scroll y click
                random.scrollIntoView({ behavior: 'smooth', block: 'center' });
                setTimeout(() => {
                    random.click();
                    const nombre = random.innerText.trim();
                    console.log("✅ Estilo aleatorio seleccionado:", nombre);
                }, 500);
            })();    
            '''
            
            pyperclip.copy(script_random_style)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Seleccion de estilo de video aleatoria clickeada correctamente.")
            
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Seleccion aleatoria del color de estilo de video
            #-------------------------------------------------------------------------#
            print("🎨 Seleccionando color de estilo de video aleatorio...")
            
            script_random_color = '''
            (function() {
                try {
                    const colores = Array.from(document.querySelectorAll('.c-cpQStm[role="button"]'));

                    if (colores.length === 0) {
                        console.warn("⚠️ No se encontraron botones de colores. Continuando ejecución.");
                        return;
                    }

                    // Filtra los que no están ya seleccionados
                    const disponibles = colores.filter(c => !c.innerHTML.includes('isSelected-true'));

                    if (disponibles.length === 0) {
                        console.warn("⚠️ Todos los colores están seleccionados o no hay alternativos. Continuando ejecución.");
                        return;
                    }

                    const random = disponibles[Math.floor(Math.random() * disponibles.length)];

                    random.scrollIntoView({ behavior: 'smooth', block: 'center' });

                    setTimeout(() => {
                        random.click();
                        console.log("✅ Color seleccionado aleatoriamente.");
                    }, 500);
                } catch (error) {
                    console.error("⚠️ Error al seleccionar color. Continuando ejecución.", error);
                }
            })();
            '''
            
            pyperclip.copy(script_random_color)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Seleccion de color de estilo de video aleatoria clickeada correctamente.")
            
            time.sleep(5)
            #-------------------------------------------------------------------------#
            # Clic al boton continuar
            #-------------------------------------------------------------------------#
            print("🖱️ Click al botón 'Continue' ...")
            
            script_continue1 = ''' 
            (function () {
                const botones = document.querySelectorAll('button.c-gqJKEJ');

                for (let btn of botones) {
                    const texto = btn.innerText.trim().toLowerCase();
                    if (texto === "continue") {
                        btn.scrollIntoView({ behavior: "smooth", block: "center" });
                        btn.click();
                        console.log("✅ Botón 'Continue' clickeado correctamente.");
                        return;
                    }
                }

                console.warn("❌ No se encontró el botón 'Continue'.");
            })();
            '''
            
            pyperclip.copy(script_continue1)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton continuar correctamente.")
            
            time.sleep(20)
            
            #-------------------------------------------------------------------------#
            # Clic al boton de generacion de video
            #-------------------------------------------------------------------------#
            print("🖱️ Click al botón 'Generate Video' ...")
            
            script_generateVideo1 = ''' 
            (function () {
                const botones = Array.from(document.querySelectorAll('button.c-gqJKEJ'));

                for (let boton of botones) {
                    const divInterno = boton.querySelector('div');
                    const texto = divInterno?.innerText?.trim()?.toLowerCase();

                    if (texto === "generate video") {
                        boton.scrollIntoView({ behavior: "smooth", block: "center" });
                        boton.click();
                        console.log("✅ Botón 'Generate Video' clickeado correctamente.");
                        return;
                    }
                }

                console.warn("❌ No se encontró el botón 'Generate Video'.");
            })();
            '''
            
            pyperclip.copy(script_generateVideo1)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton de generacion de video correctamente.")
            
            time.sleep(10)
            
            #-------------------------------------------------------------------------#
            # Se ejecuca la funcion para esperar que se genere el video y dar click al nuevo video
            #-------------------------------------------------------------------------#
            print("⏳ Esperando que se genere el video y dar click al nuevo video...")
            esperar_y_ejecutar_click_nuevo_video(driver)
            
            
            #-------------------------------------------------------------------------#
            # Agregar musica al video
            #-------------------------------------------------------------------------#
            print("🎵 Agregando música al video...")
            
            script_agregar_musica = ''' 
            (function() {
            const botones = document.querySelectorAll('button.c-dJareS[data-state="closed"]');

            const botonMusic = Array.from(botones).find(btn =>
                btn.textContent.trim().toLowerCase() === 'music'
            );

            if (botonMusic) {
                botonMusic.click();
                console.log('✅ Se hizo clic en el botón "Music".');
            } else {
                console.warn('⚠️ No se encontró el botón con texto "Music" y estado cerrado.');
            }
            })(); 
            (function() {
            const botones = document.querySelectorAll('button.c-dJareS[data-state="closed"]');

            const botonMusic = Array.from(botones).find(btn =>
                btn.textContent.trim().toLowerCase() === 'music'
            );

            if (botonMusic) {
                botonMusic.click();
                console.log('✅ Se hizo clic en el botón "Music".');
            } else {
                console.warn('⚠️ No se encontró el botón con texto "Music" y estado cerrado.');
            }
            })();
            
            
            '''
            
            pyperclip.copy(script_agregar_musica)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton de musica correctamente.")
            
            time.sleep(6)
            
            #-------------------------------------------------------------------------#
            # Escribir la musica
            #-------------------------------------------------------------------------#
            print("🖊️ Escribiendo texto en el área de música...")
            escribir_texto_en_musica(driver, self.id_contenido)    
            
            time.sleep(8)
            
            #-------------------------------------------------------------------------#
            # Desactivar consola con f12
            #-------------------------------------------------------------------------#
            
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            time.sleep(2)
            print("✅ DevTools debería estar abierta ahora.")
            time.sleep(3)
                        
            #-------------------------------------------------------------------------#
            # Activar consola con f12
            #-------------------------------------------------------------------------#
            
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            time.sleep(2)
            print("✅ DevTools debería estar abierta ahora.")
            time.sleep(3)
                        
            #-------------------------------------------------------------------------#
            # Click al boton de continuar
            #-------------------------------------------------------------------------#
            print("🖱️ Click al botón 'Continue' ...")
            
            script_generate_music = '''
            (function() {
            // Buscar todos los botones con clase principal
            const botones = document.querySelectorAll('button.c-gqJKEJ');

            // Filtrar el botón que contenga el texto "Generate"
            const botonGenerate = Array.from(botones).find(btn =>
                btn.textContent.trim().toLowerCase() === 'generate'
            );

            if (botonGenerate) {
                botonGenerate.click();
                console.log('✅ Botón "Generate" fue clickeado.');
            } else {
                console.warn('⚠️ No se encontró el botón con texto "Generate".');
            }
            })();
            '''
            
            pyperclip.copy(script_generate_music)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton de musica correctamente.")
            
            time.sleep(30)
            verificar_y_reintentar(driver, tiempo_espera=10)
            
            #-------------------------------------------------------------------------#
            # Click al boton de insertar en musica
            #-------------------------------------------------------------------------#
            print("🖱️ Click al botón 'Insert' en música ...")
            
            script_click_insert = '''
            (function() {
                const insertButton = Array.from(document.querySelectorAll("button")).find(btn =>
                    btn.textContent.trim() === "Insert"
                );
                if (insertButton) {
                    insertButton.click();
                    console.log("✅ Botón 'Insert' clickeado automáticamente.");
                } else {
                    console.warn("❌ No se encontró el botón Insert.");
                }
            })();
            '''
            
            pyperclip.copy(script_click_insert)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton de insertar musica correctamente.")
            
            time.sleep(30)
            
            
            #-------------------------------------------------------------------------#
            # Click en el slider para configurar volumen de la musica
            #-------------------------------------------------------------------------#
            
            mover_slider_a_mitad(driver)
            time.sleep(10)
            
            #-------------------------------------------------------------------------#
            # Desactivar consola con f12
            #-------------------------------------------------------------------------#
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            time.sleep(2)
            print("✅ DevTools debería estar cerrada ahora.")
            time.sleep(3)
            
            #-------------------------------------------------------------------------#            
            # Activar consola con f12
            #-------------------------------------------------------------------------#
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            time.sleep(2)
            print("✅ DevTools debería estar abierta ahora.")
            time.sleep(3)
            
            #-------------------------------------------------------------------------#
            # Click en boton cerrar editor mussica
            #-------------------------------------------------------------------------#
            print("🖱️ Click al botón de cerrar editor de música ...")
            
            script_close_music = ''' 
            (function() {
                const botones = Array.from(document.querySelectorAll("button"));
                const botonFlecha = botones.find(btn => {
                    return btn.className.includes("variant-tertiary") &&
                        btn.querySelector("svg path");
                });

                if (botonFlecha) {
                    botonFlecha.click();
                    console.log("✅ Botón de doble flecha clickeado.");
                } else {
                    console.warn("❌ Botón de doble flecha no encontrado.");
                }
            })();
            '''
            
            pyperclip.copy(script_close_music)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton de cerrar editor musica correctamente.")
            
            time.sleep(10)
            #-------------------------------------------------------------------------#         
            #Click al boton de exportar video
            #-------------------------------------------------------------------------#
            print("🖱️ Click al botón 'Export' ...")
            
            script_exportar_video = ''' 
            (function() {
                const botonExport = Array.from(document.querySelectorAll("button")).find(btn =>
                    btn.textContent.trim() === "Export"
                );

                if (botonExport) {
                    botonExport.click();
                    console.log("✅ Botón 'Export' clickeado correctamente.");
                } else {
                    console.warn("❌ No se encontró el botón 'Export'.");
                }
            })();
            '''
            pyperclip.copy(script_exportar_video)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton de exportar video correctamente.")
            
            time.sleep(10)
            
            #-------------------------------------------------------------------------#
            # Click al segundo boton de exportar video
            #-------------------------------------------------------------------------#
            print("🖱️ Click al segundo botón 'Export Video' ...")
            
            script_exportar_video2 = '''
            (function () {
            // Buscar todos los botones con la clase base
            const botones = document.querySelectorAll('button.c-bSUvQZ');

            // Filtrar por el que contenga el texto "Export Video"
            const exportBtn = Array.from(botones).find(btn =>
                btn.textContent.trim().toLowerCase() === 'export video'
            );

            if (exportBtn) {
                exportBtn.click();
                console.log('✅ Botón "Export Video" clickeado.');
            } else {
                console.warn('⚠️ No se encontró el botón "Export Video".');
            }
            })();'''
            
            pyperclip.copy(script_exportar_video2)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton de descargar correctamente.")
            
            time.sleep(10)
            
            #-------------------------------------------------------------------------#
            # Esperar a que se descargue el video
            #-------------------------------------------------------------------------#
            # Esperar descarga final
            directorio = r"C:\Users\Programador2\Downloads"
            archivo = esperar_loader_y_archivo_descargado(driver, directorio)

            if archivo:
                print("🎉 Descarga completa y archivo detectado:", archivo)
            else:
                print("⚠️ No se pudo detectar la descarga.")

            # ⚠️ Aquí ya no debe haber return, siempre continuamos
            
            #-------------------------------------------------------------------------#
            # Subir video a Drive
            #-------------------------------------------------------------------------#
            
            
            print("📤 Ejecutando función subir_video_drive()...")
            subidas = subir_video_drive()

            if subidas:
                print("📦 JSON recibido correctamente:")
                print(subidas)

                try:
                    url = subidas[0].get("url", "")
                except Exception:
                    url = ""

                self.url_generada = url

                if self.id_contenido:
                    # Registrar el video automáticamente en DB (inserta si no existe)
                    try:
                        marcar_como_subido(self.id_contenido, url)
                        print(f"✅ Video marcado como subido en DB con ID {self.id_contenido}.")
                    except Exception as e:
                        print(f"⚠️ No se pudo marcar como subido en DB: {e}")

                    try:
                        # Si tu función acepta más flags (upload_drive, upload_excel), pásalos aquí
                        guardar_video_generado(
                            self.tema,
                            self.platform_video,
                            url,
                            self.campaign_key,
                            self.id_contenido
                        )
                        print(f"✅ Video registrado con id_contenido = {self.id_contenido}")
                    except Exception as e:
                        print(f"⚠️ No se pudo registrar el video en DB: {e}")

                    # ------------------ Armado del resultado para Excel / caller ------------------ #
                    resultado = {
                        "Tema": self.tema or "",
                        "Plataforma": self.platform_video or "",
                        "Campaña": self.campaign_key or "",
                        "ID Contenido": self.id_contenido or "",
                        "Idioma": self.lenguaje or "",
                        "Hashtags": self.hashtags or "",
                        "URL": url or ""  # 👈 ahora sí con la URL real
                    }
                    # Guarda para que el return del finally sirva
                    self.resultado_video = resultado    
                    # ----------------------------------------------------------------------------- #

                    video_completado_correctamente = True
                    print(f"✅ Video registrado y marcado como subido con id_contenido = {self.id_contenido}")

                    # 🛑 Cerrar ventana emergente si existe
                    try:
                        if len(driver.window_handles) > 1:
                            # Cambiar a la última ventana (emergente) y cerrarla
                            driver.switch_to.window(driver.window_handles[-1])
                            driver.close()
                            # Volver a la ventana principal
                            driver.switch_to.window(driver.window_handles[0])
                            print("🪟 Ventana emergente cerrada y volvimos a la principal.")
                        else:
                            print("ℹ️ No se encontró ventana emergente para cerrar.")
                    except Exception as e:
                        print(f"⚠️ Error al intentar cerrar la ventana emergente: {e}")

                else:
                    print("⚠️ No se encontró id_contenido para registrar el video.")
            else:
                print("❌ No se subió ningún archivo a Drive.")

            time.sleep(2)
            #-------------------------------------------------------------------------#
            # Verificar si la sesión sigue activa (buscar algún elemento clave)
            #-------------------------------------------------------------------------#
            
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='dashboard'], nav, header"))
                )
                print("🔐 Sesión detectada en la nueva pestaña.")
            except: 
                print("⚠️ Posible deslogueo. No se detectaron elementos de sesión activa.")

        except Exception as e:
            print(f"❌ Error en el proceso: {e}")
            traceback.print_exc()

        finally:
            if video_completado_correctamente:
                print("✅ Video creado y subido. Continuando con el siguiente...")  
            else:
                print("⚠️ El video no se completó correctamente. No se marcará como subido.")
            return self.resultado_video  # 👈 IMPORTANTE
        # ------------------------------------------------------------------------- #