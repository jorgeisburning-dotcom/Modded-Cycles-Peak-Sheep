#!/usr/bin/env python3
"""Read-only probe of the official OS 1.13 for the Turing Machine wave (tools/machines/lfo_tm/DRAFT.md, [CHECK] items).

It extracts the MAIN OS from the user's own .syx into /tmp (nothing is written into the repository), then prints:
  1. where the LFO wave names and the LFO knob names are stored as text, and which 4-byte words point at them
     (the label tables the LFO page draws from);
  2. the disassembly of the LFO routine 0x40091ab2 (the wave dispatch: how many waves, where a new one could go).

    python3 tools/machines/lfo_tm/probe_lfo.py --cycles firmware/model-cycles_OS1.13.syx
"""
import argparse
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
sys.path.insert(0, str(TOOLS / "emu"))
sys.path.insert(0, str(TOOLS))

import build                        # noqa: E402
import test_sdvintage as T          # noqa: E402

BASE = build.BASE                   # 0x40000400
NAMES = ["TRI", "SIN", "SQR", "SAW", "RMP", "EXP", "RND", "S&H", "RANDOM", "SQUARE", "SINE", "WAVE", "SPD", "MULT",
         "FADE", "DEST", "SPH", "MODE", "DEP", "FREE", "TRIG", "HOLD", "ONE", "HLF"]


def find_all(data, needle):
    out, i = [], data.find(needle)
    while i >= 0:
        out.append(i)
        i = data.find(needle, i + 1)
    return out


def printable(b):
    return "".join(chr(c) if 32 <= c < 127 else "." if c else "|" for c in b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--out", default="/tmp/mainos_1.13.bin")
    args = ap.parse_args()

    stock = T.main_os_from_syx(args.cycles)
    pathlib.Path(args.out).write_bytes(stock)
    print(f"main OS: {len(stock)} bytes, loaded at {BASE:#x}, written to {args.out}\n")

    print("== 1. texts and the words that point at them ==")
    for name in NAMES:
        needle = name.encode() + b"\0"
        for off in find_all(stock, needle):
            if off and 32 <= stock[off - 1] < 127:          # inside a longer word: skip
                continue
            va = BASE + off
            ctx = stock[max(0, off - 12):off + 24]
            refs = [BASE + r for r in find_all(stock, va.to_bytes(4, "big")) if r % 2 == 0]
            print(f"{name:6} @ {va:#x}  {printable(ctx)!r}  pointed at from: {[hex(r) for r in refs[:6]]}")
    print()

    print("== 2. LFO routine 0x40091ab2 (disassembly) ==")
    for arch in ("m68k:5407", "m68k:cf", "m68k:5206e"):
        for tool in ("m68k-linux-gnu-objdump", "m68k-elf-objdump"):
            cmd = [tool, "-D", "-b", "binary", "-m", arch, f"--adjust-vma={BASE:#x}",
                   "--start-address=0x40091ab2", "--stop-address=0x40091d00", args.out]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True)
            except FileNotFoundError:
                continue
            if r.returncode == 0 and "(bad)" not in r.stdout[:2000] and r.stdout.strip():
                print(f"({tool} -m {arch})")
                print(r.stdout)
                return
    print("objdump: no working m68k objdump found / every arch gave errors")


if __name__ == "__main__":
    main()
