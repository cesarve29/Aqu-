#!/bin/bash
# usage: dl.sh list.tsv   (name session generation signature)
cd "$(dirname "$0")/sfx"
while read -r name ses gen sig; do
  [ -z "$name" ] && continue
  [ -f "$name.mp3" ] && continue
  curl -sS -o "$name.mp3" "https://elevenlabsusercontent.com/database/workspace/77c625cb4a5448d3add0700bfae30613/content_generation/$ses/$gen/content.mp3?Expires=1795410000&KeyName=assets-cdn-key-1&Signature=$sig" && echo "ok $name"
done < "$1"
