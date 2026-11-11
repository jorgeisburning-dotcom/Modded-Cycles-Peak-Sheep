# 75 — Peaks (batteries) et Sheep dans MACRO : où les mettre, ce qui est prêt

Demande d'un utilisateur (01/11/2026), suite de [74](74-sheep-dans-macro.md) : préparer les batteries de Peaks, et un fork
de Modded Cycles avec, dans MACRO, après les 47 modèles de Braids : Peaks, puis Sheep. Question : machine à part ou
modèles de MACRO ? État : **voix et passerelle prêtes et prouvées sur l'ordinateur ; rien de construit pour le Cycles**
(pas de `m68k-elf-gcc` ici, pas d'OS officiel) ; rien dans `os.json`.

## Réponse courte

- **Peaks dans MACRO, pas en machine de plus** `[FAIT]` : l'écran MACHINES est plein (avec Model-TG, 14 repères
  remplissent exactement les 2 lignes de 7, [54 §11.2](54-machine-acid.md)) ; une 15ᵉ machine demande de refaire
  l'écran, les rangées et les descripteurs, pour un gain d'organisation que SHAPE donne déjà. Dans MACRO : SHAPE 47 à 50
  = BASS DRUM, SNARE DRUM, HI-HAT, FM DRUM ; 51 à 53 = SHEEP A, B, C (dans cet ordre, comme demandé).
- **Code de Peaks : MIT, entier, 48 kHz** `[FAIT]` : seul `peaks/test/peaks_test.cc` (banc de test) contient `float` ;
  `peaks/drums/*.cc` est entier. Aucun rééchantillonnage.
- **Charge** `[HYP, mesure sur PC, pas sur le Cycles]` : bass drum et FM drum ≈ 0,6 × une voix TONE, snare ≈ 1,2, hi-hat
  ≈ 1,6 ; Sheep ≈ 2,1 (WAVE MAP de Braids : 3,5).
- **Place : Peaks tient, Sheep non** `[HYP]` : l'image de l'OS finit à `0x401fbf51`, soit **16 559 o** avant la limite du
  bootstrap (`0x40200000`, [52](52-registre-place-libre.md)). Peaks (code + tables utilisées) ≈ 11 Ko décompressé en
  x86 `-Os` (3,7 Ko de code, 7,2 Ko de tables), ≈ 9 Ko compressé (zlib, proxy d'aPLib) : **tient, de justesse** ; à
  mesurer avec `m68k-elf-gcc`. Les tables de Sheep (`wt_waves`, 178 ondes) font 91 Ko, 74 Ko compressées (une banque :
  24 à 27 Ko) : **ne tient pas** sans libérer de la place (§3).

## 1. Ce qui est prêt (`[FAIT]` sur l'ordinateur)

| Fichier | Rôle |
|---|---|
| `tools/machines/macro/voices.h` | interface commune : `ext_init`, `ext_set`, `ext_render` ; modèles hors Braids, état de 256 o par piste |
| `tools/machines/macro/peaks_glue.cc` | notre passerelle ; les batteries de Peaks sont les originales (`peaks/drums/`, `peaks/resources.cc`) |
| `tools/machines/macro/sheep.h`, `sheep_glue.cc` | la voix de Sheep ([74](74-sheep-dans-macro.md)) ; compilée avec `-DMC_SHEEP` seulement |
| `tools/machines/macro/macro.cc` | `MODELS` = 47 + `EXT_KINDS` ; SHAPE ≥ 47 : voix de Peaks / Sheep, sans RATE ni BITS, puis la chaîne d'ampli de TONE |
| `tools/check_peaks_host.sh`, `tools/emu/peaks_ref.cc` | preuve : 540 cas, 200 blocs chacun, **identiques** aux batteries d'origine |
| `tools/check_sheep_host.sh`, `tools/emu/sheep_ref.cc` | preuve de Sheep (540 cas identiques) |

Les deux en-têtes de ressources (Braids, Peaks, Tides) définissent les mêmes macros (`LUT_SVF_CUTOFF` …) avec d'autres
valeurs : chaque famille est donc dans **son** fichier `.cc`, derrière `voices.h`.

### Potards des modèles hors Braids

| Modèle | PITCH | COLOR (+ CONTOUR × enveloppe) | SWEEP | CONTOUR | DECAY |
|---|---|---|---|---|---|
| BASS DRUM | ± 7 demi-tons autour de la note 60 | TONE | PUNCH | — (enveloppe de COLOR) | DECAY de la batterie |
| SNARE DRUM | idem | TONE | SNAPPY | idem | idem |
| HI-HAT | — (aucun paramètre dans Peaks) | — | — | — | longueur par l'ampli de l'OS |
| FM DRUM | la note (24 à 96) | FM | NOISE (au-dessus du milieu) / OVERDRIVE (en dessous) | idem | idem |
| SHEEP A, B, C | la note | X de la grille | Y de la grille | quantité de repli (0 : rien) | ampli de l'OS |

## 2. Pièges relevés `[FAIT]`

- `HighHat::Init` et `FmDrum::Init` ne remettent pas tous leurs champs à zéro (les phases) : ils comptent sur une mémoire
  à zéro ; `ext_init` met donc l'état à zéro avant (sinon le son dépend de ce qu'il y avait avant).
