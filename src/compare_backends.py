"""
Q-Optima Backend Comparison Visualizer
Generates cross-backend comparison graphs from saved JSON result files.

Run AFTER completing ZZ runs on all 3 backends separately:
    python src/compare_backends.py

Reads  : results/run_*.json
Outputs: visual_dataset/  (separate folder, never overwrites)

Visualizations generated:
  1. absolute_error_heatmap.png  — corrected noise heatmap (error not probability)
  2. radar_chart.png             — normalized radar chart (all axes: lower = better)
  3. fidelity_comparison.png     — side-by-side fidelity bar chart
  4. measurement_grid.png        — 3-panel ideal vs noisy per backend
"""

import os
import json
import glob
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from datetime import datetime


# ── Output directory ──────────────────────────────────────────────────────────
OUTPUT_DIR = 'visual_dataset'
RESULTS_DIR = 'results'

BACKEND_COLORS = {
    'manila':    '#2E86AB',   # blue
    'jakarta':   '#E84855',   # red
    'guadalupe': '#3BB273',   # green
}

BACKEND_LABELS = {
    'manila':    'FakeManilaV2 (5Q Linear)',
    'jakarta':   'FakeJakartaV2 (7Q Heavy-Hex)',
    'guadalupe': 'FakeGuadalupeV2 (16Q Heavy-Hex)',
}


def ensure_dirs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)


def timestamped(name: str) -> str:
    """Return filename with timestamp so files never overwrite."""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return os.path.join(OUTPUT_DIR, f"{ts}_{name}")


# ── Load saved results ────────────────────────────────────────────────────────

def load_results(num_features: int = None) -> list:
    """Load latest JSON per backend, optionally filtered by num_features."""
    files = glob.glob(os.path.join(RESULTS_DIR, 'run_*.json'))
    if not files:
        print(f"❌ No result files found in {RESULTS_DIR}/")
        return []

    all_results = []
    for f in sorted(files):
        with open(f, 'r') as fp:
            all_results.append(json.load(fp))

    # Filter by num_features if specified
    if num_features is not None:
        all_results = [r for r in all_results if r.get('num_features', 2) == num_features]

    # Keep only latest JSON per backend_key
    latest = {}
    for r in all_results:
        key = r['backend_key']
        if key not in latest or r['timestamp'] > latest[key]['timestamp']:
            latest[key] = r

    results = list(latest.values())
    print(f"✅ Loaded {len(results)} result(s) (latest per backend): "
          f"{[r['backend_key'] for r in results]}")
    return results

def get_latest_per_backend(all_results: list, mode: str, num_features: int) -> list:
    filtered = [r for r in all_results 
                if r.get('mode') == mode 
                and r.get('num_features', 2) == num_features]
    latest = {}
    for r in filtered:
        key = r['backend_key']
        if key not in latest or r['timestamp'] > latest[key]['timestamp']:
            latest[key] = r
    return list(latest.values())

# ── Visualization 1: Absolute Error Heatmap ──────────────────────────────────

