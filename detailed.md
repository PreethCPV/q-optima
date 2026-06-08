# Q-Optima: The Definitive Technical Architecture Guide

## 1. Project Mission & High-Level Philosophy
Q-Optima is a **Digital Twin-driven Quantum Compiler Orchestrator**. Its primary goal is to ensure that "What you see is what you get" when moving from a quantum simulation to real hardware. It solves the **Fidelity Gap**—the phenomenon where a circuit works 100% in a noiseless simulator but fails or returns garbage on a real quantum computer due to thermal noise, qubit decoherence, and connectivity limits.

---

## 2. Granular Code Workflow: The "Life of a Circuit"

When a user submits a request, the following sequence occurs at the code level:

1.  **Input Parsing (`main.py` / `api.py`)**: The system captures the request and uses the **Dynamic Router** to assign a backend based on qubit count.
2.  **Topology Retrieval (`tools/hardware_tools.py`)**: The system calls `fetch_map()`. This function accesses the `BACKEND_REGISTRY`. It retrieves the `coupling_map`—a list of permitted qubit pairs (edges in a graph).
3.  **Phase 1: Generative Design (`src/agents.py`)**:
    *   The **Architect Agent** is invoked with a strict rule-based prompt.
    *   **Rule 1 (Hardware First)**: It must fetch the map before typing code.
    *   **Rule 2 (Logical expression)**: It is instructed *not* to add manual SWAPs. This is a critical design choice—we want the Architect to express the algorithm's intent, and let the Qoptima simulation backend handle the physical mapping.
