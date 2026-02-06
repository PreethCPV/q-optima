from crewai.tools import tool
from qiskit.transpiler import CouplingMap

class HardwareTools:
    
    @tool("Hardware Topology Checker")
    def check_connectivity(qubit_a: int, qubit_b: int):
        """
        Input: Two integers (qubit_a, qubit_b).
        Function: Checks if they are physically connected on a Linear (0-1-2-3-4) quantum chip.
        Returns: Success message if connected, Error if SWAP is needed.
        """
        # 1. Define the Hardware (Linear Line: 0-1-2-3-4)
        # We define it here so the tool is self-contained and stateless
        coupling_map = CouplingMap.from_line(5)

        # 2. Check strict physical connectivity (Distance must be exactly 1)
        # "distance" returns the number of hops. 1 hop = direct wire.
        if coupling_map.distance(qubit_a, qubit_b) == 1:
            return f"✅ Valid Connection: Qubit {qubit_a} and {qubit_b} are directly connected."
        else:
            return (
                f"❌ INVALID Connection: Qubit {qubit_a} and {qubit_b} are NOT connected. "
                f"Distance is {int(coupling_map.distance(qubit_a, qubit_b))} hops. "
                f"You MUST insert SWAP gates to move them adjacent."
            )