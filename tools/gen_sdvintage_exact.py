#!/usr/bin/env python3
"""Génère le tweak « sdvintage-exact » : le VRAI moteur SD VINTAGE du Syntakt dans le Model:Cycles (notes/17).

Outil de développeur (comme gen_sdvintage.py). Il lit TON Syntakt_OS1.42.syx pour ANALYSER son programme
audio (section 7), mais le tweak produit ne contient aucun octet Elektron. Il contient seulement :
  - nos écritures dans l'OS Cycles : crochet de démarrage, code de la passerelle (tools/machines/syntakt_bridge),
    pointeurs de la machine SNARE, défauts des potards ;
  - une RECETTE de charge utile : quelles plages de TON fichier Syntakt copier, où, et une table de
    relocalisation (position, ancienne adresse, nouvelle adresse) ;
build.py --syntakt exécute la recette au moment du build, sur ton fichier.

Fermeture calculée depuis update 0x40008074, render 0x4000847a, remise à zéro 0x40003ee0, 0x4000255e et
0x40002544 (init des voix), en suivant appels directs, relatifs au PC et indirects (lea abs,aN ; jsr (aN)).
Toute adresse absolue qu'elles contiennent est relocalisée :
  voir SEGMENTS : code 0x40002544..0x40008580 -> 0x43000000, tables -> 0x43006100 / 0x43006400,
  SRAM 0x80000000..0x8000ffff -> 0x43020000, BSS 0x4404f000..0x4404ffff -> 0x43030000.

    python3 tools/gen_sdvintage_exact.py --syntakt Syntakt_OS1.42.syx          # écrit 21-sdvintage-exact.json
    python3 tools/gen_sdvintage_exact.py --syntakt Syntakt_OS1.42.syx --check  # vérifie le JSON versionné

Toolchain : m68k-elf-gcc / m68k-elf-objdump (Homebrew) ou m68k-linux-gnu-* (Debian) ; M68K_CROSS pour forcer.
"""
import argparse
import collections
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "emu"))

import sprites   # noqa: E402
import syntakt   # noqa: E402

SRC = HERE / "machines" / "syntakt_bridge"
DST = HERE.parent / "tweaks" / "model-cycles_OS1.13" / "21-sdvintage-exact.json"
CROSS = os.environ.get("M68K_CROSS") or next(
    (c for c in ("m68k-linux-gnu-", "m68k-elf-") if shutil.which(c + "gcc")), "m68k-linux-gnu-")
CFLAGS = ["-mcpu=54418", "-Os", "-ffreestanding", "-fno-builtin", "-nostdlib", "-fno-pic", "-fno-common",
          "-ffunction-sections", "-fdata-sections", "-fomit-frame-pointer", "-Wall", "-Wextra", "-Werror"]

BASE = 0x40000400                        # VA du 1er octet des sections 3 (Cycles) et 7 (Syntakt)
IMAGE_LEN = 0x1a9d40                     # MAIN OS Cycles 1.13 : la charge utile commence juste après
ST_CODE = (0x40000400, 0x4004f6e0)       # code + données en lecture seule du programme audio du Syntakt (analyse)
ST_SRAM_INIT = ((0x4004f6e0, 0x40057670, 0x80000000), (0x40057670, 0x4005df10, 0x80008000))
ST_BSS = (0x4404f000, 0x44050000)        # fenêtre du BSS du Syntakt utilisée (graine 0x4404f954)
# Charge utile COMPACTE en SDRAM à 0x43000000 : au-dessus du BSS Cycles (0x423380b0), sous 64 Mo (valable même
# si la mémoire n'en faisait que 64), loin de la pile (0x48000000). Seules les plages utiles sont copiées :
#   (source Syntakt, fin, destination)
SEGMENTS = (
    (0x40002544, 0x40008580, 0x43000000),   # les 21 fonctions (plage contiguë : le relatif au PC reste juste)
    (0x40014980, 0x40014b80, 0x43006100),   # constantes lues par la remise à zéro (1ers mots de 0x40014980, 0x40014b7c)
    (0x40028438, 0x4003a238, 0x43006400),   # table DEC x MENV (64 Ko) et 16 tables de 512 o
    (0x80000000, 0x80010000, 0x43020000),   # réplique de sa SRAM (remplie comme son démarrage)
    (0x4404f000, 0x44050000, 0x43030000),   # fenêtre de son BSS (graine aléatoire)
)
DST_CODE, DST_SRAM, DST_BRIDGE, DST_END = 0x43000000, 0x43020000, 0x43031000, 0x43033000