4.  **Phase 2: Verbatim Execution (`tools/simulation_tools.py`)**:
    *   The **Verifier Agent** takes the code.
    *   The code is passed to `_execute_simulation()`.
    *   **Safety Check**: The code is scanned for "forbidden patterns" (like manual simulator runs or code injection).
    *   **Transpilation**: The circuit is transpiled for the specific backend using `optimization_level=1` (local) or `3` (cloud).
    *   **Dual Run**: An **Ideal Simulation** (noiseless) and a **Noisy Simulation** (using the backend's specific noise model) are run.
5.  **Phase 3: Mathematical Certification**:
    *   The **Hellinger Fidelity** is computed (see Section 6).
    *   If `fidelity < 0.60`, the **Optimizer** is triggered.
    *   The Optimizer looks at the exact error (e.g., "Hardware Mapping Failed") and uses the `coupling_map` to calculate a new, shorter physical path for the gates.

---

## 3. Mathematical Foundations: Feature Extraction

### 🩺 ECG Digital Signal Processing (`src/ecg_features.py`)
Q-Optima performs clinical-grade extraction of cardiac features before quantum encoding:
1.  **Butterworth Filter**: A 4th-order bandpass filter ($0.5\,Hz$ to $45\,Hz$) is applied to remove baseline wander and powerline interference.
2.  **RR Interval**: Calculated as $t_{R\_curr} - t_{R\_prev}$ in seconds.
3.  **QRS Duration**: Measured by finding the local minima (Q and S peaks) exactly centered around the annotated R peak.
4.  **PR Interval**: The time from the P-wave peak (local maximum before Q) to the R-peak.
5.  **ST Deviation**: The difference between the isoelectric baseline (post-P wave) and the ST segment mean voltage.

**Normalization**: These values (in volts and seconds) are normalized to the range $[0, 2\pi]$ using clinical reference ranges so they can be used directly as rotation angles for $R_z$ gates.

### 📐 Hellinger Fidelity (`tools/simulation_tools.py`)
To compare the "quality" of a noisy run, we use the Hellinger distance between the Ideal probability distribution $P$ and Noisy distribution $Q$:
$$BC(P, Q) = \sum_{i} \sqrt{P_i Q_i} \quad \text{(Bhattacharyya Coefficient)}$$
$$Fidelity = BC(P, Q)^2$$
In the code: `overlap_sum = sum(np.sqrt(prob1[outcome] * prob2[outcome]) for outcome in all_outcomes)`.

---

## 4. Quantum Algorithm Deep-Dive

### ZZ Feature Map Encoding
For a 2-feature input $(x_0, x_1)$, the circuit depth is intentionally doubled to ensure better state separation:
1.  **Layer 1 (Superposition)**: Hadamard gates.
2.  **Layer 3 (Single Qubit Phase)**: $R_z(2x_0)$ and $R_z(2x_1)$.
3.  **Layer 4 (Entanglement)**: $CNOT(0,1) \rightarrow R_z(2(\pi-x_0)(\pi-x_1)) \rightarrow CNOT(0,1)$. This creates "quantum interference" between the two features.
4.  **Layer 5-7**: Repeat the above for "Higher-Order Encoding."

### Bernstein-Vazirani (BV) Oracle Logic
The BV Oracle is the "heart" of the algorithm. In Q-Optima:
*   If the $i$-th bit of the hidden string is `1`, a CNOT is applied from Qubit $i$ (control) to the Ancilla Qubit (target).
*   If the bit is `0`, no gate is applied.
*   By initializing the Ancilla in the $|-\rangle$ state, the "phase kickback" mechanism flips the phase of the $|1\rangle$ component of the control qubit, allowing the entire string to be read out after a final Hadamard transformation.

---

## 5. Agent Decision Protocols (Strict Rules)

To ensure the LLM generates executable code, Q-Optima uses **Prompt-Enforced Constraints**:

1.  **Error Type A (Code Validation)**: If the agent types `simulator.run()`, the script detects it as a security risk and triggers a "Forbidden Pattern" error. This prevents the LLM from trying to manage the execution, which should only be handled by the backend tools.
2.  **Error Type B (Variable Naming)**: The circuit **MUST** be named `qc`. If the agent uses `circuit` or `q`, the Verifier returns a `FAIL`, and the Optimizer is explicitly told: "Rename the variable to qc."
3.  **Error Type C (Hardware Mapping)**: If a gate uses qubits $(0, 4)$ on a processor where they aren't connected, the Verifier detects a `Transpilation Error`. The Optimizer then uses the **Network Topology map** to insert `qc.swap()` gates to bridge the distance.

---

## 6. Detailed File & Function Reference Index

| File | Key Function | Purpose |
| :--- | :--- | :--- |
| `main.py` | `main()` | Handles CLI loops, logging setup, and mode selection. |
| `api.py` | `chat_endpoint()` | Orchestrates the FastAPI multi-agent request-response flow. |
| `agents.py` | `architect()` | Defines the LLM prompt for hardware-constrained coding. |
| `hardware_tools.py` | `fetch_map()` | Translates human-selected backends into Qiskit topology objects. |
| `simulation_tools.py` | `_execute_simulation()` | The "Engine" — runs the code and returns the Fidelity score. |
| `ibm_connector.py` | `run_cloud_validation()`| Manages real QPU authentication and result retrieval. |
| `visualizer.py` | `generate_circuit_diagram()`| Uses PIL to stitch together logical and physical diagrams. |
| `validator.py` | `validate_code()` | Uses Regex to check for 'qc' and 'measure' variables. |
| `memory.py` | `get_optimizer_context()` | Injects failed history into the Optimizer's "brain." |
| `dynamic_hardware.py`| `select_backend()` | Calculates the smallest fitting backend for a given qubit count. |

---

## 7. Cloud Execution Security & Performance

### Async Polling Pattern
In `api.py`, long-running IBM Quantum jobs are handled without blocking the server:
1.  **Submission**: Returns a `job_id` immediately.
2.  **Polling**: The frontend calls `/api/ibm_status/{job_id}` every few seconds.
3.  **Hellinger Comparison**: Upon completion, the system re-calculates Fidelity using the *real* hardware counts vs. the *ideal* simulation to validate the Digital Twin's accuracy.

### Caching Mechanism (`src/cache.py`)
To prevent hitting API rate limits or wasting compute time, the system caches `Fetch Digital Twin Topology` results. If the same backend is requested twice in a session, the system returns the cached topology immediately rather than re-querying the hardware provider.
