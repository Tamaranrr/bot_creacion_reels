import os
import re
import json
import random
import time 
import pandas as pd
from pathlib import Path
from datetime import datetime
from pathlib import Path


from utils.db_connection import obtener_descripcion_contenido
from utils.db_connection import obtener_sonido_contenido

import pygetwindow as gw
import pyautogui
import pyperclip  # Asegura copiar texto con símbolos correctamente
import traceback

# Importaciones de Selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium. webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import TimeoutException
from selenium.common.exceptions import NoSuchElementException

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
def guardar_video_en_excel(self):
            """
            Guarda los datos del video generado en un Excel con el formato esperado por fastApi y excel_update.py
            """
            excel_path = Path("videos_generados.xlsx")

            # Crear el nuevo registro con las columnas que usa excel_update.py
            nuevo_registro = {
                "Tema": self.tema or "",
                "Plataforma": self.platform_video or "",
                "Campaña": self.campaign_key or "",
                "ID Contenido": self.id_contenido or "",
                "Idioma": self.lenguaje or "",
                "Hashtags": self.hashtags or "",
                "URL": self.resultado_video["url"] if hasattr(self, "resultado_video") else ""
            }

            # Si ya existe el Excel, lo cargamos y añadimos la nueva fila
            if excel_path.exists():
                df = pd.read_excel(excel_path)
                df = pd.concat([df, pd.DataFrame([nuevo_registro])], ignore_index=True)
            else:
                df = pd.DataFrame([nuevo_registro])

            # Guardar el Excel actualizado
            df.to_excel(excel_path, index=False)
            print(f"📊 Video agregado al Excel: {excel_path}")

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

def esperar_y_ejecutar_click_nuevo_video(driver):

    print("⏳ Esperando a que se complete la animación del círculo SVG...")

    frame_anterior = driver.execute_script("return window.location.href;")

    while True:
        try:
            # Intentar encontrar el círculo animado del loader
            circle = driver.find_element(By.CSS_SELECTOR, 'circle[stroke="#FFFFFF"][stroke-dasharray]')
            dashoffset = driver.execute_script("return arguments[0].getAttribute('stroke-dashoffset');", circle)
            print(f"🔄 Cargando video... dashoffset actual: {dashoffset}")
            time.sleep(2)
        except NoSuchElementException:
            print("✅ Círculo SVG de carga desaparecido.")
            time.sleep(2)
            break
    time.sleep(20)
    # Esperar a que aparezca el nuevo video y esté listo para clic
    try:
        print("⏳ Esperando que aparezca el nuevo video en la lista...")
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.c-kWUgUw a[href^="/projects/pro-editor/"]'))
        )
        time.sleep(1)
        print("✅ Nuevo video disponible para hacer clic.")
    except:
        print("❌ No se encontró el nuevo video en el tiempo esperado.")
        return
    
    # Ejecutar JS para dar click al contenedor donde estaba el video
    script_click_video = '''
    (function () {
        const contenedores = Array.from(document.querySelectorAll('div.c-kWUgUw'));
        
        for (const div of contenedores) {
            const link = div.querySelector('a[href^="/projects/pro-editor/"]');
            if (link) {
                link.scrollIntoView({ behavior: "smooth", block: "center" });
                link.click();
                console.log("✅ Click en el primer video visible de la lista.");
                return true;
            }
        }

        console.warn("❌ No se encontró ningún enlace de video.");
        return false;
    })();
    '''

    pyperclip.copy(script_click_video)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)
    pyautogui.press('enter')
    print("✅ Script ejecutado para hacer clic al nuevo video.")

    # Verificar si el frame cambió
    time.sleep(3)
    frame_actual = driver.execute_script("return window.location.href;")
    if frame_actual != frame_anterior:
        print("🎉 El frame ha cambiado correctamente.")
        return
    else:
        print("⏳ El frame no ha cambiado aún. Reintentando...")
        time.sleep(5)
        esperar_y_ejecutar_click_nuevo_video(driver) 
        # Reintentar recursivamente

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
        x_end = x_start - int(width / 4)  # puedes ajustar esto si el arrastre requiere menos recorrido

        print(f"🎯 Moviendo slider desde ({x_start}, {y}) hasta ({x_end}, {y})")
        pyautogui.moveTo(x_start, y, duration=0.3)
        pyautogui.mouseDown()
        pyautogui.moveTo(x_end, y, duration=0.4)
        pyautogui.mouseUp()
        print("✅ Slider bajado a la mitad.")
    else:
        pyautogui.screenshot("error_slider.png")
        print("❌ No se detectó el slider. Se guardó una captura como 'error_slider.png'.")

