#!/usr/bin/env bash
# Downloads OpenStreetMap data (ODbL, © OpenStreetMap contributors) for downtown Bogotá
# around Torre Colpatria, in small tiles from the main OSM API.
#   ./fetch_osm.sh OUTDIR
set -euo pipefail
OUT=${1:-osm}; mkdir -p "$OUT"
LAT0=4.5980; LAT1=4.6260; LON0=-74.0840; LON1=-74.0580; STEP=0.004
for lat in $(seq $LAT0 $STEP $(echo "$LAT1-0.0001" | bc)); do
  for lon in $(seq -- $LON0 $STEP $(echo "$LON1-0.0001" | bc)); do
    f="$OUT/tile_${lat}_${lon}.osm"
    [ -s "$f" ] && continue
    lat2=$(echo "$lat+$STEP" | bc); lon2=$(echo "$lon+$STEP" | bc)
    for try in 1 2 3 4; do
      code=$(curl -sS -m 180 -A "blender-scene-builder/1.0" -o "$f.part" -w "%{http_code}" \
        "https://api.openstreetmap.org/api/0.6/map?bbox=$lon,$lat,$lon2,$lat2" || echo 000)
      [ "$code" = 200 ] && { mv "$f.part" "$f"; break; }
      echo "tile $lat $lon: HTTP $code (try $try)"; sleep $((try*5))
    done
    sleep 1
  done
done
ls "$OUT"/*.osm | wc -l
