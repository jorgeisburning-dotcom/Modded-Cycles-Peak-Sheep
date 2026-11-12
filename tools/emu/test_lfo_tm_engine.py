#!/usr/bin/env python3
"""Proof of the Turing Machine engine (tools/machines/lfo_tm/tm_engine.S) against tm_model.py, in Unicorn.

No firmware needed: only the m68k toolchain and Unicorn. Checks that
  1. tm_chance gives flip_chance(knob) for all 128 knob values;
  2. tm_clock reproduces TuringMachine.clock() bit for bit (register, counter, moved flag) for every length 1..32,
     DIV 1..8 and a spread of PROB values, fed with the same random bytes.

    python3 tools/emu/test_lfo_tm_engine.py
"""
import pathlib
import random
import subprocess
import sys
import tempfile

from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN
from unicorn import m68k_const as mk

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "machines" / "lfo_tm"))
import tm_model as M                # noqa: E402

SRC = HERE.parent / "machines" / "lfo_tm" / "tm_engine.S"
CODE, STATE, STACK, STOP = 0x40000000, 0x41000000, 0x42000000, 0x40001000
CROSS = "m68k-linux-gnu-"


def assemble():
    with tempfile.TemporaryDirectory() as d:
        d = pathlib.Path(d)
        o, e, b = d / "t.o", d / "t.elf", d / "t.bin"
        subprocess.run([CROSS + "gcc", "-mcpu=54418", "-c", str(SRC), "-o", str(o)], check=True)
        subprocess.run([CROSS + "ld", "-Ttext", f"{CODE:#x}", "-o", str(e), str(o)], check=True)
        subprocess.run([CROSS + "objcopy", "-O", "binary", "-j", ".text", str(e), str(b)], check=True)
        syms = {}
        for l in subprocess.run([CROSS + "nm", str(e)], capture_output=True, text=True, check=True).stdout.splitlines():
            p = l.split()
            if len(p) == 3:
                syms[p[2]] = int(p[0], 16)
        return b.read_bytes(), syms


class Rig:
    def __init__(self):
        code, self.syms = assemble()
        uc = self.uc = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        uc.ctl_set_cpu_model(mk.UC_CPU_M68K_ANY)
        for a in (CODE, STATE, STACK):
            uc.mem_map(a, 0x10000)
        uc.mem_write(CODE, code)
        uc.mem_write(STOP, b"\x4e\x71" * 4)

    def call(self, name, **regs):
        uc = self.uc
        sp = STACK + 0x8000
        sp -= 4
        uc.mem_write(sp, STOP.to_bytes(4, "big"))
        uc.reg_write(mk.UC_M68K_REG_A7, sp)
        for r, v in regs.items():
            uc.reg_write(getattr(mk, "UC_M68K_REG_" + r.upper()), v)
        try:
            uc.emu_start(self.syms[name], STOP, count=1000)
        except Exception:
            pc = uc.reg_read(mk.UC_M68K_REG_PC)
            print(f"!! CPU exception in {name} at pc={pc:#x} (offset {pc - self.syms[name]:#x} into it), regs {regs}")
            raise
        return uc.reg_read(mk.UC_M68K_REG_D0) & 0xFFFFFFFF


def main():
    rig = Rig()
    uc = rig.uc

    for knob in range(128):
        got = rig.call("tm_chance", d0=knob)
        assert got == M.flip_chance(knob), (knob, got, M.flip_chance(knob))
    print("tm_chance: all 128 knob values match flip_chance")

    rnd = random.Random(7)
    cases = 0
    for length in range(1, 33):
        for div in range(1, 9):
            for prob in (0, 1, 40, 95, 96, 110, 126, 127):
                seed = rnd.getrandbits(32)
                ref_rng = M.Rng(seed=rnd.getrandbits(32) or 1)
                tm = M.TuringMachine(length=length, prob=prob, div=div, seed=seed, rng=ref_rng)
                twin = M.Rng(seed=ref_rng.s)             # same random bytes for the code under test
                uc.mem_write(STATE, seed.to_bytes(4, "big") + (0).to_bytes(4, "big"))
                chance = rig.call("tm_chance", d0=prob)
                for step in range(120):
                    moved_ref = tm.clock()
                    # the model draws its random byte only when it moves: do the same
                    r = twin.byte() if moved_ref else 0
                    moved = rig.call("tm_clock", a0=STATE, d1=length, d2=chance, d3=div, d4=r)
                    reg = int.from_bytes(uc.mem_read(STATE, 4), "big")
                    cnt = int.from_bytes(uc.mem_read(STATE + 4, 4), "big")
                    assert moved == int(moved_ref), (length, div, prob, step, "moved")
                    assert reg == tm.reg, (length, div, prob, step, hex(reg), hex(tm.reg))
                    assert cnt == tm.count, (length, div, prob, step, "count", cnt, tm.count)
                cases += 1
    print(f"tm_clock: {cases} (length, div, prob) combinations x 120 clocks match tm_model bit for bit")
    print("ALL OK")


if __name__ == "__main__":
    main()
