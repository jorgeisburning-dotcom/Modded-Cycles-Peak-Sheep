#!/usr/bin/env python3
"""Reference model of the Turing Machine wave for LFO 2, 3, 4 (DRAFT, not part of the firmware build).

This is the algorithm the ColdFire code will implement, written so it can be run and tested without the OS or the
m68k toolchain. The assembly must reproduce it bit for bit (same register, same flip test, same outputs).

Inspired by the Music Thing Turing Machine, Grayscale Permutation (the BITS knob sets the last active bit, so any
length works) and Dead Man's Catch for Peaks (Tim Churches, MIT): a shift register whose last bit is copied back
to the first, with a chance to flip it.

    python3 tools/machines/lfo_tm/tm_model.py        # runs the self-test
"""

MASK32 = 0xFFFFFFFF


def flip_chance(knob):
    """PROB knob 0..127 -> flip chance in 1/256 (0..256).

    0           locked loop (the chance is 0)
    1..95       0 to 12.5 % : the musical range, over most of the travel (like Dead Man's Catch)
    96..126     12.5 % to 50 % : evolving, then random
    127         100 % : every bit flips, the loop inverts on each pass and lasts twice as long (Moebius,
                like the CYC position of Permutation)
    """
    if knob <= 0:
        return 0
    if knob >= 127:
        return 256
    if knob <= 95:
        return (knob * 32) // 95
    return 32 + ((knob - 95) * 96) // 31


class Rng:
    """xorshift32: stands in for the OS's global generator (0x40091a96) in the model."""

    def __init__(self, seed=0x2545F491):
        self.s = seed & MASK32 or 1

    def byte(self):
        x = self.s
        x ^= (x << 13) & MASK32
        x ^= x >> 17
        x ^= (x << 5) & MASK32
        self.s = x
        return x & 0xFF


class TuringMachine:
    """One machine per LFO per track.

    length  1..32  any number, odd ones included (3, 5, 7...): the bit that is copied back is bit length-1
    prob    0..127 PROB knob, see flip_chance
    div     1..8   the machine moves every div-th clock
    """

    def __init__(self, length=16, prob=0, div=1, seed=0xA5C3, rng=None):
        self.length = max(1, min(32, length))
        self.prob = prob
        self.div = max(1, min(8, div))
        self.reg = seed & MASK32
        self.count = 0
        self.rng = rng or Rng()

    def clock(self):
        """One clock pulse. Returns True when the register moved."""
        self.count += 1
        if self.count < self.div:
            return False
        self.count = 0
        bit = (self.reg >> (self.length - 1)) & 1
        if self.rng.byte() < flip_chance(self.prob):
            bit ^= 1
        self.reg = ((self.reg << 1) | bit) & MASK32
        return True

    @property
    def value(self):
        """The 8 newest bits, 0..255: the LFO output (centred on 128, scaled by DEP in the firmware)."""
        return self.reg & 0xFF

    @property
    def gate(self):
        """The newest bit: the trig output."""
        return self.reg & 1


def period(seq):
    """Smallest period of a sequence that repeats, or None."""
    n = len(seq)
    for p in range(1, n // 2 + 1):
        if all(seq[i] == seq[i + p] for i in range(n - p)):
            return p
    return None


def selftest():
    # 1. Locked loops last exactly `length` steps, odd lengths included, for the values and for the gates.
    for length in (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 16, 17, 24, 31, 32):
        tm = TuringMachine(length=length, prob=0)
        tm.reg = 0
        pattern = [1] + [0] * (length - 1) if length > 2 else [1, 0][:length]
        if length > 2:
            pattern = [1, 1, 0] + [0] * (length - 3)
            if length >= 5:
                pattern[3] = 1            # aperiodic seed, whatever the length
        for i, b in enumerate(pattern):
            tm.reg |= b << i
        # warm up (the 8-bit window above a short loop needs 8 clocks to fill with the ring), then record 4 loops
        vals, gates = [], []
        for _ in range(3 * length + 8):
            tm.clock()
        for _ in range(4 * length):
            tm.clock()
            vals.append(tm.value)
            gates.append(tm.gate)
        pv, pg = period(vals), period(gates)
        assert pv is not None and length % pv == 0, (length, "value period", pv)
        assert pg is not None and length % pg == 0, (length, "gate period", pg)
        if length >= 5:
            assert pg == length, (length, "gate period", pg)
    print("locked loops: period divides the length, exact for 5..32 (odd lengths 3, 5, 7, 9... OK)")

    # 2. Moebius (knob 127): the loop inverts at every pass, so it lasts twice as long.
    # The invariant is anti-periodicity: bit t+length is the inverse of bit t. The loop therefore repeats after
    # 2 * length (or after a divisor of it, for a few special seeds such as 1,0,1 : never after `length`).
    for length in (3, 5, 7, 8, 16):
        tm = TuringMachine(length=length, prob=127, seed=0b101100111010)
        for _ in range(4 * length):
            tm.clock()
        gates = []
        for _ in range(6 * length):
            tm.clock()
            gates.append(tm.gate)
        assert all(gates[t + length] == 1 - gates[t] for t in range(len(gates) - length)), length
        p = period(gates)
        assert p is not None and (2 * length) % p == 0 and p != length, (length, "moebius period", p)
    tm = TuringMachine(length=3, prob=127, seed=0b011)      # a seed with no short cut: exactly 2 * 3 = 6
    for _ in range(12):
        tm.clock()
    g = []
    for _ in range(24):
        tm.clock()
        g.append(tm.gate)
    assert period(g) == 6, period(g)
    print("moebius: every pass inverts the loop, so it repeats after twice the length (3, 5, 7, 8, 16)")

    # 3. Flip rate follows the knob (large sample, loose bounds).
    for knob, lo, hi in ((0, 0.0, 0.0), (47, 0.05, 0.08), (95, 0.115, 0.135), (127, 0.99, 1.0)):
        rng, flips, n = Rng(7), 0, 20000
        for _ in range(n):
            flips += rng.byte() < flip_chance(knob)
        rate = flips / n
        assert lo <= rate <= hi, (knob, rate)
    assert flip_chance(0) == 0 and flip_chance(127) == 256
    assert all(flip_chance(k) <= flip_chance(k + 1) for k in range(127)), "knob curve must not go down"
    print("flip rate: 0 % locked, 12.5 % at knob 95, 100 % at 127, curve never goes down")

    # 4. Clock division: the machine moves every div-th clock.
    tm = TuringMachine(length=8, div=3)
    moved = sum(tm.clock() for _ in range(30))
    assert moved == 10, moved
    print("clock division: 30 clocks / 3 = 10 moves")

    # 5. Polyrhythm: two locked machines with odd lengths 3 and 5 line up again every 15 clocks.
    a = TuringMachine(length=3, prob=0, seed=0b011)
    b = TuringMachine(length=5, prob=0, seed=0b01101)
    for _ in range(30):
        a.clock(), b.clock()
    pairs = []
    for _ in range(60):
        a.clock(), b.clock()
        pairs.append((a.gate, b.gate))
    assert period(pairs) == 15, period(pairs)
    print("polyrhythm: lengths 3 and 5 together repeat every 15 clocks")
    print("ALL OK")


if __name__ == "__main__":
    selftest()
