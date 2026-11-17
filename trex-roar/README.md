# T-Rex rugiendo a cámara (Blender 5.3, vertical 9:16)

Plano de 15 s (360 fotogramas a 24 fps, 1080×1920) generado **100 % por código**
con Blender 5.3 (`bpy`) y Cycles: un T-Rex con cicatrices de garra sale de la
bruma de un bosque a contraluz, da un paso hacia la cámara y le ruge; la cámara
(en mano) tiembla levemente con la pisada y el rugido.

| Archivo | Qué es |
|---|---|
| `trex_roar_1080x1920.mp4` | Vídeo final (con audio sintetizado) |
| `stills/` | Dos fotogramas del vídeo |
| `trex_roar.blend` | Escena completa, lista para abrir en Blender 5.3 |
| `build_scene.py` | Construye toda la escena y guarda el `.blend` |
| `trex_sdf.py` | Modelado del T-Rex como campo de distancias + *marching cubes* |
| `trex_build.py` | Dientes, garras, ojos, saliva, esqueleto, pesos y materiales (piel con escamas y heridas de garra) |
| `forest.py` | Terreno, coníferas, árboles de hoja, helechos, hierba, rocas, motas de polvo |
| `animate.py` | Actuación del T-Rex (FK + IK analítica de patas) y cámara en mano con temblor |
| `render.py` / `encode.sh` | Render de fotogramas y montaje con ffmpeg |
| `make_audio.py` | Banda sonora sintetizada (rugido, pisada, ambiente) sin samples |

## Reproducir

```bash
pip install bpy==5.3.0 numpy scipy scikit-image
python3 build_scene.py trex_roar.blend            # ~4 min (incluye hornear el fondo lejano)
python3 render.py trex_roar.blend frames 1 360 1 --pct 60
python3 make_audio.py trex_roar.wav
./encode.sh frames trex_roar.wav trex_roar_1080x1920.mp4
```

## Notas técnicas

- **Detalle de piel**: escamas por Voronoi (relieve + suciedad en las grietas),
  pliegues esculpidos en el propio campo de distancias y 11 grupos de marcas de
  garra (triples surcos paralelos); las del lado derecho son recientes (carne
  roja y húmeda) y el resto cicatrices viejas.
- **Luz**: sol bajo detrás del animal (contraluz), relleno frío desde cámara,
  bruma matinal y *bloom* en composición.
- **Render en CPU**: el bosque lejano (> 30 m) se traza una sola vez a un
  panorama HDR que hace de fondo y luz ambiente; el dinosaurio, el terreno, la
  vegetación cercana y los árboles próximos son 3D en cada fotograma.
  El vídeo entregado se renderizó al 60 % (648×1152) y se reescaló a 1080×1920.
  Con GPU basta con `--pct 100` (y más muestras) para Full HD vertical nativo;
  `build_scene.py --live-haze` activa niebla volumétrica real en el claro.
- La cámara, el foco y la focal están animados fotograma a fotograma
  (`CameraHandheld`); la intensidad del temblor sale de `animate.shake_env()`.
