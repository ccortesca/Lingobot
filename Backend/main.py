"""
LingoBot API — backend FastAPI.

Arrancar en desarrollo:
    export ANTHROPIC_API_KEY=sk-ant-...
    pip install -r requirements.txt
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler

import database as db
import languages as langs
import ai_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="LingoBot API", lifespan=lifespan)

# En producción, restringe origins al dominio real de tu frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

scheduler = BackgroundScheduler()


# ---------- Esquemas ----------

class NewConversationRequest(BaseModel):
    language_code: str
    level: str = "A2"


class SendMessageRequest(BaseModel):
    content: str


# ---------- Idiomas ----------

@app.get("/api/languages")
def search_languages(q: str = ""):
    """Buscador de idiomas: usado por la barra 'Nuevo idioma' -> sugiere nombre + bandera."""
    return langs.search_languages(q)


# ---------- Conversaciones ----------

@app.get("/api/conversations")
def get_conversations():
    """Historial lateral: una entrada por conversación, con bandera del idioma."""
    return db.list_conversations()


@app.post("/api/conversations")
def create_conversation(req: NewConversationRequest):
    lang = langs.get_language(req.language_code)
    if not lang:
        raise HTTPException(404, "Idioma no soportado")
    conv_id = db.create_conversation(lang["code"], lang["name"], lang["flag"], req.level)

    # Mensaje de bienvenida generado por el profesor al abrir el idioma por primera vez.
    try:
        class_data = ai_service.get_daily_class(lang["name"], lang["native"], req.level)
        db.add_message(conv_id, "assistant", class_data["reply"], class_data.get("corrections"))
    except Exception:
        # Si falla la IA (p.ej. sin API key configurada en este entorno demo), seguimos sin bloquear.
        pass

    return db.get_conversation(conv_id)


@app.get("/api/conversations/{conv_id}/messages")
def get_messages(conv_id: int):
    if not db.get_conversation(conv_id):
        raise HTTPException(404, "Conversación no encontrada")
    return db.list_messages(conv_id)


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int):
    if not db.get_conversation(conv_id):
        raise HTTPException(404, "Conversación no encontrada")
    db.delete_conversation(conv_id)
    return {"deleted": True}


@app.post("/api/conversations/{conv_id}/messages")
def send_message(conv_id: int, req: SendMessageRequest):
    conv = db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversación no encontrada")

    db.add_message(conv_id, "user", req.content)

    history = [
        {"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]}
        for m in db.list_messages(conv_id)
        if m["role"] in ("user", "assistant")
    ][:-1]  # excluye el mensaje recién insertado, que se pasa aparte

    lang = langs.get_language(conv["language_code"])
    result = ai_service.get_tutor_reply(
        lang["name"], lang["native"], conv["level"], history, req.content
    )

    db.add_message(conv_id, "assistant", result["reply"], result.get("corrections"))
    return result


# ---------- Clase diaria ----------

@app.post("/api/conversations/{conv_id}/daily-class")
def trigger_daily_class(conv_id: int):
    """Genera manualmente la clase de hoy (también se puede invocar desde el scheduler)."""
    conv = db.get_conversation(conv_id)
    if not conv:
        raise HTTPException(404, "Conversación no encontrada")
    lang = langs.get_language(conv["language_code"])
    class_data = ai_service.get_daily_class(lang["name"], lang["native"], conv["level"])
    db.add_message(conv_id, "assistant", class_data["reply"], class_data.get("corrections"))
    return class_data


def _run_daily_classes_job():
    """Job programado: recorre conversaciones con clase diaria activada y las genera.
    NOTA: para notificación push real al móvil hace falta integrar Web Push (VAPID) o
    Firebase Cloud Messaging aquí, guardando el 'subscription' del dispositivo del usuario
    y llamando a ese servicio tras generar el mensaje. Ver README para la guía de integración."""
    for conv in db.list_conversations():
        if conv["daily_class_enabled"]:
            try:
                trigger_daily_class(conv["id"])
            except Exception as e:
                print(f"Error generando clase diaria para conversación {conv['id']}: {e}")


# Por defecto, revisa cada minuto qué conversaciones tienen su hora de clase configurada
# y coincide con la hora actual (chequeo simple; para producción usa cron por usuario).
scheduler.add_job(_run_daily_classes_job, "cron", hour=8, minute=0, id="daily_classes")


@app.get("/api/health")
def health():
    return {"status": "ok", "model": ai_service.MODEL}
