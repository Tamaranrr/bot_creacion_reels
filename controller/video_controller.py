from client.openai_client import GPT
from utils.db_connection import obtener_datos_video
from bot_creacion_reels.controller.bot import PlaywrightBot

class VideoController:
    def __init__(self, tema, language):
        self.gpt = GPT(tema, language)

    def obtener_prompt(self):
        print("🔹 Generando prompt para video...")
        prompt = self.gpt.generate_video_prompt()
        print("\n🔹 Prompt generado:")
        print(prompt)
        return prompt

    def iniciar_creacion_video(self):
        prompt = self.obtener_prompt()

        # Aquí puedes agregar la lógica para crear el video, por ejemplo:
        # - Guardar el prompt en un archivo para ser usado por otro software
        # - Pasar el prompt a una IA de generación de videos
        # - Usar una API de edición automática de video

        print("🚀 Iniciando creación del video con el prompt generado...")

        # Simulación de generación de video
        with open("output/video_prompt.txt", "w", encoding="utf-8") as f:
            f.write(prompt)
        
        print("✅ Prompt guardado en 'output/video_prompt.txt'. Ahora el bot puede procesarlo para generar el video.")

def continuar_proceso():
    # Obtener los datos desde la base de datos
    videos = obtener_datos_video()

    if not videos:
        print("❌ No se encontraron videos en la base de datos.")
        return

    for video in videos:
        tema = video.description
        platform_video = video.platform_video

        gpt = GPT(tema)
        print("📝 Generando contenido con OpenAI...")
        resultado = gpt.generate_video_prompt()

        with open("output/video_prompt.txt", "w", encoding="utf-8") as f:
            f.write(resultado)

        print("\n🔹 Contenido generado:")
        print(resultado)

        print("\n🚀 Iniciando el bot de Playwright...")
        bot = PlaywrightBot(resultado, platform_video, tema)
        bot.run()

    print("✅ Proceso completado con éxito.")

    