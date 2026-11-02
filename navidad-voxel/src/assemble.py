"""Join the rendered chunks with the soundtrack into the final YouTube video."""
import os
import subprocess
import story
from engine import BUILD, ROOT
from render import OUT, nframes, CHUNK, scene_by_name

VIDEO_DIR = os.path.join(ROOT, "video")
os.makedirs(VIDEO_DIR, exist_ok=True)


def main():
    parts = []
    for s in story.SCENES:
        name = s[0]
        whole = os.path.join(OUT, "scenes", name + ".mp4")
        if os.path.exists(whole):
            parts.append(whole)
            continue
        sc = scene_by_name(name)
        n = nframes(sc)
        for k in range((n + CHUNK - 1) // CHUNK):
            p = os.path.join(OUT, "chunks", "%s_%03d.mp4" % (name, k))
            if not os.path.exists(p):
                raise SystemExit("missing " + p)
            parts.append(p)
    lst = os.path.join(BUILD, "concat.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write("file '%s'\n" % p)
    video_only = os.path.join(BUILD, "video_only.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", video_only], check=True)
    final = os.path.join(VIDEO_DIR, "tilo_y_la_estrella_del_alba_1080p60.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video_only, "-i", os.path.join(BUILD, "mix_final.wav"),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
                    "-shortest", "-movflags", "+faststart", final], check=True)
    print("final", final, os.path.getsize(final) / 1e6, "MB")
    # GitHub rejects files over 100 MB: store the video as numbered parts plus join scripts
    pdir = os.path.join(VIDEO_DIR, "partes")
    os.makedirs(pdir, exist_ok=True)
    for f in os.listdir(pdir):
        os.remove(os.path.join(pdir, f))
    base = os.path.basename(final)
    subprocess.run(["split", "-b", "90M", "-d", "-a", "2", final, os.path.join(pdir, base + ".parte")], check=True)
    parts = sorted(f for f in os.listdir(pdir) if ".parte" in f)
    with open(os.path.join(pdir, "unir_video.sh"), "w") as f:
        f.write("#!/bin/sh\n# Une las partes en el video completo\ncd \"$(dirname \"$0\")\"\ncat %s > ../%s\necho Listo: ../%s\n" % (" ".join(parts), base, base))
    with open(os.path.join(pdir, "unir_video.bat"), "w") as f:
        f.write("@echo off\r\nREM Une las partes en el video completo\r\ncd /d %%~dp0\r\ncopy /b %s ..\\%s\r\necho Listo\r\npause\r\n" % ("+".join(parts), base))
    os.chmod(os.path.join(pdir, "unir_video.sh"), 0o755)
    print("parts", parts)


if __name__ == "__main__":
    main()
