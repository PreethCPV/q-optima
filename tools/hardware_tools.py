from crewai.tools import tool
from qiskit_ibm_runtime.fake_provider import FakeManilaV2
import json
from src.cache import tool_cache

class HardwareTools:

    @tool("Fetch Digital Twin Topology")
    def fetch_map(query: str = "fetch"):
        """
        Fetches the complete hardware specification of IBM Manila Digital Twin.
        
        Args:
            query: Dummy parameter for CrewAI compatibility (ignored)
        
        Returns:
        - Coupling map (allowed qubit connections)
        - Number of qubits
        - Basis gates (native gates supported)
        
        CRITICAL: This data is the ONLY source of truth for circuit generation.
        Do NOT assume any topology. Use this data explicitly.
        """

        if tool_cache.has("hardware_topology"):
            return tool_cache.get("hardware_topology")
        backend = FakeManilaV2()
        config = backend.configuration()
        
        # Extract all critical hardware parameters
        coupling_map = config.coupling_map
        num_qubits = config.num_qubits
        basis_gates = config.basis_gates
        
        # Return structured data as a clear specification
        hardware_spec = {
            "backend_name": "FakeManilaV2",
            "num_qubits": num_qubits,
            "coupling_map": coupling_map,
            "basis_gates": basis_gates,
            "topology_type": "Heavy-Hex (IBM)",
            "note": "These are the ONLY allowed connections. No other qubit pairs can interact directly."
        }
        
        # Return as formatted string for agent clarity
        output = f"""
HARDWARE SPECIFICATION (IBM Manila Digital Twin):
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
        tool_cache.set("hardware_topology", output.strip())
        return output.strip()
