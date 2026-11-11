#!/bin/sh
# One command, in a fresh Ubuntu 24.04 shell (a GitHub Codespace works): installs the m68k toolchain, fetches the pinned
# Mutable Instruments sources, proves Peaks and Sheep on the host, generates the tweak "macro-acid-ext-tg" and builds
# the test firmware. Your official files go in firmware/ first (git-ignored, never commit them):
#     firmware/model-cycles_OS1.13.syx   firmware/Syntakt_OS1.42.syx
# Everything is logged in build/ext/. Nothing is flashed, committed or pushed.
set -e
cd "$(dirname "$0")/.."
LOG=build/ext; mkdir -p "$LOG" build
CY=firmware/model-cycles_OS1.13.syx; ST=firmware/Syntakt_OS1.42.syx
[ -f "$CY" ] || { echo "!! $CY missing"; exit 1; }
[ -f "$ST" ] || { echo "!! $ST missing"; exit 1; }
echo "== 1/6 toolchain"
if ! command -v m68k-linux-gnu-g++ >/dev/null; then
  sudo apt-get update -qq && sudo apt-get install -y -qq g++-m68k-linux-gnu binutils-m68k-linux-gnu
fi
m68k-linux-gnu-g++ --version | head -1
python3 -c "import unicorn, numpy" 2>/dev/null || python3 -m pip install --quiet --break-system-packages unicorn numpy 2>&1 | tail -1 || true
echo "== 2/6 Mutable Instruments sources at the pinned commit"
if [ ! -d vendor/eurorack/.git ]; then
  mkdir -p vendor
  git clone -q https://github.com/pichenettes/eurorack vendor/eurorack
fi
git -C vendor/eurorack checkout -q 08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4
git -C vendor/eurorack submodule update --init stmlib
echo "== 3/6 host proofs against the original Peaks and Tides code"
tools/check_peaks_host.sh vendor/eurorack > "$LOG/peaks_host.log" 2>&1 || { tail -20 "$LOG/peaks_host.log"; echo "!! Peaks host proof failed"; exit 1; }
tail -1 "$LOG/peaks_host.log"
tools/check_sheep_host.sh vendor/eurorack > "$LOG/sheep_host.log" 2>&1 || { tail -20 "$LOG/sheep_host.log"; echo "!! Sheep host proof failed"; exit 1; }
tail -1 "$LOG/sheep_host.log"
echo "== 4/6 baseline: the stock OS still builds with the same MAIN OS hash"
python3 tools/build.py -i "$CY" --syntakt "$ST" --os -o build/baseline.syx > "$LOG/baseline.log" 2>&1 || { tail -20 "$LOG/baseline.log"; echo "!! baseline build failed"; exit 1; }
grep "SHA-256" "$LOG/baseline.log" | head -2
echo "== 5/6 generate the tweak"
python3 tools/gen_macro_ext.py --cycles "$CY" --eurorack vendor/eurorack > "$LOG/gen.log" 2>&1 || { tail -40 "$LOG/gen.log"; echo "!! generator failed (full log: $LOG/gen.log)"; exit 1; }
tail -3 "$LOG/gen.log"
echo "== 6/6 build the test firmware (the OS recipe, the five engines replaced by macro-acid-ext-tg)"
LIST=$(python3 - <<'PY'
import json
o = json.load(open("os.json"))
ids = [t["id"] if isinstance(t, dict) else t for t in o["tweaks"]]
ids = [i for i in ids if not i.startswith("syntakt-tg-")] + ["macro-acid-ext-tg"]
print(",".join(ids))
PY
)
echo "tweaks: $LIST"
python3 tools/build.py -i "$CY" --syntakt "$ST" -t "$LIST" -o build/Peaks-Sheep-Model-Cycles-Test.syx > "$LOG/build.log" 2>&1 || { tail -30 "$LOG/build.log"; echo "!! firmware build failed (full log: $LOG/build.log)"; exit 1; }
tail -8 "$LOG/build.log"
echo
echo "Done. Test firmware: build/Peaks-Sheep-Model-Cycles-Test.syx (experimental: not tested on a Model:Cycles)."