def esperar_y_ejecutar_click_edit_style(driver):
    print("⏳ Esperando a que desaparezca el loader...")

    # 1. Esperar a que desaparezca el loader (basado en divs múltiples)
    while True:
        try:
            loader = driver.find_element(By.CSS_SELECTOR, 'div.c-hPeQtj')
            if loader.is_displayed():
                print("🔄 Loader visible, esperando...")
                time.sleep(1)
            else:
                break
        except:
            print("✅ Loader desaparecido.")
            break

    print("⏳ Esperando que aparezca el botón 'Edit style'...")


    # 3. Ejecutar script JS por consola
    script_click_edit_style = '''
    (function() {
        const botones = Array.from(document.querySelectorAll("button"));
        const boton = botones.find(b => 
            b.textContent.trim().toLowerCase().includes("edit style")
        );

        if (!boton) {
            console.warn("❌ No se encontró el botón que contenga 'edit style'.");
            return;
        }

        boton.scrollIntoView({ behavior: "smooth", block: "center" });

        setTimeout(() => {
            boton.click();
            console.log("✅ Botón 'Edit style' clickeado.");
        }, 300);
    })();
    '''
    import pyperclip
    import pyautogui

    pyperclip.copy(script_click_edit_style)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.5)
    pyautogui.press('enter')
    print("✅ Script ejecutado correctamente para hacer clic en 'Edit style'.")
    
def esperar_desaparicion_loader(driver):
    print("⏳ Esperando a que desaparezca el loader post-cambio de frame...")

    while True:
        try:
            loader = driver.find_element(By.CSS_SELECTOR, 'div.c-hPeQtj')
            print("🔄 Loader aún presente... esperando...")
            time.sleep(1)
        except NoSuchElementException:
            print("✅ Loader desaparecido. Continuando con la ejecución.")
            break
    time.sleep(10)    
    
def obtener_ultimo_archivo_descargado(directorio_descargas):
    archivos = [os.path.join(directorio_descargas, f) for f in os.listdir(directorio_descargas)]
    archivos = [f for f in archivos if os.path.isfile(f)]
    if not archivos:
        print("⚠️ No se encontraron archivos en el directorio.")
        return None
    archivo_reciente = max(archivos, key=os.path.getctime)
    print(f"📥 Último archivo descargado detectado: {archivo_reciente}")
    return archivo_reciente

def subir_ultimo_video_descargado():
    print("📤 Subiendo el último video descargado...")
    
    directorio = r"C:\Users\Programador2\Downloads"
    
    archivo = obtener_ultimo_archivo_descargado(directorio)
    if not archivo:
        return

    # Esperar a que se abra el explorador de archivos
    time.sleep(2)

    # Escribir la ruta en el diálogo
    pyautogui.write(archivo)
    time.sleep(0.5)
    pyautogui.press('enter')
    print("✅ Archivo subido correctamente.")
    time.sleep(10)


#--------------------------------------------------------#
#--------------------------------------------------------#


