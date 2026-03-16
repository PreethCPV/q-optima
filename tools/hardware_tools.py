from crewai.tools import tool
from qiskit_ibm_runtime.fake_provider import FakeManilaV2, FakeJakartaV2, FakeGuadalupeV2
import json
import os
from src.cache import tool_cache

BACKEND_REGISTRY = {
    "manila": FakeManilaV2,
    "jakarta": FakeJakartaV2,
    "guadalupe": FakeGuadalupeV2
}

class HardwareTools:

    @tool("Fetch Digital Twin Topology")
    def fetch_map(query: str = "fetch"):
        """
        Fetches the complete hardware specification of the configured IBM Digital Twin.
        
        Args:
            query: Dummy parameter for CrewAI compatibility (ignored)
        
        Returns:
        - Coupling map (allowed qubit connections)
        - Number of qubits
        - Basis gates (native gates supported)
        
        CRITICAL: This data is the ONLY source of truth for circuit generation.
        Do NOT assume any topology. Use this data explicitly.
        """

        backend_name = os.environ.get("QOPTIMA_BACKEND", "manila")
        cache_key = f"hardware_topology_{backend_name}"
        if tool_cache.has(cache_key):
            cached = tool_cache.get(cache_key)
            return cached if cached else None
        backend_class = BACKEND_REGISTRY.get(backend_name, FakeManilaV2)
        backend = backend_class()
        backend_name_str = backend.name.replace("fake_", "").capitalize()
        config = backend.configuration()
        
        coupling_map = config.coupling_map
        num_qubits = config.num_qubits
        basis_gates = config.basis_gates
    
        hardware_spec = {
            "backend_name": backend_name_str,
            "num_qubits": num_qubits,
            "coupling_map": coupling_map,
            "basis_gates": basis_gates,
            "topology_type": "IBM Quantum Architecture",
            "note": "These are the ONLY allowed connections. No other qubit pairs can interact directly."
        }
        
        # Return as formatted string for agent clarity
        output = f"""
HARDWARE SPECIFICATION ({backend_name_str} Digital Twin):
================================================
Backend: {hardware_spec['backend_name']}
Total Qubits: {hardware_spec['num_qubits']}
Topology: {hardware_spec['topology_type']}

COUPLING MAP (Allowed Connections):
{json.dumps(coupling_map, indent=2)}

NATIVE BASIS GATES:
{', '.join(basis_gates)}

CONSTRAINT: You can ONLY apply two-qubit gates between qubits listed in the coupling map.
If qubits are not directly connected, you MUST use SWAP gates through valid intermediate paths.
"""
        tool_cache.set(cache_key, output.strip())
        return output.strip()
