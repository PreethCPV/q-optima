from typing import Tuple, List, Dict
from qiskit import QuantumCircuit
from qiskit_ibm_runtime.fake_provider import FakeManilaV2, FakeJakartaV2, FakeGuadalupeV2

class DynamicHardwareSelector:
    """
    Novel Enhancement: Auto-selects the optimal Digital Twin 
    based on the required number of qubits for the circuit.
    Ensures efficiency by not loading a 16-qubit backend for a 2-qubit circuit.
    """
    def __init__(self):
        self.registry: List[Dict] = [
            {"id": "FakeManilaV2", "qubits": 5, "name": "manila", "class": FakeManilaV2},
            {"id": "FakeJakartaV2", "qubits": 7, "name": "jakarta", "class": FakeJakartaV2},
            {"id": "FakeGuadalupeV2", "qubits": 16, "name": "guadalupe", "class": FakeGuadalupeV2},
            {"id": "ibmq_qasm_simulator", "qubits": 32, "name": "ibmq_qasm_simulator", "class": None}, 
            {"id": "ibm_brisbane", "qubits": 127, "name": "ibm_brisbane", "class": None},
            {"id": "ibm_osaka", "qubits": 127, "name": "ibm_osaka", "class": None},
            {"id": "hybrid_brisbane", "qubits": 127, "name": "hybrid_brisbane", "class": None}
        ]
        # Sort by ascending qubits to find the smallest fitting backend
        self.registry.sort(key=lambda x: x["qubits"])

    def select_backend(self, required_qubits: int) -> Tuple[str, str]:
        """
        Returns (id, name) of the optimal backend.
        """
        for backend in self.registry:
            if backend["qubits"] >= required_qubits:
                return backend["id"], backend["name"]
        
        # Fallback to the largest available
        largest = self.registry[-1]
        print(f"⚠️ Warning: Requested {required_qubits} qubits, but max available is {largest['qubits']}. Returning largest.")
        return largest["id"], largest["name"]

    def get_qubit_count(self, backend_id_or_name: str) -> int:
        """
        Returns the number of qubits for a given backend ID (e.g. FakeManilaV2) 
        or short name (e.g. manila). Returns 0 if not found.
        """
        for backend in self.registry:
            if backend["id"] == backend_id_or_name or backend["name"] == backend_id_or_name:
                return backend["qubits"]
        return 0

    def analyze_circuit_and_route(self, qc: QuantumCircuit) -> Tuple[str, str]:
        """
        Takes an existing QuantumCircuit and routes it to the correct backend.
        """
        return self.select_backend(qc.num_qubits)

# Singleton instance
hardware_router = DynamicHardwareSelector()
