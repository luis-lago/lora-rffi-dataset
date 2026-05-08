#!/usr/bin/env python3
"""run_session.py — End-to-end LoRa OTA capture, frequency-based preamble extraction, and validation."""

import sys
import os
import json
import threading
from datetime import datetime

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks 
from PyQt5 import Qt

from lora_receiver import lora_receiver

# Session Parameters
device_id        = "device_11"
capture_duration = 60
gain             = 28
distance_cm      = 60

# Extraction Parameters
FS                  = 1e6
BW                  = 125e3
SF                  = 9
CHIRP_LEN           = int(2**SF / (BW / FS))   # = 4096 samples
MAX_PREAMBLE_CHIRPS = 9

WRAP_THRESH  = 0.3     # threshold = 0.3
CHIRP_TOL    = 0.15    # ±15% lower-bound tolerance on inter-boundary spacing
PREAMBLE_GAP = 5000    # samples; gap > this = sync word or burst-to-burst silence
ENV_CV_MAX   = 0.20    #0.15    # max envelope coefficient-of-variation (std/mean)
MIN_CHIRPS   = 4       # min consecutive upchirps to accept a preamble run
HOLDOFF_S    = 1.5     # min seconds between independent bursts
AMP_SNR      = 8.0     # smoothed-amplitude SNR for signal-region mask

# Helper Functions

def _build_mask(raw: np.ndarray) -> np.ndarray:
    """Bool mask: True where smoothed amplitude is well above the noise floor."""
    amp = np.abs(raw)
    kernel = np.ones(CHIRP_LEN) / CHIRP_LEN
    amp_smooth = np.convolve(amp, kernel, mode='same')
    noise_amp = np.percentile(amp_smooth, 5)
    return amp_smooth > AMP_SNR * noise_amp


def _inst_freq(raw: np.ndarray) -> np.ndarray:
    """
    Instantaneous frequency in rad/sample via conjugate product.
    Length = len(raw) - 1.  No unwrapping — LoRa BW/fs = 0.125 < 0.5.
    """
    return np.angle(np.conj(raw[:-1]) * raw[1:])


def _find_boundaries(mask: np.ndarray, freq: np.ndarray) -> np.ndarray:
    """
    Return indices of upchirp wrap-around points in the raw-signal index space.
    """
    dfreq = np.diff(freq)                        

    # Align masks
    mask2 = mask[1 : len(dfreq) + 1]

    # Zero out noise: multiply by float mask
    dfreq_m = dfreq * mask2.astype(float)

    # Peaks of −dfreq = minima of dfreq 
    min_dist = int(CHIRP_LEN * (1 - CHIRP_TOL))   # ~ 3482 samples
    peaks, _ = find_peaks(-dfreq_m, height=WRAP_THRESH, distance=min_dist)
    return peaks    


def _group_bursts(boundaries: np.ndarray) -> list[list[int]]:
    """
    Group consecutive boundary indices into preamble runs.
    """
    lo = int(CHIRP_LEN * (1 - CHIRP_TOL))   # ~ 3482 samples
    hi = PREAMBLE_GAP                         # 5000 samples

    bursts: list[list[int]] = []
    if len(boundaries) == 0:
        return bursts

    current = [int(boundaries[0])]
    for b in boundaries[1:]:
        gap = int(b) - current[-1]
        if lo <= gap <= hi:
            current.append(int(b))
        else:
            # Gap is either the sync-word separator or a burst-to-burst silence.
            if len(current) >= MIN_CHIRPS:
                bursts.append(current)
            current = [int(b)]

    if len(current) >= MIN_CHIRPS:
        bursts.append(current)

    # Cap each run to the first MAX_PREAMBLE_CHIRPS upchirps only
    bursts_capped = []
    for b in bursts:
        bursts_capped.append(b[:MAX_PREAMBLE_CHIRPS + 1])  # +1: boundaries fence chirps
    return bursts_capped


