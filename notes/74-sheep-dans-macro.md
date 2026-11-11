# 74 — Sheep (le firmware alternatif de Tides) : étude de portage vers MACRO

Demande d'un utilisateur (01/11/2026) : après Braids (MACRO, [43](43-machine-macro.md)), porter **Sheep**, le
firmware alternatif de Tides d'Émilie Gillet (oscillateur à tables d'ondes, trois banques sur une grille 2D). État : la
**voix** est portée et prouvée sur l'ordinateur ; l'intégration dans l'OS (machine, tweak, preuve Unicorn) n'est **pas**
faite : elle demande l'OS officiel 1.13 et l'essai sur la machine. Rien n'entre dans `os.json`.

## Réponse courte

- **Sheep tourne tel quel sur le ColdFire** `[FAIT]` : le code est entièrement en entiers (aucun flottant), à **48 kHz,
  la cadence du Cycles** (tables de `tides/resources.cc` calculées pour 48 kHz) : ni rééchantillonnage ni filtre
  demi-bande comme pour Braids (96 kHz).
- **Source** : `tides/generator.cc`, `Generator::ProcessWavetable`, compilation `WAVETABLE_HACK` du dépôt
  `pichenettes/eurorack` (MIT, Émilie Gillet) ; ce n'est pas un dépôt à part. Tables : `wt_waves` (45 746 mots de 16
  bits, 178 ondes de 257 points, ≈ 91,5 Ko), `ws_smooth_bipolar_fold`, `lut_cutoff`, `lut_increments` : ≈ 96 Ko au
  total, à compiler telles quelles comme celles de Braids.
- **La voix** `tools/machines/macro/sheep.h` (notre code, `sheep::Voice`) reprend l'arithmétique de `ProcessWavetable` en
  retirant l'horloge, la PLL et le changement de banque sur front d'horloge (la banque devient un paramètre).
  **540 cas, 640 échantillons chacun, identiques à l'échantillon près** au `Generator` d'origine
  (`tools/check_sheep_host.sh <dépôt eurorack>`, `tools/emu/sheep_ref.cc`) : trois banques, six hauteurs (24 à 100
  demi-tons), positions X/Y sur toute la plage, filtre et repli sur toute la plage `[FAIT]`.
- **Pas encore fait** : brancher la voix sur la boucle des voix, l'essai en émulation avec l'OS entier, le coût en
  instructions, l'essai sur la machine.

## 1. Ce que fait Sheep `[FAIT]`

Trois banques de 8×8 ondes (additive, quasi-PWM, ondes de WMAP de Braids), interpolées en continu en X et Y (SLOPE et
SHAPE de Tides), suréchantillonnage ×4 puis deux filtres passe-bas à un pôle. SMOOTHNESS : au-dessus de 0, repli
d'onde (`ws_smooth_bipolar_fold`) ; en dessous, passe-bas dont la coupure suit la hauteur. Sorties de Tides (1 bit,
sous-octave carré) : hors sujet pour une machine.

## 2. Proposition d'intégration `[HYP]`, à confirmer avec le demandeur

Mettre Sheep **dans MACRO, pas dans une machine de plus** : l'OS n'accepte que 6 machines ajoutées ([43 §2](43-machine-macro.md)),
et SHAPE choisit déjà un modèle (0..46). Trois modèles de plus, SHAPE 47, 48, 49 = SHEEP A, B, C (une banque chacun) :

| Potard | Sur un modèle SHEEP |
|---|---|
| COLOR (TIMBRE) + CONTOUR | X de la grille (comme TIMBRE pour WAVE MAP) |
| SWEEP (COLOR) | Y de la grille |
| à décider | repli / passe-bas (SMOOTHNESS) : PUNCH est pris par l'ampli ; candidat : FINE ne convient pas (RATE/BITS) |
| PITCH, DECAY, GATE | comme MACRO : note, chaîne d'ampli d'origine |

Un trig appelle `Strike()` (phase à 0, comme un front de gate sur Tides). Bornes à modifier dans `macro.cc` : `MODELS`
(47 → 50), le tableau `LITE` (−1 : ces modèles n'ont pas de version « allégée » ; ils tournent à 48 kHz sans filtre
demi-bande, donc **moins chers** que les modèles de Braids rendus à 96 kHz), le rendu (`render` n'appelle pas `osc`
pour ces modèles), `gen_macro.py` (compiler `tides/resources.cc` ; ≈ 96 Ko de plus dans la charge utile : à vérifier
contre la limite de taille de l'image, cf. l'incident rc18 de Motor:Cycles), et la boucle de sortie 16 bits → Q31.

Alternative : une machine séparée « SHEEP » si MACRO n'a plus de place dans la charge utile ; elle prendrait une des 6
places et serait incompatible avec les moteurs du Syntakt (même emplacement `0x43000000`).

## 3. À faire `[À FAIRE]`

1. L'OS officiel 1.13 (non fourni ici, non versionné) : brancher `sheep::Voice` dans `macro_update` / `macro_render`.
2. `tools/gen_macro.py` : ajouter `tides/resources.cc` (et `generator.cc` **non**) ; `--check`, `check_overlaps.py`.
3. Preuve Unicorn `tools/emu/test_macro.py` : un cas par banque, contre `sheep_ref`, seul et avec tout l'OS ; mesure du
   coût par bloc de 32 trames.
4. Licence : MIT, mêmes mentions que Braids (Émilie Gillet) ; ajouter `tides/` à `THIRD-PARTY-NOTICES.md`,
   `PROVENANCE.md`, `LICENSE-Braids` (ou `LICENSE-Tides`), `os.json` (`credit`, `license`) ; ne pas afficher le nom du
   module ni de Mutable Instruments sur la machine ([43](43-machine-macro.md)).
5. Statut `experimental` jusqu'à l'essai de Maxime sur sa machine ; aucune mention « testé » avant.

## 4. Pièges relevés pendant la preuve `[FAIT]`

- `Generator::Init()` ne remet pas à zéro la position X/Y : le Generator d'origine glisse depuis 0 au premier bloc.
  Sur la machine on **colle** à la position cible au premier rendu (`snap`), pas de glissement de 0,7 ms au trig ; la
  preuve désactive ce collage (`set_snap(false)`) pour comparer.
- Le glissement divise un `uint16_t` par un `size_t` : division **non signée**, donc un X qui baisse arrondit vers le bas,
  pas vers zéro. Reproduit tel quel.
- Quand SMOOTHNESS > 0, `lut_cutoff[(f >> 7) + 1]` lit un mot au-delà de la table (513 entrées) : sans effet (multiplié par
  une fraction nulle), conservé tel quel.
- Dans la compilation Sheep, `GeneratorMode` **est** l'indice de banque (AD 0, LOOPING 1, AR 2).
