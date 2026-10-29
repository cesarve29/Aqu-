#!/usr/bin/env bash
# Renderiza las 26 escenas (10 s c/u, 1920x1080 a 60 fps) en renders/scene_XX.mp4.
# Las escenas ya renderizadas se saltan, asi que se puede reanudar.
cd "$(dirname "$0")"
mkdir -p renders
for i in $(seq ${1:-1} ${2:-26}); do
  out=renders/scene_$(printf %02d $i).mp4
  [ -s "$out" ] && continue
  a=$(( (i - 1) * 10 )); b=$(( i * 10 ))
  node render.cjs range $a $b "$out.tmp.mp4" 60 2>&1 | grep -v "Shadow\|init ms" | tail -n 3
  mv "$out.tmp.mp4" "$out"
done
echo "TODAS LAS ESCENAS LISTAS"