- Snare, hi-hat et FM drum tirent dans **un seul** générateur (`stmlib::Random`) : sur le Cycles, une voix en tire pour les
  autres ; le son d'une voix dépend des pistes jouées en même temps (jamais le cas en preuve : générateur ré-ensemencé).
- La preuve compare à zéro de mémoire (`memset`) : c'est l'état d'un module qui démarre.

## 3. À faire `[À FAIRE]` (demande l'OS 1.13 et `m68k-elf-gcc`)

1. **Plan de la charge utile** : la zone de MACRO (`+0x42000..+0x5b000`, 102 400 o) contient déjà Braids (≈ 98 Ko) ; Peaks
   (≈ 11 Ko) doit aller ailleurs (juste après ACID, `+0x78300`, ou un 3ᵉ morceau PACK) : `gen_macro.py`,
   `gen_macro_syntakt.py`, `gen_acid_combos.py` partagent ce plan. Les variables : 6 pistes × (256 + 8) o de plus.
2. `gen_macro.py` : `SOURCES` + `peaks/drums/*.cc`, `peaks/resources.cc` (le lien garde ce qui est utilisé :
   `--gc-sections`, à vérifier), `peaks_glue.cc` ; `MODELS` / knob « Model » max 50 (puis 53 avec Sheep).
3. **Sheep : la place manque** `[FAIT, mesuré sur REGISTRY.md et sur les tables]`
   - Retirer **un** moteur du Syntakt libère peu (SD 215 o, CP 180 o, TOY 199 o, BITS 230 o, SWARM 6 182 o) : le socle
     des moteurs (≈ 136 Ko compressés) est partagé. Mais **retirer les cinq** le libère : `macro-acid-tg` (Model-TG,
     MACRO, ACID, sans moteurs) finit en `0x401dacac`, soit ≈ 152 Ko avant `0x40200000`, contre 16,5 Ko aujourd'hui.
     L'estimation « les cinq ensemble ≈ 7 Ko » de la version précédente de cette note était fausse (somme de marges).
   - Les ondes de Sheep ne se compressent pas assez : `wt_waves` = 91 Ko ; zlib 74 Ko ; meilleur codage sans perte
     essayé (prédiction d'ordre 2, entropie) ≈ 60 Ko. Banque A (additive) et B (formants) sont **calculées** par
     `tides/resources/wavetables.py` (sommes de sinus, formants) : 2 × 64 ondes ; la banque C (« Shruthi ») est lue dans
     `waves.bin`, 50 ondes × 257 × int16 ≈ 25,7 Ko (zlib ≈ 22 Ko). Calculer A (et B) au démarrage en virgule fixe
     coûterait quelques Ko de code au lieu de 33 Ko de tables par banque, mais ne serait pas identique à l'échantillon.
   - Choix possibles : (1) Peaks + Sheep banque A calculée au démarrage, tous les moteurs gardés (tient) ; (2) Peaks +
     Sheep complet en retirant les cinq moteurs du Syntakt (tient de justesse en compressé : Braids ≈ 60 + Peaks ≈ 9 +
     Sheep ≈ 74 Ko pour ≈ 152 Ko libres : à mesurer) ; (3) Peaks seul d'abord, Sheep ensuite.
4. Preuve Unicorn (`tools/emu/test_macro.py`) : un cas par modèle, seul et avec tout l'OS, coût par bloc de 32 trames.
5. Licences : MIT, Émilie Gillet : `THIRD-PARTY-NOTICES.md`, `PROVENANCE.md`, `LICENSE-Braids` (ou un fichier Peaks et un
   fichier Tides), `os.json` (`credit`, `license`) ; ni le nom du module ni celui de Mutable Instruments sur la machine.
6. Statut `experimental` jusqu'à l'essai sur la machine ; rien de « testé » avant.
