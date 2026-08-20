"""Cliente para el LLM (Google Gemini, capa gratuita) usado por el Asistente para redactar
una respuesta a partir de lo que ya encontró el buscador interno. Si no hay API key
configurada, o la llamada falla (cuota, red, etc.), la página debe caer de vuelta a mostrar
los resultados crudos — nunca depender de que esto funcione."""

import streamlit as st

DEFAULT_MODEL = "gemini-flash-lite-latest"

SYSTEM_INSTRUCTION = """Eres el asistente interno de soporte de Q10 para el equipo de CSS. \
Respondes cualquier pregunta sobre la documentación interna: cómo habilitar algo, qué hace \
un query (incluyendo su SQL), qué trae una API (endpoint, método, autenticación), qué \
significa una dimensión, qué desarrollos personalizados o personalizaciones existen para un \
cliente/institución, etc. El contexto ya fue preseleccionado por un buscador interno sobre \
TODO el catálogo (funciones, parámetros, funcionalidades, queries, APIs, dimensiones, \
desarrollos personalizados, biblioteca de desarrollos, personalizaciones) y trae, para los \
resultados más relevantes, su contenido real — no solo el nombre. Tu trabajo es usar ese \
contenido para responder de forma concreta y específica, citando datos reales (el SQL, el \
endpoint, los valores de ejemplo, etc.) en vez de solo decir "existe algo relacionado, \
revísalo".

Usa criterio para elegir qué encaja mejor con la INTENCIÓN de la pregunta, aunque el texto no \
coincida palabra por palabra. Por ejemplo, si preguntan por "cursos ligeros" y el contexto \
trae "Consolidado de educación virtual", es razonable asumir que se refiere a eso, en vez de \
decir que no encontraste nada.

Cuando el contexto ya trae una funcionalidad identificada con su descripción (para responder \
"qué debo habilitar"), tu única tarea ahí es escribir 1-2 frases de introducción amigable \
confirmando qué hay que habilitar y para qué sirve — la lista de códigos exactos a pegar en \
cada query se muestra aparte, en pantalla, así que NO transcribas ni inventes números de \
código en esa parte, ni digas cosas como "los códigos son...". Remite a ellos en general (p. \
ej. "revisa los códigos que te muestro abajo para cada query").

Para cualquier otra pregunta (sobre un query, una API, una dimensión, un desarrollo, etc.) \
responde directo usando el contenido real que tengas en el contexto — ahí sí puedes y debes \
citar el SQL, el endpoint, el código, etc., porque no se muestra aparte en pantalla.

Nunca inventes códigos, nombres, SQL, endpoints ni datos que no estén en el contexto.

Solo di que no encontraste nada si NINGÚN elemento del contexto tiene relación temática \
razonable con lo que se pregunta — no por diferencias de redacción.

Responde siempre en español, de forma concreta y completa pero sin relleno innecesario, sin \
rodeos ni saludos."""


_SUSPICIOUS_MARKERS = ("greetings", "fluff", "rubric", "system instruction", "checklist")
# Cualquiera de estos basta para considerar el texto español válido: los acentos/ñ/¿/¡ casi
# siempre aparecen tarde o temprano, y las palabras cortas cubren el resto — una respuesta
# técnica y corta (p. ej. solo un endpoint y dos palabras de contexto) puede no traer ninguna
# de las palabras "largas" (función, parámetro) que este filtro exigía antes, y terminaba
# descartándose una respuesta perfectamente buena.
_SPANISH_CHARS = "áéíóúñ¿¡"
_SPANISH_WORDS = (
    " el ", " la ", " los ", " las ", " de ", " del ", " que ", " para ", " con ", " una ",
    " un ", " es ", " son ", " no ", " en ", " y ",
)


def _looks_valid(text):
    """Filtro de sanidad: los modelos con razonamiento interno a veces filtran texto de
    autochequeo en inglés en vez de la respuesta final. Si pasa, descartamos y caemos al
    respaldo léxico en vez de mostrarle esto al usuario."""
    lowered = f" {text.lower()} "
    if any(m in lowered for m in _SUSPICIOUS_MARKERS):
        return False
    if any(c in lowered for c in _SPANISH_CHARS):
        return True
    return any(w in lowered for w in _SPANISH_WORDS)


def is_configured():
    return bool(st.secrets.get("gemini", {}).get("api_key"))


def _client():
    api_key = st.secrets.get("gemini", {}).get("api_key")
    if not api_key:
        return None
    from google import genai

    return genai.Client(api_key=api_key)


def answer(question, context):
    """Respuesta redactada por el LLM a partir del contexto ya encontrado, o None si el LLM
    no está configurado o la llamada falla por cualquier motivo."""
    client = _client()
    if client is None:
        return None
    try:
        from google.genai import types

        model = st.secrets.get("gemini", {}).get("model", DEFAULT_MODEL)
        response = client.models.generate_content(
            model=model,
            contents=f"Contexto encontrado en la documentación interna:\n{context}\n\nPregunta: {question}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.2,
                max_output_tokens=900,
            ),
        )
        text = (response.text or "").strip()
        if not text or not _looks_valid(text):
            return None
        return text
    except Exception as e:
        print(f"[lib.llm] Gemini no disponible: {type(e).__name__}: {e}")
        return None
