# La Máscara del Eco Azul — corto de Halloween estilo Minecraft (4:20, 1080p, 60 fps)

Video generado 100 % por código: mundo de vóxeles en Three.js renderizado cuadro a cuadro
en Chromium sin interfaz (WebGL por software), con post-proceso tipo *shaders*
(bloom, tone mapping ACES, niebla volumétrica, haces de luz, viñeta, grano),
banda sonora sintetizada con NumPy, voz en off grave generada con ElevenLabs ("Alejandro – Horror y Misterio") y subtítulos en español.

El protagonista usa la skin de referencia (`ref/personaje.jpg`): túnica negra con capucha
y máscara blanca que grita.

## Historia (26 escenas de 10 s)

| Acto | Tiempo | Escenas |
|---|---|---|
| I. La llegada | 0:00–1:00 | pueblo en Halloween, aldeanos bailando, la figura sale de la niebla, las calabazas se apagan, todos huyen menos la niña |
| II. El camino | 1:00–1:50 | bosque muerto, la niña lo sigue, pantano y bruja, zombis que se apartan, la lápida de runas |
| III. La cueva | 1:50–3:00 | montaña con boca de calavera, túnel, **caverna llena de esqueletos con fuego azul**, puente de huesos, el Rey Esqueleto |
| IV. La batalla | 3:00–3:50 | lluvia de flechas, la figura se vuelve humo, golpe del báculo, recupera su voz, **el grito vuelve naranja el fuego azul** |
| V. Amanecer | 3:50–4:20 | sale de la cueva, el pueblo reenciende las calabazas, la niña le regala una calabacita, sonríe y se va |

## Cómo generarlo

Requisitos: Node 18+, Playwright con Chromium, Python 3 con NumPy, ffmpeg con libass.

```bash
npm install                 # three.js
./render_all.sh             # 26 escenas -> renders/scene_XX.mp4 (≈0.7 s por cuadro en CPU; se puede reanudar)
python3 soundtrack.py       # audio/soundtrack.wav
python3 voiceover.py        # voz en off (voz/narracion_take1.mp3, ElevenLabs) + música -> audio/mezcla.wav
./make_video.sh             # une escenas + audio + subtítulos -> la_mascara_del_eco_azul_1080p60.mp4
```

Revisar cuadros sueltos: `node render.cjs stills 12.5 140 225` → `stills/`.

## Código

- `src/textures.js` texturas pixel-art procedurales (bloques, skins, máscara 16×16)
- `src/voxel.js` mundo de vóxeles: solo caras visibles + oclusión ambiental por vértice
- `src/models.js` personajes con UV de skin de Minecraft (figura, aldeanos, niña, bruja, zombis, esqueletos, rey)
- `src/army.js` ejército de esqueletos instanciado (poses, apuntar, derrumbarse en huesos)
- `src/fx.js` fuego pixelado azul↔naranja (ola por distancia), partículas, ondas, haces de luz, cielo, luna
- `src/sets.js` escenarios: pueblo, bosque, pantano, cementerio, montaña-calavera con túnel, caverna
- `src/story.js` guion: cámaras y animación de las 26 escenas (todo es función del tiempo)
- `src/main.js` render + post-proceso; `render.cjs` captura cuadros y los envía a ffmpeg
