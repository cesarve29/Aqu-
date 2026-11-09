#!/bin/bash
# Horizontal 1920x1080 @ 30 fps, full 2:22 cut.
cd "$(dirname "$0")"
mkdir -p parts_h
CHUNKS="0:540 540:1065 1065:1470 1470:1880 1880:2290 2290:2670 2670:3030 3030:3360 3360:3720 3720:4260"
echo $CHUNKS | tr ' ' '\n' | xargs -P ${JOBS:-2} -I{} bash -c 'a=${1%%:*}; b=${1##*:}; f=parts_h/p$(printf %05d $a).mp4; [ -s $f ] || MODE=h node render.js $a $b $f > parts_h/log_$a.txt 2>&1' _ {}
ls parts_h/p*.mp4 | sort | sed "s#^parts_h/#file '#; s/$/'/" > parts_h/list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i parts_h/list.txt -c copy parts_h/video_only.mp4
ffmpeg -y -loglevel error -i parts_h/video_only.mp4 -i audio/soundtrack.wav -c:v copy -c:a aac -b:a 256k -shortest -movflags +faststart terremoto_magnitud_10_horizontal.mp4
