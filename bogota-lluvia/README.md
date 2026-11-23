# Bogotá bajo la lluvia · Torre Colpatria

Plano continuo de 60 s generado en **Blender 5.3** (Cycles) a partir de datos reales del centro de Bogotá.
La cámara avanza por la Carrera 7 bajo la lluvia en la hora azul, llega a la Torre Colpatria, sube pegada a
su fachada iluminada, cruza por encima de la azotea y termina mirando la ciudad con los cerros orientales y
Monserrate al fondo. Abre con el título **COLOMBIA** (amarillo, azul y rojo) y
"Bogotá · Centro de la ciudad · Torre Colpatria"; cierra con un fundido a negro. Sin música: solo efectos de
sonido (ElevenLabs, una toma de cada uno).

**Video final:** [`bogota_lluvia_1080p.mp4`](bogota_lluvia_1080p.mp4) (60 s, 1920×1080, letterbox 2.39:1, H.264 + AAC).

## Archivos

| Archivo | Qué hace |
|---|---|
| `fetch_osm.sh` | Descarga el centro de Bogotá de OpenStreetMap en 49 teselas |
| `parse_osm.py` | Une las teselas y extrae edificios, vías y áreas en metros locales → `data/city.json` |
| `fetch_dem.py` | Descarga el relieve (AWS Terrain Tiles) → `data/dem.npz` |
| `build_bogota.py` | Construye la escena: terreno, ~4700 edificios con alturas reales o estimadas, Torre Colpatria con su iluminación LED, vías con marcas y postes, ~6900 vehículos animados (carros, taxis, SITP, TransMilenio), cerros, nubes, árboles, lluvia, cámara y compositor. Guarda `bogota_lluvia.blend` |
| `blib.py` | Utilidades compartidas (nodos de shader, ruido, curvas) |
| `render_final.py` | Render de la animación a `frames/bg_####.png` (reanudable) |
| `render_watchdog.sh` | Relanza el render si Blender se cae, hasta tener los 1440 cuadros |
| `render_stills.py` | Cuadros de prueba a resolución/muestras reducidas |
| `make_title.py` | Genera `title.png` (COLOMBIA con los colores de la bandera) |
| `mix_sfx.py` | Mezcla los 7 efectos de `audio/` siguiendo la altura de la cámara (calle → cima) |
| `encode.sh` | Escala, letterbox, grano, título de apertura, fundidos y audio (2 pasadas) |

## Reproducir

```bash
./fetch_osm.sh && python3 parse_osm.py osm data/city.json && python3 fetch_dem.py data/dem.npz   # opcional: data/ ya incluido
blender -b --factory-startup -P build_bogota.py
./render_watchdog.sh
python3 mix_sfx.py audio sfx.wav
./encode.sh frames sfx.wav bogota_lluvia_1080p.mp4
```

Render en este entorno (4 núcleos de CPU, sin GPU): 1440×603, 10 muestras + OIDN, ~14–25 s por cuadro (~7 h).

## Créditos de datos

- Edificios y vías: © colaboradores de [OpenStreetMap](https://www.openstreetmap.org/copyright), disponible bajo la licencia ODbL.
- Relieve: [AWS Terrain Tiles](https://registry.opendata.aws/terrain-tiles/) (Mapzen; fuentes SRTM y otras).
- Efectos de sonido generados con ElevenLabs.