def plot_absolute_error_heatmap(results: list, prefix: str = ""):
    """
    Corrected heatmap: plots (Noisy Probability - Ideal Probability) per state.

    Why absolute error not raw probability:
      - At 4 qubits, 16 states make raw probability comparison unreadable
      - Error map highlights exactly which states are corrupted by noise
      - A perfect circuit shows solid white/neutral row
      - Hardware errors appear as vivid red (positive error) or blue (negative)
      - Instantly comparable across backends regardless of qubit count
    """
    backends_with_data = [r for r in results if 'ideal_counts' in r and 'noisy_counts' in r]
    if not backends_with_data:
        print("⚠️  No measurement count data found. Skipping heatmap.")
        return

    # Collect all states across all backends
    all_states = set()
    for r in backends_with_data:
        all_states.update(r['ideal_counts'].keys())
        all_states.update(r['noisy_counts'].keys())
    all_states = sorted(all_states)
    shots = 1024

    backend_keys = [r['backend_key'] for r in backends_with_data]
    n_backends = len(backend_keys)
    n_states = len(all_states)

    # Build error matrix: rows=backends, cols=states
    error_matrix = np.zeros((n_backends, n_states))
    for i, r in enumerate(backends_with_data):
        for j, state in enumerate(all_states):
            ideal_p = r['ideal_counts'].get(state, 0) / shots
            noisy_p = r['noisy_counts'].get(state, 0) / shots
            error_matrix[i, j] = noisy_p - ideal_p   # signed error

    fig, ax = plt.subplots(figsize=(max(10, n_states * 0.8), 4 + n_backends))

    # Diverging colormap: blue=negative error, white=zero, red=positive error
    vmax = max(0.15, np.abs(error_matrix).max())
    im = ax.imshow(error_matrix, cmap='RdBu_r', aspect='auto',
                   vmin=-vmax, vmax=vmax)

    # Axis labels
    ax.set_xticks(range(n_states))
    ax.set_xticklabels(all_states, rotation=45, ha='right', fontsize=9)
    ax.set_yticks(range(n_backends))
    ax.set_yticklabels([BACKEND_LABELS.get(k, k) for k in backend_keys], fontsize=10)

    # Annotate each cell with error value
    for i in range(n_backends):
        for j in range(n_states):
            val = error_matrix[i, j]
            text_color = 'white' if abs(val) > 0.08 else 'black'
            ax.text(j, i, f'{val:+.3f}', ha='center', va='center',
                    fontsize=8, color=text_color, fontweight='bold')

    plt.colorbar(im, ax=ax, label='Noisy − Ideal Probability (Error)',
                 fraction=0.046, pad=0.04)

    ax.set_title('Noise Impact Heatmap: Absolute Error per Quantum State\n'
                 '(Red = noise increased probability, Blue = noise decreased probability, '
                 'White = no noise impact)',
                 fontsize=12, fontweight='bold', pad=15)
    ax.set_xlabel('Measurement Outcome', fontsize=11)

    plt.tight_layout()
    filepath = timestamped(f'{prefix}_absolute_error_heatmap.png' if prefix else 'absolute_error_heatmap.png')
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"📊 Absolute error heatmap saved: {filepath}")


# ── Visualization 2: Normalized Radar Chart ───────────────────────────────────

def plot_radar_chart(results: list, prefix: str=""):
    """
    Corrected radar chart with normalized axes where outer edge = BEST.

    Fix applied:
      - All metrics normalized so that LOWER raw value = WORSE = inner ring
      - Fidelity      : plotted directly (higher = better = outer ring) ✅
      - Circuit depth : plotted as (1 - depth/max_depth) so shallower = outer ✅
      - Gate count    : plotted as (1 - gates/max_gates) so fewer = outer ✅
      - SWAP overhead : plotted as (1 - swaps/max_swaps) so fewer = outer ✅
      - Error rate    : plotted as (1 - error_rate) so lower error = outer ✅

    This ensures the radar shape directly represents "better performance"
    — larger polygon = better backend across all metrics simultaneously.
    """
    backends_with_metrics = [r for r in results if 'metrics' in r]
    if len(backends_with_metrics) < 2:
        print("⚠️  Need metrics data from at least 2 backends. Skipping radar chart.")
        return

    metric_labels = [
        'Fidelity\n(higher=better)',
        'Circuit Efficiency\n(shallower=better)',
        'Gate Efficiency\n(fewer=better)',
        'SWAP Efficiency\n(fewer=better)',
        'Noise Resilience\n(lower error=better)',
    ]
    n_metrics = len(metric_labels)
    angles = np.linspace(0, 2 * np.pi, n_metrics, endpoint=False).tolist()
    angles += angles[:1]   # close the polygon

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

    # Collect raw values for normalization
    all_fidelities   = [r['metrics']['final_fidelity']    for r in backends_with_metrics]
    all_depths       = [r['metrics']['physical_depth']    for r in backends_with_metrics]
    all_gates        = [r['metrics']['total_gates']       for r in backends_with_metrics]
    all_swaps        = [r['metrics']['swap_count']        for r in backends_with_metrics]
    all_error_rates  = [1 - r['metrics']['final_fidelity'] for r in backends_with_metrics]

    max_depth     = max(all_depths)     if max(all_depths) > 0     else 1
    max_gates     = max(all_gates)      if max(all_gates) > 0      else 1
    max_swaps     = max(all_swaps)      if max(all_swaps) > 0      else 1
    max_error     = max(all_error_rates) if max(all_error_rates) > 0 else 1

    for r in backends_with_metrics:
        m = r['metrics']
        bk = r['backend_key']
        fidelity    = m['final_fidelity']
        error_rate  = 1 - fidelity

        # Normalize: all values mapped to [0,1] where 1 = best
        norm_fidelity   = fidelity
        norm_depth      = 1 - (m['physical_depth'] / max_depth)
        norm_gates      = 1 - (m['total_gates']    / max_gates)
        norm_swaps      = 1 - (m['swap_count']     / max_swaps)
        norm_noise      = 1 - (error_rate           / max_error)

        values = [norm_fidelity, norm_depth, norm_gates, norm_swaps, norm_noise]
        values += values[:1]   # close polygon

        color = BACKEND_COLORS.get(bk, '#888888')
        label = BACKEND_LABELS.get(bk, bk)

        ax.plot(angles, values, 'o-', linewidth=2, color=color, label=label)
        ax.fill(angles, values, alpha=0.15, color=color)

    # Axis formatting
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(metric_labels, fontsize=9)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(['25%', '50%', '75%', '100%'], fontsize=7)
    ax.grid(color='grey', linestyle='--', linewidth=0.5, alpha=0.7)

    ax.set_title('Backend Performance Radar Chart\n'
                 '(Outer edge = Best performance on each metric)',
                 fontsize=13, fontweight='bold', pad=25)
    ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.15), fontsize=9)

    plt.tight_layout()
    filepath = timestamped(f'{prefix}_radar_chart.png' if prefix else 'radar_chart.png')
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"📊 Radar chart saved: {filepath}")


