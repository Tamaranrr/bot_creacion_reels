import json
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import text
from sqlalchemy.orm import synonym
from sqlalchemy.orm import aliased


# Configuración de la base de datos
# DATABASE_URL = "postgresql://admin:BzsDWRk8DDBjHprCQT0i@10.0.0.90:5432/socialMedia"
DATABASE_URL = "postgresql://postgres:azteca@localhost:5432/socialMedia"

# Crear la conexión a la base de datos|
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Declarar la clase base para los modelos
Base = declarative_base()

# Modelo de la tabla 'videos'
class Videos(Base):
    __tablename__ = 'videos'
    id = Column(Integer, primary_key=True, autoincrement=True)
    platform_video = Column(String)
    upload_drive = Column(Boolean, nullable=False, default=False)
    url_drive = Column(String)
    description = Column(String)
    campaign = Column(String)
    id_contenido = Column(Integer)
    
    
# Obtener solo los videos pendientes (no subidos aún)
def obtener_datos_video():
    try:
        VideosAlias = aliased(Videos)
        contenidos = session.query(ContenidoSemanal).filter(
            ~session.query(VideosAlias).filter(VideosAlias.id_contenido == ContenidoSemanal.id).exists()
        ).all()
        
        print(f"🔍 Contenidos pendientes detectados: {len(contenidos)}")
        return contenidos
    except Exception as e:
        print(f"❌ Error al obtener datos de contenido_semanal: {e}")
        return []
    
    
# Marcar un video como subido y guardar la URL del drive
def marcar_como_subido(id_video, url):
    try:
        video = session.query(Videos).filter_by(id=id_video).first()
        if video:
            video.upload_drive = True
            video.url_drive = url
            session.commit()
            print(f"✅ Video con ID {id_video} marcado como subido con URL.")
        else:
            print(f"❌ No se encontró video con ID {id_video}.")
    except Exception as e:
        session.rollback()
        print(f"❌ Error al actualizar video con ID {id_video}: {e}")
       
    

def guardar_video_generado(description, platform, url, campaign, id_contenido):
    """Guarda un nuevo registro del video generado en la base de datos."""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        query = text("""
            INSERT INTO videos (description, platform_video, url_drive, upload_drive, campaign, id_contenido)
            VALUES (:description, :platform, :url, true, :campaign, :id_contenido)
        """)
        session.execute(query, {
            "description": description,
            "platform": platform,
            "url": url,
            "campaign": campaign,
            "id_contenido": id_contenido
        })
        session.commit()
    except Exception as e:
        print(f"❌ Error al guardar video generado: {e}")
    finally:
        session.close()


def eliminar_primer_registro():
    """Elimina el primer registro de la base de datos (registro que generó el video)."""
    Session = sessionmaker(bind=engine)
    session = Session()

    # Obtener el primer registro en la tabla
    primer_video = session.query(Videos).first()
    
    if primer_video:
        try:
            session.delete(primer_video)  # Eliminar el primer registro
            session.commit()  # Confirmar cambios
            print("✅ Primer registro eliminado de la base de datos.")
        except Exception as e:
            session.rollback()  # Si hay un error, hacer rollback
            print(f"❌ Error al eliminar el primer registro: {e}")
    else:
        print("❌ No se encontró ningún registro para eliminar.")
    
    session.close()
    
def obtener_datos_campania(campaign_key):
    """
    Busca la configuración de tono, voz, tipo de negocio, ciudad y audiencia para una campaña específica.
    """
    try:
        query = text("""
            SELECT business_type, city, suggested_tone, target_audience, voice
            FROM campaign_profiles
            WHERE LOWER(campaign) = :campaign
            LIMIT 1
        """)
        result = session.execute(query, {"campaign": campaign_key.lower()}).fetchone()
        return result if result else None
    except Exception as e:
        print(f"❌ Error al obtener datos de campaña: {e}")
        return None

def historial_prompts_hashes(campaign_key):
    try:
        with open("historial_prompts.json", "r") as f:
            data = json.load(f)
        return data.get(campaign_key, [])
    except FileNotFoundError:
        return []

def guardar_hash_prompt(campaign_key, prompt_hash):
    path = "historial_prompts.json"
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}

    if campaign_key not in data:
        data[campaign_key] = []

    if prompt_hash not in data[campaign_key]:
        data[campaign_key].append(prompt_hash)

    with open(path, "w") as f:
        json.dump(data, f, indent=2)


class ContenidoSemanal(Base):
    __tablename__ = 'contenido_semanal'
    id = Column(Integer, primary_key=True)
    descripcion = Column(String)
    sonido = Column(String)


def obtener_descripcion_contenido(id_contenido):
    try:
        contenido = session.query(ContenidoSemanal).filter_by(id=id_contenido).first()
        return contenido.descripcion if contenido else None
    except Exception as e:
        print(f"❌ Error al obtener descripción de contenido_semanal: {e}")
        return None
    
def obtener_sonido_contenido(id_contenido):
    try:
        contenido = session.query(ContenidoSemanal).filter_by(id=id_contenido).first()
        return contenido.sonido if contenido else None
    except Exception as e:
        print(f"❌ Error al obtener sonido de contenido_semanal: {e}")
        return None