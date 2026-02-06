from crewai.tools import tool
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator
from qiskit.quantum_info import Operator

class QuantumTools:
    
    @tool("Circuit Optimizer")
    def optimize_circuit(qasm_string: str):
        """
        Input: A valid OpenQASM 2.0 string representing a quantum circuit.
        Function: Creates the circuit, calculates its depth, optimizes it using Qiskit, and returns the stats.
        Useful for: Checking if a circuit can be made smaller or faster.
        """
        try:
            # 1. Convert text (QASM) back to a Circuit
            qc = QuantumCircuit.from_qasm_str(qasm_string)
            original_depth = qc.depth()
            
            # 2. Optimize
            simulator = AerSimulator()
            # Optimization level 3 = Heavy optimization (folding gates, cancelling inverses)
            transpiled_qc = transpile(qc, backend=simulator, optimization_level=3)
            new_depth = transpiled_qc.depth()
            
            # 3. Calculate Stats
            reduction = 100 * (original_depth - new_depth) / original_depth if original_depth > 0 else 0
            
            return (
                f"--- Optimization Results ---\n"
                f"Original Depth: {original_depth}\n"
                f"Optimized Depth: {new_depth}\n"
                f"Reduction: {reduction:.1f}%\n"
                f"Status: {'✅ Optimized' if new_depth < original_depth else '⚠️ No reduction possible'}"
            )
            
        except Exception as e:
            return f"❌ Error processing circuit: {str(e)}"
        
class VerificationTools:

    @tool("Circuit Verifier")
    def verify_equivalence(original_qasm: str, optimized_qasm: str):
        """
        Input: Two OpenQASM strings (original and optimized).
        Function: Checks if they are mathematically identical using Unitary Matrices.
        Useful for: Ensuring the optimizer didn't break the logic.
        """
        try:
            # 1. Rebuild circuits
            qc1 = QuantumCircuit.from_qasm_str(original_qasm)
            qc2 = QuantumCircuit.from_qasm_str(optimized_qasm)

            # 2. Extract Unitary Matrices (The Math Fingerprint)
            # Note: We remove measurements because they collapse the state, 
            # making unitary comparison impossible.
            qc1.remove_final_measurements()
            qc2.remove_final_measurements()

            op1 = Operator(qc1)
            op2 = Operator(qc2)

            # 3. Compare
            # We check if (Op1 == Op2)
            if op1.equiv(op2):
                return "✅ SUCCESS: Circuits are mathematically equivalent. Safe to execute."
            else:
                return "❌ DANGER: Optimization changed the circuit logic! Reject this circuit."

        except Exception as e:
            return f"Error during verification: {str(e)}"