from utils.db_connection import session, ContenidoSemanal, Videos
import sys
from controller.bot_tutorial import BotTutorial
from controller.bot_testimonio import BotTestimonio
from controller.bot_testimonio2 import BotTestimonio2


def _read_arg(idx: int, default: str = "") -> str:
    """Lee sys.argv[idx] de forma segura."""
    return sys.argv[idx] if len(sys.argv) > idx else default


def ejecutar_bot_por_tipo(contenido):
    # 🔹 Si viene desde la base de datos
    try:
        tipo_num = int(contenido.tipo.strip()) if hasattr(contenido, "tipo") and contenido.tipo is not None else None
    except Exception:
        tipo_num = None

    # 🔹 Si viene desde argumentos del subprocess (posición 7 en tu main actual)
    if tipo_num is None:
        arg_tipo = _read_arg(7, "")
        try:
            tipo_num = int(arg_tipo) if arg_tipo != "" else None
        except Exception:
            tipo_num = None

    # Mapear número a texto (1=tutorial, 2=testimonio, otro=testimonio2)
    if tipo_num == 1:
        tipo_texto = "tutorial"
    elif tipo_num == 2:
        tipo_texto = "testimonio"
    else:
        tipo_texto = "testimonio2"

    # Lee argumentos (manteniendo tu orden actual)
    tema = _read_arg(1)
    plataforma = _read_arg(2)
    descripcion = _read_arg(3)
    campaign_key = _read_arg(4)
    language = _read_arg(5)
    canal = _read_arg(6)
    tipo = _read_arg(7)           # puede seguir existiendo si lo necesitas como string original
    sonido = _read_arg(8)
    main_cta_final = _read_arg(9)
    servicio = _read_arg(10)
    id_contenido = _read_arg(11)
    hashtags = _read_arg(12)

    contenido_id = getattr(contenido, "id", id_contenido or "N/A")
    print(f"\n🎬 Procesando contenido ID {contenido_id} | Tipo detectado: {tipo_texto.title()}")

    # 📌 Ejecutar bot según tipo
    if tipo_texto == "tutorial":
        bot = BotTutorial(
            prompt=tema,
            platform_video=plataforma,
            tema=descripcion,
            campaign_key=campaign_key,
            id_contenido=id_contenido,
            lenguaje=language,
            sonido=sonido,
            tipo=tipo,
            hashtags=hashtags,
            servicio=servicio,
            main_cta=main_cta_final
        )

    elif tipo_texto == "testimonio":
        bot = BotTestimonio(
            prompt=tema,
            platform_video=plataforma,
            tema=descripcion,
            campaign_key=campaign_key,
            id_contenido=id_contenido,
            lenguaje=language,
            sonido=sonido,
            tipo=tipo,
            hashtags=hashtags,
            servicio=servicio,
            main_cta=main_cta_final
        )

    else:  
        bot = BotTestimonio2(
            prompt=tema,
            platform_video=plataforma,
            tema=descripcion,
            campaign_key=campaign_key,
            id_contenido=id_contenido,
            lenguaje=language,
            sonido=sonido,
            tipo=tipo,
            hashtags=hashtags,
            servicio=servicio,
            main_cta=main_cta_final
        )

    # 👇 Ejecutar y capturar el resultado que devuelve run()
    salida = bot.run()
    return salida  # 👈 devuelve el dict o None


def procesar_programacion_semanal():
    contenidos = session.query(ContenidoSemanal).all()
    if not contenidos:
        print("✅ No hay contenidos semanales para procesar.")
        return

    print(f"📦 Contenidos semanales encontrados: {len(contenidos)}")

    resultados = []  # Lista para almacenar datos de todos los bots

    for contenido in contenidos:
        try:
            resultado = ejecutar_bot_por_tipo(contenido)
            if resultado:
                resultados.append(resultado)
        except Exception as e:
            cid = getattr(contenido, "id", "N/A")
            print(f"❌ Error procesando contenido ID {cid}: {e}")

    return resultados  # Aquí devolvemos todos los datos listos para Excel


if __name__ == "__main__":
    procesar_programacion_semanal()
