import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import FakeManilaV2, FakeJakartaV2, FakeGuadalupeV2
from qiskit_ibm_runtime import QiskitRuntimeService

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

FS = 360 
BACKEND_REGISTRY = {
    "manila": FakeManilaV2,
    "jakarta": FakeJakartaV2,
    "guadalupe": FakeGuadalupeV2,
    "FakeManilaV2": FakeManilaV2,
    "FakeJakartaV2": FakeJakartaV2,
    "FakeGuadalupeV2": FakeGuadalupeV2
}

def ensure_output_dir():
    os.makedirs('visualizations', exist_ok=True)

def ensure_ecg_dir():
    os.makedirs('visualizations/ecg', exist_ok=True)

def _get_backend_instance(backend_name: str):
    """Helper to fetch either local FakeBackend or Live Cloud Backend."""
    is_live_hardware = backend_name not in BACKEND_REGISTRY
    if is_live_hardware:
        from ibm_connector import get_ibm_backend
        service = QiskitRuntimeService()
        if backend_name == "ibmq_qasm_simulator":
            return get_ibm_backend(service, "simulator")
        else:
            os.environ["IBM_QPU_NAME"] = backend_name
            return get_ibm_backend(service, "specific_qpu")
    else:
        return BACKEND_REGISTRY.get(backend_name, FakeManilaV2)()

