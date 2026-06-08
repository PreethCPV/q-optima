import numpy as np
from scipy.signal import butter, filtfilt
from sklearn.preprocessing import MinMaxScaler
import warnings
import pandas as pd

FS = 360   
CLINICAL_MINS = np.array([0.3,  0.04, 0.08, -0.5])   # [RR, QRS, PR, ST]
CLINICAL_MAXS = np.array([1.5,  0.20, 0.30,  0.5])

BEAT_LABELS = {
    'N': 'Normal',
    'V': 'Premature Ventricular Contraction (PVC)',
    'A': 'Atrial Premature Beat (APC)',
    'L': 'Left Bundle Branch Block (LBBB)',
    'R': 'Right Bundle Branch Block (RBBB)',
    '/': 'Paced Beat',
    'f': 'Fusion of Paced and Normal',
    'F': 'Fusion of Ventricular and Normal',
}

# ── Bandpass Filter ───────────────────────────────────────────────────────────

def bandpass_filter(signal: np.ndarray,
                    lowcut: float = 0.5,
                    highcut: float = 45.0,
                    fs: int = FS,
                    order: int = 4) -> np.ndarray:
    """
    Butterworth bandpass filter — mandatory before any ECG analysis.
    """
    nyq = 0.5 * fs
    b, a = butter(order, [lowcut / nyq, highcut / nyq], btype='band')
    return filtfilt(b, a, signal)

# ── Core Feature Extraction ───────────────────────────────────────────────────

# ── Core Feature Extraction ───────────────────────────────────────────────────

def extract_ecg_features_for_beat(filtered_signal: np.ndarray,
                                   ann_samples: np.ndarray,
                                   beat_idx: int) -> dict:
    """
    Extract 4 clinical features using highly robust NumPy local search.
    Bypasses third-party libraries to prevent crashes on severely arrhythmic data.
    """
    if beat_idx < 1 or beat_idx >= len(ann_samples):
        return None

    # ── 1. RR Interval (Perfectly accurate from annotations) ──────────────────
    r_curr = int(ann_samples[beat_idx])
    r_prev = int(ann_samples[beat_idx - 1])
    rr_interval = (r_curr - r_prev) / FS   # seconds

    # Define standard clinical search windows (in samples)
    w_06 = int(0.06 * FS)  # 60 ms
    w_12 = int(0.12 * FS)  # 120 ms
    w_25 = int(0.25 * FS)  # 250 ms

    # Ensure we don't go out of bounds at the very start/end of the recording
    if r_curr - w_25 < 0 or r_curr + w_12 >= len(filtered_signal):
        return None

    # ── 2. QRS Duration (Local minima around R peak) ────────────────────────
    # Q wave: lowest point just before R
    q_window = filtered_signal[r_curr - w_06 : r_curr]
    q_idx = (r_curr - w_06) + np.argmin(q_window)

    # S wave: lowest point just after R
    s_window = filtered_signal[r_curr : r_curr + w_06]
    s_idx = r_curr + np.argmin(s_window)

    qrs_duration = max(0.04, (s_idx - q_idx) / FS)

    # ── 3. PR Interval (Local max before Q wave) ────────────────────────────
    p_window = filtered_signal[r_curr - w_25 : q_idx]
    if len(p_window) > 0:
        p_idx = (r_curr - w_25) + np.argmax(p_window)
    else:
        p_idx = r_curr - w_25 # Fallback
        
    pr_interval = max(0.08, (r_curr - p_idx) / FS)

    # ── 4. ST Deviation (Relative to PR isoelectric baseline) ───────────────
    # Isoelectric baseline: mean voltage between P and Q waves
    if p_idx < q_idx:
        baseline = float(np.mean(filtered_signal[p_idx:q_idx]))
    else:
        baseline = float(filtered_signal[q_idx])

    # ST Segment: mean voltage 60ms to 120ms after S peak
    st_window = filtered_signal[s_idx + w_06 : s_idx + w_12]
    if len(st_window) > 0:
        st_mean = float(np.mean(st_window))
    else:
        st_mean = baseline
        
    st_deviation = st_mean - baseline

    return {
        'rr_interval':  float(rr_interval),
        'qrs_duration': float(qrs_duration),
        'pr_interval':  float(pr_interval),
        'st_deviation': float(st_deviation),
    }
# ── Public API ────────────────────────────────────────────────────────────────

