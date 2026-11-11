/*
 * Peaks' drum voices as MACRO models (notes/75): BASS DRUM, SNARE DRUM, HI-HAT, FM DRUM, from the module Peaks by
 * Emilie Gillet (MIT, pichenettes/eurorack, peaks/drums/ and peaks/resources.cc, compiled as is). Integer code at 48 kHz,
 * the Cycles' rate: no resampling. This file is our glue; the voices are the originals.
 *
 * Knobs (COLOR a, SWEEP b, PITCH = note, DECAY = decay; CONTOUR unused):
 *   BASS DRUM  : PITCH +-7 semitones around the drum's own pitch (note 60 = centre), a TONE, b PUNCH
 *   SNARE DRUM : PITCH +-7 semitones around the drum's own pitch (note 60 = centre), a TONE, b SNAPPY
 *   HI-HAT     : no parameter in Peaks (a, b, decay unused: the amp chain of the OS shapes the length)
 *   FM DRUM    : PITCH = the note (24..96), a FM amount, b NOISE (above half) / OVERDRIVE (below half)
 * DECAY also drives the drum's own decay (Peaks' DECAY), on top of the OS amp envelope.
 */
#include <new>
#include <stdint.h>
#include <string.h>

#include "peaks/drums/bass_drum.h"
#include "peaks/drums/snare_drum.h"
#include "peaks/drums/fm_drum.h"
#include "peaks/drums/high_hat.h"

#include "voices.h"

using namespace peaks;

union PeaksVoice {
	BassDrum bass;
	SnareDrum snare;
	HighHat hat;
	FmDrum fm;
	PeaksVoice() { }
	~PeaksVoice() { }
};
static_assert(sizeof(PeaksVoice) <= EXT_BYTES, "EXT_BYTES too small for the Peaks drums");

static inline PeaksVoice *V(void *st) { return reinterpret_cast<PeaksVoice *>(st); }

static inline int clampi(int x, int lo, int hi) { return x < lo ? lo : (x > hi ? hi : x); }

/* +-7 semitones around note 60, as the 16-bit frequency parameter of the bass and snare drums */
static inline int16_t transpose(int note)
{
	int d = clampi(note - (60 << 7), -(7 << 7), 7 << 7);
	return static_cast<int16_t>(clampi(d * 32768 / 896, -32767, 32767));
}

extern "C" void ext_init(void *st, int kind)
{
	/* HighHat::Init and FmDrum::Init leave some fields alone (phases): they expect zeroed memory, as on a fresh module */
	memset(st, 0, EXT_BYTES);
	switch (kind) {
	case 0: new (&V(st)->bass) BassDrum; V(st)->bass.Init(); break;
	case 1: new (&V(st)->snare) SnareDrum; V(st)->snare.Init(); break;
	case 2: new (&V(st)->hat) HighHat; V(st)->hat.Init(); break;
	case 3: new (&V(st)->fm) FmDrum; V(st)->fm.Init(); V(st)->fm.set_sd_range(false); break;
#ifdef MC_SHEEP
	default: sheep_init(st, kind); break;
#endif
	}
}

extern "C" void ext_set(void *st, int kind, int note, int a, int b, int c, int decay)
{
	(void)c;
	uint16_t ua = static_cast<uint16_t>(a * 2), ub = static_cast<uint16_t>(b * 2);
	uint16_t dec = static_cast<uint16_t>(clampi(decay, 0, 127) * 516);
	switch (kind) {
	case 0:
		V(st)->bass.set_frequency(transpose(note));
		V(st)->bass.set_tone(ua);
		V(st)->bass.set_punch(ub);
		V(st)->bass.set_decay(dec);
		break;
	case 1:
		V(st)->snare.set_frequency(transpose(note));
		V(st)->snare.set_tone(ua);
		V(st)->snare.set_snappy(ub);
		V(st)->snare.set_decay(dec);
		break;
	case 3:
		V(st)->fm.set_frequency(static_cast<uint16_t>(clampi((note - (24 << 7)) * 65535 / (72 << 7), 0, 65535)));
		V(st)->fm.set_fm_amount(ua);
		V(st)->fm.set_noise(ub);
		V(st)->fm.set_decay(dec);
		break;
#ifdef MC_SHEEP
	default:
		sheep_set(st, kind, note, a, b, c, decay);
		break;
#endif
	}
}

extern "C" void ext_render(void *st, int kind, int strike, short *out, int n)
{
#ifdef MC_SHEEP
	if (kind >= EXT_PEAKS) {
		sheep_render(st, kind, strike, out, n);
		return;
	}
#endif
	GateFlags gate[64];
	if (n > 64)
		n = 64;
	for (int i = 0; i < n; i++)
		gate[i] = GATE_FLAG_LOW;
	if (strike)
		gate[0] = GATE_FLAG_HIGH | GATE_FLAG_RISING;
	switch (kind) {
	case 0: V(st)->bass.Process(gate, out, n); break;
	case 1: V(st)->snare.Process(gate, out, n); break;
	case 2: V(st)->hat.Process(gate, out, n); break;
	case 3: V(st)->fm.Process(gate, out, n); break;
#ifdef MC_SHEEP
#endif
	}
}
