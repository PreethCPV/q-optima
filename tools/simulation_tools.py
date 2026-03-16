from crewai.tools import tool
import sys
import io
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit_aer.noise import NoiseModel
from qiskit_ibm_runtime.fake_provider import FakeManilaV2, FakeJakartaV2, FakeGuadalupeV2
import numpy as np
import os

BACKEND_REGISTRY = {
    "manila": FakeManilaV2,
    "jakarta": FakeJakartaV2,
    "guadalupe": FakeGuadalupeV2
}

class SimulationTools:


    @staticmethod
    def _execute_simulation(qiskit_code: str) -> str:
        """
        Executes Qiskit code on the configured Digital Twin with noise modeling.
        
        Uses measurement-based fidelity (more realistic for actual quantum hardware).
        
        Args:
            qiskit_code: String containing ONLY circuit definition code
        
        Returns:
        - 'STATUS: SUCCESS | Fidelity: X.XX' if fidelity >= 0.60
        - 'STATUS: FAIL | [Reason]' with specific error details
        """
        # ===== STEP 1: VALIDATION =====
        if not qiskit_code or qiskit_code.strip() == "":
            return "STATUS: FAIL | Runtime Error: No code provided to simulate."
        
        # Check for forbidden execution code patterns
        if 'class QuantumCircuit' in qiskit_code and 'def __init__' in qiskit_code:
            return "STATUS: FAIL | Code injection detected: QuantumCircuit class override"
        if 'simulator.run(' in qiskit_code:
            return "STATUS: FAIL | Code Validation Error: forbidden execution code detected"
        if 'AerSimulator()' in qiskit_code and 'from qiskit_aer' not in qiskit_code:
            return "STATUS: FAIL | Code Validation Error: forbidden simulator instantiation"
        forbidden_patterns = {
            'simulator.run(': 'Execution code detected',
            'execute(': 'Deprecated execute() function',
            '.get_statevector(': 'Result extraction code',
            '.get_counts(': 'Result extraction code',
            'job =': 'Job execution code',
            'result =': 'Result storage code',
            'AerSimulator()': 'Simulator instantiation',
            'transpile(qc': 'Manual transpilation'
        }
        
        for pattern, error_msg in forbidden_patterns.items():
            if pattern in qiskit_code:
                return (
                    f"STATUS: FAIL | Code Validation Error: {error_msg}\n\n"
                    f"Found forbidden pattern: '{pattern}'\n\n"
                    "ALLOWED CODE STRUCTURE:\n"
                    "```python\n"
                    "from qiskit import QuantumCircuit\n"
                    "# Define your circuit with the correct number of qubits based on the prompt\n"
                    "qc = QuantumCircuit(num_qubits, num_clbits)\n"
                    "# ... apply valid gates ...\n"
                    "qc.measure(qubits, clbits)\n"
                    "```\n\n"
                    "Remove any execution code after qc.measure_all()"
                )
        
        try:
            # ===== STEP 2: EXECUTE CODE =====
            old_stdout = sys.stdout
            redirected_output = io.StringIO()
            sys.stdout = redirected_output

            local_scope = {}
            
            header = (
                "from qiskit import QuantumCircuit, transpile\n"
                "from qiskit_aer import AerSimulator\n"
                "import numpy as np\n\n"
            )
            
            full_code = header + qiskit_code
            exec(full_code, globals(), local_scope)
            
            sys.stdout = old_stdout

            # ===== STEP 3: VALIDATE OUTPUT =====
            if 'qc' not in local_scope:
                return (
                    "STATUS: FAIL | Runtime Error: Variable 'qc' not found.\n\n"
                    "Your code must define 'qc' as a QuantumCircuit with dimensions matching the user request."
                )
            
            qc = local_scope['qc']
            
            if not isinstance(qc, QuantumCircuit):
                return f"STATUS: FAIL | Type Error: 'qc' is {type(qc).__name__}, not QuantumCircuit."
            
            backend_name = os.environ.get("QOPTIMA_BACKEND", "manila")
            backend_class = BACKEND_REGISTRY.get(backend_name, FakeManilaV2)
            backend = backend_class()
            try:
                transpiled_qc = transpile(qc, backend, optimization_level=1, layout_method='trivial')
            except Exception as e:
                error_msg = str(e)
                if "not in coupling map" in error_msg.lower():
                    return (
                        f"STATUS: FAIL | Hardware Mapping Failed: {error_msg}\n\n"
                        "The circuit uses invalid qubit connections.\n"
                        "Transpiler should handle this automatically - check that your qubit indices exist on the current hardware."
                    )
                else:
                    return f"STATUS: FAIL | Transpilation Error: {error_msg}"

            # ===== STEP 6: IDEAL SIMULATION (NOISELESS) =====
            # Run on perfect simulator
            ideal_sim = AerSimulator()
            ideal_result = ideal_sim.run(transpile(qc, ideal_sim), shots=1024).result()
            ideal_counts = ideal_result.get_counts()
            
            # ===== STEP 7: NOISY SIMULATION (WITH HARDWARE ERRORS) =====
            # Create noisy simulator from backend
            noisy_sim = AerSimulator.from_backend(backend)
            noisy_result = noisy_sim.run(transpiled_qc, shots=1024).result()
            noisy_counts = noisy_result.get_counts()
            
            # ===== STEP 8: COMPUTE MEASUREMENT FIDELITY =====
            # This compares measurement distributions (more realistic than statevector)
            fidelity = calculate_hellinger_fidelity(ideal_counts, noisy_counts)
            
            threshold = 0.60

            if fidelity >= threshold:
                return f"STATUS: SUCCESS | Fidelity: {fidelity:.4f} (>= 0.60 threshold)"
            else:
                return (
                    f"STATUS: FAIL | Low Fidelity: {fidelity:.4f} (below 0.60 threshold)\n\n"
                    "Circuit is mathematically valid, but physical hardware noise degraded the data.\n"
                    "OPTIMIZER ACTION REQUIRED: Analyze the Coupling Map from the hardware specification. "
                    "Rewrite the circuit to use a different, quieter pair of physically connected qubits to avoid this noise."
                )

        except Exception as e:
            sys.stdout = sys.__stdout__
            error_str = str(e)
            
            if "qc" in error_str or "not defined" in error_str:
                return f"STATUS: FAIL | Runtime Error: {error_str}\n\nEnsure you define 'qc' as a QuantumCircuit with the correct dimensions."
            elif "import" in error_str.lower():
                return f"STATUS: FAIL | Import Error: {error_str}\n\nUse: from qiskit import QuantumCircuit"
            else:
                return f"STATUS: FAIL | Runtime Error: {error_str}"
    
    @tool("Run Noisy Simulation")  
    def calculate_fidelity(qiskit_code: str = ""):
        """
        Executes Qiskit code on the configured Digital Twin with noise modeling.
        Returns STATUS: SUCCESS or FAIL with fidelity score.
        """
        return SimulationTools._execute_simulation(qiskit_code)


def calculate_hellinger_fidelity(counts1, counts2, shots=1024):
    """
    Calculate Hellinger fidelity between two probability distributions.
    This is a standard metric for comparing measurement results.
    
    F = (sum_i sqrt(p_i * q_i))^2
    
    Where p_i and q_i are probabilities of outcome i.
    Returns value between 0 (completely different) and 1 (identical).
    """
    # Get all possible measurement outcomes
    all_outcomes = set(counts1.keys()) | set(counts2.keys())
    
    # Convert counts to probabilities
    prob1 = {outcome: counts1.get(outcome, 0) / shots for outcome in all_outcomes}
    prob2 = {outcome: counts2.get(outcome, 0) / shots for outcome in all_outcomes}
    
    # Compute Hellinger fidelity: F = (sum sqrt(p*q))^2
    overlap_sum = sum(np.sqrt(prob1[outcome] * prob2[outcome]) for outcome in all_outcomes)
    fidelity = overlap_sum ** 2
    
    return fidelity

def run_simulation_direct(qiskit_code: str) -> str:
    """
    Direct simulation call for ground truth fidelity extraction in main.py.
    Bypasses CrewAI Tool object wrapping — callable as a plain Python function.
    """
    return SimulationTools._execute_simulation(qiskit_code)