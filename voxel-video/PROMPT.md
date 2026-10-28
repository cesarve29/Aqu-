# BLOCKCRAFT: La Leyenda de la Dragona — prompts

Este directorio contiene dos cosas:

1. **Los prompts** (abajo) para generar el mundo y el vídeo con herramientas de IA
   (Sora, Veo, Kling, Runway, Luma, Midjourney, etc.).
2. **El vídeo ya generado por código**: `blockcraft_1080p.mp4`, 1920x1080 (16:9), 24 fps y 5:35 de duración,
   renderizado con un motor voxel propio (Three.js + shaders WebGL) y banda sonora sintetizada.

---

## 1. Prompt del mundo (imagen o escena 3D)

**Español**

> Mundo 3D de vóxeles al estilo de los juegos de construcción con bloques, renderizado con shaders realistas:
> una isla de bloques cúbicos de 1x1 m rodeada de un océano turquesa con olas animadas, reflejos de Fresnel y
> brillo especular del sol. Colinas escalonadas de hierba, tierra y piedra, montañas con nieve en la cima,
> bosques de robles cúbicos con hojas translúcidas, una cabaña de madera con farolillos brillantes y una mesa
> de trabajo. Texturas pixel-art de 16x16 con filtrado nítido (sin difuminar), oclusión ambiental suave en las
> esquinas de los bloques, sombras dinámicas en tiempo real, niebla atmosférica, nubes planas de bloques que se
> desplazan, sol cuadrado y bloom cálido al amanecer, gradación de color cinematográfica, viñeteado sutil.
> Cámara aérea, 16:9, ultra detallado, 8K, estilo "Minecraft con shaders BSL/SEUS".

**English** (suele dar mejores resultados en los modelos de vídeo)

> A 3D voxel world in the style of block-building sandbox games, rendered with realistic shaders: an island
> made of 1x1 m cubic blocks surrounded by a turquoise ocean with animated waves, Fresnel reflections and sun
> glints. Terraced grass, dirt and stone hills, snow-capped mountains, forests of cubic oak trees with
> translucent leaves, a wooden cabin with glowing lanterns. Crisp 16x16 pixel-art textures (nearest-neighbour,
> no blur), soft ambient occlusion in block corners, real-time dynamic shadows, atmospheric fog, flat blocky
> clouds drifting, square sun with warm bloom at sunrise, cinematic color grading, subtle vignette.
> Aerial camera, 16:9, ultra detailed, 8K, "Minecraft with BSL/SEUS shaders" look.

**Negative prompt:** `blurry textures, smooth round shapes, realistic humans, text artifacts, watermark, low poly mush, fisheye distortion`

---

## 2. Prompt del vídeo completo (5+ minutos, 16:9)

Los generadores de vídeo actuales producen clips de 5 a 20 s, así que el vídeo largo se hace **escena a escena**
con el mismo estilo y personaje, y luego se monta. Pon siempre este **bloque de estilo** delante de cada escena:

> **ESTILO (repetir en cada clip):** vídeo cinematográfico 16:9 en 4K/1080p, 24 fps, mundo de vóxeles estilo
> Minecraft con shaders (sombras dinámicas, oclusión ambiental, bloom, agua reflectante, niebla volumétrica),
> texturas pixel-art nítidas de 16x16. Protagonista: un héroe de bloques con pelo castaño, camiseta turquesa,
> pantalón azul y una espada de diamante cian brillante. Movimientos de cámara suaves tipo dron y planos de
> acción en tercera y primera persona. Sin texto ni marcas de agua.

### Guion por escenas (duración total ≈ 5:35)