# ── Visualization 3: Fidelity Comparison Bar Chart ───────────────────────────

def plot_fidelity_comparison(results: list, prefix: str = ""):
    """
    Simple grouped bar chart comparing final fidelity across backends.
    Includes threshold line at 0.60.
    """
    backends = [r['backend_key'] for r in results]
    fidelities = [r.get('final_fidelity', 0) for r in results]
    colors = [BACKEND_COLORS.get(b, '#888888') for b in backends]
    labels = [BACKEND_LABELS.get(b, b) for b in backends]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(range(len(backends)), fidelities, color=colors,
                  alpha=0.85, edgecolor='black', linewidth=0.8, width=0.5)

    # Threshold line
    ax.axhline(y=0.60, color='#DC143C', linestyle='--',
               linewidth=2, label='Threshold (0.60)')

    # Value labels on bars
    for bar, fid in zip(bars, fidelities):
        color = '#2E8B57' if fid >= 0.60 else '#DC143C'
        status = '✅ CERTIFIED' if fid >= 0.60 else '❌ REJECTED'
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.01,
                f'{fid:.4f}\n{status}',
                ha='center', va='bottom', fontsize=9,
                fontweight='bold', color=color)

    ax.set_xticks(range(len(backends)))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel('Hellinger Fidelity', fontsize=12)
    ax.set_ylim(0, 1.15)
    ax.set_title('ZZ Feature Map Encoding Fidelity Across Backends\n'
                 '(Q-Optima Certification Results)',
                 fontsize=13, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(axis='y', alpha=0.3)

    plt.tight_layout()
    filepath = timestamped(f'{prefix}_fidelity_comparison.png' if prefix else 'fidelity_comparison.png')
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"📊 Fidelity comparison saved: {filepath}")


# ── Visualization 4: 3-Panel Measurement Grid ─────────────────────────────────

