# Replace the existing synthesize_virtual_bass function with this one
import numpy as np
from scipy import signal
from typing import Dict


def _duplicate_sos(sos: np.ndarray, times: int) -> np.ndarray:
    """
    Duplicate each second-order section in 'sos' a total of 'times' times,
    by simply stacking the same sos matrix over and over.

    Example: if sos has shape (n_sections, 6), then the result will have
    shape (n_sections * times, 6).
    """
    return np.vstack([sos for _ in range(times)])


def _mag_at(freq_hz: float, fs: int, ir: np.ndarray) -> float:
    """
    Return the magnitude (absolute value) of IR 'ir' at frequency 'freq_hz'.
    We compute the FFT of the entire impulse response and pick the bin closest
    to freq_hz.

    - freq_hz: frequency (in Hz) at which to measure magnitude
    - fs: sampling rate of 'ir'
    - ir: 1D NumPy array of impulse‐response samples

    Returns:
        Absolute‐value of IR spectrum at 'freq_hz'.
    """
    n = len(ir)
    # Compute a real‐FFT of the IR
    H = np.fft.rfft(ir)
    freqs = np.fft.rfftfreq(n, 1.0 / fs)      # bins in Hz
    # Find the index closest to freq_hz
    idx = np.argmin(np.abs(freqs - freq_hz))
    return float(np.abs(H[idx]))


def _rbj_high_shelf(fc: float, fs: int, gain_db: float, Q: float) -> np.ndarray:
    """
    Design a 2nd‐order (biquad) high‐shelf filter using RBJ (AudioEQ) formulas,
    returning it as an SOS matrix.

    - fc: shelf cutoff frequency (Hz)
    - fs: sampling rate (Hz)
    - gain_db: shelf gain in dB (positive → boost; negative → cut)
    - Q: filter Q factor

    Returns:
        sos array of shape (1, 6) (one biquad section).
    """
    A = 10 ** (gain_db / 40.0)        # linear gain
    w0 = 2 * np.pi * fc / fs
    alpha = np.sin(w0) / (2 * Q)
    cos_w0 = np.cos(w0)

    # RBJ (Audio EQ Cookbook) high‐shelf coefficients:
    b0 =    A * ((A + 1) + (A - 1) * cos_w0 + 2 * np.sqrt(A) * alpha)
    b1 = -2 * A * ((A - 1) + (A + 1) * cos_w0)
    b2 =    A * ((A + 1) + (A - 1) * cos_w0 - 2 * np.sqrt(A) * alpha)
    a0 =        (    (A + 1) - (A - 1) * cos_w0 + 2 * np.sqrt(A) * alpha)
    a1 =  2 * ((A - 1) - (A + 1) * cos_w0)
    a2 =        ((A + 1) - (A - 1) * cos_w0 - 2 * np.sqrt(A) * alpha)

    # Convert to SOS form (one biquad section)
    sos = signal.tf2sos([b0, b1, b2], [a0, a1, a2])
    return sos


def _shift(sig: np.ndarray, delay: int, length: int) -> np.ndarray:
    """
    Circularly shift (delay or advance) 1D array 'sig' to length 'length',
    padding or truncating so the output is exactly 'length' samples.

    - sig: input array (1D)
    - delay: integer number of samples to delay (+) or advance (–)
    - length: desired length of output array

    Returns:
        1D array of length 'length'.  If delay > 0, the signal is
        shifted right by 'delay' samples (zero‐padding at front);
        if delay < 0, the signal is shifted left (zero‐padding at end).
    """
    out = np.zeros(length, dtype=sig.dtype)
    if delay >= 0:
        # Delay (pad with zeros at front, then truncate if sig is too long)
        if delay < length:
            # Copy as much of sig as fits
            avail = min(length - delay, len(sig))
            out[delay : delay + avail] = sig[:avail]
    else:
        # Advance: shift signal left by |delay|
        adv = -delay  # positive number of samples to advance
        if adv < len(sig):
            avail = min(length, len(sig) - adv)
            out[:avail] = sig[adv : adv + avail]
        # else if adv ≥ len(sig), everything is shifted off → remains zeros
    return out


