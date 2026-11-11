/*
 * SHEEP A, B, C as MACRO models (notes/74, notes/75): the wavetable oscillator of Sheep (Emilie Gillet, MIT, Tides
 * firmware), one bank per model. Our voice is sheep.h, proved sample for sample against the original code.
 *
 * Knobs: COLOR (a) = X in the wave map, SWEEP (b) = Y, CONTOUR (c) = wavefolder amount (0: none), PITCH = the note.
 * Only compiled with MC_SHEEP: its tables are about 96 KB, which the OS image has no room for yet (notes/75 §2).
 */
#ifdef MC_SHEEP
#include <new>

#include "sheep.h"
#include "voices.h"

static_assert(sizeof(sheep::Voice) <= EXT_BYTES, "EXT_BYTES too small for the Sheep voice");

struct SheepState {
	sheep::Voice v;
	int note, x, y, fold;
};

static_assert(sizeof(SheepState) <= EXT_BYTES, "EXT_BYTES too small for the Sheep state");

static inline SheepState *S(void *st) { return reinterpret_cast<SheepState *>(st); }

extern "C" void sheep_init(void *st, int kind)
{
	if (kind < 4)
		return;
	new (st) SheepState;
	S(st)->v.Init();
	S(st)->note = 60 << 7;
	S(st)->x = S(st)->y = S(st)->fold = 0;
}

extern "C" void sheep_set(void *st, int kind, int note, int a, int b, int c, int decay)
{
	(void)decay;
	if (kind < 4)
		return;
	S(st)->note = note;
	S(st)->x = (a - 16383) * 2;
	S(st)->y = (b - 16383) * 2;
	S(st)->fold = c * 32767 / 32766;                 /* 0 .. 32767: fold, no filtering */
}

extern "C" void sheep_render(void *st, int kind, int strike, short *out, int n)
{
	if (kind < 4)
		return;
	if (strike)
		S(st)->v.Strike();
	S(st)->v.Render(S(st)->note, S(st)->x, S(st)->y, S(st)->fold, kind - 4, out, n);
}
#endif
