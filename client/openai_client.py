from openai import OpenAI
from dotenv import load_dotenv
import os

from utils.db_connection import guardar_hash_prompt, historial_prompts_hashes, obtener_datos_campania

# Cargar variables de entorno
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("⚠️ ERROR: OPENAI_API_KEY no está definida en .env")

config_por_campania = {
    "quick_cleaning": {
        "rol_protagonista": "personal de limpieza profesional",
        "apariencia": "personal de limpieza"
    },
    "osceola_fence_corporation": {
        "rol_protagonista": "trabajador o constructor",
        "apariencia": "Viste gorra con logo, polo de la empresa y pantalones cargo con múltiples bolsillos; completa su equipo con guantes resistentes, botas antideslizantes y un cinturón que sostiene alicates, metro y tensores para instalar postes y tensar alambres con precisión."
    },
    "elite_chicago_spa": {
        "rol_protagonista": "esteticista, mujer joven",
        "apariencia": "manos y uñas muy bien arregladas"
    },
    "lopez_y_lopez_abogados": {
        "rol_protagonista": "abogado o abogada profesional",
        "apariencia": "traje formal oscuro, escritorio con documentos legales y laptop"
    },
     "spa312": {
        "rol_protagonista": "terapeuta de spa",
        "apariencia": "personal en un ambiente de relajación",
    },
     "elite_frenchies": {
        "rol_protagonista": "criador profesional de bulldogs franceses",
        "apariencia": "persona en ambiente hogareño con cachorros Frenchie alrededor",
    },
}

def obtener_configuracion_por_campania(campaign_key):
    if "botanica" in campaign_key.lower() or "botánica" in campaign_key.lower():
        return {
            "rol_protagonista": "chamán o brujo",
            "apariencia": "brujo con vestimenta de chamán",
            "sonido_especial": "efectos sobrenaturales, de terror, intriga o sonidos de ritual, no usar musica animada"
        }
    
    for clave, valores in config_por_campania.items():
        if clave in campaign_key:
            return valores

    return {
        "rol_protagonista": "persona principal",
        "apariencia": "vestimenta y elementos acordes al servicio"
    }


