# Magnitud 10 — ¿Qué pasaría?

Video explicativo (≈2 min 22 s, 1920×1080, 30 fps) en primera persona sobre un
hipotético terremoto de magnitud 10, animado en 3D con Three.js y renderizado
fotograma a fotograma en Chromium sin interfaz.

**Archivo final:** `terremoto_magnitud_10.mp4`

## Guion
| Tiempo | Escena |
|---|---|
| 0:00 | Vuelo sobre la ciudad costera · título · Valdivia 1960 (M 9,5) |
| 0:18 | Paseo en primera persona · infografías: energía (×32 por grado) y longitud de ruptura (4.000+ km) |
| 0:37 | Alerta sísmica en el teléfono · llegan las ondas P |
| 0:49 | Ondas S: edificios que se balancean, cristales, derrumbe, poste eléctrico que cae |
| 1:00 | Huida a la plaza · "Agáchate, cúbrete, sujétate" · duración de hasta 20 min |
| 1:16 | Licuefacción: grietas y coche que se hunde · la ciudad en ruinas |
| 1:29 | En la costa el mar se retira (barcos varados) · alerta de tsunami · huida |
| 1:41 | Desde la colina: la ola de 20–30 m entra en la ciudad |
| 1:52 | La Tierra vibra como una campana · eje y duración del día |
| 2:04 | Cierre: cómo prepararse |

## Cómo regenerarlo
```bash
npm install                 # three.js
python3 make_audio.py       # banda sonora (requiere numpy y scipy)
./render_all.sh             # renderiza los tramos en parts/ (Playwright + ffmpeg)
./finalize.sh               # une tramos y audio
node snap.js out 1500 2400  # vista previa de fotogramas sueltos
```

- `js/` — escena: ciudad (`city.js`), personas articuladas y su comportamiento
  (`people.js`), partículas, mar y tsunami (`fx.js`), cámara y teléfono (`camera.js`),
  globo (`globe.js`), gráficos y subtítulos (`overlay.js`), guion temporal (`timeline.js`).
- Narración: voz "Damián" de ElevenLabs (`audio/narration.wav`).
- Música y efectos: sintetizados en `make_audio.py`.
