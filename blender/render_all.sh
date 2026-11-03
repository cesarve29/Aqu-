#!/bin/bash
# Render completo y REANUDABLE del corto.
# Cada tramo de 48 fotogramas se codifica a MP4 y se sube a git, así que si la
# sesión o el contenedor se reinician, basta con volver a lanzar este script:
# salta los tramos que ya existen en chunks/.
set -u
cd "$(dirname "$0")"
BRANCH=${BRANCH:-ccr-cda9c777-24izn1}
SAMPLES=${SAMPLES:-32}
CHUNK=48
declare -A LEN=([1]=240 [2]=288 [3]=312 [4]=360 [5]=240)

# dependencias (por si el contenedor es nuevo)
python3 -c "import bpy" 2>/dev/null || pip install -q bpy==5.2.3
ldconfig -p | grep -q libEGL.so.1 || { apt-get update -q >/dev/null; apt-get install -y -q libegl1 libegl-mesa0 libgl1-mesa-dri libgles2 >/dev/null; }

push() {
  for d in 0 2 4 8 16; do
    sleep $d
    git push -q -u origin "$BRANCH" && return 0
  done
  return 1
}

mkdir -p chunks frames
for shot in 1 2 3 4 5; do
  n=${LEN[$shot]}
  for ((a=1; a<=n; a+=CHUNK)); do
    b=$((a+CHUNK-1)); ((b>n)) && b=$n
    out=chunks/s${shot}_$(printf %04d $a).mp4
    [ -f "$out" ] && continue
    tmp=frames/s${shot}
    echo "[$(date +%H:%M:%S)] plano $shot fotogramas $a-$b"
    python3 film.py --shot $shot --frames $a-$b --outdir $tmp --samples $SAMPLES 2>&1 | grep -E "RENDERED|Error|Traceback"
    cnt=$(ls $tmp/*.png 2>/dev/null | awk -F/ -v a=$a -v b=$b '{f=$NF+0} f>=a && f<=b' | wc -l)
    if [ "$cnt" -ne $((b-a+1)) ]; then echo "faltan fotogramas en $shot $a-$b"; exit 1; fi
    ffmpeg -y -loglevel error -framerate 24 -start_number $a -i $tmp/%04d.png \
      -frames:v $((b-a+1)) -c:v libx264 -crf 15 -preset slow -pix_fmt yuv420p "$out" || exit 1
    for ((f=a; f<=b; f++)); do rm -f $tmp/$(printf %04d $f).png; done
    git add "$out" && git commit -q -m "Render: plano $shot fotogramas $a-$b" && push
  done
done
echo "[$(date +%H:%M:%S)] render terminado"
./finalize.sh && git add final && git commit -q -m "Render final del corto con audio y subtitulos" && push
