#!/bin/bash
# Render the film in independent chunks (2 in parallel), then concatenate.
cd "$(dirname "$0")"
mkdir -p parts
CHUNKS="0:540 540:1065 1065:1470 1470:1880 1880:2290 2290:2670 2670:3030 3030:3360 3360:3720 3720:4260"
echo $CHUNKS | tr ' ' '\n' | xargs -P ${JOBS:-2} -I{} bash -c 'a=${1%%:*}; b=${1##*:}; f=parts/p$(printf %05d $a).mp4; [ -s $f ] || node render.js $a $b $f > parts/log_$a.txt 2>&1' _ {}
