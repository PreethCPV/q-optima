
import os
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend, no display needed
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import FakeManilaV2, FakeJakartaV2, FakeGuadalupeV2

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False

FS = 360 
BACKEND_REGISTRY = {
    "manila": FakeManilaV2,
    "jakarta": FakeJakartaV2,
    "guadalupe": FakeGuadalupeV2
}

def ensure_output_dir():
    """Create visualizations directory if it doesn't exist."""
    if not os.path.exists('visualizations'):
        os.makedirs('visualizations')

def ensure_ecg_dir():
    os.makedirs('visualizations/ecg', exist_ok=True)


def generate_circuit_diagram(code: str, filename: str = "circuit_diagram.png", backend_name: str = "manila"):
    """
    Generate and save a circuit diagram PNG from circuit code.
    Shows both logical (original) and transpiled (physical) circuit side by side.
    """
    ensure_output_dir()

    try:
        # Execute code to get qc object
        local_scope = {}
        header = "from qiskit import QuantumCircuit, transpile\nimport numpy as np\n\n"
        exec(header + code, {}, local_scope)
        qc = local_scope['qc']

        # Get transpiled version for comparison
        backend = BACKEND_REGISTRY.get(backend_name, FakeManilaV2)()
        transpiled_qc = transpile(qc, backend, optimization_level=1)

        # Create side-by-side figure
        fig, axes = plt.subplots(1, 2, figsize=(18, 6))
        fig.suptitle('Circuit Comparison: Logical vs Physical', fontsize=14, fontweight='bold')

        # Draw logical circuit (left)
        qc_no_meas = qc.remove_final_measurements(inplace=False)
        logical_fig = qc_no_meas.draw(output='mpl', style={'backgroundcolor': '#FFFFF0'})
        logical_fig.savefig('visualizations/temp_logical.png', dpi=100, bbox_inches='tight')
        plt.close(logical_fig)

        # Draw transpiled circuit (right)
        transpiled_fig = transpiled_qc.draw(output='mpl', style={'backgroundcolor': '#F0F8FF'})
        transpiled_fig.savefig('visualizations/temp_transpiled.png', dpi=100, bbox_inches='tight')
        plt.close(transpiled_fig)

        # Combine into one image
        from PIL import Image
        img1 = Image.open('visualizations/temp_logical.png')
        img2 = Image.open('visualizations/temp_transpiled.png')

        total_width = img1.width + img2.width + 20
        max_height = max(img1.height, img2.height) + 60

        combined = Image.new('RGB', (total_width, max_height), color='white')

        # Add labels
        from PIL import ImageDraw, ImageFont
        draw = ImageDraw.Draw(combined)
        
        logical_depth  = qc.depth()
        logical_gates  = qc.size()
        physical_depth = transpiled_qc.depth()
        physical_gates = transpiled_qc.size()
        swap_count     = sum(1 for inst in transpiled_qc.data
                            if inst.operation.name == 'swap')
        overhead_pct   = round((physical_depth - logical_depth) / max(logical_depth, 1) * 100, 1)

        draw.text((img1.width // 2 - 80, 5),
                "LOGICAL CIRCUIT (Your Code)", fill='#2E8B57', font=None)
        draw.text((img1.width // 2 - 80, 20),
                f"Depth: {logical_depth} | Gates: {logical_gates}",
                fill='#2E8B57', font=None)
        draw.text((img1.width + 20 + img2.width // 2 - 100, 5),
                f"PHYSICAL CIRCUIT ({backend_name.capitalize()})", fill='#4169E1', font=None)
        draw.text((img1.width + 20 + img2.width // 2 - 100, 20),
                f"Depth: {physical_depth} | Gates: {physical_gates} | SWAPs: {swap_count} | Overhead: +{overhead_pct}%",
                fill='#4169E1', font=None)


        combined.paste(img1, (0, 50))
        combined.paste(img2, (img1.width + 20, 50))

        filepath = f'visualizations/{filename}'
        combined.save(filepath)

        # Cleanup temp files
        os.remove('visualizations/temp_logical.png')
        os.remove('visualizations/temp_transpiled.png')

        print(f"📊 Circuit diagram saved: {filepath}")
        return filepath

    except ImportError:
        # PIL not available — save circuits separately instead
        ensure_output_dir()
        local_scope = {}
        header = "from qiskit import QuantumCircuit, transpile\nimport numpy as np\n\n"
        exec(header + code, {}, local_scope)
        qc = local_scope['qc']
        backend = FakeManilaV2()
        transpiled_qc = transpile(qc, backend, optimization_level=1)

        filepath_logical = 'visualizations/circuit_logical.png'
        filepath_physical = 'visualizations/circuit_physical.png'

        fig = qc.draw(output='mpl')
        fig.savefig(filepath_logical, dpi=100, bbox_inches='tight')
        plt.close(fig)

        fig = transpiled_qc.draw(output='mpl')
        fig.savefig(filepath_physical, dpi=100, bbox_inches='tight')
        plt.close(fig)

        print(f"📊 Logical circuit saved: {filepath_logical}")
        print(f"📊 Physical circuit saved: {filepath_physical}")
        return filepath_logical

    except Exception as e:
        print(f"⚠️  Circuit diagram generation failed: {str(e)}")
        return None


def generate_measurement_chart(code: str, filename: str = "measurement_comparison.png", backend_name: str = "manila"):
    """
    Generate ideal vs noisy measurement bar chart.
    Shows how noise affects the expected measurement outcomes.
    """
    ensure_output_dir()

    try:
        # Execute code to get qc
        local_scope = {}
        header = "from qiskit import QuantumCircuit, transpile\nimport numpy as np\n\n"
        exec(header + code, {}, local_scope)
        qc = local_scope['qc']

        backend = BACKEND_REGISTRY.get(backend_name, FakeManilaV2)()
        transpiled_qc = transpile(qc, backend, optimization_level=1)

        # Ideal simulation
        ideal_sim = AerSimulator()
        ideal_counts = ideal_sim.run(
            transpile(qc, ideal_sim), shots=1024
        ).result().get_counts()

        # Noisy simulation
        noisy_sim = AerSimulator.from_backend(backend)
        noisy_counts = noisy_sim.run(
            transpiled_qc, shots=1024
        ).result().get_counts()

        # Get all states
        all_states = sorted(set(ideal_counts.keys()) | set(noisy_counts.keys()))

        ideal_probs = [ideal_counts.get(s, 0) / 1024 for s in all_states]
        noisy_probs = [noisy_counts.get(s, 0) / 1024 for s in all_states]

        # Plot
        x = np.arange(len(all_states))
        width = 0.35

        fig, ax = plt.subplots(figsize=(12, 6))
        bars1 = ax.bar(x - width/2, ideal_probs, width, label='Ideal (No Noise)',
                       color='#2E8B57', alpha=0.85, edgecolor='black', linewidth=0.5)
        bars2 = ax.bar(x + width/2, noisy_probs, width, label=f'Noisy ({backend_name.capitalize()})',
                       color='#DC143C', alpha=0.85, edgecolor='black', linewidth=0.5)

        ax.set_xlabel('Measurement Outcome', fontsize=12)
        ax.set_ylabel('Probability', fontsize=12)
        ax.set_title(f"Ideal vs Noisy Measurement Distribution\n({backend_name.capitalize()} Digital Twin)",
                     fontsize=13, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(all_states, rotation=45, ha='right', fontsize=9)
        ax.legend(fontsize=11)
        ax.set_ylim(0, 1.1)
        ax.grid(axis='y', alpha=0.3)

        # Add value labels on bars
        for bar in bars1:
            h = bar.get_height()
            if h > 0.01:
                ax.text(bar.get_x() + bar.get_width()/2., h + 0.01,
                        f'{h:.2f}', ha='center', va='bottom', fontsize=7)
        for bar in bars2:
            h = bar.get_height()
            if h > 0.01:
                ax.text(bar.get_x() + bar.get_width()/2., h + 0.01,
                        f'{h:.2f}', ha='center', va='bottom', fontsize=7)

        plt.tight_layout()
        filepath = f'visualizations/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"📊 Measurement chart saved: {filepath}")
        return filepath

    except Exception as e:
        print(f"⚠️  Measurement chart generation failed: {str(e)}")
        return None


def generate_fidelity_graph(fidelity_history: list, filename: str = "fidelity_progress.png", backend_name: str = "manila"):
    """
    Generate fidelity progress graph across optimizer iterations.
    Only called if optimizer ran at least once.
    
    Args:
        fidelity_history: List of (iteration, fidelity_value) tuples
                         e.g. [(1, 0.62), (2, 0.65), (3, 0.71)]
    """
    ensure_output_dir()

    if not fidelity_history or len(fidelity_history) < 2:
        print("⚠️  Not enough iterations for fidelity graph (need 2+)")
        return None

    try:
        iterations = [x[0] for x in fidelity_history]
        fidelities = [x[1] for x in fidelity_history]

        fig, ax = plt.subplots(figsize=(10, 5))

        ax.plot(iterations, fidelities, marker='o', linewidth=2.5,
                color='#4169E1', markersize=10, markerfacecolor='white',
                markeredgewidth=2.5, label='Circuit Fidelity')

        # Threshold line
        ax.axhline(y=0.60, color='#DC143C', linestyle='--',
                   linewidth=1.5, label='Threshold (0.60)')

        # Color points: red = fail, green = pass
        for i, (it, fid) in enumerate(fidelity_history):
            color = '#2E8B57' if fid >= 0.60 else '#DC143C'
            ax.plot(it, fid, 'o', markersize=12, color=color, zorder=5)
            ax.annotate(f'{fid:.3f}', (it, fid),
                        textcoords="offset points", xytext=(0, 12),
                        ha='center', fontsize=10, fontweight='bold')

        ax.set_xlabel('Iteration', fontsize=12)
        ax.set_ylabel('Fidelity', fontsize=12)
        ax.set_title(f"Fidelity Progress Across Optimizer Iterations\n({backend_name.capitalize()} Digital Twin)",
             fontsize=13, fontweight='bold')
        ax.set_xticks(iterations)
        ax.set_ylim(0, 1.1)
        ax.legend(fontsize=11)
        ax.grid(alpha=0.3)

        plt.tight_layout()
        filepath = f'visualizations/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"📊 Fidelity progress graph saved: {filepath}")
        return filepath

    except Exception as e:
        print(f"⚠️  Fidelity graph generation failed: {str(e)}")
        return None
    

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
    
def generate_topology_map(backend_name: str, used_qubits: list, filename: str = "topology_map.png"):
    """
    Visual graph of IBM chip coupling map.
    Used qubits highlighted in orange, unused in grey.
    Explains to reviewers why SWAP gates are needed for certain circuits.
    """
    ensure_ecg_dir()

    if not HAS_NETWORKX:
        print("⚠️  networkx not installed. Run: pip install networkx. Skipping topology map.")
        return None

    try:
        backend_class = BACKEND_REGISTRY.get(backend_name, FakeManilaV2)
        backend = backend_class()
        coupling_map = backend.coupling_map

        G = nx.DiGraph()
        num_qubits = backend.num_qubits
        G.add_nodes_from(range(num_qubits))
        for edge in coupling_map:
            G.add_edge(edge[0], edge[1])

        # Node colors: orange for used qubits, grey for unused
        node_colors = ['#E67E22' if i in used_qubits else '#BDC3C7'
                       for i in range(num_qubits)]
        node_sizes  = [800 if i in used_qubits else 500
                       for i in range(num_qubits)]

        pos = nx.spring_layout(G, seed=42)

        fig, ax = plt.subplots(figsize=(10, 7))
        nx.draw_networkx_nodes(G, pos, node_color=node_colors,
                               node_size=node_sizes, ax=ax, alpha=0.9)
        nx.draw_networkx_labels(G, pos, font_size=11,
                                font_weight='bold', ax=ax)
        nx.draw_networkx_edges(G, pos, ax=ax, arrows=True,
                               arrowsize=15, edge_color='#7F8C8D',
                               width=1.5, alpha=0.7)

        # Legend
        used_patch   = mpatches.Patch(color='#E67E22', label=f'Used qubits {used_qubits}')
        unused_patch = mpatches.Patch(color='#BDC3C7', label='Unused qubits')
        ax.legend(handles=[used_patch, unused_patch], fontsize=10, loc='upper left')

        ax.set_title(f'Hardware Topology — {backend_name.capitalize()} Coupling Map\n'
                     f'({num_qubits} qubits, highlighted = circuit qubits)',
                     fontsize=13, fontweight='bold')
        ax.axis('off')

        plt.tight_layout()
        filepath = f'visualizations/ecg/{filename}'
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        print(f"📊 Topology map saved: {filepath}")
        return filepath

    except Exception as e:
        print(f"⚠️  Topology map generation failed: {e}")
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
    
