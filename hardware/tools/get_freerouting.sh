#!/bin/sh
# Download the Freerouting jar used by gen_pcb.py into hardware/tools/.cache/.
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)/.cache"
VERSION="${FREEROUTING_VERSION:-v2.4.1}"
mkdir -p "$DIR"
if ls "$DIR"/freerouting-*.jar >/dev/null 2>&1; then echo "have $(ls "$DIR"/freerouting-*.jar)"; exit 0; fi
gh release download "$VERSION" -R freerouting/freerouting --pattern 'freerouting-*.jar' -D "$DIR"
ls "$DIR"/freerouting-*.jar
