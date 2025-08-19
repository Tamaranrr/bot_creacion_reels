from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from utils.db_connection import Session, Videos


# 1) Define el modelo Pydantic para validación y documentación automática
class DriverInfo(BaseModel):
    nombre: str
    id: str
    url: str

app = FastAPI()


@app.get("/buscar_video")
def buscar_video(text: str):
    """
    Busca un video por texto exacto en la columna description y retorna el registro.
    """
    session = Session()
    try:
        print(f"🔍 Buscando en base de datos: '{text}'")
        video = session.query(Videos).filter_by(description=text).first()

        if video:
            resultado = {
                "id": video.id,
                "platform_video": video.platform_video,
                "upload_drive": video.upload_drive,
                "url_drive": video.url_drive,
                "description": video.description
            }
            print("✅ Video encontrado:")
            print(resultado)
            return resultado
        else:
            print("❌ No se encontró ningún video con ese texto.")
            return {"error": "No encontrado"}
    except Exception as e:
        print(f"❌ Error en búsqueda: {e}")
        return {"error": str(e)}
    finally:
        session.close()

