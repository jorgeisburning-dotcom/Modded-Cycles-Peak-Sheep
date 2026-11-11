#!/usr/bin/env python3
"""Generate the tweak "macro-acid-ext-tg": Model-TG + MACRO + ACID without the five Syntakt engines, with MACRO's model
list extended after Braids' 47 models by Peaks' four drums (47..50) and Sheep's three wavetable banks (51..53), notes/75.

Same mechanics as tools/gen_acid_combos.py (build_macro_acid): MACRO linked at the start of the payload, ACID at
+0x76000, and Sheep's 91 KB wavetable on its own at +0x7a000 (it does not fit in MACRO's code window). What changes: tools/gen_macro.py is switched to EXT (Peaks and Sheep sources, -DMC_EXT -DMC_SHEEP), and the
machine's "Model" knob goes up to 53. The existing tweaks are not touched (EXT is False for them): this one is a new
tweak, conflicting with every other MACRO combination.

    git clone https://github.com/pichenettes/eurorack vendor/eurorack
    git -C vendor/eurorack checkout 08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4
    git -C vendor/eurorack submodule update --init stmlib
    python3 tools/gen_macro_ext.py --cycles firmware/model-cycles_OS1.13.syx --eurorack vendor/eurorack [--check]

Needs the m68k toolchain of tools/gen_macro.py (Ubuntu 24.04: g++-m68k-linux-gnu, binutils-m68k-linux-gnu).
Peaks and Tides: Emilie Gillet, MIT (same pinned commit as Braids).
"""
import argparse
import json
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))

import gen_macro as gm             # noqa: E402
import gen_acid_combos as gac      # noqa: E402
import gen_sdvintage_exact as gx   # noqa: E402
import gen_sdvintage_7th as g7     # noqa: E402
import gen_syntakt_engines as gs   # noqa: E402
import gen_macro_syntakt as gms    # noqa: E402

TID = "macro-acid-ext"
BASE_ID = "macro-acid-tg"          # the tweak this one replaces


def build(img, repo):
    """(tweak, info) : Model-TG + MACRO (Braids, Peaks, Sheep) + ACID."""
    gm.EXT = True
    n_models = len(gm.MODELS) + len(gm.EXT_NAMES)
    gm.MACHINE = dict(gm.MACHINE, knobs=(("Timbre", "TIMB", 64), ("Model", "MODL", 0, 0, n_models - 1),
                                         ("Color", "COLR", 64), ("Env Timbre", "ENVT", 0)))
    tg = gs.tg_context(img)
    real = gm.added_machine

    def with_sheep(img_, tg_, machines, tmp, blobs, bss_end):
        """Add Sheep's wavetable (linked at pay + SHEEP_OFF by gm.compile_machine) as one more part of the payload."""
        at, data = gm.EXT_BLOB
        end = (at + len(data) + 3) & ~3
        if end > gs.PAY_TG + gms.TG_ROOM:
            raise SystemExit(f"!! Sheep's wavetable up to {end:#x}: beyond the room Model-TG leaves")
        return real(img_, tg_, machines, tmp, list(blobs) + [(at, data)], max(bss_end, end))

    gm.added_machine = with_sheep
    try:
        out, info = gac.build_macro_acid(img, repo, tg)
    finally:
        gm.added_machine = real
    out["id"] = TID + "-tg"
    out["name"] = ("Model-TG + MACRO with Peaks drums and Sheep wavetables (47 Braids models, then " +
                   ", ".join(gm.EXT_NAMES) + ") and ACID, without the Syntakt engines")
    out["description"] = [
        "EXPERIMENTAL (notes/75): not tested on a Model:Cycles. Model-TG + MACRO + ACID, the five Syntakt engines are left out.",
        f"MACRO's Model knob goes to {n_models - 1}: 0..46 Braids (unchanged), 47..50 Peaks BASS DRUM, SNARE DRUM, HI-HAT, "
        "FM DRUM, 51..53 SHEEP A, B, C (Sheep: the wavetable oscillator of the alternative Tides firmware).",
        f"Peaks, Tides' wavetables and Braids compiled as is from {gm.EURORACK_REPO} {gm.EURORACK_COMMIT[:7]} "
        "(Emilie Gillet, MIT: LICENSE-Braids); our glue: tools/machines/macro/ (voices.h, peaks_glue.cc, sheep_glue.cc, "
        "sheep.h).",
        "Models 47+ run at 48 kHz without RATE or BITS (FUNC + PITCH does nothing on them); the amp chain of the OS is kept.",
    ] + [d for d in out["description"] if d.startswith("ACID")]
    out["conflicts"] = sorted((set(out["conflicts"]) | {BASE_ID, "macro-acid", "macro-tg", "macro"}) - {out["id"]})
    return out, info


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cycles", required=True, help="official model-cycles_OS1.13.syx")
    ap.add_argument("--eurorack", required=True, help=f"clone of {gm.EURORACK_REPO} at {gm.EURORACK_COMMIT[:7]}")
    ap.add_argument("--check", action="store_true", help="check that the committed JSON matches")
    args = ap.parse_args()
    img = g7.cycles_main(args.cycles)
    if len(img) != gx.IMAGE_LEN:
        raise SystemExit("!! not the official MAIN OS 1.13")
    repo = pathlib.Path(args.eurorack).resolve()
    gm.check_sources(repo)
    tweak, info = build(img, repo)
    path = gm.DEV / f"{tweak['order']}-{tweak['id']}.json"
    print(f"  {tweak['id']} : {len(tweak['writes'])} writes, payload {info['size']} B, packed {info['packed']} B, "
          f"image up to {info['end']:#x} (limit {gs.END_LIMIT:#x}, {gs.END_LIMIT - info['end']} B free)")
    if gm.emit(path, json.dumps(tweak, indent=1) + "\n", args.check):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
