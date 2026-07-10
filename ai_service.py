"""
Integración con la API de Claude (Anthropic).

Requiere la variable de entorno ANTHROPIC_API_KEY.
Instalar dependencia: pip install anthropic
"""
import os
import json
import re
from anthropic import Anthropic

# Modelo por defecto: rápido y barato, ideal para chat conversacional.
# Si quieres respuestas más matizadas en la corrección gramatical, cambia a "claude-sonnet-5".
MODEL = os.environ.get("LINGOBOT_MODEL", "claude-haiku-4-5-20251001")

client = Anthropic()  # usa ANTHROPIC_API_KEY del entorno


def _extract_json(text: str) -> dict:
    """El modelo debe devolver JSON puro, pero por robustez extraemos el primer bloque {...}."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No se encontró JSON en la respuesta del modelo: {text[:200]}")
    return json.loads(match.group(0))


def _system_prompt(language_name: str, native_name: str, level: str) -> str:
    return f"""Eres un profesor de {language_name} ({native_name}) nativo, cercano y paciente,
que enseña a hispanohablantes. El nivel actual del alumno es {level} (escala MCER: A1-C2).

Reglas:
- Conversa SIEMPRE en {language_name}, adaptando vocabulario y complejidad al nivel {level}.
- En cada turno, revisa el último mensaje del alumno en busca de errores gramaticales y
  ortográficos en {language_name}. Si hay errores, indícalos de forma breve y constructiva.
- Si el alumno escribe en español o mezcla idiomas, corrígelo suavemente y anímalo a intentarlo
  en {language_name}.
- Sé motivador, nunca condescendiente. Haz preguntas para mantener la conversación viva.
- Ajusta la dificultad progresivamente si detectas que el alumno domina el nivel actual.

Responde ÚNICAMENTE con un objeto JSON válido (sin texto fuera del JSON, sin backticks), con
esta forma exacta:
{{
  "reply": "tu respuesta en {language_name}, como profesor, continuando la conversación",
  "reply_translation_es": "traducción breve al español de tu respuesta, para que el alumno entienda",
  "has_corrections": true/false,
  "corrections": [
    {{"original": "fragmento con error del alumno", "corrected": "versión corregida", "explanation_es": "explicación breve en español"}}
  ],
  "suggested_level": "A1|A2|B1|B2|C1|C2"
}}
Si no hay errores que corregir, "corrections" debe ser una lista vacía y "has_corrections": false.
"""


def get_tutor_reply(language_name: str, native_name: str, level: str, history: list, user_message: str) -> dict:
    """
    history: lista de dicts {"role": "user"|"assistant", "content": str} (mensajes previos,
             usar el campo 'reply' guardado para los turnos del asistente).
    """
    messages = []
    for turn in history[-20:]:  # limitamos contexto para no disparar coste/latencia
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=_system_prompt(language_name, native_name, level),
        messages=messages,
    )
    raw_text = "".join(block.text for block in response.content if block.type == "text")
    return _extract_json(raw_text)


def get_daily_class(language_name: str, native_name: str, level: str) -> dict:
    """Genera una breve clase diaria (mini-lección) para abrir la conversación por la mañana."""
    system = f"""Eres un profesor de {language_name} ({native_name}) para hispanohablantes de nivel {level}.
Genera una mini-clase diaria breve (máximo 120 palabras en {language_name}, más traducción),
con: 1) un punto gramatical o de vocabulario del día, 2) un ejemplo, 3) una pregunta para que
el alumno practique respondiendo.

Responde ÚNICAMENTE con JSON válido, sin texto fuera del JSON:
{{
  "reply": "la mini-clase completa en {language_name}, con la pregunta final incluida",
  "reply_translation_es": "traducción al español de toda la clase",
  "has_corrections": false,
  "corrections": [],
  "suggested_level": "{level}"
}}
"""
    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=system,
        messages=[{"role": "user", "content": "Genera la clase de hoy."}],
    )
    raw_text = "".join(block.text for block in response.content if block.type == "text")
    return _extract_json(raw_text)