def synthesize_virtual_bass(hrir, *, xo_hz: int = 250, head_ms: float = 1.0,
                            hp_fc: float = 15.0) -> None:
    """Mutate *hrir* in‑place, injecting virtual‑bass split/merge."""
    fs = hrir.fs

    # 0) Normalise lengths
    n_ir = max(len(ir.data) for sp in hrir.irs.values() for ir in sp.values())
    for pair in hrir.irs.values():
        for ear in ("left", "right"):
            d = pair[ear].data
            if len(d) < n_ir:
                pair[ear].data = np.pad(d, (0, n_ir - len(d)))

    # 1) Build a single, base band-passed impulse response for bass
    imp = np.zeros(n_ir)
    imp[0] = 1.0
    
    # Create high-pass filter for sub-bass roll-off
    sos_hp4 = signal.butter(4, hp_fc / (fs / 2), btype="high", output="sos")
    mpbass_hp_only = signal.sosfilt(sos_hp4, imp)

    # Create crossover low-pass filter
    sos_lp4_xo = signal.butter(4, xo_hz / (fs / 2), btype="low", output="sos")
    sos_lp8_xo = _duplicate_sos(sos_lp4_xo, 2)
    
    # Create the final base bass impulse (now band-passed)
    mpbass = signal.sosfilt(sos_lp8_xo, mpbass_hp_only)

    # 2) Prepare ILD shelf filters and the complementary crossover high-pass
    shelves = [
        (150.0, -1.5, 0.760),
        (400.0, -3.0, 0.660),
        (800.0, -3.5, 0.610),
    ]
    sos_ild = np.vstack([_rbj_high_shelf(fc, fs, g, Q) for fc, g, Q in shelves])
    
    sos_hp4_xo = signal.butter(4, xo_hz / (fs / 2), btype="high", output="sos")
    sos_hp8_xo = _duplicate_sos(sos_hp4_xo, 2)

    # 3) Compute a single global VBass gain (g_global) across all HRIR pairs
    all_xo_mags = []
    for spk, pair in hrir.irs.items():
        hi_l = signal.sosfilt(sos_hp8_xo, pair["left"].data)
        hi_r = signal.sosfilt(sos_hp8_xo, pair["right"].data)
        all_xo_mags.append(_mag_at(xo_hz, fs, hi_l))
        all_xo_mags.append(_mag_at(xo_hz, fs, hi_r))

    mean_xo_mag = float(np.mean(all_xo_mags))
    mpbass_mag = _mag_at(xo_hz, fs, mpbass) + 1e-20
    g_global = mean_xo_mag / mpbass_mag

    # 3) Cached per-speaker gains and other parameters
    speaker_gain: Dict[str, float] = {}
    head_samples = int(round(head_ms * 1e-3 * fs))

    # 4) Process each speaker
    for spk, pair in hrir.irs.items():
        spk_on_left = spk.upper().endswith("L")
        left_peak, right_peak = pair["left"].peak_index(), pair["right"].peak_index()
        itd_samples = right_peak - left_peak

        gain = g_global

        # 4b) Determine polarity by looking at whichever ear has the larger peak magnitude.
        left_peak_idx  = pair["left"].peak_index()
        right_peak_idx = pair["right"].peak_index()
        left_val  = pair["left"].data[left_peak_idx]
        right_val = pair["right"].data[right_peak_idx]

        # Pick sign of the bigger‐magnitude peak, so both ears use the same "pol".
        if abs(left_val) >= abs(right_val):
            pol = +1.0 if left_val >= 0 else -1.0
        else:
            pol = +1.0 if right_val >= 0 else -1.0

        # 4c) Create scaled and shaped synth IRs (NEW, CORRECTED LOGIC)
        # First, scale the primary mpbass. This is the direct signal.
        synth_direct_undelayed = mpbass * gain * pol
        
        # Second, create the cross signal by applying ILD shelves to the *already scaled* direct signal.
        # This preserves the ILD shape relative to the correctly matched direct signal.
        synth_cross_undelayed = signal.sosfilt(sos_ild, synth_direct_undelayed)

        # 4d) Apply delays to the synthesized signals
        direct_delay = head_samples
        cross_delay = head_samples + (itd_samples if spk_on_left else -itd_samples)
        synth_direct = _shift(synth_direct_undelayed, direct_delay, n_ir)
        synth_cross  = _shift(synth_cross_undelayed,  cross_delay,  n_ir)

        # 4e) High-pass the original signals and sum them with the new synthetic signals
        orig_left  = pair["left"].data
        orig_right = pair["right"].data
        hi_left  = signal.sosfilt(sos_hp8_xo, orig_left)
        hi_right = signal.sosfilt(sos_hp8_xo, orig_right)

        new_left  = hi_left  + (synth_direct if spk_on_left else synth_cross)
        new_right = hi_right + (synth_cross  if spk_on_left else synth_direct)

        pair["left"].data  = new_left[:len(orig_left)]
        pair["right"].data = new_right[:len(orig_right)]

    # Done – *hrir* mutates in‑place
    return None