# 👇 Clase principal con Selenium y playautogui
class BotTestimonio:
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
            # Activar consola con f12
            #-------------------------------------------------------------------------#
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            print("✅ DevTools debería estar abierta ahora.")
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Click al boton AI Creator
            #-------------------------------------------------------------------------#
            print("🖱️ Buscando el botón 'AI Creator' en pantalla con PyAutoGUI...")
            
            script_ai_creator = '''
            (function(){
                const aiCreatorButton = document.querySelector('a[data-testid="home-ai-creators-button"]');
                if (aiCreatorButton) {
                    aiCreatorButton.click();
                    console.log("✅ Botón 'AI Creator' clickeado.");
                } else {
                    console.log("❌ Botón 'AI Creator' no encontrado.");
                }
            })();
            '''
            # Copiar el script al portapapeles (más seguro que escribirlo)
            pyperclip.copy(script_ai_creator)

            # Pegar el contenido
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
        
            # Ejecutar
            pyautogui.press('enter')
            print("✅ Click al boton AI Creator correctamente.")
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Click al boton Prompt to Video
            #-------------------------------------------------------------------------#
            print("🖱️ Buscando el botón 'Prompt to Video' en pantalla con PyAutoGUI...")
            
            script_prompt_to_video = '''
            (function () {
                const botones = document.querySelectorAll('button.c-dCHVwK');

                const botonPromptToVideo = Array.from(botones).find(btn =>
                    btn.textContent.trim().toLowerCase().includes('prompt to video')
                );

                if (botonPromptToVideo) {
                    botonPromptToVideo.click();
                    console.log('✅ Botón "Prompt to video" clickeado.');
                } else {
                    console.warn('⚠️ No se encontró el botón "Prompt to video".');
                }
            })();

            '''
            pyperclip.copy(script_prompt_to_video)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
        
            pyautogui.press('enter')
            print("✅ Click al boton Prompt To Video correctamente.")
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Desactivar consola con f12
            #-------------------------------------------------------------------------#
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            print("✅ DevTools debería estar Cerrada ahora.")
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
                ruta_img_descripcion = os.path.join(base_dir, "img", "testimonio", "descripcion.png")
                descripcion = pyautogui.locateOnScreen(ruta_img_descripcion, confidence=0.8)

                if descripcion:
                    x, y = pyautogui.center(descripcion)
                    pyautogui.click(x, y)
                    print("✅ Caja de descripción encontrada y clicada.")
                    time.sleep(1)
                    descripcion = obtener_descripcion_contenido(self.id_contenido)
                    if descripcion:
                        pyautogui.write(descripcion, interval=0.03)
                        pyautogui.press("enter")
                    else:
                        pyautogui.write("Descripción por defecto", interval=0.03)
                        pyautogui.press("enter")
                else:
                    raise Exception("No se detectó la caja de descripción.")
            except Exception as e:
                print(f"❌ Error al procesar el área de descripción: {e}")
                traceback.print_exc()
                pyautogui.screenshot("error_descripcion.png")
                return
        
            #-------------------------------------------------------------------------#
            # Click al boton de idioma
            #-------------------------------------------------------------------------#
        
            print("🖱️ Buscando el botón 'Idioma' en pantalla con PyAutoGUI...")
            base_dir = os.path.dirname(__file__)
            ruta_globe_button = os.path.join(base_dir, "img","testimonio", "globe_button.png")
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
            # Click en flecha continuar
            #-------------------------------------------------------------------------#
            print("➡️ Esperando a que cargue el botón de flecha continuar...")
            
            script_select_language = '''
            (function () {
            const boton = document.querySelector('button.c-bSUvQZ.c-bSUvQZ-idqmXT-size-sm.c-bSUvQZ-jjRsmM-variant-primary-niagara.c-bSUvQZ-ctncdz-colorScheme-purple.c-bSUvQZ-hyPGYo-cv');
            if (boton) {
                boton.click();
                console.log("✅ Botón de flecha continuar correctamente.");
            } else {
                console.warn("⚠️ Botón no encontrado.");
            }
            })();
            '''
            pyperclip.copy(script_select_language)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
        
            pyautogui.press('enter')
            print("✅ Click continuar correctamente.")
            time.sleep(15)

        
            #-------------------------------------------------------------------------#
            # Click en editar estilo
            #-------------------------------------------------------------------------#
            print("✏️ Esperando a que cargue el área de edición de estilo...")
            
            esperar_y_ejecutar_click_edit_style(driver)
            
        
            #-------------------------------------------------------------------------#
            #Click en seleccion de personaje
            #-------------------------------------------------------------------------#
            esperar_desaparicion_loader(driver)
            
            print("👤 Esperando a que cargue el área de selección de personaje...")
            script_select_character = ''' 
            (function () {
                const nombresValidos = [
                    "elena","jason","grace","isabella","james","ava","erica","norah","kate","jake","kira","luke",
                    "selene","anna","ethan","elle","liam","olivia","michael","brooke","lucy","alison","victor",
                    "leah","daniela","violet","amanda","douglas","harper","jayden","madison","jack","monica",
                    "heidi","frankie","emmett","molly","ashley","eliza","luca","veronica","julie","kieran","cam"
                ];

                const spans = Array.from(document.querySelectorAll('span.c-jpZrnk'));
                const candidatos = [];

                spans.forEach(span => {
                    const nombre = span.textContent.trim().toLowerCase();
                    if (nombresValidos.includes(nombre)) {
                        const contenedor = span.closest('.c-dtARzA');
                        if (contenedor) {
                            const elementoClickable = contenedor.querySelector('video, img, div'); // intentamos con hijos típicos
                            if (elementoClickable) {
                                candidatos.push({ nombre, elemento: elementoClickable });
                            } else {
                                candidatos.push({ nombre, elemento: contenedor }); // fallback
                            }
                        }
                    }
                });

                if (candidatos.length === 0) {
                    console.warn("❌ No se encontraron personajes válidos.");
                    return;
                }

                const seleccionado = candidatos[Math.floor(Math.random() * candidatos.length)];
                const el = seleccionado.elemento;

                el.scrollIntoView({ behavior: "smooth", block: "center" });

                setTimeout(() => {
                    const evt = new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    const success = el.dispatchEvent(evt);

                    if (success) {
                        console.log("✅ Personaje seleccionado:", seleccionado.nombre);
                    } else {
                        console.warn("⚠️ El evento no fue aceptado.");
                    }
                }, 500); // tiempo para scroll
            })();

            '''

            pyperclip.copy(script_select_character)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
        
            pyautogui.press('enter')
            print("✅ Seleccion de caracter correctamente.")
            time.sleep(10)
        
            #-------------------------------------------------------------------------#
            # Click en el botón de Generar
            #-------------------------------------------------------------------------#
            print("🎥 Esperando a que cargue el área de generación de video...")
            
            script_generate_button = '''
            (function () {
                const botones = Array.from(document.querySelectorAll('button'));

                const boton = botones.find(b => 
                    b.innerText.trim().toLowerCase().includes("generate video")
                );

                if (!boton) {
                    console.warn("❌ No se encontró el botón 'Generate Video'.");
                    return;
                }

                boton.scrollIntoView({ behavior: "smooth", block: "center" });

                setTimeout(() => {
                    const evento = new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    const exito = boton.dispatchEvent(evento);
                    if (exito) {
                        console.log("✅ Botón 'Generate Video' clickeado correctamente.");
                    } else {
                        console.warn("⚠️ No se pudo ejecutar el clic.");
                    }
                }, 500);
            })();
            '''
            
            pyperclip.copy(script_generate_button)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
        
            pyautogui.press('enter')
            print("✅ Click en Generate Video correctamente.")
            time.sleep(10)
            
            #-------------------------------------------------------------------------#
            # Esperar a que se genere el video y hacer clic en el nuevo video
            #-------------------------------------------------------------------------#
            esperar_y_ejecutar_click_nuevo_video(driver)
            time.sleep(10)
            
            esperar_desaparicion_loader(driver)
            time.sleep(2)
        
            #-------------------------------------------------------------------------#
            #Click en visibility para eliminar subrititulos
            #-------------------------------------------------------------------------#
            print("👁️ Esperando a que cargue el área de subtitulos...")
            
            script_visibility = ''' 
            (function () {
                const switches = Array.from(document.querySelectorAll('button[role="switch"]'));

                if (switches.length === 0) {
                    console.warn("❌ No se encontraron botones con role='switch'.");
                    return;
                }

                const targetSwitch = switches.find(sw => 
                    sw.getAttribute('aria-checked') === "true" || 
                    sw.getAttribute('aria-checked') === "false"
                );

                if (!targetSwitch) {
                    console.warn("⚠️ No se encontró ningún switch con estado válido.");
                    return;
                }

                targetSwitch.scrollIntoView({ behavior: "smooth", block: "center" });

                setTimeout(() => {
                    targetSwitch.click();
                    console.log("✅ Switch clickeado. Estado anterior:", targetSwitch.getAttribute('aria-checked'));
                }, 300);
            })();            
            '''
        
            pyperclip.copy(script_visibility)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
        
            pyautogui.press('enter')
            print("✅ Click en Visibility correctamente.")
            time.sleep(8)
            
            

            #-------------------------------------------------------------------------#
            # Click en el primer botón de exportar
            #-------------------------------------------------------------------------#
            print("📤 Esperando a que cargue el área de exportación...")
            
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
            
            time.sleep(20)
            
            #--------------------------------------------------------------------------#
            #Click al segundo boton de exportar video
            #--------------------------------------------------------------------------#
            print("📤 Esperando a que cargue el segundo botón de exportación...")
            
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
            
            time.sleep(20)
            
            #-------------------------------------------------------------------------#
            # Esperar a que se descargue el video
            #-------------------------------------------------------------------------#
            print("⏳ Esperando a que se descargue el video...")
            
            directorio = r"C:\Users\Programador2\Downloads"
            archivo = esperar_loader_y_archivo_descargado(driver, directorio)
            if archivo:
                print("🎉 Descarga completa y archivo detectado:", archivo)
            else:
                print("⚠️ No se pudo detectar la descarga.")

            #-------------------------------------------------------------------------#
            # Cerrar la ventana de descarga
            #-------------------------------------------------------------------------#
            print("❌ Buscando el botón 'Close' en la ventana de descarga ")
            
            script_close_download = '''
            (function() {
                const botones = document.querySelectorAll('button');
                for (let btn of botones) {
                    if (btn.innerText.trim() === "Close") {
                        btn.click();
                        console.log("✅ Botón 'Close' clickeado por texto.");
                        return;
                    }
                }
                console.warn("❌ Botón con texto 'Close' no encontrado.");
            })();
            '''
            
            pyperclip.copy(script_close_download)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton de descargar correctamente.")
            
            time.sleep(20)
            
            #-------------------------------------------------------------------------#
            #Volver a la página principal
            #-------------------------------------------------------------------------#
            print("🏠 Volviendo a la página principal...")
            
            script_home_page = '''
            (function () {
                const enlace = Array.from(document.querySelectorAll('a.c-dJareS')).find(a => 
                    a.getAttribute('href') === '/projects'
                );

                if (!enlace) {
                    console.warn("❌ No se encontró el enlace con href='/projects'.");
                    return;
                }

                enlace.scrollIntoView({ behavior: "smooth", block: "center" });

                setTimeout(() => {
                    enlace.click();
                    console.log("✅ Enlace '/projects' clickeado correctamente.");
                }, 500); // Espera para asegurar que esté en pantalla
            })();
            '''
            pyperclip.copy(script_home_page)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton de home correctamente.")
            
            time.sleep(10)
            
            #-------------------------------------------------------------------------#
            #Click al boton Ai Edit
            #-------------------------------------------------------------------------#
            print("🖱️ Click al botón 'AI Edit' " )
            
            script_edit = '''
            (function() {
                const botonAIEdit = document.querySelector('a[data-testid="home-ai-edit-button"]');
                if (botonAIEdit) {
                    botonAIEdit.click();
                    console.log("✅ Botón 'AI Edit' clickeado correctamente.");
                } else {
                    console.warn("❌ No se encontró el botón 'AI Edit'.");
                }
            })();
            ''' 
            
            pyperclip.copy(script_edit)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton de Ai Edit correctamente.")
            time.sleep(10)
            
            #-------------------------------------------------------------------------#
            # Subir el último video descargado
            #-------------------------------------------------------------------------#

            subir_ultimo_video_descargado()
            
            #-------------------------------------------------------------------------#
            # Estilo seleccionado aleatoriamente
            #-------------------------------------------------------------------------#
            print("🎨 Seleccionando un estilo aleatorio...")
            
            script_select_style = ''' 
            (function () {
                const spans = document.querySelectorAll('span.c-kilcUL');
                if (!spans.length) {
                    console.warn("⚠️ No se encontraron estilos.");
                    return;
                }

                const randomIndex = Math.floor(Math.random() * spans.length);
                const span = spans[randomIndex];
                const styleName = span.innerText;

                const parentDiv = span.closest('.c-kcwvRG');
                if (parentDiv) {
                    parentDiv.click();
                    console.log(`✅ Click realizado en el estilo: ${styleName}`);
                } else {
                    console.warn("⚠️ No se encontró el contenedor del estilo.");
                }
            })();
            '''
            pyperclip.copy(script_select_style)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Estilo seleccionado aleatoriamente.")
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Seleccion aleatoria del color de estilo de video
            #-------------------------------------------------------------------------#
            print("🎨 Seleccionando un color de estilo de video aleatorio...")
            
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
            # Desactivar consola con f12
            #-------------------------------------------------------------------------#
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            print("✅ DevTools debería estar Cerrada ahora.")
            time.sleep(5)
            
            
            #-------------------------------------------------------------------------------#
            # 13. Seleccion de idioma 
            #-------------------------------------------------------------------------------#
            print("🖱️ Buscando el botón 'Idioma' en pantalla con PyAutoGUI...")
            
            base_dir = os.path.dirname(__file__)
            ruta_idiome_button = os.path.join(base_dir, "img","testimonio", "idioma.png")
            try:
                time.sleep(2)  # da tiempo a que termine cualquier animación
                boton_pos = pyautogui.locateCenterOnScreen(ruta_idiome_button, confidence=0.8)
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
            
            #---------------------------------------------------------------------------#
            # Seleccionar el idioma Inglés
            #---------------------------------------------------------------------------#
            print("⌨️ Escribiendo 'English' en el campo de búsqueda de idiomas...")
            
            script_select_language = '''
            (async function () {
                const input = document.querySelector('input[type="search"][placeholder="Search languages"]');
                if (!input) {
                    console.warn("⚠️ No se encontró el input de búsqueda.");
                    return;
                }

                // Enfocar y escribir "English"
                input.focus();
                input.value = "English";
                input.dispatchEvent(new Event("input", { bubbles: true }));
                input.dispatchEvent(new Event("change", { bubbles: true }));
                console.log("⌨️ Escribiendo 'English'...");

                // Esperar a que aparezca la opción
                const maxRetries = 15;
                let retries = 0;
                let option;

                while (retries < maxRetries) {
                    await new Promise(r => setTimeout(r, 200));
                    option = Array.from(document.querySelectorAll('[role="option"]')).find(el =>
                        el.textContent.trim().toLowerCase().includes("english")
                    );
                    if (option) break;
                    retries++;
                }

                if (option) {
                    option.click();
                    console.log("✅ Opción 'English' seleccionada.");
                } else {
                    console.warn("⚠️ No se encontró la opción 'English' después de buscar.");
                }
            })();
            '''
            pyperclip.copy(script_select_language)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Seleccion de lenguaje clickeada correctamente.")
            
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Click "Create Project"
            #-------------------------------------------------------------------------#
            print("🖱️ Click al botón 'Create Project' ...")
            
            script_create_project = '''
            (function () {
                const botones = Array.from(document.querySelectorAll('button'));
                const botonCrear = botones.find(btn =>
                    btn.textContent.trim().toLowerCase() === 'create project'
                );

                if (botonCrear) {
                    botonCrear.click();
                    console.log("✅ Botón 'Create project' clickeado correctamente.");
                } else {
                    console.warn("❌ No se encontró el botón 'Create project'.");
                }
            })();
            '''
            pyperclip.copy(script_create_project)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Create Projects clickeada correctamente.")
            
            time.sleep(5)
            
            #-------------------------------------------------------------------------#
            # Esperar a que se genere el video y hacer clic en el nuevo video
            #-------------------------------------------------------------------------#
            
            esperar_y_ejecutar_click_nuevo_video(driver)
            time.sleep(10)
            
            esperar_desaparicion_loader(driver)
            time.sleep(2)
            
            #---------------------------------------------------------------------------#
            #Agregar musica al video
            #---------------------------------------------------------------------------#
            print("🎵 Esperando a que cargue el área de música...")
            
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
            '''
            
            pyperclip.copy(script_agregar_musica)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(0.5)
            pyautogui.press('enter')
            print("✅ Click al boton de musica correctamente.")
            
            time.sleep(6)
            
            #---------------------------------------------------------------------------#
            # Escribir la musica
            #---------------------------------------------------------------------------#
            
            escribir_texto_en_musica(driver, self.id_contenido)    
            time.sleep(8)
            
            #---------------------------------------------------------------------------#
            # Desactivar consola con f12
            #---------------------------------------------------------------------------#
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            time.sleep(2)
            print("✅ DevTools debería estar abierta ahora.")
            time.sleep(3)
                        
            #-----------------------------------------------------------------------------#
            # Activar consola con f12
            #-----------------------------------------------------------------------------#
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            time.sleep(2)
            print("✅ DevTools debería estar abierta ahora.")
            time.sleep(3)
                        
            #-------------------------------------------------------------------------#
            #Click al boton de Generate
            #-------------------------------------------------------------------------#
            print("🎵 Click al boton Generate...")
            
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
            print("✅ Click al boton de Generate correctamente.")
            
            time.sleep(30)
            
            
            #-------------------------------------------------------------------------#
            #Click al boton de insertar en musica
            #-------------------------------------------------------------------------#
            print("🎵 Esperando a que cargue el área de música...")
            
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
            
            time.sleep(20)
            
             
            #-------------------------------------------------------------------------#
            #Click en el slider para configurar volumen de la musica
            #-------------------------------------------------------------------------#
            print("🔊 Ajustando el volumen de la música...")
            
            mover_slider_a_mitad(driver)
            time.sleep(10)
            
            #. Desactivar consola con f12
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            time.sleep(2)
            print("✅ DevTools debería estar cerrada ahora.")
            time.sleep(3)
                        
            #. Activar consola con f12
            print("🛠️ Enviando F12 desde teclado con PyAutoGUI...")
            pyautogui.press("f12")
            time.sleep(2)
            print("✅ DevTools debería estar abierta ahora.")
            time.sleep(3)
            
            
            #-------------------------------------------------------------------------#
            # Click en boton cerrar editor musica
            #-------------------------------------------------------------------------#
            print("❌ Buscando el botón de cerrar editor de música en pantalla con PyAutoGUI...")
            
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
            # Click en el primer botón de exportar
            #-------------------------------------------------------------------------#
            print("📤 Esperando a que cargue el área de exportación...")
            
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
            
            time.sleep(20)
            
            #--------------------------------------------------------------------------#
            #Click al segundo boton de exportar video
            #--------------------------------------------------------------------------#
            print("📤 Esperando a que cargue el segundo botón de exportación...")
            
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
            
            time.sleep(20)
            
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