class GPT:
    def __init__(self, tema, language, servicio, campaign_key, canal, tipo, descripcion, sonido, main_cta_final, hashtags):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.tema = tema
        self.lang = language
        self.servicio = servicio
        self.campaign_key = campaign_key
        self.campaign_name = campaign_key.replace("_", " ").title()
        self.canal = canal
        self.tipo = tipo.strip().lower() 
        self.descripcion = descripcion
        self.sonido = sonido
        self.hashtags = hashtags
        self.main_cta_final = main_cta_final
        self.SYSTEM_MESSAGE = f"Eres un sistema que genera ideas únicas de contenido de video de alta calidad. Siempre responde **exclusivamente** en {self.lang}, sin usar ningún otro idioma bajo ninguna circunstancia."
        self.ASSISTANT_MESSAGE = "Eres un asistente que ayuda a crear ideas unicas, atractivas para videos comerciales."
        self.prompts_activados = False
        
    def create_message(self, role, content):
        if not self.prompts_activados:
            print("⚠️ Prompts desactivados por configuración.")
            return ""
    
        return {"role": role, "content": content}

    def generate_response(self, model, messages, temperature=1):
        if not self.prompts_activados:
            print("⚠️ Prompts desactivados por configuración.")
            return ""
        
        response = self.client.chat.completions.create(
            model=model, messages=messages, temperature=temperature
        )
        return response.choices[0].message.content.strip()

    def generar_prompt_base(self):
        if not self.prompts_activados:
            print("⚠️ Prompts desactivados por configuración.")
            return ""
        
        
        if "botanica" in self.campaign_key.lower() or "botánica" in self.campaign_key.lower():
            self.SYSTEM_MESSAGE = f"Eres un sistema espiritual que genera contenido místico e informativo. Siempre responde exclusivamente en el idioma de {self.lang}."
            
        perfil_vis = obtener_configuracion_por_campania(self.campaign_key)
        rol = perfil_vis["rol_protagonista"]
        apariencia = perfil_vis["apariencia"]
        sonido_especial = perfil_vis.get("sonido_especial")
        extra_visual = "Asegúrate de que las escenas visuales sean completamente distintas, mostrando nuevos lugares, encuadres y acciones. No reutilices secuencias comunes o de stock genérico."

        if self.tipo == "asmr":
            return f"""
        🧠 **Brief para video ASMR ultra detallado – duración: 30 segundos**  
        Idioma del video: **{self.lang}**  
        Tema principal: **{self.descripcion}**

        🎯 **Objetivo:**  
        Crear un video ASMR donde **cada acción visual genere de inmediato un sonido específico y natural que coincida perfectamente**.  
        No se permiten sonidos flotantes sin fuente clara en pantalla. El espectador debe identificar con exactitud qué produce cada sonido, cómo y cuándo.

        🧩 **Estructura por bloque (obligatoria):**

        1. 🎥 **VISUAL**  
        – Describe claramente una acción o interacción física (ej: “una mano roza hojas secas lentamente”).  
        – Indica objeto, textura, movimiento, ritmo y entorno.  
        – Toda imagen debe generar un **sonido identificable**, y este debe estar descrito justo después.

        2. 🔊 **SONIDO ASOCIADO**  
        – Describe el **sonido que surge exactamente de la acción anterior** (ej: “crujido seco de hojas, canal derecho, 50 Hz, suave, 10 cm del micrófono”).  
        – Detalla canal (izq/der), distancia al micrófono, volumen, tipo (susurro, golpe, roce), duración y efectos (eco, reverb).  
        – NO inventes sonidos sin una acción física visual clara.

        3. 🧠 **COHERENCIA AUDIOVISUAL**  
        – Indica claramente **el momento exacto** de inicio del sonido respecto al movimiento.  
        – Si el sonido persiste, menciona si la imagen se mantiene estática, en loop, o cambia.

        🚫 **Prohibido:**  
        – Imágenes sin sonido.  
        – Sonidos sin acción visible que los justifique.  
        – Música de fondo.  
        – Repeticiones de escenas.  
        – Transiciones o cortes rápidos.

        📎 **Notas adicionales para la IA**  
        – Este video será generado con inteligencia artificial que necesita correspondencia 1:1 entre lo que se ve y lo que se oye.  
        – No usar metáforas ni planos abstractos.  
        – El espectador debe poder “adivinar” qué está sonando solo con mirar la imagen.

        🧾 **Instrucción técnica**  
        ⏱ **Duración:** 50 segundos  
        Genera al menos 5 bloques consecutivos que sigan esta estructura con sonidos variados.  
        Todo el contenido debe ajustarse a una duración total de 30 segundos.

        {extra_visual}
        """

        
        # Tipo especial Documental o Storytime
        if self.tipo in ["documental", "storytime"]:
            return f"""
            🎯 **Objetivo:** Crear un guion hiperrealista exclusivamente en el idioma de **{self.lang}** para un video tipo **{self.tipo}** basado en la empresa **{self.campaign_name}** y el tema: **{self.descripcion}**.
            🚫 **Prohibido usar cualquier palabra, instrucción o frase en otro idioma distinto a {self.lang}.**

            📌 **Pautas específicas**:
            – Describe el lugar, acciones y procedimientos con **detalle cinematográfico**.  
            – El relato debe incluir **emociones reales** de la protagonista: antes, durante y después.  
            – **No incluir textos, logotipos ni gráficos en pantalla.**  
            – El ambiente debe sentirse auténtico, no exagerado ni ficticio.  
            – **Usa exactamente el nombre:** **{self.campaign_name}** (sin modificar, traducir o abreviar).
            - La musica de fondo debe tener relación con {self.sonido}

            ⏱ **Duración del video:** 60 segundos  
            🔄 **Evita repeticiones:** No repitas secuencias ya utilizadas.  
            {extra_visual}
            """

        if self.tipo == "tips":
            return f"""
            🎯 **Objetivo:** Generar un guion detallado exclusivamente en el idioma de **{self.lang}** para un video de consejos prácticos sobre: **{self.descripcion}**.
            🚫 **Prohibido usar cualquier palabra, instrucción o frase en otro idioma distinto a {self.lang}.**

            📌 **Instrucciones obligatorias**:
            – La protagonista es una trabajadora de la empresa **{self.campaign_name}** (usa siempre este nombre **sin modificar**).  
            – Lleva **delantal verde** y **guantes amarillos**.  
            – Presenta un **procedimiento paso a paso**, usando herramientas comunes y con **resultado visual claro**.  
            – El estilo visual debe tener:
            • Toma inicial del problema  
            • Transformación fluida  
            • Primeros planos, efectos suaves  
            – **No mostrar marcas, textos ni logotipos.**
            - La musica de fondo debe tener relación con {self.sonido}

            🔁 **Elemento viral:** Truco visual simple, útil y sorprendente.  
            ⏱ **Duración:** 50 segundos  
            📹 **Coherencia máxima:** Voz, imagen y sonido deben sincronizarse sin distracciones externas.  
            🔄 **Evita repeticiones:** No uses escenas ya empleadas.  
            {extra_visual}
            """

        
        if self.tipo == "demo":
            return f"""
            🎯 **Objetivo:** Generar un guion extremadamente detallado exclusivamente en el idioma de **{self.lang}** para un video tipo DEMO titulado: **{self.descripcion}**.
            🚫 **Prohibido usar cualquier palabra, instrucción o frase en otro idioma distinto a {self.lang}.**

            📌 **Especificaciones obligatorias**:
            – Muestra a una persona con vestimenta adecuada realizando un proceso paso a paso.  
            – Enfócate en el **cambio visual**: antes vs después.  
            – **Técnica:** mostrar aplicación del producto, acción (frotar, limpiar, calentar), y resultado visible.  
            – Estilo visual:
            • Pantalla dividida: izquierda "antes", derecha "después"  
            • Música en tendencia sincronizada con los momentos clave o musica especificada como {self.sonido} 
            • Texto animado sutil con {self.hashtags} (sin logos)

            ⏱ **Duración:** 50 segundos  
            🎯 **Prohibido:** No incluir logotipos ni marcas.  
            🔄 **Evita repeticiones:** No reciclar escenas previas.  
            {extra_visual}
            """

        
        return f"""
            🎯 **Objetivo:** Generar un guion **muy detallado** exclusivamente en el idioma de **{self.lang}** para un video tipo **{self.tipo}** sobre: **{self.descripcion}**.
            🚫 **Prohibido usar cualquier palabra, instrucción o frase en otro idioma distinto a {self.lang}.**

            📌 **Pautas esenciales**:
            – Empresa: **{self.campaign_name}** (usa el nombre tal como está, sin traducir ni alterar).  
            – Duración total: 50 segundos  
            – Protagonista: **{rol}**, apariencia: **{apariencia}**

            📋 **Formato de salida (tabla)**:
            | Tiempo | VISUAL | AUDIO | VOZ EN OFF | TEXTO EN PANTALLA |
            |--------|--------|--------|--------------|--------------------|
            • **VISUAL:** planos, lentes, movimientos, iluminación, objetos  
            • **AUDIO:** música, sonidos con rango de frecuencias y volumen estimado (usa {sonido_especial or self.sonido})
            • **VOZ EN OFF:** diálogo exacto del narrador incluyendo el nombre de la empresa cuando sea necesario  
            • **TEXTO:** tipografías, tamaños, colores y animaciones (sin logos)

            📌 Estilo: hiperrealista, sincronizado entre voz, imagen y audio  
            🚫 Prohibido: marcas, textos decorativos o elementos que alteren la neutralidad visual  
            🔄 Evita escenas ya utilizadas.  
            {extra_visual}
             
            ---

            ### ✨ Estructura sugerida (tabla con bloques por tiempo):

            | Tiempo     | Contenido                                                                 |
            |------------|---------------------------------------------------------------------------|
            | 0–[a] s    | **INTRO + HOOK**:<br>  
                        – VISUAL: ...<br>  
                        – AUDIO: ...<br>  
                        – VOZ EN OFF: ... (menciona **{self.campaign_name}**)<br>  
                        – TEXTO EN PANTALLA: ... |
            | [a]–[b] s  | **Paso 1: [Título paso 1]**<br>  
                        – VISUAL: ...<br>  
                        – AUDIO: ...<br>  
                        – VOZ EN OFF: ...<br>  
                        – TEXTO EN PANTALLA: ... |
            | [b]–[c] s  | **Paso 2: [Título paso 2]**<br>  
                        – VISUAL: ...<br>  
                        – AUDIO: ...<br>  
                        – VOZ EN OFF: ...<br>  
                        – TEXTO EN PANTALLA: ... |
            | [y]–[z] s  | **CTA + Hashtags**<br>  
                        – VISUAL: ...<br>  
                        – AUDIO: ...<br>  
                        – VOZ EN OFF: ...<br>  
                        – TEXTO EN PANTALLA: {self.hashtags} |
            """

    def formatear_prompt_estilo(self, guion_detallado):
            if not self.prompts_activados:
                print("⚠️ Prompts desactivados por configuración.")
                return ""
        
            """Aplica el formato técnico tipo SCENE INSTRUCTIONS al guion generado"""
            return f"""
            🎯 **Tarea:** Transforma el guion generado en un formato técnico tipo **SCENE INSTRUCTIONS**, siguiendo estrictamente las especificaciones estructurales exclusivamente en el idioma de {self.lang}.

            📋 **Formato requerido** (no debe modificarse):

            [SCENE INSTRUCTIONS]

            Cada bloque debe incluir lo siguiente, sin excepción:

            ---
            ### **[0:00–0:04] Nombre de la escena**
            - **VISUAL**:  
            Describe el plano exacto, tipo de lente (en mm), iluminación, cámara (fps si aplica), textura o movimiento relevante.
            - **AUDIO**:  
            - **Frecuencias dominantes** (en Hz)  
            - **Panoramización** (L/R o centro, y transición si aplica)  
            - **Dinámica**: indica dB iniciales y comportamiento (pico, decaimiento, etc.)
            - **Capas adicionales o efectos**: EQ, reverb, delays, loops.
            - **TEXTO EN PANTALLA**:  
            Texto literal, fuente, tamaño en pt, color, animación (fade-in, rebote, goteo, etc.)

            🔁 **Duración por bloque**: 4 segundos  
            🧠 **Importante**:
            – Asegúrate de que todos los elementos visuales y auditivos sean **coherentes entre sí**.  
            – No inventes nombres de escena irreales: deben representar acciones concretas.  
            – Mantén consistencia sonora (frecuencias realistas, efectos posibles)  
            – **No repitas efectos o planos ya utilizados** en bloques anteriores.  
            – Usa lenguaje técnico y descriptivo.

            ---

            🔧 **Aplica esto a todo el guion detallado que se muestra a continuación:**

            {guion_detallado}
            """


    def generate_video_prompt(self):
        if not self.prompts_activados:
            print("⚠️ GPT desactivado — usando tema por defecto.")
            return f"""🎬 Video tipo {self.tipo} sobre "{self.tema}" para {self.campaign_name}.   #Esta parte es justamente para no activaar gpt 
            Visual: antes y después de {self.servicio}.
            Audio: usar sonido sugerido ({self.sonido}).
            Texto: {self.main_cta_final}.
            Hashtags: {self.hashtags}"""
            
            
        perfil = obtener_datos_campania(self.campaign_key)
        if not perfil:
            raise ValueError(f"❌ No se encontró perfil de campaña para: {self.campaign_key}")

        business_type, city, suggested_tone, target_audience, voice = perfil
        print(f"[🔑] Campaña recibida: {self.campaign_key}")
        print(f"[✅] Perfil encontrado: {perfil}")

        # Etapa 1: generar prompt base según tipo
        prompt_tipo = self.generar_prompt_base()
        messages_1 = [
            self.create_message("system", self.SYSTEM_MESSAGE),
            self.create_message("assistant", self.ASSISTANT_MESSAGE),
            self.create_message("user", prompt_tipo),
        ]
        guion_base = self.generate_response("gpt-4", messages_1)
        
        # 🧠 Verificación anti-duplicado
        prompt_checksum = hash(guion_base)
        if prompt_checksum in historial_prompts_hashes(self.campaign_key):
            print("⚠️ Prompt similar a uno ya usado. Regenerando...")
            return self.generate_video_prompt()

        guardar_hash_prompt(self.campaign_key, prompt_checksum)


        # Si es tipo especial, formatearlo como SCENE INSTRUCTIONS
        if self.tipo in ["asmr", "documental", "storytime"]:
            prompt_formato = self.formatear_prompt_estilo(guion_base)
            messages_2 = [
                self.create_message("system", self.SYSTEM_MESSAGE),
                self.create_message("assistant", self.ASSISTANT_MESSAGE),
                self.create_message("user", prompt_formato),
            ]
            return self.generate_response("gpt-4", messages_2)

        # Si es tipo general, devolver solo el guion
        return guion_base
