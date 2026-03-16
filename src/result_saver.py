"""
Q-Optima Result Saver
Saves per-run results to results/run_*.json for offline comparison.

Called from main.py at end of each session.
compare_backends.py reads these files to generate cross-backend graphs.
"""

import os
import json
from datetime import datetime

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

RESULTS_DIR = 'results'


def ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def extract_circuit_metrics(code: str, backend_key: str) -> dict:
    """
    Compile circuit and extract depth/gate/SWAP metrics for radar chart.

    Args:
        code        : Final certified circuit code string
        backend_key : 'manila', 'jakarta', or 'guadalupe'

    Returns:
        Dict with logical_depth, physical_depth, total_gates, swap_count
    """
    try:
        from tools.hardware_tools import BACKEND_REGISTRY
        from qiskit_ibm_runtime.fake_provider import FakeManilaV2

        local_scope = {}
        header = "from qiskit import QuantumCircuit, transpile\nimport numpy as np\n\n"
        exec(header + code, {}, local_scope)
        qc = local_scope.get('qc')

        if qc is None or not isinstance(qc, QuantumCircuit):
            return _empty_metrics()

        logical_depth = qc.depth()
        logical_gates = qc.size()

        backend_class = BACKEND_REGISTRY.get(backend_key, FakeManilaV2)
        backend = backend_class()
        transpiled = transpile(qc, backend, optimization_level=1)

        physical_depth = transpiled.depth()
        total_gates = transpiled.size()
        swap_count = sum(
            1 for inst in transpiled.data
            if inst.operation.name == 'swap'
        )

        return {
            'logical_depth':  logical_depth,
            'logical_gates':  logical_gates,
            'physical_depth': physical_depth,
            'total_gates':    total_gates,
            'swap_count':     swap_count,
        }

    except Exception as e:
        print(f"⚠️  Metrics extraction failed: {e}")
        return _empty_metrics()


def _empty_metrics() -> dict:
    return {
        'logical_depth':  0,
        'logical_gates':  0,
        'physical_depth': 0,
        'total_gates':    0,
        'swap_count':     0,
    }


def extract_measurement_counts(code: str, backend_key: str) -> tuple:
    """
    Re-run ideal and noisy simulations on final certified code
    to capture measurement counts for heatmap and grid visualizations.

    Returns:
        (ideal_counts dict, noisy_counts dict)
    """
    try:
        from tools.hardware_tools import BACKEND_REGISTRY
        from qiskit_ibm_runtime.fake_provider import FakeManilaV2

        local_scope = {}
        header = "from qiskit import QuantumCircuit, transpile\nimport numpy as np\n\n"
        exec(header + code, {}, local_scope)
        qc = local_scope.get('qc')

        if qc is None:
            return {}, {}

        backend_class = BACKEND_REGISTRY.get(backend_key, FakeManilaV2)
        backend = backend_class()
        transpiled = transpile(qc, backend, optimization_level=1)

        ideal_sim = AerSimulator()
        ideal_counts = ideal_sim.run(
            transpile(qc, ideal_sim), shots=1024
        ).result().get_counts()

        noisy_sim = AerSimulator.from_backend(backend)
        noisy_counts = noisy_sim.run(
            transpiled, shots=1024
        ).result().get_counts()

        return dict(ideal_counts), dict(noisy_counts)

    except Exception as e:
        print(f"⚠️  Measurement extraction failed: {e}")
        return {}, {}


def save_run_results(
    backend_key: str,
    backend_full_name: str,
    mode: str,
    current_code: str,
    fidelity_history: list,
    success: bool,
    timestamp: str,
    extra_info: dict = None,
    num_features: int = 2
):
    """
    Save complete run results to a timestamped JSON file.

    Args:
        backend_key       : 'manila', 'jakarta', 'guadalupe'
        backend_full_name : 'FakeManilaV2' etc.
        mode              : '1', '2', or '3'
        current_code      : Final certified circuit code
        fidelity_history  : List of (iteration, fidelity) tuples
        success           : Whether compilation passed threshold
        timestamp         : Run timestamp string
        extra_info        : Optional dict (e.g. zz_info, hidden string)
    """
    ensure_results_dir()

    # Final fidelity: last entry in history, or 0 if empty
    final_fidelity = fidelity_history[-1][1] if fidelity_history else 0.0

    # Circuit metrics for radar chart
    metrics = extract_circuit_metrics(current_code, backend_key)
    metrics['final_fidelity'] = final_fidelity

    # Measurement counts for heatmap and grid
    ideal_counts, noisy_counts = extract_measurement_counts(current_code, backend_key)

    result = {
        'timestamp':        timestamp,
        'backend_key':      backend_key,
        'backend_full_name': backend_full_name,
        'mode':             mode,
        'num_features':      num_features,
        'success':          success,
        'final_fidelity':   final_fidelity,
        'fidelity_history': fidelity_history,
        'metrics':          metrics,
        'ideal_counts':     ideal_counts,
        'noisy_counts':     noisy_counts,
        'circuit_code':     current_code,
        'extra_info':       extra_info or {},
    }

    filename = os.path.join(
        RESULTS_DIR,
        f"run_{backend_key}_{mode}_{timestamp}.json"
    )

    with open(filename, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"💾 Run results saved: {filename}")
    return filename