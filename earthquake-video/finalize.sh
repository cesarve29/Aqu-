#!/bin/bash
# Concatenate rendered chunks and mux the soundtrack.
cd "$(dirname "$0")"
ls parts/p*.mp4 | sort | sed "s/^/file '/; s/$/'/" | sed "s#file 'parts/#file '#" > parts/list.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i parts/list.txt -c copy parts/video_only.mp4
ffmpeg -y -loglevel error -i parts/video_only.mp4 -i audio/soundtrack_vertical.wav -c:v copy -c:a aac -b:a 256k -shortest -movflags +faststart terremoto_magnitud_10.mp4
ffprobe -v error -show_entries format=duration,size -of default=nw=1 terremoto_magnitud_10.mp4
