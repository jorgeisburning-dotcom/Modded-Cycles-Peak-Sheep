#!/usr/bin/env python3
"""Second read-only probe of OS 1.13 for the Turing Machine wave (tools/machines/lfo_tm/DRAFT.md).

probe_lfo.py found: 7 waves (TRI SIN SQR SAW EXP RMP RND) whose names are a pointer array at 0x40108f24, the LFO
routine 0x40091ab2 clamping the wave to 0..6 and calling a function table at 0x40115e94, and the knob descriptors of
the LFO page 0x38 bytes apart from 0x4010e36c (SPD) to 0x4010e4f4 (DEP). This probe shows what is inside them, so we
know where a wave number 7 ("TM") can be allowed and drawn. Nothing is written except /tmp.

    python3 tools/machines/lfo_tm/probe_lfo2.py --cycles firmware/model-cycles_OS1.13.syx
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

BASE = build.BASE
CODE_END = 0x40100000               # code is below, tables and texts above (what probe_lfo.py showed)


def text_at(stock, va):
    off = va - BASE
    if not 0 <= off < len(stock) - 1:
        return None
    end = stock.find(b"\0", off, off + 48)
    if end <= off:
        return None
    s = stock[off:end]
    return s.decode("ascii") if all(32 <= c < 127 for c in s) else None


def word_note(stock, w):
    if BASE <= w < BASE + len(stock):
        t = text_at(stock, w)
        if t:
            return f"-> text {t!r}"
        return "-> code" if w < CODE_END else "-> data"
    return ""


def dump(stock, va, n_words, title):
    print(f"-- {title} ({va:#x}, {n_words} words) --")
    for i in range(n_words):
        a = va + 4 * i
        w = int.from_bytes(stock[a - BASE:a - BASE + 4], "big")
        print(f"{a:#x}: {w:#010x}  {w >> 16:5d} {w & 0xffff:5d}  {word_note(stock, w)}")
    print()


def refs(stock, va):
    pat = va.to_bytes(4, "big")
    out, i = [], stock.find(pat)
    while i >= 0:
        if i % 2 == 0:
            out.append(BASE + i)
        i = stock.find(pat, i + 1)
    return out


def disasm(path, start, stop):
    for tool in ("m68k-linux-gnu-objdump", "m68k-elf-objdump"):
        cmd = [tool, "-D", "-b", "binary", "-m", "m68k:5407", f"--adjust-vma={BASE:#x}",
               f"--start-address={start:#x}", f"--stop-address={stop:#x}", path]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True)
        except FileNotFoundError:
            continue
        if r.returncode == 0:
            return "\n".join(l for l in r.stdout.splitlines() if l[:8].strip().endswith(":") or ":\t" in l)
    return "(no objdump)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", required=True)
    ap.add_argument("--out", default="/tmp/mainos_1.13.bin")
    args = ap.parse_args()

    stock = T.main_os_from_syx(args.cycles)
    pathlib.Path(args.out).write_bytes(stock)

    print("== A. wave and mode name pointers ==")
    dump(stock, 0x40108f24, 12, "array of names: 7 waves, then the trig modes")

    print("== B. who uses that array (word that holds its address) ==")
    for r in refs(stock, 0x40108f24):
        print(f"ref at {r:#x} ({'code' if r < CODE_END else 'data'})")
        if r < CODE_END:
            print(disasm(args.out, max(BASE, r - 0x30), r + 0x40))
    print()

    print("== C. wave function table used by the LFO routine ==")
    dump(stock, 0x40115e94, 8, "table indexed by the wave 0..5 (6 = RND is inline)")
    sqr = int.from_bytes(stock[0x40115e94 + 8 - BASE:0x40115e94 + 12 - BASE], "big")
    print(f"-- wave 2 (SQR) function at {sqr:#x} --")
    print(disasm(args.out, sqr, sqr + 0x50))
    print()

    print("== D. knob descriptors of the LFO page ==")
    for name, va in (("SPD", 0x4010e36c), ("WAVE", 0x4010e44c), ("SPH", 0x4010e484)):
        dump(stock, va - 0x10, 18, f"descriptor of {name} (its name pointer is at {va:#x})")

    print("== E. who points at the WAVE descriptor area ==")
    for r in refs(stock, 0x4010e44c - 0x10) + refs(stock, 0x4010e44c):
        print(f"ref at {r:#x}")
    print()

    print("== F. the routine's calls to the OS wave-label draw: words near the 'Waveform' long name ==")
    for r in refs(stock, 0x40129901)[:6] + refs(stock, 0x401298fc)[:6]:
        print(f"ref at {r:#x}")


if __name__ == "__main__":
    main()
