"""
Circuit Visualization for Q-Optima
Generates circuit diagrams and measurement comparison charts after successful runs.
"""

import os
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend, no display needed
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_ibm_runtime.fake_provider import FakeManilaV2


def ensure_output_dir():
    """Create visualizations directory if it doesn't exist."""
    if not os.path.exists('visualizations'):
        os.makedirs('visualizations')


def generate_circuit_diagram(code: str, filename: str = "circuit_diagram.png"):
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
        backend = FakeManilaV2()
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
        draw.text((img1.width // 2 - 80, 10), "LOGICAL CIRCUIT (Your Code)", fill='#2E8B57', font=None)
        draw.text((img1.width + 20 + img2.width // 2 - 100, 10), "PHYSICAL CIRCUIT (After Transpilation)", fill='#4169E1', font=None)

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


def generate_measurement_chart(code: str, filename: str = "measurement_comparison.png"):
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

        backend = FakeManilaV2()
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
        bars2 = ax.bar(x + width/2, noisy_probs, width, label='Noisy (FakeManilaV2)',
                       color='#DC143C', alpha=0.85, edgecolor='black', linewidth=0.5)

        ax.set_xlabel('Measurement Outcome', fontsize=12)
        ax.set_ylabel('Probability', fontsize=12)
        ax.set_title('Ideal vs Noisy Measurement Distribution\n(FakeManilaV2 Digital Twin)',
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


def generate_fidelity_graph(fidelity_history: list, filename: str = "fidelity_progress.png"):
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
        ax.axhline(y=0.70, color='#DC143C', linestyle='--',
                   linewidth=1.5, label='Threshold (0.70)')

        # Color points: red = fail, green = pass
        for i, (it, fid) in enumerate(fidelity_history):
            color = '#2E8B57' if fid >= 0.70 else '#DC143C'
            ax.plot(it, fid, 'o', markersize=12, color=color, zorder=5)
            ax.annotate(f'{fid:.3f}', (it, fid),
                        textcoords="offset points", xytext=(0, 12),
                        ha='center', fontsize=10, fontweight='bold')

        ax.set_xlabel('Iteration', fontsize=12)
        ax.set_ylabel('Fidelity', fontsize=12)
        ax.set_title('Fidelity Progress Across Optimizer Iterations', fontsize=13, fontweight='bold')
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