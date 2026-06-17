"""
Synthesize a cinematic A-minor trailer score — 78 seconds.

Structure:
  0-8s  : Bass drone fades in
  8-20s : Chord pad enters (Am voicing)
  20-38s: Lead melody begins, simple and sparse
  38-55s: Full arrangement — rhythm pulse + sub bass kicks in
  55-70s: Peak intensity, high shimmer
  70-78s: Fade out and resolve
"""
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, filtfilt

SR = 44100
TOTAL = 78
N = SR * TOTAL
t = np.arange(N) / SR

# ── Helpers ──────────────────────────────────────────────────────────────────

def sine(freq, t_arr, harmonics=((1, 1.0), (2, 0.5), (3, 0.25), (4, 0.12), (6, 0.06))):
    """Additive synthesis: fundamental + harmonics → rich tone."""
    out = np.zeros_like(t_arr)
    for ratio, amp in harmonics:
        out += amp * np.sin(2 * np.pi * freq * ratio * t_arr)
    return out

def env(t_arr, t0, t1, attack=0.5, release=1.0, level=1.0):
    """Linear attack / flat sustain / linear release envelope."""
    out = np.zeros_like(t_arr)
    # attack
    a1 = min(t0 + attack, t1)
    mask = (t_arr >= t0) & (t_arr < a1)
    out[mask] = (t_arr[mask] - t0) / attack * level
    # sustain
    s0, s1 = a1, max(a1, t1 - release)
    mask = (t_arr >= s0) & (t_arr < s1)
    out[mask] = level
    # release
    mask = (t_arr >= s1) & (t_arr < t1)
    out[mask] = level * (1 - (t_arr[mask] - s1) / release)
    return out

def lp(sig, cutoff, order=3):
    b, a = butter(order, cutoff / (SR / 2), btype='low')
    return filtfilt(b, a, sig)

def hp(sig, cutoff, order=2):
    b, a = butter(order, cutoff / (SR / 2), btype='high')
    return filtfilt(b, a, sig)

# ── Layer mixer ──────────────────────────────────────────────────────────────

mix = np.zeros(N)

# === 1. SUB BASS DRONE — A1 55 Hz ==========================================
bass_sig = sine(55, t, ((1, 1.0), (2, 0.35), (3, 0.12)))
bass_sig = lp(bass_sig, 180)
bass_sig *= env(t, 0, 78, attack=7, release=5, level=0.40)
mix += bass_sig

# === 2. CHORD PAD — Am voicing ==============================================
# A2=110  E3=164.8  A3=220  C4=261.6  E4=329.6
pad_freqs = [110, 164.8, 220, 261.6, 329.6]
pad_sig = np.zeros(N)
for f in pad_freqs:
    pad_sig += sine(f, t, ((1, 1.0), (2, 0.3), (3, 0.08))) * (1 / len(pad_freqs))
pad_sig = lp(pad_sig, 700)
pad_sig *= env(t, 8, 74, attack=5, release=5, level=0.28)
mix += pad_sig

# Second chord — F major / Fmaj7 for contrast  (enters t=28, exits t=74)
# F2=87.3  A2=110  C3=130.8  E3=164.8
pad2_freqs = [87.3, 130.8, 164.8, 207.7]   # F2 A2 C3 Ab3 (iv chord)
pad2_sig = np.zeros(N)
for f in pad2_freqs:
    pad2_sig += sine(f, t, ((1, 1.0), (2, 0.25))) * (1 / len(pad2_freqs))
pad2_sig = lp(pad2_sig, 500)
pad2_sig *= env(t, 28, 72, attack=4, release=5, level=0.16)
mix += pad2_sig

# High octave shimmer — A5=880 E5=659.3 (enters t=45)
shim_sig = sine(880, t, ((1, 1.0), (2, 0.15))) * 0.5
shim_sig += sine(659.3, t, ((1, 1.0), (2, 0.12))) * 0.5
shim_sig = lp(shim_sig, 3000)
# Tremolo: 4Hz modulation
shim_sig *= (0.7 + 0.3 * np.sin(2 * np.pi * 4 * t))
shim_sig *= env(t, 45, 70, attack=8, release=5, level=0.07)
mix += shim_sig

