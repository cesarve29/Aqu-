# Jardín Lumen · El golem dormido

Plano FPV continuo de 60 s (más 3.5 s de tarjeta final) generado proceduralmente en **Blender 5.3** con Cycles.
La cámara entra por un cañón de roca cubierto de musgo, sale a un cráter con miles de flores
bioluminiscentes azul neón y rosa, y termina frente a un golem de roca con musgo cubierto de las
mismas flores, que abre los ojos. Sin música: solo efectos de sonido (ElevenLabs, una toma de cada uno).

**Video final:** [`lumen_garden_AISTUDIO3D_1080p.mp4`](lumen_garden_AISTUDIO3D_1080p.mp4) (63.5 s, 1920×1080, H.264 + AAC).

## Archivos

| Archivo | Qué hace |
|---|---|
| `build_garden.py` | Construye toda la escena (terreno, rocas, golem, flores con Geometry Nodes, luces, cámara FPV, compositor) y guarda `lumen_garden.blend` |
| `render_final.py` | Render de la animación a `frames/lg_####.png` (reanudable; `--gpu` para usar GPU) |
| `render_watchdog.sh` | Relanza el render si Blender se cae, hasta tener los 1440 cuadros |
| `render_stills.py` | Cuadros de prueba a resolución/muestras reducidas |
| `mix_sfx.py` | Mezcla los 8 efectos de `audio/` sincronizados con la cámara |
| `encode.sh` | Escala, letterbox 2.39:1 en 16:9, grano, títulos, tarjeta AISTUDIO3D y audio |

## Reproducir

```bash
blender -b --factory-startup -P build_garden.py
./render_watchdog.sh                       # o: blender -b lumen_garden.blend -P render_final.py -- --gpu
python3 mix_sfx.py audio sfx.wav
./encode.sh frames sfx.wav lumen_garden_1080p.mp4 20
```

Render en este entorno (4 núcleos de CPU, sin GPU): 1440×603, 8 muestras + OIDN, ~25–28 s por cuadro (~10.5 h).
Con una GPU tipo RTX 3070 (OptiX) se estima ~2–4 s por cuadro.
