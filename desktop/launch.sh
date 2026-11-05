#!/usr/bin/env sh
# Otevře CheckIn v samostatném okně (bez panelu adres). Vyžaduje nainstalovaný Chrome, Chromium nebo Edge.
# Použití: CHECKIN_URL=http://localhost:8080 ./launch.sh
URL="${CHECKIN_URL:-http://localhost:8080}"
PROFILE="${CHECKIN_PROFILE:-$HOME/.checkin-desktop}"

find_browser() {
  for b in google-chrome google-chrome-stable chromium chromium-browser microsoft-edge msedge; do
    if command -v "$b" >/dev/null 2>&1; then echo "$b"; return; fi
  done
  if [ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
    echo "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; return
  fi
  if [ -x "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge" ]; then
    echo "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"; return
  fi
}

BROWSER="$(find_browser)"
if [ -z "$BROWSER" ]; then
  echo "Nenalezen Chrome, Chromium nebo Edge. Nainstalujte některý z nich." >&2
  exit 1
fi
exec "$BROWSER" --app="$URL" --user-data-dir="$PROFILE" --no-first-run --window-size=1200,820 "$@"
