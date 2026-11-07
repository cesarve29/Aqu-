# Instrucciones del repositorio

## Proyecto: canal de Shorts "Seis en Vice" (`canal-gta6/`)

Canal de YouTube de clips cortos sobre GTA 6, en español. Handle: `@SeisEnVice`.
Guía completa (títulos, descripciones, etiquetas, derechos): `canal-gta6/GUIA-CANAL.md`.

### Reglas de edición — aplicar SIEMPRE

1. **Shorts: SIN intro.** El vídeo empieza directamente con el momento más fuerte del clip
   (el gancho en el primer segundo). Nunca poner el logo ni la intro al principio de un Short.
2. **Shorts: logo al FINAL como cierre.** Añadir `canal-gta6/intro/cierre-shorts-9x16.mp4`
   (2 s, "SUSCRÍBETE @SeisEnVice") al final de cada Short.
3. La intro completa (`intro-logo-16x9.mp4` / `montar-intro.sh` con cortes del tráiler) es solo
   para vídeos largos o recopilaciones.
4. Formato Shorts: 1080×1920, 30 fps, menos de 60 s en total (incluido el cierre),
   subtítulos grandes grabados en el vídeo, colores de marca (rosa neón #ff3fb4, cian #5ef2ff,
   amarillo #ffe066, fondo morado #120626).
5. Para cada Short entregar también: título, descripción y etiquetas según `GUIA-CANAL.md`.
6. No usar el logo oficial de GTA/Rockstar ni música comercial. Material de terceros solo en
   fragmentos breves y con aporte propio; avisar al usuario del riesgo de reclamaciones.

7. **Efectos de sonido: usar SIEMPRE la biblioteca `canal-gta6/sfx/`** (generados con ElevenLabs,
   ver `canal-gta6/sfx/README.md`). No sintetizar efectos ni generar nuevos si ya existe uno adecuado.
   Mezclar con `canal-gta6/diseno/biblioteca-sfx.js`. Si hace falta un efecto nuevo, generarlo con
   ElevenLabs, añadirlo a la biblioteca y al README.
8. En los Shorts con material del tráiler: el audio original se elimina; solo efectos de sonido
   (la música la añade el usuario). Vídeo del tráiler grande, sin bordes de color, fundido con el fondo.

### Herramientas

- Diseños y animaciones: `canal-gta6/diseno/` (`banner.js`, `avatar.js`, `intro.js`, `cuenta-atras.js`, `componer-cuenta-atras.js`).
- `yt-dlp` no viene instalado (`pip install -U yt-dlp`); YouTube suele bloquear las descargas
  desde servidores en la nube, así que el material normalmente llega por Google Drive.
