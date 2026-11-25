#!/bin/bash
# Builds the soundtrack: 6 s reverse-swell intro (made from the song's own
# drop, reversed and filtered) followed by the full song.
set -e
cd "$(dirname "$0")"
ffmpeg -y -v error -ss 52.4 -t 6.0 -i song.mp3 -ar 48000 -ac 2 \
  -af "areverse,highpass=f=70,lowpass=f=1400,volume=-5dB,afade=t=in:st=0:d=5.6:curve=exp,afade=t=out:st=5.88:d=0.12" intro.wav
ffmpeg -y -v error -i song.mp3 -ar 48000 -ac 2 song.wav
ffmpeg -y -v error -i intro.wav -i song.wav -filter_complex "[0:a][1:a]concat=n=2:v=0:a=1[a]" -map "[a]" -c:a pcm_s16le soundtrack.wav
rm -f intro.wav song.wav
ffprobe -v error -show_entries format=duration -of csv=p=0 soundtrack.wav