def plot_measurement_grid(results: list, prefix: str=""):
    """
    3-panel figure: one ideal vs noisy bar chart per backend side by side.
    Allows direct visual comparison of noise pattern differences.
    """
    backends_with_data = [r for r in results if 'ideal_counts' in r and 'noisy_counts' in r]
    if not backends_with_data:
        print("⚠️  No measurement data. Skipping measurement grid.")
        return

    n = len(backends_with_data)
    fig, axes = plt.subplots(1, n, figsize=(7 * n, 6), sharey=True)
    if n == 1:
        axes = [axes]

    shots = 1024

    for ax, r in zip(axes, backends_with_data):
        bk = r['backend_key']
        all_states = sorted(
            set(r['ideal_counts'].keys()) | set(r['noisy_counts'].keys())
        )
        ideal_p = [r['ideal_counts'].get(s, 0) / shots for s in all_states]
        noisy_p = [r['noisy_counts'].get(s, 0) / shots for s in all_states]

        x = np.arange(len(all_states))
        width = 0.35
        ax.bar(x - width / 2, ideal_p, width, label='Ideal',
               color='#2E8B57', alpha=0.85, edgecolor='black', linewidth=0.5)
        ax.bar(x + width / 2, noisy_p, width, label=f'Noisy ({bk.capitalize()})',
               color=BACKEND_COLORS.get(bk, '#888888'),
               alpha=0.85, edgecolor='black', linewidth=0.5)

        ax.set_xticks(x)
        ax.set_xticklabels(all_states, rotation=45, ha='right', fontsize=8)
        ax.set_title(BACKEND_LABELS.get(bk, bk), fontsize=10, fontweight='bold')
        ax.set_xlabel('Measurement Outcome', fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(axis='y', alpha=0.3)
        ax.set_ylim(0, 1.0)

    axes[0].set_ylabel('Probability', fontsize=11)
    fig.suptitle('Ideal vs Noisy Measurement Distribution — Backend Comparison',
                 fontsize=13, fontweight='bold', y=1.02)

    plt.tight_layout()
    filepath = timestamped(f'{prefix}_measurement_grid.png' if prefix else 'measurement_grid.png')
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"📊 Measurement grid saved: {filepath}")

def plot_swap_scaling(results_2q: list, results_4q: list):
    """
    Line graph showing fidelity at 2-qubit vs 4-qubit per backend.
    Proves NISQ scaling problem — linear topology collapses at 4 qubits.
    """
    if not results_2q or not results_4q:
        print("⚠️  Need both 2-qubit and 4-qubit results for scaling graph. Skipping.")
        return

    fig, ax = plt.subplots(figsize=(8, 5))

    # Build dict keyed by backend for easy lookup
    fid_2q = {r['backend_key']: r['final_fidelity'] for r in results_2q}
    fid_4q = {r['backend_key']: r['final_fidelity'] for r in results_4q}

    # Only plot backends present in both
    common_backends = set(fid_2q.keys()) & set(fid_4q.keys())
    if not common_backends:
        print("⚠️  No common backends between 2-qubit and 4-qubit results. Skipping scaling graph.")
        return

    for bk in sorted(common_backends):
        color = BACKEND_COLORS.get(bk, '#888888')
        label = BACKEND_LABELS.get(bk, bk)
        fidelities = [fid_2q[bk], fid_4q[bk]]
        ax.plot([2, 4], fidelities, 'o-', color=color, label=label,
                linewidth=2.5, markersize=8)
        for x, y in zip([2, 4], fidelities):
            ax.annotate(f'{y:.4f}', (x, y),
                        textcoords='offset points', xytext=(0, 10),
                        ha='center', fontsize=9, color=color, fontweight='bold')

    ax.axhline(y=0.60, color='#DC143C', linestyle='--',
               linewidth=2, label='Threshold (0.60)')
    ax.set_xticks([2, 4])
    ax.set_xticklabels(['2 Qubits\n(2 Features)', '4 Qubits\n(4 Features)'], fontsize=11)
    ax.set_ylabel('Hellinger Fidelity', fontsize=12)
    ax.set_ylim(0, 1.15)
    ax.set_title('NISQ Scaling: Fidelity vs Circuit Size Across Backends\n'
                 '(Proves topology penalty grows with qubit count)',
                 fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    filepath = timestamped('swap_scaling.png')
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"📊 SWAP scaling graph saved: {filepath}")