def _validate_chirp(raw: np.ndarray, freq: np.ndarray,
                    b0: int, b1: int) -> tuple[bool, float]:
    """
    Check whether the segment raw[b0:b1] is a clean upchirp.
    Returns (is_valid, cv).
    """
    seg      = raw[b0:b1]
    seg_freq = freq[b0 : b1 - 1]

    if len(seg) < 4 or len(seg_freq) < 4:
        return False, float('inf')

    slope_ok = float(seg_freq[-1]) > float(seg_freq[0])

    mag = np.abs(seg)
    cv  = float(mag.std() / mag.mean()) if mag.mean() > 0 else float('inf')

    return (slope_ok and cv < ENV_CV_MAX), cv


# Phase 1: Hardware Capture

timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
session_dir = f"dataset/{device_id}/{distance_cm}cm/session_{timestamp}"
os.makedirs(session_dir, exist_ok=True)

filepath_iq   = f"{session_dir}/raw_capture.iq"
filepath_meta = f"{session_dir}/metadata.json"
filepath_npy  = f"{session_dir}/extracted_preambles.npy"
filepath_plot = f"{session_dir}/verification_plot.png"

print(f"\n[{timestamp}] --- STARTING NEW SESSION ---")
print(f"Directory: {session_dir}")

print("\n--- PHASE 1: HARDWARE CAPTURE ---")
qapp = Qt.QApplication(sys.argv)

tb = lora_receiver(
    samp_rate=FS,
    gain=gain,
    filepath=filepath_iq
)

tb.start()
tb.show()

flowgraph_done = False

def wait_for_flowgraph():
    global flowgraph_done
    tb.wait()
    flowgraph_done = True

threading.Thread(target=wait_for_flowgraph, daemon=True).start()

def check_done():
    if flowgraph_done:
        qapp.quit()

timer = Qt.QTimer()
timer.timeout.connect(check_done)
timer.start(500)

qapp.exec_()

tb.stop()
tb.wait()
print(f"Capture complete. Raw IQ saved to {filepath_iq}")

# Phase 2: Frequency-based Preamble Extraction

print("\n--- PHASE 2: FREQUENCY-BASED PREAMBLE EXTRACTION ---")

try:
    raw = np.fromfile(filepath_iq, dtype=np.complex64)
    raw = raw - np.mean(raw)
except Exception as e:
    print(f"Error loading raw data: {e}")
    sys.exit(1)

print(f"  {len(raw):,} samples  ({len(raw)/FS:.1f} s at {FS/1e6:.0f} MHz)")

mask = _build_mask(raw)
print(f"  Signal mask: {mask.mean()*100:.1f}% of samples above threshold "
      f"(AMP_SNR={AMP_SNR})")

freq = _inst_freq(raw)

boundaries = _find_boundaries(mask, freq)
print(f"  Upchirp wrap-around peaks detected: {len(boundaries)}"
      f"  (expected ≈{len(raw)/FS/2:.0f} bursts × ~7 chirps each)")

bursts = _group_bursts(boundaries)
print(f"  Preamble runs (≥{MIN_CHIRPS} chirps, gap cutoff {PREAMBLE_GAP} samples, "
      f"capped at {MAX_PREAMBLE_CHIRPS}): {len(bursts)}")

preambles: list[np.ndarray] = []
holdoff = int(HOLDOFF_S * FS)
last_t  = -holdoff

for bi, bnd in enumerate(bursts):
    first = bnd[0]
    if first - last_t < holdoff:
        print(f"  Burst {bi:02d} @ {first:,}: skipped (holdoff)")
        continue

    n_pairs = len(bnd) - 1
    valid_segs: list[np.ndarray] = []
    rej: list[str] = []

    for ci in range(n_pairs):
        b0, b1 = bnd[ci], bnd[ci + 1]
        ok, cv = _validate_chirp(raw, freq, b0, b1)
        if ok:
            valid_segs.append(raw[b0:b1].copy())
        else:
            rej.append(f"c{ci}:cv={cv:.2f}")

    n_ok = len(valid_segs)
    status = f"{n_pairs} chirps, {n_ok} valid"
    if rej:
        status += f"  [rej: {' '.join(rej)}]"
    print(f"  Burst {bi:02d} @ sample {first:,}: {status}")

    if n_ok == 0:
        continue

    preamble = np.concatenate(valid_segs).astype(np.complex64)
    preambles.append(preamble)
    last_t = first

