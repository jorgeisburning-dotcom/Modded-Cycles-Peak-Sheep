#!/bin/sh
# Proves tools/machines/macro/peaks_glue.cc against the original Peaks drums, on the host (no Elektron file needed).
# usage: tools/check_peaks_host.sh <pichenettes/eurorack checkout, with stmlib>
set -e
MI=${1:?path to a pichenettes/eurorack checkout (with the stmlib submodule)}
HERE=$(cd "$(dirname "$0")" && pwd)
OUT=$(mktemp -d)
g++ -O1 -std=c++14 -I"$MI" -I"$HERE/machines/macro" -o "$OUT/peaks_ref" \
    "$HERE/emu/peaks_ref.cc" "$HERE/machines/macro/peaks_glue.cc" "$MI"/peaks/drums/*.cc "$MI/peaks/resources.cc" \
    "$MI/stmlib/utils/random.cc"
"$OUT/peaks_ref"
