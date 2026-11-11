#!/usr/bin/env python3
"""Third read-only probe (tools/machines/lfo_tm/DRAFT.md). probe_lfo2.py dumped each knob descriptor from the wrong
offset: the short name is the LAST field (+0x34) of a 0x38-byte entry, so an entry starts at name_ptr - 0x34.
This prints the whole entries of the LFO page, the label formatter's tail, and its callers. Writes only /tmp.

    python3 tools/machines/lfo_tm/probe_lfo3.py --cycles firmware/model-cycles_OS1.13.syx
"""
import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import probe_lfo2 as P  # noqa: E402

BASE = P.BASE


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--out", default="/tmp/mainos_1.13.bin")
    args = ap.parse_args()
    stock = P.T.main_os_from_syx(args.cycles)
    pathlib.Path(args.out).write_bytes(stock)

    print("== A. LFO page entries (0x38 bytes each; +0 machine, +4 slot, +8 min, +c max, +10 default) ==")
    for name in ("SPD", "MULT", "FADE", "DEST", "WAVE", "SPH", "MODE", "DEP"):
        for off in P.find_all(stock, name.encode() + b"\0") if hasattr(P, "find_all") else []:
            pass
    first = 0x4010e36c - 0x34
    for i in range(14):
        e = first + 0x38 * i
        w = [int.from_bytes(stock[e + 4 * k - BASE:e + 4 * k + 4 - BASE], "big") for k in range(14)]
        nm = P.text_at(stock, w[13]) or "?"
        print(f"{e:#x} {nm:6} machine={w[0]:#x} slot={w[1]} min={w[2]:#x} max={w[3]:#x} def={w[4]:#x} "
              f"cc={w[6]} idx={w[8]} flags={w[9]:#x}")
    print()

    print("== B. label formatter tail (index > 6 path) ==")
    print(P.disasm(args.out, 0x40045932, 0x400459a0))
    print()

    print("== C. callers of the formatter 0x400458dc ==")
    for r in P.refs(stock, 0x400458dc):
        print(f"word ref at {r:#x}")
    pat = bytes.fromhex("4eb9") + (0x400458dc).to_bytes(4, "big")
    i = stock.find(pat)
    while i >= 0:
        print(f"jsr at {BASE + i:#x}")
        i = stock.find(pat, i + 1)


if __name__ == "__main__":
    main()
