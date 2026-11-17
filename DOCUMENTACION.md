# LingoBot — Documentación del proyecto

Chatbot profesor de idiomas: clases diarias + conversación con corrección gramatical/ortográfica,
historial por idioma con banderas, buscador de idiomas.

Última actualización: 15 julio 2026.

---

## 1. Arquitectura general

```
┌─────────────────────┐       ┌──────────────────────────┐       ┌─────────────────┐
│   GitHub Pages       │──────▶│   Render (backend)        │──────▶│  Google Gemini   │
│   (frontend estático) │ HTTP  │   FastAPI + SQLite         │  API  │  (modelo de IA)  │
│   Siempre activo      │       │   Se "duerme" sin uso      │       │  Nivel gratuito  │
└─────────────────────┘       └──────────────────────────┘       └─────────────────┘
        ▲
        │ navegador (tablet / móvil / PC)
        │
     Usuario
```

- **No hay nada instalado ni corriendo en la tablet/móvil.** Todo vive en la nube; el dispositivo
  solo abre la URL en el navegador, como cualquier página web.
- **Repositorio GitHub:** `github.com/ccortesca/Lingobot` (público — necesario para que
  GitHub Pages funcione gratis).

---

## 2. Estructura de archivos y qué hace cada uno

Dentro del repo de GitHub:

```
Lingobot/
├── Backend/
│   ├── main.py            → API FastAPI: define todos los endpoints (/api/...)
│   ├── database.py        → acceso a SQLite: conversaciones y mensajes
│   ├── languages.py       → catálogo de idiomas soportados (nombre, bandera, código)
│   ├── ai_service.py      → llamadas a Gemini: genera respuestas del profesor y clases diarias
│   └── requirements.txt   → dependencias Python que Render instala automáticamente
│
├── Frontend/
│   └── index.html         → toda la app web (HTML+CSS+JS en un solo archivo): sidebar,
│                             buscador de idiomas, chat, botón de borrar conversación
│
└── docs/                  → carpeta antigua de un primer intento con Jekyll, ya no se usa
                              (se sustituyó por GitHub Actions apuntando a /Frontend)
```

### ¿Qué hace cada archivo del backend?

| Archivo | Función |
|---|---|
| `main.py` | Recibe las peticiones del frontend: buscar idiomas, crear/listar/borrar conversaciones, enviar mensajes, generar clase diaria. Programa el job diario con APScheduler. |
| `database.py` | Guarda y lee de `lingobot.db` (SQLite): tablas `conversations` y `messages`. |
| `languages.py` | Lista fija de ~30 idiomas con su bandera emoji, usada por el buscador. |
| `ai_service.py` | Construye el prompt para el profesor, llama a la API de Gemini, y parsea la respuesta JSON (texto + correcciones). **Aquí se define qué modelo de Gemini se usa.** |

---

## 3. Render (backend)

**Qué es:** hosting gratuito donde corre el servidor Python 24/7 (con matices, ver más abajo).

**Configuración actual del servicio:**
- **Root Directory:** `Backend` (con B mayúscula, tal y como está la carpeta en GitHub)
- **Build Command:** `pip install -r requirements.txt`
- **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Variable de entorno:** `GEMINI_API_KEY` = tu clave de Google AI Studio
- **URL del servicio:** `https://lingobot-jpio.onrender.com`

**Comportamiento del plan gratuito — IMPORTANTE:**
El backend se "duerme" tras ~15 minutos sin recibir tráfico. La siguiente petición (p. ej. abrir
la app tras un rato) tarda 20-30 segundos extra mientras Render lo "despierta". No hay que tener
Render abierto en ningún navegador para que funcione — el dormir/despertar pasa en su servidor,
independientemente de si tú tienes esa pestaña abierta o no.

**Ping anti-inactividad — ya configurado ✅**
Se ha creado un cron-job en **cron-job.org** que llama a
`https://lingobot-jpio.onrender.com/api/health` cada 10 minutos, para que Render no llegue a
dormirse por falta de tráfico. Con esto la app debería responder rápido siempre, sin la espera
de 20-30 segundos de "despertar".

**Dónde mirar si algo falla:** Render → tu servicio → pestaña **"Logs"** (errores en tiempo real)
y pestaña **"Events"** (historial de despliegues).

---

## 4. GitHub Pages (frontend)

**Qué es:** hosting gratuito y estático para el `index.html`. Siempre está activo, no se duerme.

**Configuración actual:**
- **Source:** GitHub Actions (no "Deploy from a branch" — ese modo solo permite servir desde la
  raíz o una carpeta llamada exactamente `docs`, y nuestro frontend vive en `Frontend`)
- **Workflow:** `.github/workflows/static.yml`, con `path: './Frontend'`
- **URL pública:** `https://ccortesca.github.io/Lingobot/`

