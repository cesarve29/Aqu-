# Luna en bloques (motor voxel propio)

Animación 1920×1080 de 20 s, sin audio. Muestra la luna sonriente en bloques sobre un poblado japonés de estilo anime.
Todo está hecho con código, sin Blender: un trazador de rayos voxel en GLSL (OpenGL 4.5 sin ventana) con efectos de shader pack.
Los efectos son sombras de la luna, AO suave, luz de bloques y de cielo, reflejos en el agua, niebla, bloom y gradación de color.

| Script | Qué hace |
|---|---|
| `make_texturepack.py` | Genera el texture pack anime propio de 32×32 en `texturepack/`, con bloques, caras y kimonos |
| `voxel_moon.py` | Voxeliza la luna de la referencia y la guarda en `assets/moon_vox.npz` |
| `world_gen.py` | Genera el mundo y la luz propagada estilo Minecraft, y lo guarda en `assets/world.npz` |
| `shaders/voxel.frag` | Shader de trazado de rayos voxel |
| `engine.py` | Sube el mundo a la GPU y aplica pétalos, bloom y tonemap |
| `scene.py` | Anima la cámara, la luna, los aldeanos, la hoguera y los pétalos |
| `render.py` | Renderiza: `python3 render.py all` crea los fotogramas en `frames/` |

Requiere `pip install moderngl numpy scipy pillow`. El vídeo se monta con ffmpeg a partir de `frames/`.
