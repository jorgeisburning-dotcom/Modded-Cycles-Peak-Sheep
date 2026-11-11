// Host proof for the Peaks glue (tools/machines/macro/peaks_glue.cc): the same drum, driven directly with the
// parameter values the glue is documented to set, against ext_render. Build: tools/check_peaks_host.sh <eurorack>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include "peaks/drums/bass_drum.h"
#include "peaks/drums/snare_drum.h"
#include "peaks/drums/fm_drum.h"
#include "peaks/drums/high_hat.h"
#include "stmlib/utils/random.h"
#include "voices.h"

using namespace peaks;
static int bad = 0;

template <class D> static void run_ref(D &d, int blocks, short *out) {
  GateFlags g[32];
  for (int b = 0; b < blocks; ++b) {
    for (int i = 0; i < 32; ++i) g[i] = (b == 0 && i == 0) ? (GATE_FLAG_HIGH | GATE_FLAG_RISING) : GATE_FLAG_LOW;
    d.Process(g, out + b * 32, 32);
  }
}

int main() {
  // Direct comparison per kind
  const int notes[] = {50 << 7, 60 << 7, (67 << 7) + 40};
  const int ks[] = {0, 8000, 16383, 25000, 32766};
  const int decs[] = {0, 40, 127};
  static short r[200 * 32], m[200 * 32];
  alignas(16) static unsigned char st[EXT_BYTES];
  long checked = 0, loud = 0;
  for (int kind = 0; kind < 4; ++kind)
    for (unsigned n = 0; n < 3; ++n)
      for (unsigned ia = 0; ia < 5; ++ia)
        for (unsigned ib = 0; ib < 5; ib += 2)
          for (unsigned id = 0; id < 3; ++id) {
            int note = notes[n] & 0x3fff, a = ks[ia], b = ks[ib], dec = decs[id];
            stmlib::Random::Seed(0x12345678 + kind);  // the drums share one noise generator: same start for both runs
            memset(st, 0, sizeof st);
            ext_init(st, kind);
            ext_set(st, kind, note, a, b, 0, dec);
            for (int bl = 0; bl < 200; ++bl) ext_render(st, kind, bl == 0, m + bl * 32, 32);
            uint16_t ua = a * 2, ub = b * 2, ud = dec * 516;
            int d7 = note - (60 << 7); d7 = d7 < -(7 << 7) ? -(7 << 7) : (d7 > (7 << 7) ? 7 << 7 : d7);
            int16_t tr = (int16_t)(d7 * 32768 / 896 < -32767 ? -32767 : (d7 * 32768 / 896 > 32767 ? 32767 : d7 * 32768 / 896));
            stmlib::Random::Seed(0x12345678 + kind);
            if (kind == 0) { static BassDrum d; memset((void*)&d, 0, sizeof d); d.Init(); d.set_frequency(tr); d.set_tone(ua); d.set_punch(ub); d.set_decay(ud); run_ref(d, 200, r); }
            if (kind == 1) { static SnareDrum d; memset((void*)&d, 0, sizeof d); d.Init(); d.set_frequency(tr); d.set_tone(ua); d.set_snappy(ub); d.set_decay(ud); run_ref(d, 200, r); }
            if (kind == 2) { static HighHat d; memset((void*)&d, 0, sizeof d); d.Init(); run_ref(d, 200, r); }
            if (kind == 3) {
              static FmDrum d; memset((void*)&d, 0, sizeof d); d.Init(); d.set_sd_range(false);
              int fr = (note - (24 << 7)) * 65535 / (72 << 7); fr = fr < 0 ? 0 : (fr > 65535 ? 65535 : fr);
              d.set_frequency((uint16_t)fr); d.set_fm_amount(ua); d.set_noise(ub); d.set_decay(ud); run_ref(d, 200, r);
            }
            ++checked;
            if (memcmp(r, m, sizeof r)) { ++bad; printf("FAIL kind=%d note=%d a=%d b=%d dec=%d\n", kind, note, a, b, dec); }
            int peak = 0; for (int i = 0; i < 200 * 32; ++i) { int v = abs(m[i]); if (v > peak) peak = v; }
            if (peak > 2000) ++loud;
          }
  printf("%ld cases, %ld with a clear signal (peak > 2000), %d mismatch(es)\n", checked, loud, bad);
  return bad != 0;
}
