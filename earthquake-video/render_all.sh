#!/bin/bash
# Render the film in independent chunks (2 in parallel), then concatenate.
cd "$(dirname "$0")"
mkdir -p parts
CHUNKS="0:360 360:720 720:1080 1080:1440 1440:1800 1800:2160 2160:2520 2520:2880 2880:3240 3240:3600 3600:3960 3960:4284"
echo $CHUNKS | tr ' ' '\n' | xargs -P ${JOBS:-2} -I{} bash -c 'a=${1%%:*}; b=${1##*:}; f=parts/p$(printf %05d $a).mp4; [ -s $f ] || node render.js $a $b $f > parts/log_$a.txt 2>&1' _ {}