# === 3. LEAD MELODY — A minor pentatonic ====================================
# A C D E G (440, 523.3, 587.3, 659.3, 784)
LEAD_NOTES = [
    # Phrase 1 — sparse and emotional (t=20 – 38)
    (20.0, 2.2,  440.0),   # A4
    (22.5, 1.8,  523.3),   # C5
    (24.5, 2.2,  587.3),   # D5
    (27.0, 2.6,  659.3),   # E5
    (30.0, 1.8,  523.3),   # C5
    (32.0, 2.0,  440.0),   # A4
    (34.2, 1.6,  392.0),   # G4
    (36.0, 2.8,  440.0),   # A4 (hold)
    # Phrase 2 — ascends (t=40 – 58)
    (40.0, 1.6,  659.3),   # E5
    (42.0, 1.6,  784.0),   # G5
    (44.0, 2.2,  880.0),   # A5 (first peak)
    (46.6, 1.4,  784.0),   # G5
    (48.2, 2.2,  659.3),   # E5
    (50.8, 1.6,  587.3),   # D5
    (52.6, 1.8,  523.3),   # C5
    (54.6, 3.0,  440.0),   # A4 (resolve to root)
    # Phrase 3 — climax (t=59 – 72)
    (59.0, 1.4,  523.3),   # C5
    (60.6, 1.4,  587.3),   # D5
    (62.2, 1.8,  659.3),   # E5
    (64.4, 2.0,  784.0),   # G5
    (66.6, 1.6,  880.0),   # A5
    (68.4, 3.4,  1046.5),  # C6 (final peak, half-octave above)
]

lead_sig = np.zeros(N)
for (t0, dur, freq) in LEAD_NOTES:
    t1 = min(t0 + dur, 72.0)
    note_env = env(t, t0, t1, attack=0.06, release=min(0.35, dur * 0.4), level=1.0)
    lead_sig += sine(freq, t, ((1, 1.0), (2, 0.55), (3, 0.3), (4, 0.12))) * note_env
lead_sig = lp(lead_sig, 5000)
lead_sig *= 0.17
mix += lead_sig

# === 4. RHYTHMIC PULSE — enters t=38, builds to t=55 =======================
BPM = 75
beat_s = 60.0 / BPM          # 0.8s per beat
half_s = beat_s / 2          # 0.4s — 8th note pulse

pulse_start = 38.0
n_pulses = int((72.0 - pulse_start) / half_s)
kick_dur = int(0.15 * SR)
kick_t_local = np.arange(kick_dur) / SR

for i in range(n_pulses):
    bt = pulse_start + i * half_s
    if bt >= 72:
        break
    bt_n = int(bt * SR)

    # Intensity ramp 0→1 over first 17s of section
    ramp = min(1.0, (bt - pulse_start) / 17.0)
    level = ramp * 0.13

    # Downbeat (i%2==0) gets a deeper kick
    if i % 2 == 0:
        freq_sweep = 90 * np.exp(-kick_t_local * 22)  # pitch drops fast
        kick = np.sin(2 * np.pi * freq_sweep * kick_t_local)
        kenv = np.exp(-kick_t_local * 20)
        pulse = kick * kenv * level * 1.5
    else:
        # Off-beat: softer, higher thump
        freq_sweep = 180 * np.exp(-kick_t_local * 30)
        kick = np.sin(2 * np.pi * freq_sweep * kick_t_local)
        kenv = np.exp(-kick_t_local * 30)
        pulse = kick * kenv * level * 0.6

    end_n = min(bt_n + kick_dur, N)
    mix[bt_n:end_n] += pulse[:end_n - bt_n]

# === 5. SIMPLE CONVOLUTION REVERB — early reflections =======================
# Only on dry (before adding to mix) — simulate room reflections
# Apply to the lead and pad layers via a simple FIR approach
reflections = [(22, 0.28), (45, 0.18), (80, 0.12), (150, 0.08), (240, 0.05)]
dry = lead_sig * 0.4 + pad_sig * 0.25   # only reverb melodic layers
wet = np.zeros(N)
for delay_ms, gain in reflections:
    delay_n = int(delay_ms * SR / 1000)
    w = np.zeros(N)
    w[delay_n:] = dry[:-delay_n] * gain
    wet += w
mix += lp(wet, 4000)

# === 6. GLOBAL FADE IN / OUT =================================================
fin  = int(1.5 * SR)
fout = int(6.0 * SR)
mix[:fin]  *= np.linspace(0, 1, fin) ** 2   # quadratic ease-in
mix[-fout:] *= np.linspace(1, 0, fout) ** 1.5

# === 7. SOFT CLIP + NORMALISE ================================================
# Soft-knee limiter via tanh
mix = np.tanh(mix * 1.4) / 1.4
peak = np.max(np.abs(mix))
mix = mix / peak * 0.88

# === 8. WRITE WAV ============================================================
out_path = "/home/user/ni/trailer/public/music.wav"
wavfile.write(out_path, SR, (mix * 32767).astype(np.int16))
print(f"Written {out_path}  peak={peak:.4f}  samples={N}  duration={TOTAL}s")