print(f"\nResult: {len(preambles)} valid preamble(s) extracted")

if len(preambles) == 0:
    print("CRITICAL: 0 valid preambles extracted. Check signal quality.")
    sys.exit(1)

lengths = {len(p) for p in preambles}
if len(lengths) == 1:
    arr = np.array(preambles, dtype=np.complex64)
    print(f"  Uniform length {next(iter(lengths))} → 2-D array {arr.shape}")
else:
    arr = np.empty(len(preambles), dtype=object)
    for i, p in enumerate(preambles):
        arr[i] = p
    print(f"  Variable lengths {lengths} → object array (shape {arr.shape})")

np.save(filepath_npy, arr, allow_pickle=True)
print(f"  Saved → {filepath_npy}")

# Phase 3: Metadata Verification Plot

print("\n--- PHASE 3: METADATA & VISUAL VERIFICATION ---")

metadata = {
    "device_id":               device_id,
    "timestamp":               timestamp,
    "sample_rate":             FS,
    "gain":                    gain,
    "distance_cm":             distance_cm,
    "chirp_length":            CHIRP_LEN,
    "num_preambles_extracted": len(preambles),
    "SF":                      SF,
    "BW":                      BW,
}

with open(filepath_meta, 'w') as f:
    json.dump(metadata, f, indent=4)
print(f"-> Saved {filepath_meta}")

# 4-panel verification plot for the first extracted preamble
p     = preambles[0]
t     = np.arange(len(p))
pfreq = _inst_freq(p)

pdfreq   = np.diff(pfreq)
min_dist = int(CHIRP_LEN * (1 - CHIRP_TOL))
in_peaks, _ = find_peaks(-pdfreq, height=WRAP_THRESH, distance=min_dist)

n_chirps = len(p) // CHIRP_LEN

fig, axes = plt.subplots(4, 1, figsize=(13, 10), sharex=False)
fig.suptitle(
    f"Verification: {device_id} | {distance_cm} cm | "
    f"{len(p):,} samples ({n_chirps} upchirps × {CHIRP_LEN} samples)",
    fontsize=11
)

axes[0].plot(t, np.abs(p), 'k', lw=0.7)
axes[0].set_ylabel("Magnitude")
for b in in_peaks:
    axes[0].axvline(b, color='crimson', lw=0.8, alpha=0.55)

axes[1].plot(t, p.real, color='royalblue', lw=0.5)
axes[1].set_ylabel("I (Real)")

axes[2].plot(t, p.imag, color='darkorange', lw=0.5)
axes[2].set_ylabel("Q (Imag)")

axes[3].plot(np.arange(len(pfreq)), pfreq, color='seagreen', lw=0.8)
for b in in_peaks:
    axes[3].axvline(b, color='crimson', lw=0.8, alpha=0.55,
                    label='chirp boundary' if b == in_peaks[0] else '')
axes[3].set_ylabel("Inst. freq (rad/samp)")
axes[3].set_xlabel("Sample index")
axes[3].set_title(
    "Instantaneous frequency — positive-slope sawtooth = upchirps only  "
    "(red = wrap-around boundaries)"
)
if len(in_peaks):
    axes[3].legend(loc='upper right', fontsize=8)

plt.tight_layout()
plt.savefig(filepath_plot, dpi=130)
plt.close()
print(f"-> Saved {filepath_plot}")

samples_per_preamble = [len(p) for p in preambles]
print(f"\n=== Session Complete ===")
print(f"  Bursts detected:        {len(bursts)}")
print(f"  Valid preambles saved:  {len(preambles)}")
print(f"  Samples per preamble:   {samples_per_preamble[0]}"
      + (f"  (varies: {set(samples_per_preamble)})" if len(set(samples_per_preamble)) > 1 else ""))
print(f"  Output directory:       {session_dir}")
