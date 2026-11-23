#!/bin/bash
# Relaunch render_all.sh whenever it is not running, until the render is complete.
cd "$(dirname "$0")"
while ! grep -q "ALL DONE" render.log 2>/dev/null; do
  if ! pgrep -f render_all.sh > /dev/null; then
    echo "WATCHDOG relaunch $(date -u +%H:%M)" >> render.log
    setsid nohup ./render_all.sh > /dev/null 2>&1 < /dev/null &
  fi
  sleep 30
done
