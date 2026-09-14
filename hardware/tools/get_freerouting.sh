#!/bin/sh
# Download the Freerouting jar used by gen_pcb.py into hardware/tools/.cache/.
# gen_pcb.py reads the default version below (or $FREEROUTING_VERSION) and uses only that jar.
set -eu
DIR="$(cd "$(dirname "$0")" && pwd)/.cache"
# v2.2+ needs Java 25; v2.1.0 runs on Java 21 (checked 2026-09-14).
VERSION="${FREEROUTING_VERSION:-v2.1.0}"
JAR="$DIR/freerouting-${VERSION#v}.jar"
mkdir -p "$DIR"
if [ -f "$JAR" ]; then echo "have $JAR"; exit 0; fi
gh release download "$VERSION" -R freerouting/freerouting --pattern "freerouting-${VERSION#v}.jar" -D "$DIR"
ls "$JAR"
