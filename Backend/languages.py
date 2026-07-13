"""
Catálogo de idiomas para el selector con búsqueda + bandera.
Cada entrada: code (usado internamente e indicado al modelo), name (en español,
lo que ve el usuario), native (nombre nativo, ayuda a la búsqueda), flag (emoji).
"""

LANGUAGES = [
    {"code": "en", "name": "Inglés", "native": "English", "flag": "🇬🇧"},
    {"code": "fr", "name": "Francés", "native": "Français", "flag": "🇫🇷"},
    {"code": "de", "name": "Alemán", "native": "Deutsch", "flag": "🇩🇪"},
    {"code": "it", "name": "Italiano", "native": "Italiano", "flag": "🇮🇹"},
    {"code": "pt", "name": "Portugués", "native": "Português", "flag": "🇵🇹"},
    {"code": "ja", "name": "Japonés", "native": "日本語", "flag": "🇯🇵"},
    {"code": "ko", "name": "Coreano", "native": "한국어", "flag": "🇰🇷"},
    {"code": "zh", "name": "Chino (mandarín)", "native": "中文", "flag": "🇨🇳"},
    {"code": "ru", "name": "Ruso", "native": "Русский", "flag": "🇷🇺"},
    {"code": "ar", "name": "Árabe", "native": "العربية", "flag": "🇸🇦"},
    {"code": "nl", "name": "Neerlandés", "native": "Nederlands", "flag": "🇳🇱"},
    {"code": "sv", "name": "Sueco", "native": "Svenska", "flag": "🇸🇪"},
    {"code": "no", "name": "Noruego", "native": "Norsk", "flag": "🇳🇴"},
    {"code": "da", "name": "Danés", "native": "Dansk", "flag": "🇩🇰"},
    {"code": "fi", "name": "Finés", "native": "Suomi", "flag": "🇫🇮"},
    {"code": "pl", "name": "Polaco", "native": "Polski", "flag": "🇵🇱"},
    {"code": "tr", "name": "Turco", "native": "Türkçe", "flag": "🇹🇷"},
    {"code": "el", "name": "Griego", "native": "Ελληνικά", "flag": "🇬🇷"},
    {"code": "he", "name": "Hebreo", "native": "עברית", "flag": "🇮🇱"},
    {"code": "hi", "name": "Hindi", "native": "हिन्दी", "flag": "🇮🇳"},
    {"code": "id", "name": "Indonesio", "native": "Bahasa Indonesia", "flag": "🇮🇩"},
    {"code": "vi", "name": "Vietnamita", "native": "Tiếng Việt", "flag": "🇻🇳"},
    {"code": "th", "name": "Tailandés", "native": "ไทย", "flag": "🇹🇭"},
    {"code": "cs", "name": "Checo", "native": "Čeština", "flag": "🇨🇿"},
    {"code": "ro", "name": "Rumano", "native": "Română", "flag": "🇷🇴"},
    {"code": "hu", "name": "Húngaro", "native": "Magyar", "flag": "🇭🇺"},
    {"code": "uk", "name": "Ucraniano", "native": "Українська", "flag": "🇺🇦"},
    {"code": "ca", "name": "Catalán", "native": "Català", "flag": "🏴"},
    {"code": "eu", "name": "Euskera", "native": "Euskara", "flag": "🏴"},
    {"code": "es", "name": "Español", "native": "Español", "flag": "🇪🇸"},
]


def search_languages(query: str, limit: int = 8):
    if not query:
        return LANGUAGES[:limit]
    q = query.strip().lower()
    scored = []
    for lang in LANGUAGES:
        name = lang["name"].lower()
        native = lang["native"].lower()
        if name.startswith(q) or native.startswith(q):
            scored.append((0, lang))
        elif q in name or q in native or q in lang["code"]:
            scored.append((1, lang))
    scored.sort(key=lambda x: x[0])
    return [lang for _, lang in scored[:limit]]


def get_language(code: str):
    for lang in LANGUAGES:
        if lang["code"] == code:
            return lang
    return None
