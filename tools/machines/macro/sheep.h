/*
 * SHEEP : the wavetable oscillator of Sheep, the alternative Tides firmware by Emilie Gillet (MIT, repository
 * pichenettes/eurorack, tides/generator.cc, ProcessWavetable, the WAVETABLE_HACK build).
 *
 * This file is our code: a free-running voice, with Tides' clock, PLL and bank-on-clock behaviour removed (the bank
 * is a parameter). The arithmetic is the one of ProcessWavetable, line for line, so the output is the same
 * samples; tools/emu/sheep_ref.cc and tools/check_sheep_host.sh prove it against the original Generator.
 * The tables (tides/resources.cc: wt_waves, ws_smooth_bipolar_fold, lut_cutoff, lut_increments) are compiled as is.
 *
 * Rate: 48 kHz, the Model:Cycles' own rate (Tides' tables are made for 48 kHz): no resampling.
 * Pitch: 1/128 semitone, 440 Hz at 69, the Cycles' convention (Tides' lut_increments is built the same way).
 * Integer only, no FPU: about 4 table reads and 8 multiplies per output sample, times the 4x oversampling.
 */
#ifndef MC_SHEEP_H_
#define MC_SHEEP_H_

#include <stdint.h>

#include "stmlib/utils/dsp.h"
#include "tides/resources.h"

namespace sheep {

using namespace tides;  // the resource tables of tides/resources.h

/* Tides' 4x oversampling decimator weights (generator.cc, kDownsampleCoefficient) */
static const int32_t kDownsample[4] = { 17162, 19069, 17162, 12140 };

const int kBanks = 3;
const int kWaveSize = 257;

class Voice {
 public:
  void Init() {
    phase_ = 0;
    x_ = y_ = 0;
    lp_[0] = lp_[1] = 0;
    first_ = true;
    snap_ = true;
  }

  /* host proof only: start the position at 0 and glide, as the zeroed Tides Generator does */
  void set_snap(bool snap) { snap_ = snap; }

  /* A trig restarts the cycle, as a gate edge does on Tides. */
  void Strike() { phase_ = 0; }

  /* pitch  : note in 1/128 semitone (Tides' own pitch_, i.e. already including its +1 octave if you want parity)
   * x, y   : position in the wave map, -32768..32767 (Tides' SLOPE and SHAPE)
   * fold   : -32768..32767 (Tides' SMOOTHNESS): above 0 wavefolder, below 0 low-pass filter
   * bank   : 0 additive harmonics, 1 PWM-ish, 2 Braids' WMAP waves
   * out    : size samples, 16 bit */
  void Render(int pitch, int x, int y, int fold, int bank, int16_t* out, int size) {
    uint32_t phase_increment = PhaseIncrement(pitch);

    /* The grid is 8x8 rather than 9x9, so the position is scaled by 7/8. */
    uint16_t target_x = static_cast<uint16_t>(x + 32768);
    target_x = target_x * 57344 >> 16;
    uint16_t target_y = static_cast<uint16_t>(y + 32768);
    target_y = target_y * 57344 >> 16;
    if (first_ && snap_) {  /* no glide from 0 on the first block */
      x_ = target_x;
      y_ = target_y;
    }
    first_ = false;
    uint16_t px = x_, py = y_;
    /* unsigned division, as in Tides (size_t): a falling position floors instead of truncating */
    uint16_t x_increment = static_cast<uint32_t>(target_x - px) / static_cast<uint32_t>(size);
    uint16_t y_increment = static_cast<uint32_t>(target_y - py) / static_cast<uint32_t>(size);

    int32_t wf_gain = fold > 0 ? fold : 0;
    wf_gain = wf_gain * wf_gain >> 15;

    int32_t frequency = CutoffFrequency(pitch, fold);
    int32_t f_a = lut_cutoff[frequency >> 7] >> 16;
    int32_t f_b = lut_cutoff[(frequency >> 7) + 1] >> 16;
    int32_t f = f_a + ((f_b - f_a) * (frequency & 0x7f) >> 7);
    int32_t lp0 = lp_[0], lp1 = lp_[1];

    const int16_t* bank_base = wt_waves + bank * 64 * kWaveSize - (bank & 2) * 4 * kWaveSize;
    uint32_t phase = phase_;
    while (size--) {
      px += x_increment;
      py += y_increment;
      uint16_t x_integral = px >> 13;
      uint16_t y_integral = py >> 13;
      const int16_t* wave_1 = &bank_base[(x_integral + y_integral * 8) * kWaveSize];
      const int16_t* wave_2 = wave_1 + kWaveSize * 8;
      uint16_t x_fractional = px << 3;
      int32_t y_fractional = (py << 2) & 0x7fff;

      int32_t s = 0;
      for (int32_t subsample = 0; subsample < 4; ++subsample) {
        int32_t y_1 = stmlib::Crossfade(wave_1, wave_1 + kWaveSize, phase << 1, x_fractional);
        int32_t y_2 = stmlib::Crossfade(wave_2, wave_2 + kWaveSize, phase << 1, x_fractional);
        int32_t y_mix = y_1 + ((y_2 - y_1) * y_fractional >> 15);
        int32_t folded = stmlib::Interpolate1022(ws_smooth_bipolar_fold, (y_mix + 32768) << 16);
        y_mix = y_mix + ((folded - y_mix) * wf_gain >> 15);
        s += y_mix * kDownsample[subsample];
        phase += (phase_increment >> 3);
      }
      lp0 += f * ((s >> 16) - lp0) >> 15;
      lp1 += f * (lp0 - lp1) >> 15;
      *out++ = static_cast<int16_t>(lp1);
    }
    phase_ = phase;
    x_ = px;
    y_ = py;
    lp_[0] = lp0;
    lp_[1] = lp1;
  }

 private:
  static uint32_t PhaseIncrement(int pitch) {
    int num_shifts = 0;
    const int kOct = 12 * 128;
    if (pitch < 0) pitch = 0;
    if (pitch > 120 << 7) pitch = 120 << 7;  /* Tides clamps pitch_ to 0..120 semitones */
    while (pitch >= kOct) {
      pitch -= kOct;
      ++num_shifts;
    }
    uint32_t a = lut_increments[pitch >> 4];
    uint32_t b = lut_increments[(pitch >> 4) + 1];
    uint32_t inc = a + ((b - a) * (pitch & 0xf) >> 4);
    return inc << num_shifts;
  }

  static int32_t CutoffFrequency(int pitch, int smoothness) {
    int32_t frequency;
    if (pitch < 0) pitch = 0;
    if (pitch > 120 << 7) pitch = 120 << 7;
    if (smoothness > 0) {
      frequency = 256 << 7;
    } else if (smoothness > -16384) {
      int32_t start = pitch + (36 << 7);
      int32_t end = 256 << 7;
      frequency = start + ((end - start) * (smoothness + 16384) >> 14);
    } else {
      int32_t start = pitch - (36 << 7);
      int32_t end = pitch + (36 << 7);
      frequency = start + ((end - start) * (smoothness + 32768) >> 14);
    }
    frequency += 32768;
    return frequency < 0 ? 0 : frequency;
  }

  uint32_t phase_;
  uint16_t x_, y_;
  int32_t lp_[2];
  bool first_;
  bool snap_;
};

}  // namespace sheep

#endif  // MC_SHEEP_H_