def generate_circuit_diagram(code: str, filename: str = "circuit_diagram.png", backend_name: str = "manila"):
    ensure_output_dir()
    try:
        local_scope = {}
        header = "from qiskit import QuantumCircuit, transpile\nimport numpy as np\n\n"
        exec(header + code, {}, local_scope)
        qc = local_scope['qc']

        backend = _get_backend_instance(backend_name)
        transpiled_qc = transpile(qc, backend, optimization_level=1)

        fig, axes = plt.subplots(1, 2, figsize=(18, 6))
        fig.suptitle('Circuit Comparison: Logical vs Physical', fontsize=14, fontweight='bold')

        qc_no_meas = qc.remove_final_measurements(inplace=False)
        logical_fig = qc_no_meas.draw(output='mpl', style={'backgroundcolor': '#FFFFF0'})
        logical_fig.savefig('visualizations/temp_logical.png', dpi=100, bbox_inches='tight')
        plt.close(logical_fig)

        transpiled_fig = transpiled_qc.draw(output='mpl', style={'backgroundcolor': '#F0F8FF'})
        transpiled_fig.savefig('visualizations/temp_transpiled.png', dpi=100, bbox_inches='tight')
        plt.close(transpiled_fig)

        from PIL import Image, ImageDraw
        img1 = Image.open('visualizations/temp_logical.png')
        img2 = Image.open('visualizations/temp_transpiled.png')

        total_width = img1.width + img2.width + 20
        max_height = max(img1.height, img2.height) + 60
        combined = Image.new('RGB', (total_width, max_height), color='white')
        draw = ImageDraw.Draw(combined)
        
        logical_depth  = qc.depth()
        logical_gates  = qc.size()
        physical_depth = transpiled_qc.depth()
        physical_gates = transpiled_qc.size()
        swap_count     = sum(1 for inst in transpiled_qc.data if inst.operation.name == 'swap')
        overhead_pct   = round((physical_depth - logical_depth) / max(logical_depth, 1) * 100, 1)

        draw.text((img1.width // 2 - 80, 5), "LOGICAL CIRCUIT", fill='#2E8B57')
        draw.text((img1.width // 2 - 80, 20), f"Depth: {logical_depth} | Gates: {logical_gates}", fill='#2E8B57')
        draw.text((img1.width + 20 + img2.width // 2 - 100, 5), f"PHYSICAL CIRCUIT ({backend.name})", fill='#4169E1')
        draw.text((img1.width + 20 + img2.width // 2 - 100, 20), f"Depth: {physical_depth} | Gates: {physical_gates} | SWAPs: {swap_count}", fill='#4169E1')

        combined.paste(img1, (0, 50))
        combined.paste(img2, (img1.width + 20, 50))
        filepath = f'visualizations/{filename}'
        combined.save(filepath)

        os.remove('visualizations/temp_logical.png')
        os.remove('visualizations/temp_transpiled.png')
        return filepath
    except Exception as e:
        print(f"⚠️  Circuit diagram generation failed: {str(e)}")
        return None

def generate_measurement_chart(code: str, filename: str = "measurement_comparison.png", backend_name: str = "manila"):
    ensure_output_dir()
    try:
        local_scope = {}
        header = "from qiskit import QuantumCircuit, transpile\nimport numpy as np\n\n"
        exec(header + code, {}, local_scope)
        qc = local_scope['qc']

        backend = _get_backend_instance(backend_name)
        transpiled_qc = transpile(qc, backend, optimization_level=1)

        ideal_sim = AerSimulator()
        ideal_counts = ideal_sim.run(transpile(qc, ideal_sim), shots=1024).result().get_counts()

        noisy_sim = AerSimulator.from_backend(backend)
        noisy_counts = noisy_sim.run(transpiled_qc, shots=1024).result().get_counts()

        all_states = sorted(set(ideal_counts.keys()) | set(noisy_counts.keys()))
        ideal_probs = [ideal_counts.get(s, 0) / 1024 for s in all_states]
        noisy_probs = [noisy_counts.get(s, 0) / 1024 for s in all_states]

        x = np.arange(len(all_states))
        width = 0.35

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(x - width/2, ideal_probs, width, label='Ideal', color='#2E8B57', alpha=0.85)
        ax.bar(x + width/2, noisy_probs, width, label=f'Noisy ({backend.name})', color='#DC143C', alpha=0.85)

        ax.set_title(f"Measurement Distribution ({backend.name})", fontsize=13, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(all_states, rotation=45, ha='right')
        ax.legend()
        plt.tight_layout()
        
        filepath = f'visualizations/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        return filepath
    except Exception as e:
        print(f"⚠️  Measurement chart failed: {str(e)}")
        return None

def generate_topology_map(backend_name: str, used_qubits: list, filename: str = "topology_map.png"):
    ensure_ecg_dir()
    if not HAS_NETWORKX: return None

    try:
        backend = _get_backend_instance(backend_name)
        coupling_map = backend.coupling_map
        if hasattr(coupling_map, 'get_edges'):
            edges = list(coupling_map.get_edges())
        else:
            edges = coupling_map

        G = nx.DiGraph()
        num_qubits = backend.num_qubits
        G.add_nodes_from(range(num_qubits))
        for edge in edges:
            G.add_edge(edge[0], edge[1])

        # Scale nodes for 127-qubit processors
        is_large = num_qubits > 20
        active_size = 600 if not is_large else 250
        inactive_size = 400 if not is_large else 80
        font_size = 11 if not is_large else 7

        node_colors = ['#E67E22' if i in used_qubits else '#BDC3C7' for i in range(num_qubits)]
        node_sizes  = [active_size if i in used_qubits else inactive_size for i in range(num_qubits)]

        # kamada_kawai renders IBM heavy-hex grids much cleaner than spring_layout
        pos = nx.kamada_kawai_layout(G)

        fig, ax = plt.subplots(figsize=(12, 8))
        nx.draw_networkx_nodes(G, pos, node_color=node_colors, node_size=node_sizes, ax=ax, alpha=0.9)
        
        # Only label active qubits on massive chips to prevent clutter
        labels = {i: i for i in range(num_qubits) if not is_large or i in used_qubits}
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=font_size, font_weight='bold', ax=ax)
        nx.draw_networkx_edges(G, pos, ax=ax, arrows=False, edge_color='#7F8C8D', alpha=0.5)

        used_patch   = mpatches.Patch(color='#E67E22', label=f'Used qubits {used_qubits}')
        unused_patch = mpatches.Patch(color='#BDC3C7', label=f'Unused ({num_qubits - len(used_qubits)})')
        ax.legend(handles=[used_patch, unused_patch], loc='upper left')
        ax.set_title(f'Hardware Topology — {backend.name}', fontsize=14, fontweight='bold')
        ax.axis('off')

        filepath = f'visualizations/ecg/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        return filepath
    except Exception as e:
        print(f"⚠️  Topology map failed: {e}")
        return None

def generate_fidelity_graph(fidelity_history: list, filename: str = "fidelity_progress.png", backend_name: str = "manila"):
    """(Unchanged - purely uses lists, no Qiskit backend interaction required)"""
    ensure_output_dir()
    if not fidelity_history or len(fidelity_history) < 2: return None
    try:
        iterations = [x[0] for x in fidelity_history]
        fidelities = [x[1] for x in fidelity_history]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(iterations, fidelities, marker='o', color='#4169E1')
        ax.axhline(y=0.60, color='#DC143C', linestyle='--')
        filepath = f'visualizations/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        return filepath
    except Exception: return None

def generate_ecg_waveform(waves_info: dict, filename: str = "ecg_waveform.png"):
    """
    Plot raw filtered ECG signal for the selected beat window with
    clinical markers: P, Q, R, S peaks labeled as vertical lines.
    Proves to medical reviewers that data extraction is clinically accurate.
    """
    ensure_ecg_dir()
    try:
        sig    = waves_info['filtered_signal']
        start  = waves_info['beat_window_start']
        end    = waves_info['beat_window_end']
        r_curr = waves_info['r_curr']
        p_idx  = waves_info['p_idx']
        q_idx  = waves_info['q_idx']
        s_idx  = waves_info['s_idx']

        window = sig[start:end]
        time_axis = np.arange(len(window)) / FS * 1000   # convert to ms

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.plot(time_axis, window, color='#2C3E50', linewidth=1.5, label='ECG Signal (Filtered)')

        # Marker positions relative to window
        markers = {
            'P': (p_idx - start, '#3498DB'),
            'Q': (q_idx - start, '#E67E22'),
            'R': (r_curr - start, '#E74C3C'),
            'S': (s_idx - start, '#9B59B6'),
        }

        for label, (idx, color) in markers.items():
            if 0 <= idx < len(window):
                t = idx / FS * 1000
                ax.axvline(x=t, color=color, linestyle='--', linewidth=1.5, alpha=0.8)
                ax.plot(t, window[idx], 'o', color=color, markersize=8, zorder=5)
                ax.text(t, window[idx] + 0.02, label, color=color,
                        fontsize=11, fontweight='bold', ha='center')

        ax.set_xlabel('Time (ms)', fontsize=12)
        ax.set_ylabel('Amplitude (mV)', fontsize=12)
        ax.set_title('Raw ECG Signal — Beat with Clinical Markers\n'
                     '(P, Q, R, S peaks detected for feature extraction)',
                     fontsize=13, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(alpha=0.3)

        plt.tight_layout()
        filepath = f'visualizations/ecg/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"📊 ECG waveform saved: {filepath}")
        return filepath
    
    except Exception as e:
        print(f"⚠️  ECG waveform generation failed: {e}")
        return None


def generate_bloch_sphere(code: str, num_features: int, filename: str = "bloch_sphere.png"):
    """
    Plot Bloch sphere showing qubit states after Rz encoding gates,
    before measurement. Proves classical radians were converted to
    quantum phase shifts successfully.
    Uses statevector simulator — no noise, pure encoding state.
    """
    ensure_ecg_dir()
    try:
        from qiskit.quantum_info import Statevector
        from qiskit.visualization import plot_bloch_multivector

        # Remove measurement gates to get encoding state
        local_scope = {}
        header = "from qiskit import QuantumCircuit, transpile\nimport numpy as np\n\n"
        exec(header + code, {}, local_scope)
        qc = local_scope['qc']
        qc_no_meas = qc.remove_final_measurements(inplace=False)

        # Get statevector after encoding
        sv = Statevector(qc_no_meas)

        fig = plot_bloch_multivector(sv)
        fig.suptitle(f'Bloch Sphere — Qubit States After ZZ Encoding\n'
                     f'({num_features}-qubit circuit, before measurement)',
                     fontsize=12, fontweight='bold', y=1.02)

        filepath = f'visualizations/ecg/{filename}'
        fig.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"📊 Bloch sphere saved: {filepath}")
        return filepath

    except Exception as e:
        print(f"⚠️  Bloch sphere generation failed: {e}")
        return None