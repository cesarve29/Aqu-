# El Jinete de la Calabaza Llameante — corto de Halloween estilo Minecraft (4:20, 1080p, 60 fps)

Video generado 100 % por código: mundo de vóxeles en Three.js renderizado cuadro a cuadro en
Chromium sin interfaz (WebGL por software), con post-proceso tipo *shaders* (bloom, ACES,
gradación, niebla, haces de luz, viñeta, grano). Todo el audio está hecho con ElevenLabs:

- **Voz en off**: "Alejandro – Horror y Misterio" (eleven_v4), generada en una sola toma y cortada
  en sus 12 frases por programación dinámica; la línea del Rey va más grave y con eco.
- **Efectos de sonido**: 30 clips de ElevenLabs Sound Effects (`sfx/`): galope, relincho, trueno,
  tierra que se agrieta, fuego, puertas, gritos, zombis, huesos, arcos, flechas, espada, báculo,
  cristal, explosión dorada, corona, pájaros…
- **Música**: 5 piezas de ElevenLabs Music (`music/`), una por acto, con fundidos cruzados.

Motor reutilizado y ampliado de `../halloween-video` ("La Máscara del Eco Azul").

## Historia (26 escenas de 10 s)

| Acto | Tiempo | Escenas |
|---|---|---|
| I | 0:00–1:00 | pueblo en Halloween, fiesta, leyenda del herrero (flashback sepia), rayo sobre el roble, el Jinete surge de la tumba, galope en cámara lenta |
| II | 1:00–1:50 | plaza vacía, la calabaza mira al niño (lágrima de brasa), la montaña azul y la Llama Eterna, el niño sube al caballo, bosque muerto |
| III | 1:50–3:00 | cementerio y zombis, cueva-calavera, túnel de faroles de almas, **caverna con cientos de esqueletos y fuego azul**, arqueros, el Rey Esqueleto |
| IV | 3:00–3:50 | lluvia de flechas y espada llameante, combate, golpe del báculo, el niño roba la Llama, **la ola dorada vuelve naranja todo el fuego azul** |
| V | 3:50–4:20 | amanecer, regreso al pueblo, la calabaza sonríe y el Jinete se deshace en brasas doradas |

## Cómo generarlo

Requisitos: Node 18+, Playwright con Chromium, Python 3 con NumPy y Pillow, ffmpeg con libass.

```bash
npm install                 # three.js
./render_all.sh 1 26        # renders/scene_XX.mp4 (~0.7 s por cuadro en CPU; salta las ya hechas)
python3 mix.py              # audio/mezcla.wav (voz + efectos + música de ElevenLabs)
./make_video.sh             # el_jinete_de_la_calabaza_llameante_1080p60.mp4
python3 thumbnail.py        # miniatura de YouTube 1920x1080
```

Revisar cuadros sueltos: `node render.cjs stills 47 77.5 222` → `stills/`.

## Código

- `src/rider.js` el Jinete (armadura, capa rasgada, cabeza de calabaza con fuego en ojos y boca, espada), el caballo negro (ojos rojos, cascos en llamas) y el niño espantapájaros
- `src/fx.js` fuego pixelado azul↔naranja↔dorado (ola por distancia `uWave`/`iDelay`, tinte, modo dorado), `FireTrail` para huellas ardiendo, partículas, ondas, haces, cielo, luna
- `src/sets.js` pueblo con el viejo roble y la tumba, bosque, cementerio, montaña-calavera con túnel, caverna
- `src/story.js` guion: cámaras y animación de las 26 escenas (función pura del tiempo)
- `src/voxel.js`, `src/models.js`, `src/army.js`, `src/textures.js`, `src/main.js` motor heredado
- `mix.py` mezcla de audio · `subtitles.py` subtítulos .ass · `thumbnail.py` miniatura
