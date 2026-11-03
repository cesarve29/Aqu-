#!/bin/bash
# Previa: 4 fotogramas a 1080p (2.39:1 con franjas) con la calidad final.
cd "$(dirname "$0")"
mkdir -p preview/raw
for spec in "1 225" "2 220" "3 220" "4 230"; do
  set -- $spec
  python3 film.py --shot $1 --still $2 --out preview/raw/plano$1.png --samples 64 2>&1 | grep RENDERED
  ffmpeg -loglevel error -y -i preview/raw/plano$1.png \
    -vf "vignette=PI/5,noise=alls=5:allf=u,pad=1920:1080:0:138:black" \
    preview/plano$1.jpg -q:v 2
done
