# Preferencias del proyecto

## ElevenLabs: ahorrar créditos
- **Voz en off: generar UNA sola toma** (`generations_count: 1`). Nunca 2 ni más.
- Si el usuario pide una voz concreta, usar exactamente esa. Si no, elegir con
  `creative_list_voices` la mejor voz **narrativa** en el idioma del guion
  (en español: `QtPMrakdgePQIUwOX7Ut` "Arconte", voz grave y narrativa, ya aprobada por el usuario).
- Efectos de sonido: **1 variación por efecto** (`generations_count: 1`) y solo los imprescindibles.
- No repetir generaciones para "probar": si hace falta otra toma, preguntar antes.
- Para sincronizar subtítulos, transcribir la voz con Scribe (coste 0) en vez de generar por frases.

## Vídeos
- Formato por defecto: vertical 9:16, 1080x1920, 60 fps, renderizado por código (ver `viaje-tiempo/make_video.py`).
- Subtítulos solo en los momentos clave, no en toda la narración.
- Calibrar el volumen de cada efecto según su sonoridad medida, para que quede por debajo de la voz.
