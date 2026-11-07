#!/usr/bin/env bash
# Monta la intro: cortes MUY breves del tráiler + animación del logo.
#
# Uso:
#   ./montar-intro.sh <16x9|9x16> <video_trailer> <seg1> [seg2] [seg3] ...
#   Ej: ./montar-intro.sh 16x9 trailer.mp4 12.5 47 63.2 88
#
# Cada segundo indicado se convierte en un corte de DUR segundos (0.4 por defecto)
# con destello de neón. Resultado: ../intro/intro-<formato>.mp4
set -euo pipefail
FMT=$1; SRC=$2; shift 2
DUR=${DUR:-0.4}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/../intro/intro-$FMT.mp4"
LOGO="$HERE/../intro/intro-logo-$FMT.mp4"
if [ "$FMT" = "16x9" ]; then W=1920; H=1080; else W=1080; H=1920; fi
TMP=$(mktemp -d)
i=0; list=""
for T in "$@"; do
  ffmpeg -loglevel error -y -ss "$T" -i "$SRC" -t "$DUR" \
    -vf "scale=$W:$H:force_original_aspect_ratio=increase,crop=$W:$H,fps=30,eq=saturation=1.35:contrast=1.08,colorbalance=rs=.12:bs=.12,fade=in:st=0:d=0.08:color=white,format=yuv420p" \
    -af "volume=0.8,afade=in:st=0:d=0.03,afade=out:st=$(awk "BEGIN{print $DUR-0.05}"):d=0.05,aresample=48000,aformat=channel_layouts=stereo" \
    -c:v libx264 -crf 18 -c:a aac -b:a 192k "$TMP/c$i.mp4"
  list="$list -i $TMP/c$i.mp4"; i=$((i+1))
done
pre=""; inputs=""
for j in $(seq 0 $((i))); do pre="$pre[$j:v]setsar=1,fps=30[v$j];"; inputs="$inputs[v$j][$j:a]"; done
ffmpeg -loglevel error -y $list -i "$LOGO" \
  -filter_complex "${pre}${inputs}concat=n=$((i+1)):v=1:a=1[v][a]" -map "[v]" -map "[a]" \
  -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a aac -b:a 192k "$OUT"
rm -rf "$TMP"
echo "Listo: $OUT"