**Por qué no se usó el método simple ("Deploy from a branch"):** ese modo también intenta procesar
el sitio con Jekyll (un generador de páginas de Ruby) salvo que la carpeta se llame `docs`, y
aun con `.nojekyll` seguía fallando por el nombre de carpeta. El método de GitHub Actions evita
Jekyll por completo y permite apuntar a cualquier carpeta.

**Cómo actualizar el frontend:** editar `Frontend/index.html` en GitHub (lápiz → editar → commit).
GitHub Pages reconstruye solo, tarda 1-2 minutos en reflejar el cambio (a veces hace falta refresco
forzado en el navegador si queda cacheado).

---

## 5. Google Gemini (motor de IA)

**Qué es:** el modelo de lenguaje que hace de "profesor" — genera las respuestas, corrige
gramática/ortografía y crea la clase diaria. Se usa la capa **gratuita** de Google AI Studio.

- **Clave:** se obtiene en `aistudio.google.com` → "Get API key". No pide tarjeta.
- **Se configura como variable de entorno `GEMINI_API_KEY` en Render** (no está escrita en
  ningún archivo del código).
- **Modelo actual:** `gemini-3.1-flash-lite` (definido en `Backend/ai_service.py`, línea `MODEL = ...`)

**Aviso importante:** Google retira modelos del catálogo gratuito con bastante frecuencia (ya
pasó una vez con `gemini-2.5-flash`, que dejó de estar disponible para cuentas nuevas). Si en el
futuro vuelve a fallar con un error `404 - model no longer available`:
1. Ir a `ai.google.dev/gemini-api/docs/models` y ver qué modelo gratuito vigente recomiendan.
2. Cambiar el valor de `MODEL` en `ai_service.py` por ese nombre.
3. Commit en GitHub → Render redepliega solo.

---

## 6. Flujo de una conversación (de principio a fin)

1. Usuario abre `ccortesca.github.io/Lingobot` → el navegador carga `index.html`.
2. `index.html` pide la lista de idiomas a `GET /api/languages?q=...` (Render).
3. Usuario elige idioma + nivel → `POST /api/conversations` (Render) → esto además dispara
   una llamada a Gemini para generar la clase de bienvenida, que se guarda en SQLite.
4. Usuario escribe un mensaje → `POST /api/conversations/{id}/messages` → el backend manda el
   historial + mensaje nuevo a Gemini, pidiendo JSON con: respuesta del profesor, traducción
   breve, y lista de correcciones si las hay.
5. Cada mañana (job programado con APScheduler, hora fija del servidor), se genera
   automáticamente una clase nueva por cada conversación activa — de momento solo se guarda en
   la base de datos, no se envía como notificación push real al dispositivo (ver pendientes).

---

## 7. Incidencias ya resueltas (por si se repiten)

| Problema | Causa | Solución |
|---|---|---|
| Render: `Root directory "backend" does not exist` | La carpeta en GitHub se llama `Backend` (mayúscula) | Poner `Backend` con mayúscula en el campo Root Directory de Render |
| GitHub Pages: build falla con error de Jekyll/SCSS | El modo "Deploy from a branch" fuerza Jekyll y solo admite carpeta `docs` | Cambiar a Source: GitHub Actions, plantilla "Static HTML", `path: './Frontend'` |
| No se podía seleccionar idioma / nada respondía | `index.html` tenía `const API = "http://localhost:8000/api"` en vez de la URL de Render | Cambiar esa línea a `https://lingobot-jpio.onrender.com/api` |
| Chat no mostraba nada al abrir conversación | `height: 100vh` no descuenta la barra del navegador en Android | Añadir `height: 100dvh` junto a `100vh` en `body` y `#app` |
| Bot no respondía, error 404 en logs | Google retiró `gemini-2.5-flash` para cuentas nuevas | Cambiar `MODEL` en `ai_service.py` a `gemini-3.1-flash-lite` |

---

## 8. Pendiente / próximos pasos posibles

- [ ] **Notificaciones push reales** por la mañana (ahora la clase se genera en el backend pero
  no se empuja como notificación al dispositivo — requiere Web Push/VAPID o Firebase).
- [ ] **Ajustar el scheduler a la hora local** del usuario (ahora usa la hora del servidor, UTC).
- [ ] **Autenticación de usuarios** si en algún momento más de una persona va a usar la app con
  historiales separados (ahora mismo cualquiera con la URL ve las mismas conversaciones).
- [ ] Guardar y usar el `suggested_level` que ya devuelve Gemini para subir/bajar el nivel del
  alumno automáticamente con el tiempo.

---

## 9. Accesos rápidos

- Repo: `github.com/ccortesca/Lingobot`
- App (frontend): `https://ccortesca.github.io/Lingobot/`
- Backend (Render): `https://lingobot-jpio.onrender.com`
- Comprobar que el backend está vivo: `https://lingobot-jpio.onrender.com/api/health`
- Consola de Render: `dashboard.render.com`
- Clave de Gemini: `aistudio.google.com`
- Ping anti-inactividad: `cron-job.org` (llama a `/api/health` cada 10 min)