def move(v):
    """Nouvelle adresse d'une adresse du Syntakt, ou None si elle n'est pas dans une plage copiée."""
    for lo, hi, dst in SEGMENTS:
        if lo <= v < hi:
            return v - lo + dst
    return None
ROOTS = (0x40008074, 0x4000847a, 0x40003ee0, 0x4000255e, 0x40002544)
CAVE = 0x4016cae8                        # masque de sprite libéré (tools/sprites.py) : crochet de démarrage
HOOK = 0x400004b2                        # remise à zéro du BSS du Cycles
HOOK_OLD = "4feffff048d700f0"            # lea -16(sp),sp ; movem.l d4-d7,(sp)
RENDER_TAB, UPDATE_TAB = 0x40118610, 0x40118628
STOCK = {"render": 0x400ab6e8, "update": 0x400ab3b0}
DEFAULTS = {  # champ « défaut » des descripteurs SNARE : (va, d'origine, SD VINTAGE du Syntakt)
    "color": (0x4010e818, 0, 0), "shape": (0x4010e850, 127, 110), "sweep": (0x4010e888, 8, 74),
    "contour": (0x4010e8c0, 0, 80), "decay": (0x4010e8f8, 40, 33),
}
BRANCH = re.compile(r"b(ra|sr|cc|cs|eq|ne|ge|gt|le|lt|hi|ls|mi|pl|vc|vs)[swl]?$")


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw); r.returncode and print(r.stderr[-4000:]); r.check_returncode(); return r.stdout


