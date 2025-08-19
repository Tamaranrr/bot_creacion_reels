import json
import subprocess
from client.drive_api import upload_and_delete_local
from pathlib import Path
from utils.db_connection import eliminar_primer_registro
import os


CARPETA_DESCARGAS = Path.home() / "Downloads"
EXTENSIONES_PERMITIDAS = {".mp4"}

def obtener_archivo_por_nombre(nombre_base: str):
    for f in Path(CARPETA_DESCARGAS).iterdir():
        if f.is_file() and f.suffix.lower() == ".mp4" and nombre_base in f.name:
            return f
    return None

def obtener_archivos_recientes(directorio, cantidad=1):
    archivos = [
        f for f in Path(directorio).iterdir() 
        if f.is_file() and f.suffix.lower() in EXTENSIONES_PERMITIDAS
    ]
    archivos_ordenados = sorted(archivos, key=lambda f: f.stat().st_mtime, reverse=True)
    return archivos_ordenados[:cantidad]

def subir_video_drive():
    archivos = obtener_archivos_recientes(CARPETA_DESCARGAS, cantidad=1)
    resultados = []

    if not archivos:
        print("❌ No se encontraron archivos en la carpeta Descargas.")
        return resultados

    for archivo in archivos:
        try:
            print(f"📤 Subiendo archivo: {archivo.name}")

            # ======= PARCHE MÍNIMO (sin cambiar la lógica) =======
            # Escapar comillas simples en el NOMBRE que se envía a Drive
            # (NO cambiamos la ruta local; solo el 'name' del metadata).
            safe_name = archivo.name.replace("'", r"\'")
            # =====================================================

            # Antes: file_url = upload_and_delete_local(str(archivo), archivo.name)
            file_url = upload_and_delete_local(str(archivo), safe_name)

            resultado = {
                "nombre": archivo.name,
                "url": file_url,
                "campaign": os.getenv("CAMPAIGN_KEY") or "desconocida"
            }
            resultados.append(resultado)

            print(f"✅ Archivo '{archivo.name}' subido con éxito")
            print(json.dumps(resultados, indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"❌ Error al subir '{archivo.name}': {e}")

    return resultados
