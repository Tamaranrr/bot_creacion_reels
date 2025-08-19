import undetected_chromedriver as uc
from pathlib import Path
import os
import time
import json
import psutil
import pygetwindow as gw

# Configuración del perfil de Chrome
CHROME_EXECUTABLE_PATH = "C:/Program Files/Google/Chrome/Application/chrome.exe"
CHROME_USER_DATA_DIR = "C:/Users/programador2/AppData/Local/Google/Chrome/User Data"
CHROME_PROFILE_NAME = "Profile 1"
DOWNLOADS_PATH = Path.home() / "Downloads"

class SeleniumClient:
    def __init__(self, headless=False):
        self.headless = headless
        self.driver = None

    def cerrar_chrome(self):
        """Cierra TODOS los procesos relacionados con Chrome y Chromedriver."""
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() in ("chrome.exe", "chromedriver.exe"):
                    proc.kill()
                    print(f"🛑 Proceso cerrado: {proc.info['name']} (PID {proc.pid})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    def _normalizar_preferencias_perfil(self):
        """
        Evita el diálogo de 'restaurar páginas' marcando la salida previa como limpia
        y forzando 'nueva pestaña' al inicio.
        """
        try:
            pref_path = Path(CHROME_USER_DATA_DIR) / CHROME_PROFILE_NAME / "Preferences"
            if not pref_path.exists():
                return

            with open(pref_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            data.setdefault("profile", {})
            data["profile"]["exit_type"] = "Normal"
            data["profile"]["exited_cleanly"] = True

            data.setdefault("session", {})
            # 0 = abrir página de nueva pestaña; 2 = continuar donde quedó (no queremos esto)
            data["session"]["restore_on_startup"] = 0

            data.setdefault("browser", {})
            data["browser"]["has_seen_welcome_page"] = True

            with open(pref_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print("🧹 Preferencias del perfil ajustadas (exit_type=Normal, exited_cleanly=True).")

        except Exception as e:
            print(f"⚠️ No se pudieron ajustar las preferencias del perfil: {e}")

    def start_browser(self):
        try:
            # Paso 0: cerrar cualquier Chrome
            self.cerrar_chrome()
            time.sleep(1)

            # Paso 0.5: normalizar preferencias del perfil (evita popup de restaurar)
            self._normalizar_preferencias_perfil()

            print("🚀 Iniciando navegador manualmente con flags anti-popup...")
            # Lanzar Chrome con puerto de depuración + flags que quitan burbujas de restore
            os.system(
                f'start "" "{CHROME_EXECUTABLE_PATH}" '
                f'--remote-debugging-port=9222 '
                f'--user-data-dir="{CHROME_USER_DATA_DIR}" '
                f'--profile-directory="{CHROME_PROFILE_NAME}" '
                f'--no-first-run --no-default-browser-check '
                f'--disable-session-crashed-bubble '
                f'--disable-features=InProductHelpSuppressWelcome,ChromeWhatsNewUI '
                f'--start-maximized'
            )

            # Esperar que haya una ventana
            print("🕒 Esperando a que Chrome termine de iniciar...")
            for _ in range(20):
                ventanas = gw.getWindowsWithTitle("Chrome")
                if ventanas:
                    print("✅ Ventana de Chrome detectada.")
                    break
                time.sleep(0.5)
            else:
                print("❌ No se detectó ventana de Chrome. Abortando conexión.")
                return None

            # Pequeño colchón para que el puerto quede listo
            time.sleep(2)

            # Conectar Selenium al navegador ya abierto
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from selenium import webdriver

            options = Options()
            options.debugger_address = "127.0.0.1:9222"

            print("🔌 Conectando Selenium al navegador ya abierto...")
            self.driver = webdriver.Chrome(options=options)
            print("✅ Conexión exitosa.")
            return self.driver

        except Exception as e:
            import traceback
            print(f"❌ Error al conectar con navegador: {e}")
            traceback.print_exc()
            return None