def disasm(img, tmp):
    path = tmp / "sec7.bin"
    path.write_bytes(img)
    out = run([CROSS + "objdump", "-D", "-b", "binary", "-m", "m68k:isa-c:emac", f"--adjust-vma={BASE:#x}",
               f"--start-address={ST_CODE[0]:#x}", f"--stop-address={ST_CODE[1]:#x}", str(path)])
    ins = {}
    for line in out.splitlines():
        m = re.match(r"\s*([0-9a-f]+):\t([0-9a-f ]+)\t(\S+)\s*(.*)$", line)
        if m:
            ins[int(m.group(1), 16)] = (len(m.group(2).replace(" ", "")) // 2, m.group(3), m.group(4).strip())
    return ins


def values(ops, immediates=True):
    out = [int(x, 16) for x in re.findall(r"0x([0-9a-f]+)", ops)]
    if immediates:
        out += [int(x) & 0xffffffff for x in re.findall(r"#(-?\d+)", ops)]
    return out


# Immédiats qui SONT des adresses (vérifiés à la main dans le désassemblage) : #1141176660 = 0x4404f954,
# la graine passée par adresse (0x4000421a « move.l #...,(sp) »). Tout autre immédiat de la forme d'une
# adresse fait échouer la génération, pour être examiné : ce pourrait être une constante numérique.
# Idem pour les tables et tampons SRAM que la remise à zéro et update/render rangent dans la voix comme
# pointeurs (« move.l #0x8000945c,d1 » puis stockage) : ce sont exactement les adresses des tables référencées.
IMM_ADDR = {0x4404f954, 0x80004b70, 0x80008c60, 0x8000945c, 0x80009580, 0x800096a4, 0x800097c8, 0x8000a080,
            0x8000a484}
# Immédiats de la forme d'une adresse mais NUMÉRIQUES (vérifiés à la main) : Q31 -1,0 = 0x80000000.
IMM_NUM = {0x80000000}
AMBIGUOUS = []
# Plages où une référence relative au PC peut viser (défaut : la plage de code SEGMENTS[0]). Un générateur qui
# déplace le code par blocs (gen_syntakt_engines.py) y met ses blocs et recalcule lui-même les déplacements.
PC_OK = None


def closure(ins):
    """Fonctions atteintes depuis ROOTS et instructions qu'elles contiennent."""
    funcs, insns, todo = set(), set(), list(ROOTS)
    while todo:
        f = todo.pop()
        if f in funcs:
            continue
        funcs.add(f)
        stack, seen = [f], set()
        while stack:
            a = stack.pop()
            if a in seen or a not in ins:
                continue
            seen.add(a)
            insns.add(a)
            size, mn, ops = ins[a]
            for v in values(ops):
                if not ST_CODE[0] <= v < ST_CODE[1] or v not in ins:
                    continue
                if mn in ("jsr", "bsrw", "bsrl", "bsrs"):
                    todo.append(v)
                elif mn == "lea" and "%pc@" in ops or (mn == "lea" and re.search(r",%a[0-6]$", ops)):
                    prev = max((p for p in ins if p < v), default=None)
                    if prev is not None and ins[prev][1] in ("rts", "rte"):
                        todo.append(v)                  # pointeur de fonction (lea f,aN ; jsr (aN))
                elif BRANCH.match(mn) or mn == "jmp":
                    stack.append(v)
            if mn in ("rts", "rte") or mn in ("bra", "bras", "braw", "bral", "jmp"):
                continue
            stack.append(a + size)
    return funcs, insns


def relocations(img, ins, insns):
    """[(va Syntakt du champ 32 bits, ancienne valeur, nouvelle valeur)]"""
    relocs = []
    for a in sorted(insns):
        size, mn, ops = ins[a]
        if BRANCH.match(mn):
            continue
        raw = img[a - BASE:a - BASE + size]
        if "%pc@" in ops:
            for v in values(ops, immediates=False):
                if not any(lo <= v < hi for lo, hi in (PC_OK or [SEGMENTS[0][:2]])):
                    raise SystemExit(f"!! {a:#x} {mn} {ops} : relatif au PC hors de la plage de code copiée")
        absolute = set(values(ops, immediates=False))
        for v in set(values(ops)):
            if v not in absolute and v not in IMM_ADDR:
                if (ST_CODE[0] <= v < ST_CODE[1] or 0x80000000 <= v < 0x80010000 or ST_BSS[0] <= v < ST_BSS[1]) \
                        and v not in IMM_NUM:
                    AMBIGUOUS.append(f"{a:#x} {mn} {ops} : immédiat {v:#x}")
                continue
            new = move(v)
            if new is None:
                if ST_CODE[0] <= v < 0x44100000 or 0x80000000 <= v < 0x80010000 or 0xfc000000 <= v < 0xfd000000:
                    raise SystemExit(f"!! {a:#x} {mn} {ops} : adresse {v:#x} hors des plages copiées")
                continue
            pat = v.to_bytes(4, "big")
            k = raw.find(pat)
            if k < 0:
                if "%pc@" in ops:
                    continue                            # relatif au PC : valable après copie d'un seul bloc
                raise SystemExit(f"!! {a:#x} {mn} {ops} : champ de {v:#x} introuvable")
            if raw.find(pat, k + 1) >= 0:
                raise SystemExit(f"!! {a:#x} : {v:#x} apparaît deux fois dans l'instruction")
            relocs.append((a + k, v, new))
    if AMBIGUOUS:
        raise SystemExit("!! immédiats à examiner (adresse ou nombre ?) :\n   " + "\n   ".join(AMBIGUOUS))
    return relocs


def compile_bridge(tmp, payload_longs):
    obj, stub, elf = tmp / "bridge.o", tmp / "stub.o", tmp / "bridge.elf"
    run([CROSS + "gcc", *CFLAGS, "-c", str(SRC / "bridge.c"), "-o", str(obj)])
    run([CROSS + "gcc", "-mcpu=54418", "-c", str(SRC / "stub.S"), "-o", str(stub),
         f"-DPAYLOAD_SRC={BASE + IMAGE_LEN:#x}", f"-DPAYLOAD_DST={DST_CODE:#x}", f"-DPAYLOAD_LONGS={payload_longs}"])
    run([CROSS + "ld", "-T", str(SRC / "link.ld"), "-o", str(elf), str(stub), str(obj)])
    blobs = {}
    for sec in (".stub", ".bridge"):
        out = tmp / (sec.strip(".") + ".bin")
        run([CROSS + "objcopy", "-O", "binary", "-j", sec, str(elf), str(out)])
        blobs[sec] = out.read_bytes()
    syms, data_end = {}, DST_BRIDGE + 0x1000
    for line in run([CROSS + "nm", "-S", str(elf)]).splitlines():
        parts = line.split()
        syms[parts[-1]] = int(parts[0], 16)
        if len(parts) == 4 and int(parts[0], 16) >= DST_BRIDGE + 0x1000:
            data_end = max(data_end, int(parts[0], 16) + int(parts[1], 16))
    if len(blobs[".bridge"]) > 0x1000:
        raise SystemExit("!! passerelle > 4 Ko")
    return blobs, syms, data_end


def be32(x):
    return (x & 0xffffffff).to_bytes(4, "big").hex()


def build_tweak(img):
    with tempfile.TemporaryDirectory() as d:
        tmp = pathlib.Path(d)
        ins = disasm(img, tmp)
        funcs, insns = closure(ins)
        relocs = relocations(img, ins, insns)
        _, _, data_end = compile_bridge(tmp, 1)          # 1er passage : taille des données de la passerelle
        if data_end > DST_END:
            raise SystemExit("!! données de la passerelle trop grandes")
        size = (data_end - DST_CODE + 15) & ~15
        blobs, syms, _ = compile_bridge(tmp, size // 4)
    stub = blobs[".stub"]
    writes = [
        {"off": CAVE - BASE, "old": "ff" * len(stub), "new": stub.hex()},
        sprites.redirect_write(CAVE),
        {"off": HOOK - BASE, "old": HOOK_OLD, "new": "4ef9" + be32(CAVE) + "4e71"},
        {"off": RENDER_TAB + 4 - BASE, "old": be32(STOCK["render"]), "new": be32(syms["bridge_render"])},
        {"off": UPDATE_TAB + 4 - BASE, "old": be32(STOCK["update"]), "new": be32(syms["bridge_update"])},
    ]
    for va, old, new in DEFAULTS.values():
        if new != old:
            writes.append({"off": va - BASE, "old": be32(old << 8), "new": be32(new << 8)})
    writes.sort(key=lambda w: w["off"])
    parts = [{"dest": f"{dst:#x}", "syntakt": [f"{lo:#x}", f"{hi:#x}"]} for lo, hi, dst in SEGMENTS[:3]]
    for lo, hi, dst in ST_SRAM_INIT:
        parts.append({"dest": f"{move(dst):#x}", "syntakt": [f"{lo:#x}", f"{hi:#x}"]})
    parts.append({"dest": f"{DST_BRIDGE:#x}", "hex": blobs[".bridge"].hex()})
    code_bytes = sum(ins[a][0] for a in insns)
    return {
        "id": "sdvintage-exact",
        "order": 21,
        "name": "Vrai moteur SD VINTAGE du Syntakt a la place de SNARE",
        "description": [
            "Le moteur SD VINTAGE du Syntakt (OS 1.42 ou 1.41), extrait AU BUILD de TON Syntakt_OS1.42.syx",
            f"({len(funcs)} fonctions, {code_bytes} o de code, avec ses tables), relocalise en SDRAM a 0x43000000",
            "au-dessus du BSS de l'OS Cycles, branche a la place de SNARE par une passerelle (notes/17).",
            "Potards au sens du Syntakt : PITCH=TUNE, COLOR=INHM, SHAPE=FCMP, SWEEP=SWEP, CONTOUR=MENV,",
            "PUNCH=PNCH, GATE, DECAY=DEC ; defauts du Syntakt. Demande : build.py --syntakt Syntakt_OS1.42.syx.",
            "Aucun octet Elektron dans ce fichier : recette de copie et table de relocalisation seulement.",
        ],
        "device": "Model:Cycles",
        "os": "1.13",
        "section": 3,
        "conflicts": ["sdvintage-snare"],
        "writes": writes,
        "append": {
            "at": f"{BASE + IMAGE_LEN:#x}",
            "dest": f"{DST_CODE:#x}",
            "size": size,
            "syntakt": {"os": dict(syntakt.OFFICIAL), "section": 7, "section_sha256": syntakt.DSP_SHA256},
            "parts": parts,
            "reloc": [[f"{move(va):#x}", be32(old), be32(new)] for va, old, new in relocs],
        },
    }, funcs, code_bytes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--syntakt", required=True, help="Syntakt_OS1.42.syx (ou 1.41) officiel")
    ap.add_argument("--check", action="store_true", help="vérifie que le JSON versionné correspond")
    args = ap.parse_args()
    tweak, funcs, code_bytes = build_tweak(syntakt.dsp_image(args.syntakt))
    text = json.dumps(tweak, indent=1) + "\n"
    ap_ = tweak["append"]
    print(f"  fermeture : {len(funcs)} fonctions, {code_bytes} o ; {len(ap_['reloc'])} relocalisations ;"
          f" charge utile {ap_['size']} o -> {ap_['dest']}")
    if args.check:
        if not DST.exists() or DST.read_text(encoding="utf-8") != text:
            raise SystemExit(f"!! {DST.name} ne correspond pas (autre GCC ?)")
        print(f"  {DST.name} est à jour")
        return
    DST.write_text(text, encoding="utf-8")
    print(f"  écrit : {DST.relative_to(HERE.parent)}")


if __name__ == "__main__":
    main()
