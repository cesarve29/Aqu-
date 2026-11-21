# NEON RUSH

Cortometraje cinematográfico de ~65 s (16:9, 1080p, 24 fps) generado 100 % por código en **Blender 5.3**:
un dron de carreras despierta en una azotea bajo la lluvia, se lanza al vacío, persigue el tráfico
volador por una avenida de neón, gira bajo un puente en cámara lenta y asciende hasta una torre
monumental donde se enciende el letrero **NEON RUSH**.

## Tomas

| # | Cuadros | Toma | Técnica de cámara |
|---|---------|------|-------------------|
| S1 | 0–191 | Establecimiento | Grúa descendente sobre la ciudad con niebla |
| S2 | 192–359 | Azotea | Macro 50 mm f/1.8, *rack focus* de la ciudad al dron, encendido de LEDs |
| S3 | 360–527 | Despegue y clavado | Seguimiento con resorte, plano holandés, vértigo por la fachada |
| S4a | 528–671 | Persecución | Cámara de persecución 24 mm con vibración de alta velocidad |
| S4b | 672–815 | Seguimiento lateral | Teleobjetivo 38 mm, paralaje con letreros |
| S5 | 816–959 | Puente | *Speed ramp* a cámara lenta + *barrel roll* de 360° del dron y la cámara |
| S6 | 960–1127 | Frontal | Cámara volando hacia atrás, el dron la rebasa, *whip pan* |
| S7 | 1128–1343 | Ascenso | Contrapicado y grúa orbital siguiendo la subida |
| S8 | 1344–1487 | Revelación | Silueta frente al letrero y *pull-back* hasta la vista de la ciudad |

Después vienen 3.5 s de tarjeta de título (ffmpeg).

## Archivos

- `build_scene.py` — genera toda la escena y guarda `neon_rush.blend` (ciudad, dron, tráfico, lluvia con Geometry Nodes, letreros, cámaras, compositor con niebla, bloom y aberración cromática).
- `neon_rush.blend` — la escena lista para abrir o renderizar.
- `render_final.py` / `render_watchdog.sh` — render reanudable (salta cuadros existentes).
- `render_stills.py` — cuadros sueltos de prueba.
- `audio/` — una toma de música y de cada efecto generados con **ElevenLabs** (Music v2.5 y Sound Effects v3).
- `mix_audio.py` — edita la música por compases (el *drop* cae en el corte de la persecución) y sincroniza los efectos con cada toma.
- `soundtrack.py` — banda sonora alternativa 100 % sintetizada con numpy (no se usa en el video final).
- `encode.sh` — escala, barras 2.39:1 dentro de 16:9, grano, viñeta, textos, título y audio.

## Reproducir

```bash
blender -b --factory-startup -P build_scene.py          # regenera neon_rush.blend
./render_watchdog.sh                                     # CPU: 1600x670, 12 muestras (~15 s/cuadro, 4 núcleos)
python3 mix_audio.py audio soundtrack.wav
./encode.sh frames soundtrack.wav neon_rush_1080p.mp4
```

### En una PC con NVIDIA RTX (p. ej. 3070)

```bash
blender -b neon_rush.blend -P render_final.py -a -- --gpu
```

Usa OptiX, 1920×804 nativo, 128 muestras y light tree. Calcula unos 10–20 s por cuadro en una RTX 3070.
