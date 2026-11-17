#!/usr/bin/env bash
# frames + synthesised soundtrack -> vertical 1080x1920 H.264
# usage: ./encode.sh <frames_dir> <audio.wav> <out.mp4>
set -euo pipefail
FRAMES=${1:?frames dir}; AUDIO=${2:?audio wav}; OUT=${3:-trex_roar_1080x1920.mp4}
ffmpeg -y -loglevel error -framerate 24 -start_number 1 -i "$FRAMES/trex_%04d.png" -i "$AUDIO" \
  -vf "scale=1080:1920:flags=lanczos,unsharp=5:5:0.55:5:5:0.0,vignette=angle=PI/6.5,noise=alls=3:allf=t,format=yuv420p" \
  -c:v libx264 -preset slow -crf 21 -maxrate 22M -bufsize 44M -pix_fmt yuv420p -movflags +faststart \
  -c:a aac -b:a 192k -shortest "$OUT"
echo "wrote $OUT"
