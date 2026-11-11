#!/bin/sh
# Proves tools/machines/macro/sheep.h against the original Tides code, on the host (no Elektron file needed).
# usage: tools/check_sheep_host.sh <pichenettes/eurorack checkout, with stmlib>
set -e
MI=${1:?path to a pichenettes/eurorack checkout (with the stmlib submodule)}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$(mktemp -d)
g++ -O1 -std=c++14 -DWAVETABLE_HACK -I"$MI" -I"$HERE/machines/macro" -o "$OUT/sheep_ref" \
    "$HERE/emu/sheep_ref.cc" "$MI/tides/generator.cc" "$MI/tides/resources.cc"
"$OUT/sheep_ref" | tail -${TAIL:-5}