def plot_optimizer_convergence(results: list):
    """
    Step chart showing fidelity per optimizer iteration.
    Only plotted when at least one backend has more than 1 iteration.
    Proves the multi-agent optimizer is actually fixing failing circuits.
    """
    multi_iter = [r for r in results if len(r.get('fidelity_history', [])) > 1]
    if not multi_iter:
        print("⚠️  No multi-iteration runs found. Skipping convergence chart.")
        return

    fig, ax = plt.subplots(figsize=(9, 5))

    for r in multi_iter:
        bk = r['backend_key']
        color = BACKEND_COLORS.get(bk, '#888888')
        label = BACKEND_LABELS.get(bk, bk)
        history = r['fidelity_history']   # list of [iteration, fidelity]
        iterations = [h[0] for h in history]
        fidelities  = [h[1] for h in history]
        ax.step(iterations, fidelities, where='post', color=color,
                label=label, linewidth=2.5)
        ax.plot(iterations, fidelities, 'o', color=color, markersize=7)
        for it, fid in zip(iterations, fidelities):
            ax.annotate(f'{fid:.4f}', (it, fid),
                        textcoords='offset points', xytext=(0, 10),
                        ha='center', fontsize=8, color=color)

    ax.axhline(y=0.60, color='#DC143C', linestyle='--',
               linewidth=2, label='Threshold (0.60)')
    ax.set_xlabel('Optimizer Iteration', fontsize=12)
    ax.set_ylabel('Hellinger Fidelity', fontsize=12)
    ax.set_ylim(0, 1.15)
    ax.set_title('Optimizer Convergence: Fidelity Improvement Per Iteration\n'
                 '(Proves autonomous multi-agent self-repair capability)',
                 fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)

    plt.tight_layout()
    filepath = timestamped('optimizer_convergence.png')
    plt.savefig(filepath, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"📊 Optimizer convergence chart saved: {filepath}")

# ── Main ──────────────────────────────────────────────────────────────────────

# Replace entire run_comparison() function with:
def run_comparison():
    ensure_dirs()
    print("\n📂 Q-Optima Backend Comparison")
    print("=" * 50)

    # Load all JSONs
    all_files = glob.glob(os.path.join(RESULTS_DIR, 'run_*.json'))
    if not all_files:
        print(f"❌ No result files found in {RESULTS_DIR}/")
        return
    all_results = []
    for f in sorted(all_files):
        with open(f, 'r') as fp:
            all_results.append(json.load(fp))
    print(f"✅ Loaded {len(all_results)} total result file(s)")

    mode_map = {
        '1': 'free_input',
        '2': 'bv_algorithm',
        '3': 'zz_iris',
        '4': 'ecg_arrhythmia'
    }

    for mode_key, mode_label in mode_map.items():

        if mode_key == "4":
            # ECG: handle 2Q and 4Q separately
            results_2q = get_latest_per_backend(all_results, mode="4", num_features=2)
            results_4q = get_latest_per_backend(all_results, mode="4", num_features=4)

            if results_2q:
                print(f"\n🎨 ECG 2-qubit ({len(results_2q)} backends)")
                plot_fidelity_comparison(results_2q, prefix="ecg_2q")
                plot_absolute_error_heatmap(results_2q, prefix="ecg_2q")
                plot_radar_chart(results_2q, prefix="ecg_2q")
                plot_measurement_grid(results_2q, prefix="ecg_2q")

            if results_4q:
                print(f"\n🎨 ECG 4-qubit ({len(results_4q)} backends)")
                plot_fidelity_comparison(results_4q, prefix="ecg_4q")
                plot_absolute_error_heatmap(results_4q, prefix="ecg_4q")
                plot_radar_chart(results_4q, prefix="ecg_4q")
                plot_measurement_grid(results_4q, prefix="ecg_4q")
                plot_optimizer_convergence(results_4q)

            if results_2q and results_4q:
                print(f"\n🎨 ECG scaling graph")
                plot_swap_scaling(results_2q, results_4q)

        else:
            # All other modes: only 2-qubit standard graphs
            results = get_latest_per_backend(all_results, mode=mode_key, num_features=2)
            if not results:
                continue
            print(f"\n🎨 Mode {mode_key} — {mode_label} ({len(results)} backends)")
            plot_fidelity_comparison(results, prefix=mode_label)
            plot_absolute_error_heatmap(results, prefix=mode_label)
            plot_radar_chart(results, prefix=mode_label)
            plot_measurement_grid(results, prefix=mode_label)

    print(f"\n✅ All graphs saved in: {OUTPUT_DIR}/")
    print("   Files are timestamped — no existing graphs will be overwritten.\n")


if __name__ == '__main__':
    run_comparison()