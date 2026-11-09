# Turing Machine wave for LFO 2, 3, 4 (DRAFT)

Status: design draft. The algorithm has a tested reference model (`tm_model.py`, run it with `python3`). There is
no ColdFire code yet. Items marked **[CHECK]** need the official OS 1.13 file (disassembly or emulator); they cannot
be settled from the repository alone.

## 1. What the user gets

A new **TM** wave on the extra LFOs. Instead of a smooth shape, the LFO plays a looping, semi-random pattern of
steps, like the Music Thing Turing Machine. Aimed at any destination of the LFO (pitch, filter, decay...), and its
gate bit can also fire trigs (second stage, see section 8).

## 2. Algorithm (matches `tm_model.py`)

- A 32-bit shift register per LFO per track.
- On each clock: take the bit at position `length - 1`, flip it with a chance set by PROB, shift the register left
  and put that bit in position 0.
- LFO output = the 8 newest bits (0..255, centred on 128, scaled by the LFO's DEP). Gate = the newest bit.
- PROB knob 0..127: 0 = locked loop, up to 12.5 % flip chance over most of the travel (the musical range), then 50 %
  (random), and the last notch = 100 % (Moebius: the loop inverts each pass and lasts twice as long, like the CYC
  position of Grayscale Permutation).

## 3. Lengths: any number from 1 to 32

The length is simply the position of the bit that is copied back, as the BITS knob does on Grayscale Permutation.
So **3, 5, 7, 9, 11...** work exactly like 8, 12, 16. Two locked machines of length 3 and 5 realign every 15 clocks
(tested): that is the polyrhythm use. The Moebius notch doubles any length (a 5-step loop becomes a 10-step one).

## 4. Clock

Both, chosen by the SRC control:

- **LFO clock.** The LFO's own SPD and MULT drive the machine. Plan: run the stock LFO routine on the faux obj with
  a square wave and take one tick on each rising edge of its output. This keeps tempo sync, MULT, start phase, MODE
  and retrig exactly as the LFO page already works. **[CHECK]** the index of the square wave in the OS wave list, and
  that a square output changes sign cleanly in the state words (`LFO_ST + 20`).
- **Sequencer step.** One tick per step of the track. **[CHECK]** the step event of the sequencer to hook (notes 32
  to 34); the tick must follow the track's own length and tempo, and stop with the sequencer.
- **Clock division (DIV 1..8)** applies to both.

## 5. Controls: 4 new ones

| Control | Range | Meaning |
|---|---|---|
| PROB | 0..127 | flip chance, section 2 |
| LEN | 1..32 | loop length, any number |
| DIV | 1..8 | clock division |
| SRC | STEP / LFO | clock source |

SPD, MULT and DEST keep their meaning. **DEP is the span** of the output. FADE, SPH and MODE stay shared with
LFO 1, as they are now.

Where the four controls go **[CHECK]**:

1. **Best: four knobs of the LFO page that the page does not use.** The page uses 8 parameters (SPD, MULT, FADE,
   DEST, WAVE, SPH, MODE, DEP) out of 12 knobs, so four may be free. No key combination needed; they would only act
   when WAVE = TM. To confirm in the LFO view's callback table (`0x40025798` and the vtable `0x401016dc`).
2. **If not: FUNC + [LFO] on the LFO page** opens a second layer with the same knobs remapped. The repository notes
   say FUNC + [LFO] "works as stock" and the shortcut map lists no use of it; to confirm what the stock OS does with
   it.
3. **Fallback: Mod Settings page** (SETTINGS > Mods). Works, but it is global and slower to reach while playing.

## 6. Storage

- TM state (register, counter) lives in the working memory above the BSS (the `SCR` area `lfo_plus.S` already
  uses): about 12 bytes per LFO per track, 216 bytes for 3 LFOs x 6 tracks.
- LFO 3 and 4 settings: the existing in-memory tables get 4 more entries (not saved, defaults at power-on, as now).
- LFO 2: there are no free words left in the sound for 4 more values, so in version 1 its TM settings also live in
  memory, not saved with the sound. Saving them needs a new use of spare bytes of the sound record. **[CHECK]**

## 7. Cost and safety

One 32-bit shift and one random byte per tick; the stock LFO run already costs 1.2 to 1.3 % per LFO set. The TM
should add well under that. The OS's own random generator (`0x40091a96`) is the source of the flip test.

## 8. Not in version 1

- The gate bit firing trigs (needs a second hook into the sequencer).
- Saving TM settings in the sound for LFO 2.
- Using TM on LFO 1 (the stock routine is untouched on purpose).

## 9. Next steps, in order

1. Get the official `model-cycles_OS1.13.syx` (and the Syntakt file) into `firmware/` of a machine with the m68k
   toolchain and Unicorn (the user's Codespace).
2. Answer the **[CHECK]** items by disassembly: wave list and WAVE range/label, LFO page knob layout, step event.
3. Write the ColdFire routine and the generator hooks; prove it in the emulator against `tm_model.py`, alone and with
   the whole OS (`AGENTS.md` rule 5).
4. Note, guide text (English and French), `FEATURES.md` row, `os.json` entry as `experimental`; hardware test is the
   owner's.
