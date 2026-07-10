# Lingobot
# LingoBot â€” Prototipo

Chatbot profesor de idiomas: clase diaria + conversaciÃ³n con correcciÃ³n gramatical/ortogrÃ¡fica en vivo.

## QuÃ© incluye este prototipo

- **Backend (Python / FastAPI)**: `backend/`
  - BÃºsqueda de idiomas con bandera (`GET /api/languages?q=...`)
  - Conversaciones por idioma, guardadas en SQLite, con historial (`/api/conversations`)
  - Chat con correcciÃ³n gramatical vÃ­a Claude, devuelve JSON estructurado con correcciones
  - Endpoint de "clase diaria" + un scheduler (APScheduler) que la dispara cada maÃ±ana
- **Frontend**: `frontend/index.html`
  - Un Ãºnico archivo HTML/CSS/JS (sin build), mobile-first, funciona igual en escritorio
  - Sidebar de conversaciones con bandera de cada idioma
  - BotÃ³n "+ Nuevo idioma" con buscador (nombre, nombre nativo o cÃ³digo) y selector de nivel
  - Chat con burbujas, traducciÃ³n breve y bloque de correcciones bajo cada respuesta

## CÃ³mo arrancarlo

### 1. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate   # opcional pero recomendado
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-tu-clave           # https://console.anthropic.com
uvicorn main:app --reload --port 8000
```

### 2. Frontend

Abre `frontend/index.html` directamente en el navegador del mÃ³vil u ordenador
(o sÃ­rvelo con `python -m http.server` dentro de `frontend/`). Si el backend no estÃ¡ en
`localhost:8000`, cambia la constante `API` al principio del `<script>` en `index.html`.

## Convertirlo en app instalable en el mÃ³vil (PWA)

Para que "+ Nuevo idioma", el historial y el chat se sientan como una app nativa:
1. AÃ±ade un `manifest.json` (nombre, icono, `display: standalone`) y un `service worker` bÃ¡sico.
2. Sirve el frontend por HTTPS (necesario para PWA y para notificaciones push).
3. En Android/Chrome el usuario podrÃ¡ "AÃ±adir a pantalla de inicio"; en iOS 16.4+ funciona igual
   desde Safari (Compartir â†’ AÃ±adir a inicio).

## Notificaciones push reales (la clase de la maÃ±ana)

Este prototipo genera la clase diaria en el backend (job programado en `main.py`), pero **no**
la empuja aÃºn al mÃ³vil â€” hace falta uno de estos dos servicios:

- **Web Push (VAPID)**: funciona en Android/desktop y en iOS 16.4+ si la PWA estÃ¡ instalada.
  LibrerÃ­a recomendada: `pywebpush`. Pasos: generar claves VAPID, guardar la `subscription` que
  el navegador te da al pedir permiso de notificaciones, y llamar a `webpush()` desde
  `_run_daily_classes_job()` en `main.py` tras generar la clase.
- **Firebase Cloud Messaging (FCM)**: mÃ¡s simple si en el futuro haces una app nativa
  (React Native / Flutter) en vez de PWA.

Te lo puedo integrar en la siguiente iteraciÃ³n si quieres seguir por ahÃ­.

## Desplegar de verdad

- Backend: Render, Railway, Fly.io o un VPS con Docker (necesitas persistir `lingobot.db`,
  o migrar a Postgres si vas a tener varios usuarios).
- Frontend: Vercel, Netlify o el mismo backend sirviendo el HTML como estÃ¡tico.
- Multiusuario: este prototipo es de un solo usuario (no hay login). Para varias personas,
  aÃ±ade autenticaciÃ³n (p. ej. `fastapi-users`) y un `user_id` en `conversations`.

## Siguientes pasos sugeridos

1. AutenticaciÃ³n de usuarios (para que cada uno tenga su historial).
2. Notificaciones push reales (ver arriba).
3. Ajuste automÃ¡tico de nivel: ya se pide al modelo un `suggested_level`; falta guardarlo
   y usarlo para subir/bajar el nivel de la conversaciÃ³n con el tiempo.
4. Ampliar el frontend a React si quieres una app mÃ¡s rica (el backend ya estÃ¡ desacoplado).
Actualizar proyecto