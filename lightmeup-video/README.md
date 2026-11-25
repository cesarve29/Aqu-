# Light Me Up — EchoBot (voxel lyric video)

Videoclip 1920x1080 @ 30 fps, estilo voxel con letras animadas por shaders.

Pipeline:
1. `transcribe.py` — Whisper large-v3 (faster-whisper) → `whisper_words.json` (tiempos por palabra).
2. `build_lyrics.py` — limpia/corrige la letra → `lyrics.json`.
3. `make_audio.sh` — intro de 6 s (swell invertido del drop) + canción → `soundtrack.wav` (necesita `song.mp3`).
4. `analyze_audio.py soundtrack.wav audio_features.json` — energía, bandas, espectro de 32 bandas por fotograma.
5. `render_all.sh` — Three.js en Chromium headless (WebGL/SwiftShader), 4 workers en paralelo → `LightMeUp_EchoBot_1080p.mp4`.

Escenas (sincronizadas a 131 BPM), un viaje de la Tierra al universo: título voxel → océano nocturno →
bosque luminoso → montañas al atardecer con farolillos → ascenso entre nubes → ecualizador sobre las nubes (drop) →
salida de la atmósfera → planeta voxel con anillo → superficie lunar → túnel hiperespacial → nacimiento de una estrella →
galaxia espiral ecualizador con el título → outro.

Las letras se dibujan en un canvas y se componen en un shader final: karaoke por palabra,
glow neón, aberración cromática, glitch en los golpes y entrada/salida con pixelado "voxel".
