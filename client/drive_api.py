import os
import gc
import pickle
import time
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv

# Cargar variables de entorno si existen
load_dotenv()

# Alcances necesarios
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# 📂 Carpeta raíz de Google Drive (donde estarán las subcarpetas por campaña)
GOOGLE_DRIVE_FOLDER_ID = "1ma3i5PqrIF31UZg0DBxZQxWgAjk7t-VJ"

# Archivos de credenciales
OAUTH_CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), '..', 'credentials.json')
TOKEN_PICKLE = "token_drive.pickle"

def get_drive_service():
    creds = None
    if os.path.exists(TOKEN_PICKLE):
        with open(TOKEN_PICKLE, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PICKLE, "wb") as token:
            pickle.dump(creds, token)

    return build("drive", "v3", credentials=creds)

def eliminar_archivo_drive_si_existe(nombre_archivo, carpeta_id):
    service = get_drive_service()
    query = f"name = '{nombre_archivo}' and '{carpeta_id}' in parents"
    results = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
    archivos = results.get("files", [])
    for archivo in archivos:
        service.files().delete(fileId=archivo["id"]).execute()
        print(f"🗑 Archivo eliminado en Drive: {archivo['name']} ({archivo['id']})")

def crear_carpeta_en_drive(nombre_carpeta, parent_folder_id=None):
    service = get_drive_service()
    metadata = {
        "name": nombre_carpeta,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_folder_id:
        metadata["parents"] = [parent_folder_id]

    carpeta = service.files().create(body=metadata, fields="id").execute()
    return carpeta.get("id")

def buscar_carpeta(nombre, parent_id=None):
    service = get_drive_service()
    query = f"name = '{nombre}' and mimeType = 'application/vnd.google-apps.folder'"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
    archivos = results.get("files", [])
    return archivos[0]["id"] if archivos else None

def upload_and_delete_local(filepath: str, drive_filename: str, slug: str = "general", mimetype: str = None):
    print(f"⬆️ Intentando subir: {filepath}")

    if not os.path.exists(filepath):
        print(f"❌ El archivo '{filepath}' no existe.")
        return None

    try:
        service = get_drive_service()

        # 📁 Buscar o crear carpeta por campaña
        carpeta_campana_id = buscar_carpeta(slug, GOOGLE_DRIVE_FOLDER_ID)
        if not carpeta_campana_id:
            carpeta_campana_id = crear_carpeta_en_drive(slug, GOOGLE_DRIVE_FOLDER_ID)

        eliminar_archivo_drive_si_existe(drive_filename, carpeta_campana_id)

        file_metadata = {
            "name": drive_filename,
            "parents": [carpeta_campana_id]
        }
        media = MediaFileUpload(filepath, mimetype=mimetype)
        file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()

        print(f"✅ Archivo subido correctamente. ID: {file.get('id')}")

        # Hacer público
        service.permissions().create(
            fileId=file.get("id"),
            body={"role": "reader", "type": "anyone"}
        ).execute()

        public_url = f"https://drive.google.com/file/d/{file.get('id')}/view"
        print(f"🌍 Enlace público: {public_url}")

        # 🧹 Eliminar archivo local
        try:
            gc.collect()
            time.sleep(0.5)
            os.remove(filepath)
            print(f"🧹 Archivo local eliminado: {filepath}")
        except PermissionError:
            print(f"⚠️ No se pudo eliminar el archivo local: {filepath}")

        return public_url

    except Exception as e:
        print(f"❌ ERROR SUBIENDO O ELIMINANDO ARCHIVO: {e}")
        return None
