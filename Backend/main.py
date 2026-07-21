"""
LingoBot API — backend FastAPI.

Arrancar en desarrollo:
    export ANTHROPIC_API_KEY=sk-ant-...
    pip install -r requirements.txt
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
from apscheduler.schedulers.background import BackgroundScheduler
from typing import Optional

import database as db
import languages as langs
import ai_service
import auth


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


class AuthRequest(BaseModel):
    username: str
    password: str


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Extrae y valida el token 'Bearer <token>' del header Authorization."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "No autenticado")
    token = authorization.removeprefix("Bearer ").strip()
    session = db.get_session(token)
    if not session or auth.is_expired(session["expires_at"]):
        raise HTTPException(401, "Sesión inválida o caducada")
    return {"id": session["user_id"]}


# ---------- Autenticación ----------

@app.post("/api/auth/register")
def register(req: AuthRequest):
    if len(req.username.strip()) < 3:
        raise HTTPException(400, "El usuario debe tener al menos 3 caracteres")
    if len(req.password) < 6:
        raise HTTPException(400, "La contraseña debe tener al menos 6 caracteres")
    if db.get_user_by_username(req.username):
        raise HTTPException(409, "Ese usuario ya existe")

    salt, pw_hash = auth.hash_password(req.password)
    user_id = db.create_user(req.username, salt, pw_hash)

    token = auth.generate_token()
    db.create_session(token, user_id, auth.session_expiry())
    return {"token": token, "username": req.username}


@app.post("/api/auth/login")
def login(req: AuthRequest):
    user = db.get_user_by_username(req.username)
    if not user or not auth.verify_password(req.password, user["password_salt"], user["password_hash"]):
        raise HTTPException(401, "Usuario o contraseña incorrectos")

    token = auth.generate_token()
    db.create_session(token, user["id"], auth.session_expiry())
    return {"token": token, "username": user["username"]}


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        db.delete_session(authorization.removeprefix("Bearer ").strip())
    return {"ok": True}


# ---------- Idiomas ----------

@app.get("/api/languages")
def search_languages(q: str = ""):
    """Buscador de idiomas: usado por la barra 'Nuevo idioma' -> sugiere nombre + bandera."""
    return langs.search_languages(q)


# ---------- Conversaciones ----------

@app.get("/api/conversations")
def get_conversations(user: dict = Depends(get_current_user)):
    """Historial lateral: una entrada por conversación, con bandera del idioma."""
    return db.list_conversations(user["id"])


@app.post("/api/conversations")
def create_conversation(req: NewConversationRequest, user: dict = Depends(get_current_user)):
    lang = langs.get_language(req.language_code)
    if not lang:
        raise HTTPException(404, "Idioma no soportado")
    conv_id = db.create_conversation(user["id"], lang["code"], lang["name"], lang["flag"], req.level)

    # Mensaje de bienvenida generado por el profesor al abrir el idioma por primera vez.
    try:
        class_data = ai_service.get_daily_class(lang["name"], lang["native"], req.level)
        db.add_message(conv_id, "assistant", class_data["reply"], class_data.get("corrections"))
    except Exception:
        # Si falla la IA (p.ej. sin API key configurada en este entorno demo), seguimos sin bloquear.
        pass

    return db.get_conversation(conv_id, user["id"])


@app.get("/api/conversations/{conv_id}/messages")
def get_messages(conv_id: int, user: dict = Depends(get_current_user)):
    if not db.get_conversation(conv_id, user["id"]):
        raise HTTPException(404, "Conversación no encontrada")
    return db.list_messages(conv_id)


@app.delete("/api/conversations/{conv_id}")
def delete_conversation(conv_id: int, user: dict = Depends(get_current_user)):
    if not db.get_conversation(conv_id, user["id"]):
        raise HTTPException(404, "Conversación no encontrada")
    db.delete_conversation(conv_id)
    return {"deleted": True}


@app.post("/api/conversations/{conv_id}/messages")
def send_message(conv_id: int, req: SendMessageRequest, user: dict = Depends(get_current_user)):
    conv = db.get_conversation(conv_id, user["id"])
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

def _generate_daily_class(conv: dict) -> dict:
    lang = langs.get_language(conv["language_code"])
    class_data = ai_service.get_daily_class(lang["name"], lang["native"], conv["level"])
    db.add_message(conv["id"], "assistant", class_data["reply"], class_data.get("corrections"))
    return class_data


@app.post("/api/conversations/{conv_id}/daily-class")
def trigger_daily_class(conv_id: int, user: dict = Depends(get_current_user)):
    """Genera manualmente la clase de hoy."""
    conv = db.get_conversation(conv_id, user["id"])
    if not conv:
        raise HTTPException(404, "Conversación no encontrada")
    return _generate_daily_class(conv)


def _run_daily_classes_job():
    """Job programado: recorre conversaciones (de todos los usuarios) con clase diaria activada
    y las genera.
    NOTA: para notificación push real al móvil hace falta integrar Web Push (VAPID) o
    Firebase Cloud Messaging aquí, guardando el 'subscription' del dispositivo del usuario
    y llamando a ese servicio tras generar el mensaje. Ver README para la guía de integración."""
    for conv in db.list_all_conversations():
        if conv["daily_class_enabled"]:
            try:
                _generate_daily_class(conv)
            except Exception as e:
                print(f"Error generando clase diaria para conversación {conv['id']}: {e}")


# Por defecto, revisa cada minuto qué conversaciones tienen su hora de clase configurada
# y coincide con la hora actual (chequeo simple; para producción usa cron por usuario).
scheduler.add_job(_run_daily_classes_job, "cron", hour=8, minute=0, id="daily_classes")


@app.get("/api/health")
def health():
    return {"status": "ok", "model": ai_service.MODEL}