def get_ecg_features(record_id: str = '100',
                      beat_idx: int = 10,
                      num_features: int = 2):
    """
    Full ECG feature extraction pipeline — public interface matching
    get_iris_features() signature for drop-in use in main.py.
    """
    try:
        import wfdb
    except ImportError:
        raise ImportError(
            "wfdb not installed.\n"
            "Run: pip install wfdb\n"
            "MIT-BIH data downloads automatically from PhysioNet on first call."
        )

    if num_features not in (2, 4):
        raise ValueError(f"num_features must be 2 or 4, got {num_features}")

    # Load record and annotation from PhysioNet
    record     = wfdb.rdrecord(record_id, pn_dir='mitdb')
    annotation = wfdb.rdann(record_id,   'atr',  pn_dir='mitdb')

    # Use Lead II (channel 0) — standard clinical monitoring lead
    raw_signal = record.p_signal[:, 0]

    # Mandatory bandpass filter before any processing
    filtered = bandpass_filter(raw_signal, lowcut=0.5, highcut=45.0, fs=FS)

    # Fix 1: R-peak positions directly from annotation — no find_peaks
    ann_samples = annotation.sample

    # Beat label from annotation symbol list
    symbols    = annotation.symbol
    beat_char  = symbols[beat_idx] if beat_idx < len(symbols) else 'N'
    beat_label = BEAT_LABELS.get(beat_char, f'Unknown ({beat_char})')

    # Extract features using NeuroKit2 delineation
    raw_features = extract_ecg_features_for_beat(filtered, ann_samples, beat_idx)

    if raw_features is None:
        raise ValueError(
            f"Feature extraction failed for beat {beat_idx} in record {record_id}.\n"
            f"Try a different beat_idx (recommended range: 10–100)."
        )

    # Select features based on num_features
    all_names       = ['rr_interval', 'qrs_duration', 'pr_interval', 'st_deviation']
    selected_names  = all_names[:num_features]
    selected_values = np.array([[raw_features[n] for n in selected_names]])

    # Normalize to [0, 2π] using fixed clinical reference ranges
    scaler = MinMaxScaler(feature_range=(0, 2 * np.pi))
    scaler.fit(np.vstack([
        CLINICAL_MINS[:num_features],
        CLINICAL_MAXS[:num_features]
    ]))
    normalized = scaler.transform(selected_values)[0]

    display_names = {
        'rr_interval':  'RR Interval (s)',
        'qrs_duration': 'QRS Duration (s)',
        'pr_interval':  'PR Interval (s)',
        'st_deviation': 'ST Deviation (mV)',
    }
    feature_names = [display_names[n] for n in selected_names]

    # Build waves_info for ECG waveform visualization
    # Contains raw sample indices in global signal coordinates
    raw = extract_ecg_features_for_beat(filtered, ann_samples, beat_idx)
    w_06 = int(0.06 * FS)
    w_25 = int(0.25 * FS)
    r_curr = int(ann_samples[beat_idx])
    q_window = filtered[r_curr - w_06 : r_curr]
    q_idx = (r_curr - w_06) + int(np.argmin(q_window))
    s_window = filtered[r_curr : r_curr + w_06]
    s_idx = r_curr + int(np.argmin(s_window))
    p_window = filtered[r_curr - w_25 : q_idx]
    p_idx = (r_curr - w_25) + int(np.argmax(p_window)) if len(p_window) > 0 else r_curr - w_25

    waves_info = {
        'r_curr': r_curr,
        'p_idx':  p_idx,
        'q_idx':  q_idx,
        's_idx':  s_idx,
        'filtered_signal': filtered,
        'beat_window_start': max(0, r_curr - w_25 - int(0.05 * FS)),
        'beat_window_end':   min(len(filtered), r_curr + int(0.30 * FS)),
    }

    return list(normalized), feature_names, beat_label, waves_info

def get_ecg_description(features: list,
                         feature_names: list,
                         beat_label: str,
                         record_id: str) -> dict:
    """Display metadata matching zz_info interface used in main.py."""
    return {
        'record_id':     record_id,
        'beat_label':    beat_label,
        'feature_names': feature_names,
        'features':      features,
        'num_features':  len(features),
        'class_name':    beat_label,   # matches zz_info['class_name']
    }

def generate_ecg_prompt(features: list, feature_names: list) -> str:
    """
    Generate ZZ Feature Map circuit prompt from ECG features.
    Drop-in replacement for generate_zz_prompt() — identical interface.
    """
    n = len(features)

    if n == 2:
        x0, x1 = features
        zz_angle = 2 * (np.pi - x0) * (np.pi - x1)
        return (
            f"Create a 2-qubit ZZ Feature Map circuit with {n} qubits and {n} classical bits. "
            f"Step 1: Apply H gate to qubits 0 and 1. "
            f"Step 2: Apply Rz({x0:.4f}) to qubit 0 and Rz({x1:.4f}) to qubit 1. "
            f"Step 3: Apply CNOT from qubit 0 to qubit 1. "
            f"Step 4: Apply Rz({zz_angle:.4f}) to qubit 1 (ZZ interaction angle). "
            f"Step 5: Apply CNOT from qubit 0 to qubit 1. "
            f"Step 6: Repeat Steps 1-5 exactly once more (second ZZ layer). "
            f"Step 7: Measure qubits 0 and 1 using qc.measure([0, 1], [0, 1]). "
            f"Do NOT use measure_all(). Write clean static code only."
        )

    elif n == 4:
        x0, x1, x2, x3 = features
        zz_01 = 2 * (np.pi - x0) * (np.pi - x1)
        zz_12 = 2 * (np.pi - x1) * (np.pi - x2)
        zz_23 = 2 * (np.pi - x2) * (np.pi - x3)
        return (
            f"Create a 4-qubit ZZ Feature Map circuit with {n} qubits and {n} classical bits. "
            f"Step 1: Apply H gate to all qubits 0, 1, 2, 3. "
            f"Step 2: Apply Rz({x0:.4f}) to qubit 0, Rz({x1:.4f}) to qubit 1, "
            f"Rz({x2:.4f}) to qubit 2, Rz({x3:.4f}) to qubit 3. "
            f"Step 3: Apply CNOT(0,1), then Rz({zz_01:.4f}) to qubit 1, then CNOT(0,1). "
            f"Step 4: Apply CNOT(1,2), then Rz({zz_12:.4f}) to qubit 2, then CNOT(1,2). "
            f"Step 5: Apply CNOT(2,3), then Rz({zz_23:.4f}) to qubit 3, then CNOT(2,3). "
            f"Step 6: Repeat Steps 1-5 exactly once more (second ZZ layer). "
            f"Step 7: Measure qubits 0,1,2,3 using qc.measure([0,1,2,3],[0,1,2,3]). "
            f"Do NOT use measure_all(). Write clean static code only."
        )

    else:
        raise ValueError(f"num_features must be 2 or 4, got {n}")