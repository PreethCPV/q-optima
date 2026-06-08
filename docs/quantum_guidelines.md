# Qiskit 1.0 Quantum Circuit Construction Guidelines

This document provides essential knowledge for building accurate, hardware-valid quantum circuits using Qiskit 1.0.

## 1. Imports and Setup
*   **Correct imports:** `from qiskit import QuantumCircuit`
*   **Deprecated/Forbidden imports:** `from qiskit import Aer`, `from qiskit import execute`, `qiskit.Aer`
*   **Circuit Initialization:** `qc = QuantumCircuit(num_qubits, num_classical_bits)` (e.g. `qc = QuantumCircuit(5, 5)`)
*   **Variable Name:** Always use `qc` as the variable name for your quantum circuit.

## 2. Hardware Topology and Coupling Maps
*   You **MUST** respect the hardware coupling map provided by the Digital Twin tool.
*   Two-qubit gates (like CX/CNOT) can ONLY be applied between qubits that are directly connected in the coupling map.
*   If a request requires a two-qubit gate between unconnected qubits, you MUST swap the state using the built-in SWAP gate (`qc.swap(i, j)`) along a valid path until the two qubits are adjacent, apply the gate, and optionally route them back if necessary.
*   **Never** use manual CNOT sequences to implement a swap; use `qc.swap(i, j)`.
*   **Never** assume a coupling map exists; always calculate based on the specific `coupling_map` list of edges provided.

## 3. Basic Gates
*   Hadamard (Superposition): `qc.h(qubit)`
*   Pauli-X (NOT): `qc.x(qubit)`
*   Pauli-Y: `qc.y(qubit)`
*   Pauli-Z: `qc.z(qubit)`
*   Controlled-NOT (Entanglement): `qc.cx(control_qubit, target_qubit)`

## 4. Measurement
*   Always measure the circuit at the very end unless specified otherwise.
*   Use `qc.measure_all()` to measure all qubits and map them to classical bits automatically.
*   Alternatively, measure specific qubits: `qc.measure(qubit_index, classical_bit_index)`

## 5. What NOT to do
*   Do NOT include execution or simulation code like `simulator.run()`, `transpile()`, or `job.result()`.
*   Do NOT add visualization code like `print(qc)`.
*   Do NOT define your circuit inside a Python function unless specifically requested; provide raw executable code starting with imports and ending with measurements.
*   Keep the circuit as simple as possible. Minimal depth equals higher fidelity.
