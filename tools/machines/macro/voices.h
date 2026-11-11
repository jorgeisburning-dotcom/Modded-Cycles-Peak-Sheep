/*
 * Voices of MACRO that are not Braids models (notes/74, notes/75): the drums of Peaks and the wavetable oscillator of
 * Sheep, all by Emilie Gillet (MIT). Each one lives in its own translation unit (peaks_glue.cc, sheep_glue.cc): the
 * resource headers of Braids, Peaks and Tides define the same macro names (LUT_SVF_CUTOFF ...) with different values
 * and cannot be included together.
 *
 * The voice state is an opaque block of EXT_BYTES bytes inside the track; the glue checks its own size.
 * kind: 0 BASS DRUM, 1 SNARE DRUM, 2 HI-HAT, 3 FM DRUM (Peaks) ; 4, 5, 6 SHEEP bank A, B, C.
 */
#ifndef MC_VOICES_H_
#define MC_VOICES_H_

#define EXT_BYTES   256
#define EXT_PEAKS   4                                /* kinds 0..3 */
#ifdef MC_SHEEP
#define EXT_KINDS   7
#else
#define EXT_KINDS   4
#endif

extern "C" {
/* (re)initialise the voice of this kind */
void ext_init(void *st, int kind);
/* note: 1/128 semitone, 440 Hz at 69 ; a, b, c: COLOR (+ envelope), SWEEP, CONTOUR in 0..32766 ; decay: DECAY 0..127 */
void ext_set(void *st, int kind, int note, int a, int b, int c, int decay);
/* n samples (16 bit, full scale) ; strike: a trig happens at the first sample */
void ext_render(void *st, int kind, int strike, short *out, int n);
#ifdef MC_SHEEP
/* kinds 4..6, defined in sheep_glue.cc ; peaks_glue.cc owns ext_* and hands the Sheep kinds over to these */
void sheep_init(void *st, int kind);
void sheep_set(void *st, int kind, int note, int a, int b, int c, int decay);
void sheep_render(void *st, int kind, int strike, short *out, int n);
#endif
}

#endif
