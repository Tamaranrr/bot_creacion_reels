import io
import sys
import uvicorn
from client.openai_client import GPT
from controller.bot_tutorial import BotTutorial
from controller.bot_testimonio import BotTestimonio
from utils.db_connection import guardar_video_generado
from utils.helpers import crear_directorio_si_no_existe
from utils.db_connection import session, ContenidoSemanal
from utils.db_connection import Videos
from controller.bot import ejecutar_bot_por_tipo


sys.path.append("..") 

# sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def main():
    print("🔹 Iniciando creación de video automático...\n")

    # Validación de argumentos
    if len(sys.argv) < 13:
        print("❌ Faltan argumentos. Uso esperado:")
        print("python main.py <tema> <plataforma> <descripcion>")
        print(f"📦 Argumentos recibidos: {len(sys.argv) - 1}")
        for i, arg in enumerate(sys.argv[1:], 1):
            print(f"  Arg {i}: {arg}")
        return

    tema = sys.argv[1]
    plataforma = sys.argv[2]
    descripcion = sys.argv[3]
    campaign_key = sys.argv[4]
    language = sys.argv[5]
    canal = sys.argv[6]
    tipo = sys.argv[7]
    sonido = sys.argv[8]
    main_cta_final = sys.argv[9]
    servicio = sys.argv[10]
    id_contenido = sys.argv[11]
    hashtags = sys.argv[12]

    gpt = GPT(
        tema=tema,
        language=language,
        canal=canal,
        servicio=servicio,
        campaign_key = campaign_key,
        tipo=tipo,
        descripcion=descripcion,
        sonido=sonido,
        main_cta_final = main_cta_final,
        hashtags = hashtags
    )
    prompt = gpt.generate_video_prompt()

    # Debug
    print(f"📥 Prompt generado por GPT:")
    print(prompt)
    print(f"\n🎯 Plataforma: {plataforma}")
    print(f"📝 Tema original: {tema}")
    print(f"📝 Categoria original: {campaign_key}")
    print(f"📝 Idioma original: {language}")
    print(f"📝 canal: {canal}")
    print(f"📝 Tipo: {tipo}")
    print(f"📝 sugerencias: {sonido}")
    print(f"📝 Descripción: {descripcion}")

    crear_directorio_si_no_existe("output")
    print(f"🔍 Buscando video con id_contenido = {id_contenido} (tipo: {type(id_contenido)})")

    

    # Convertir ID recibido como string a entero
    try:
        id_contenido_int = int(id_contenido)
    except:
        print(f"❌ ID inválido: {id_contenido}")
        return

    # Verificar si ya está en la tabla videos
    video_existente = session.query(Videos).filter_by(id_contenido=id_contenido_int).first()
    if video_existente:
        print(f"⏭️ El contenido ID {id_contenido_int} ya fue generado previamente. Se omite desde el bot.")
        return

    # Buscar el contenido original por ID
    contenido = session.query(ContenidoSemanal).filter_by(id=id_contenido_int).first()
    if contenido:
        ejecutar_bot_por_tipo(contenido)
    else:
        print(f"❌ No se encontró contenido_semanal con id {id_contenido_int}")

    print(f"📝 Se cierra bot 2")

if __name__ == "__main__":
    main()
    