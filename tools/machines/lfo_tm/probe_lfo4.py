#!/usr/bin/env python3
"""Fourth read-only probe (tools/machines/lfo_tm/DRAFT.md): how a knob turn reaches the LFO page, and the FUNC test.

Known from the repo: ParameterPageView vtable slot 124 (0x401005a8) = knob -> descriptor lookup 0x4001e814, called
(view, knob, FUNC, -1); KEY_HELD 0x4007faf4(code) -> 1 if held (track_filter uses it for MACHINES = 5); the LFO view
vtable is 0x401016dc. This prints: the LFO vtable against ParameterPageView's, KEY_HELD, the knob lookup, and the
code around the knob-turn call 0x4001f6ee. Writes only /tmp.

    python3 tools/machines/lfo_tm/probe_lfo4.py --cycles firmware/model-cycles_OS1.13.syx
"""
import argparse
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import probe_lfo2 as P  # noqa: E402

BASE = P.BASE


def word(stock, va):
    return int.from_bytes(stock[va - BASE:va - BASE + 4], "big")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--out", default="/tmp/mainos_1.13.bin")
    args = ap.parse_args()
    stock = P.T.main_os_from_syx(args.cycles)
    pathlib.Path(args.out).write_bytes(stock)

    print("== A. vtables: slot, LFO view (0x401016dc) vs ParameterPageView (0x40100388 = 0x401005a8 - 124*4) ==")
    ppv = 0x401005a8 - 124 * 4
    for slot in list(range(0, 8)) + list(range(120, 128)):
        a, b = word(stock, 0x401016dc + 4 * slot), word(stock, ppv + 4 * slot)
        print(f"slot {slot:3}: LFO {a:#010x}  PPV {b:#010x} {'same' if a == b else 'DIFFERENT'}")
    print()

    print("== B. KEY_HELD 0x4007faf4 ==")
    print(P.disasm(args.out, 0x4007faf4, 0x4007fb40))
    print()

    print("== C. knob lookup 0x4001e814 ==")
    print(P.disasm(args.out, 0x4001e814, 0x4001e880))
    print()

    print("== D. around the knob-turn call 0x4001f6ee ==")
    print(P.disasm(args.out, 0x4001f6a0, 0x4001f780))


if __name__ == "__main__":
    main()
