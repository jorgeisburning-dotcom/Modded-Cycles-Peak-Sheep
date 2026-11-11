// Host proof for the SHEEP voice (tools/machines/macro/sheep.h): the original Tides Generator, built with
// WAVETABLE_HACK (= Sheep), against sheep::Voice, sample for sample, free-running, 16-sample blocks.
// Build and run: tools/check_sheep_host.sh <path to a pichenettes/eurorack checkout>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "tides/generator.h"
#include "sheep.h"

using namespace tides;

static Generator g_ref;  // static storage: zeroed, like the global Generator on the module

static bool run_case(int pitch, int x, int y, int fold, int bank, int blocks) {
  memset(&g_ref, 0, sizeof(g_ref));  // Init() does not clear the glide position: start from the zeroed state of a fresh module
  g_ref.Init();
  g_ref.set_range(GENERATOR_RANGE_HIGH);
  g_ref.set_sync(false);
  g_ref.set_pitch(pitch);
  g_ref.set_shape(y);
  g_ref.set_slope(x);
  g_ref.set_smoothness(fold);
  // GeneratorMode is the bank index in the WAVETABLE_HACK build: AD = 0, LOOPING = 1, AR = 2
  g_ref.set_mode(static_cast<GeneratorMode>(bank));
  const int n = blocks * kBlockSize;
  std::vector<int> ref, mine(n);
  for (int i = 0; i < n + 64; ++i) {
    ref.push_back(g_ref.Process(0).bipolar);
    if (((i + 1) % kBlockSize) == 0) g_ref.Process();
  }

  sheep::Voice v;
  v.Init();
  v.set_snap(false);
  std::vector<int16_t> out(kBlockSize);
  for (int b = 0; b < blocks; ++b) {
    // pitch_ inside Tides is the pitch we gave plus one octave
    v.Render(pitch + 12 * 128, x, y, fold, bank, out.data(), kBlockSize);
    for (int i = 0; i < (int)kBlockSize; ++i) mine[b * kBlockSize + i] = out[i];
  }
  // Tides' double buffer plays three blocks of silence before the first rendered one: the port starts 48 samples earlier
  const int lag = 3 * kBlockSize;
  bool same = true;
  int nonzero = 0;
  for (int i = 0; i < n; ++i) {
    if (ref[i + lag] != mine[i]) same = false;
    if (mine[i]) ++nonzero;
  }
  if (same) {
    printf("OK    pitch=%5d x=%6d y=%6d fold=%6d bank=%d  %d samples identical (%d non-zero)\n", pitch, x, y, fold, bank, n, nonzero);
    return true;
  }
  int first = -1;
  for (int i = 0; i < n; ++i) if (ref[i + lag] != mine[i]) { first = i; break; }
  printf("FAIL  pitch=%5d x=%6d y=%6d fold=%6d bank=%d  first difference at sample %d (ref %d, port %d)\n", pitch, x, y, fold, bank, first, first < 0 ? 0 : ref[first + lag], first < 0 ? 0 : mine[first]);
  return false;
}

int main() {
  int bad = 0;
  const int pitches[] = {24 * 128, 48 * 128, 57 * 128 + 37, 69 * 128, 84 * 128 + 5, 100 * 128};
  const int xs[] = {-32768, -9000, 0, 12345, 32767};
  const int folds[] = {-32768, -20000, -8000, 0, 9000, 32767};
  for (int bank = 0; bank < 3; ++bank)
    for (unsigned p = 0; p < sizeof(pitches) / sizeof(*pitches); ++p)
      for (unsigned k = 0; k < sizeof(xs) / sizeof(*xs); ++k)
        for (unsigned f = 0; f < sizeof(folds) / sizeof(*folds); ++f) {
          int x = xs[k], y = xs[(k * 2 + p) % 5];
          if (!run_case(pitches[p] - 12 * 128, x, y, folds[f], bank, 40)) ++bad;
        }
  printf(bad ? "%d case(s) FAILED\n" : "all cases identical\n", bad);
  return bad != 0;
}
