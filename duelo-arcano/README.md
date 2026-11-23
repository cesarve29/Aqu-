# El Duelo Arcano

Animación cinematográfica de **60 s en una sola toma** hecha íntegramente por código en
**Blender 5.3** (Cycles) con efectos de sonido generados con **ElevenLabs** (SFX v3).

Un mago malvado (capucha con vacío negro y ojos magenta, cuello de picos, ribetes de neón)
conjura un **orbe de vacío con reborde neón**, lo carga absorbiendo partículas, rayos y rocas
levitando, y lo lanza contra una guardiana que lo bloquea con un **escudo hexagonal cian**.

- Resultado: `duelo_arcano_1080p.mp4` (1920×1080, 24 fps, 60 s, audio AAC 320 kbps).
- Plan de la toma y tiempos: [`PLAN.md`](PLAN.md).

## Cómo se construye

```bash
B=/ruta/a/blender-5.3.0/blender
$B -b --factory-startup -P scene/build.py        # genera duelo.blend (~15 s)
./render_all.sh                                  # render reanudable en 12 bloques de 120 fotogramas
python3 audio/select.py                          # elige la mejor variación de cada efecto
./assemble.sh                                    # mezcla el audio y une los segmentos
```

| Archivo | Qué hace |
|---|---|
| `scene/timeline.py` | Fuente única de tiempos: eventos, trayectoria del orbe, carga, empuje del escudo. Lo usan imagen y sonido. |
| `scene/environment.py` | Cielo procedural (nubes, luna, relámpagos), terreno con losas mojadas, monolitos, trilito, montañas. |
| `scene/characters.py` | Mago y guardiana: túnicas por lathe/loft, capucha, cuello, mangas, manos con Skin modifier, esqueleto con IK, materiales con ribete neón. |
| `scene/anim.py` | Coreografía: manos que siguen al orbe, lanzamiento, escudo, retroceso; cabeza con seguimiento; aleteo de tela. |
| `scene/fx.py` | Orbe de vacío, círculo rúnico que se dibuja, escudo hexagonal con ondas, rocas que levitan, ondas expansivas, luces mágicas. |
| `scene/fx_runtime.py` | Efectos por fotograma deterministas: partículas absorbidas, chispas orbitales, rayos, estela, chispas balísticas, fragmentos, ascuas, polvo, escombros, disolución del escudo, llama. |
| `scene/camera.py` | La toma única: trayectoria suavizada, seguimiento del proyectil, cámara en mano, sacudidas, foco dinámico, fundidos. |
| `scene/comp.py` | Niebla por profundidad, blur por vectores, bloom, destellos anamórficos, dispersión de lente, viñeta y gradación. |
| `audio/mix.py` | 30 cues de ElevenLabs sincronizados con el timeline, normalizados por clip y masterizados a −16 LUFS lineal. |

## Render

Cycles CPU, 10 muestras adaptativas + OIDN, AgX Punchy. Las luces mágicas son lámparas
explícitas y las superficies emisivas no se muestrean como luces, lo que reduce el ruido y
el tiempo (~50 s por fotograma en 4 núcleos).
