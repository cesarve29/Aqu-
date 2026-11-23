# El Duelo Arcano — plan de la toma única (60 s · 1920×1080 · 24 fps)

## Concepto
Noche de tormenta en un círculo de piedras rituales sobre una meseta. Un **mago malvado**
(capucha puntiaguda con vacío negro y ojos magenta, cuello alto con picos, túnica con
ribetes de neón magenta, manos esqueléticas con venas brillantes) conjura un **orbe de
vacío**: núcleo negro con un **reborde de neón magenta**, rodeado de partículas, arcos
eléctricos y rocas que levitan. Lo carga, lo lanza, y una **guardiana** (capa gris acero,
ribetes cian, coraza y guantelete metálicos) lo bloquea con un **escudo hexagonal** cian.

Paleta: sombras azul‑luna, magia del mago en magenta/violeta, magia defensiva en cian.

## Toma única (cámara continua, sin cortes)
| Tiempo | Fotogramas | Acción | Cámara |
|---|---|---|---|
| 0–5 s | 1–120 | Viento, ascuas, relámpago lejano. El mago inmóvil con la cabeza baja. | Plano general alto por detrás de la guardiana, desciende en grúa. |
| 5–11 s | 120–270 | Se encienden los ojos. El círculo rúnico se dibuja en el suelo. | Travelling hacia delante pasando junto al hombro de la guardiana. |
| 11–14 s | 270–336 | Alza los brazos; partículas empiezan a ser absorbidas. | Se acerca al mago, 3/4 frontal. |
| 14–23 s | 336–560 | Nace el orbe entre sus manos; espirales de partículas. | Arco lateral lento, plano medio. |
| 23–33 s | 560–800 | Eleva el orbe sobre la cabeza; crece, arcos eléctricos, rocas levitan, venas brillan. | Contrapicado, empuje hasta primer plano del orbe y la capucha. |
| 33–36 s | 800–868 | Preparación: lleva el orbe atrás sobre el hombro, se comprime. | Leve retroceso, temblor. |
| 36 s | 868–872 | LANZAMIENTO: onda de choque, ráfaga de polvo, rocas caen. | La cámara se lanza tras el proyectil. |
| 36–39.5 s | 872–950 | Vuelo con rampa de velocidad (cámara lenta a mitad). La guardiana alza la mano: el escudo hexagonal se forma celda a celda. | Travelling lateral junto al orbe, gira para encuadrar a la guardiana. |
| 39.5 s | 950 | IMPACTO: destello, onda en el escudo, chispas. | Sacudida de cámara. |
| 39.5–45.5 s | 950–1092 | Forcejeo: el orbe empuja, la guardiana retrocede, chispas continuas, el escudo parpadea; ella empuja de vuelta. | Lento empuje y órbita. |
| 45.5 s | 1092 | El orbe estalla y se desvía en fragmentos que impactan contra las piedras. | Sacudida. |
| 45.5–60 s | 1092–1440 | Ascuas caen, el escudo se disuelve en hexágonos, el mago se yergue y sus ojos destellan. Fundido a negro. | Grúa hacia atrás y arriba revelando a ambos. |

## Técnica
- Blender 5.3.0, Cycles CPU, OIDN, desenfoque de movimiento, composición con bloom (Glare),
  niebla por pase Mist, aberración cromática, viñeta y gradación de color.
- Personajes modelados por código (lathe/loft + Skin modifier), esqueleto con IK en brazos,
  pesos calculados por distancia a huesos, aleteo de tela con desplazamiento animado.
- Efectos (partículas, arcos, estela, chispas, escudo) deterministas: funciones del tiempo
  evaluadas por fotograma → nubes de puntos y curvas renderizadas nativamente por Cycles.
- Audio: capas de efectos generadas con ElevenLabs (SFX v3), mezcladas con ffmpeg y
  sincronizadas con los mismos tiempos de `scene/timeline.py`.