| # | Tiempo | Prompt de la escena |
|---|--------|---------------------|
| 1 | 0:00–0:12 | Amanecer naranja sobre una isla de vóxeles; la cámara vuela en círculo alto sobre la pradera central, rodeada de montañas nevadas y océano brillante. Aparece el logotipo de piedra "BLOCKCRAFT – La Leyenda de la Dragona". |
| 2 | 0:12–0:40 | Vuelos de dron: sobre los bosques cúbicos, rasante sobre el mar con reflejos del sol, y bajada lenta hasta una cabaña de madera con farolillos donde espera el héroe. |
| 3 | 0:40–1:15 | De día: el héroe camina hasta un roble y lo tala a puñetazos (partículas de madera, bloques que desaparecen y las hojas quedan flotando). En una mesa de trabajo aparece girando una espada de diamante brillante que vuela a su mano. Plano en primera persona mirando la espada. |
| 4 | 1:15–1:32 | Timelapse de atardecer a noche: cielo naranja y luego estrellado con luna cuadrada; luciérnagas; zombis verdes emergen de la tierra en la pradera. |
| 5 | 1:32–1:55 | Combate nocturno: tres zombis se acercan con los brazos extendidos; el héroe los derrota con tajos de espada (destellos de crítico, retroceso, se tiñen de rojo y desaparecen en humo). Alternar tercera y primera persona. |
| 6 | 1:55–2:13 | Un esqueleto arquero en una colina dispara flechas; dos fallan y se clavan en la hierba, una impacta (pantalla con viñeta roja). El héroe corre colina arriba y lo destruye. |
| 7 | 2:13–2:32 | Un monstruo verde explosivo se acerca por la espalda en silencio, parpadea en blanco, se hincha y explota: bola de fuego, humo, cráter de bloques, el héroe sale despedido. |
| 8 | 2:32–2:48 | Una araña negra de ojos rojos salta desde la oscuridad; el héroe la vence y levanta la espada victorioso. Aviso de logro "Cazador de monstruos". |
| 9 | 2:48–3:20 | Amanecer: el héroe construye bloque a bloque un marco de obsidiana, lo enciende con pedernal y se llena de un remolino morado brillante. Entra en el portal: distorsión en espiral y destello blanco. |
| 10 | 3:20–3:38 | Dimensión del Fin: isla flotante de piedra amarillenta en un vacío violeta con nebulosas; pilares de obsidiana coronados por cristales rosas que giran. Una enorme dragona negra de ojos morados sobrevuela y ruge. Aparece la barra "DRAGONA DEL FIN". |
| 11 | 3:38–4:00 | El héroe dispara flechas con el arco a los seis cristales: cada uno explota con fuego rosa, mientras los rayos curativos hacia la dragona se cortan. |
| 12 | 4:00–4:35 | La dragona se lanza en picado contra el héroe, que la esquiva; escupe una nube de aliento morado; luego se posa sobre la fuente central y el héroe la golpea una y otra vez con la espada (planos en primera persona hacia su cabeza). |
| 13 | 4:35–4:52 | Golpe crítico final con salto. La dragona se eleva, rayos de luz rosas y dorados salen de su cuerpo, se desintegra en partículas y desaparece en un destello. |
| 14 | 4:52–5:03 | Se activa el portal de salida estrellado, aparece el huevo de dragón, orbes de experiencia verdes, texto "¡VICTORIA!" y el héroe salta al portal. |
| 15 | 5:03–5:35 | Créditos finales desplazándose sobre la isla al amanecer: "BLOCKCRAFT – La Leyenda de la Dragona", reparto, música, shaders... y al final "FIN – Gracias por jugar". Fundido a negro. |

### Prompt único (para herramientas que aceptan un guion largo)

> Cinematic 16:9 4K video, 5 minutes 30 seconds, 24 fps, voxel block world in the style of Minecraft with
> realistic shaders (dynamic shadows, ambient occlusion, bloom, reflective animated water, volumetric fog,
> crisp 16x16 pixel textures). A blocky hero with brown hair, teal shirt and a glowing diamond sword.
> Act 1 – sunrise drone flyover of a voxel island, hero chops a tree and crafts a diamond sword.
> Act 2 – night falls, zombies rise from the ground, a skeleton archer shoots arrows, a green explosive
> creature blows a crater, a red-eyed spider leaps; the hero defeats them all in third- and first-person
> combat shots with hit sparks and smoke puffs.
> Act 3 – dawn, the hero builds an obsidian portal, ignites a swirling purple vortex and jumps through.
> Act 4 – The End dimension: floating pale-stone island in a violet void, obsidian pillars with spinning pink
> crystals healing a giant black dragon with purple eyes; the hero shoots the crystals with a bow, dodges the
> dragon's dive and purple breath, strikes its head when it perches, lands a final critical hit; the dragon
> rises, bursts into beams of light and disintegrates; exit portal opens, dragon egg appears, "VICTORY!".
> Ending – scrolling end credits over the island at sunrise, "THE END – Thanks for playing", fade to black.
> Epic orchestral and chiptune-ambient soundtrack, sword swooshes, monster growls, explosions, dragon roars.

---

## 3. Cómo se generó el vídeo incluido (por código, sin IA de vídeo)

| Archivo | Qué hace |
|---|---|
| `src/world.js` | Genera la isla (ruido fractal), árboles, cabaña, portal, cráter y la isla del Fin con sus pilares. |
| `src/voxel.js` | Mallado de vóxeles por caras visibles con oclusión ambiental por vértice y "versiones" de chunk para talar, construir y explotar. |
| `src/fx.js` | Shaders GLSL: cielo día/noche con sol y luna cuadrados y estrellas, nubes de bloques, agua con olas, Fresnel y especular, portales, partículas y post-procesado (bloom, FXAA, aberración cromática, viñeta, remolino del portal). |
| `src/entities.js` | Héroe, zombis, esqueleto, explosivo, araña y la dragona articulada (cuello, cola y alas). |
| `src/story.js` | El guion: todos los tiempos, posiciones, golpes, daños, logros y créditos. |
| `src/main.js` | Dirección: coreografía, cámaras, luz, HUD y `renderAt(t)` (cada fotograma es función pura del tiempo). |
| `src/hud.js` | Interfaz pixelada: corazones, barra de objetos, logros, barra del jefe, títulos y créditos. |
| `audio.py` | Música por capítulos y efectos sincronizados con los eventos del guion (numpy). |
| `render.cjs` | Renderiza fotogramas en Chromium headless y los envía a ffmpeg. |
| `build.sh` | Render paralelo por segmentos + banda sonora + montaje final. |

```bash
cd voxel-video
npm install                 # three.js
./build.sh                  # -> blockcraft_1080p.mp4  (FPS=30 ./build.sh para 30 fps)
node render.cjs --w 960 --h 540 --stills 50 143.5 260   # fotogramas sueltos para revisar
```

Requisitos: Node 18+, Playwright con Chromium, Python 3 con numpy y ffmpeg con libx264.
