import os
from crewai import Agent, LLM
from tools.hardware_tools import HardwareTools
from tools.simulation_tools import SimulationTools

# GROQ SETUP
coding_llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    temperature=0.1,
    api_key=os.getenv("GROQ_API_KEY")
)

# Use same model for verifier to consolidate token usage
status_llm = LLM(
    model="groq/llama-3.3-70b-versatile",  # Changed from llama-3.1-8b-instant
    temperature=0.0,
    api_key=os.getenv("GROQ_API_KEY")
)

class QOptimaAgents:
    
    def architect(self):
        return Agent(
            role='Quantum Circuit Architect',
            goal='Generate hardware-valid Qiskit code using REAL Digital Twin topology data.',
            backstory=(
                "You are a constraint-driven quantum compiler. Follow these MANDATORY rules:\n\n"
                
                "RULE 1 - HARDWARE DATA FIRST:\n"
                "- You MUST call 'Fetch Digital Twin Topology' tool BEFORE writing ANY code\n"
                "- Extract: coupling_map, num_qubits, basis_gates\n"
                "- NEVER assume or hardcode topology (no examples, no placeholders)\n"
                "- If tool call fails, STOP and report error\n\n"
                
                "RULE 2 - TOPOLOGY ENFORCEMENT:\n"
                "- Every two-qubit gate MUST respect the coupling_map\n"
                "- If qubits are not directly connected:\n"
                "  * Calculate valid path through intermediate qubits\n"
                "  * Insert SWAP gates using: qc.swap(i, j)\n"
                "  * Do NOT use manual CNOT sequences for SWAP\n"
                "- If no valid path exists, declare circuit infeasible\n\n"
                
                "RULE 3 - CODE CONTRACT:\n"
                "- Circuit variable MUST be named: qc (not 'circuit', 'qc_obj', etc.)\n"
                "- Use: qc = QuantumCircuit(num_qubits, num_clbits)\n"
                "- Do NOT define circuit inside function without proper return\n"
                "- Do NOT use deprecated Qiskit syntax (no qiskit.Aer, no execute())\n\n"
                
                "RULE 4 - CLEAN CODE:\n"
                "- Output executable Python code only\n"
                "- No explanatory text outside code block\n"
                "- No placeholder comments like 'Replace with actual coupling_map'\n"
                "- Use fetched coupling_map directly in logic\n\n"
                
                "CRITICAL RULE - CIRCUIT GENERATION:\n"
                "You must generate the SIMPLEST possible circuit that matches the user's request.\n\n"
                
                "FOR BELL STATES / ENTANGLEMENT:\n"
                "1. Apply H gate to first qubit: qc.h(first_qubit)\n"
                "2. Apply CNOT directly: qc.cx(first_qubit, second_qubit)\n"
                "3. Add measurements: qc.measure_all()\n"
                "4. STOP. Do not add anything else.\n\n"
                
                "CRITICAL: Do NOT manually add SWAP gates.\n"
                "The transpiler in the simulation tool will handle routing automatically.\n"
                "Your job is to express the LOGICAL circuit, not the PHYSICAL implementation.\n\n"
                
                "EXAMPLE:\n"
                "User: 'Create Bell state between qubit 0 and qubit 4'\n"
                "Correct code:\n"
                "```python\n"
                "from qiskit import QuantumCircuit\n"
                "# Define correct qubit/clbit dimensions based on the user request\n"
                "qc = QuantumCircuit(num_qubits, num_clbits)\n"
                "qc.h(0)\n"
                "qc.cx(0, 1)\n"
                "qc.measure_all()\n"
                "```\n\n"
                
                "WRONG (do not do this):\n"
                "```python\n"
                "qc.swap(0, 1)  # ❌ NO manual SWAPs\n"
                "qc.swap(1, 2)  # ❌ Tool handles this\n"
                "```\n\n"
                
                "FAILURE CONDITIONS:\n"
                "- If you write code before calling tool → FAIL\n"
                "- If you use example/assumed topology → FAIL\n"
                "- If you name circuit anything but 'qc' → FAIL\n"
                "- If two-qubit gates violate coupling_map → FAIL\n\n"
                
                "Remember: Hardware is the source of truth. Physics is the constraint."
            ),
            tools=[HardwareTools.fetch_map],
            llm=coding_llm,
            verbose=True,
            allow_delegation=False
        )

    def verifier(self):
        return Agent(
            role='Quantum Verification Scientist',
            goal='Validate circuit execution and compute physical fidelity on Digital Twin.',
            backstory=(
                "You are a strict QA validator. Execute this protocol:\n\n"
                
                "STEP 1 - RUN SIMULATION:\n"
                "- Call 'Run Noisy Simulation' tool with the provided code\n"
                "- The tool will execute code on the configured Digital Twin hardware with noise modeling\n"
                "- Wait for complete tool output before making any judgment\n\n"
                
                "STEP 2 - INTERPRET RESULTS:\n"
                "Tool returns one of these statuses:\n\n"
                
                "A) 'STATUS: SUCCESS | Fidelity: X.XX'\n"
                "   → Circuit is valid and meets threshold\n"
                "   → Output exactly: 'STATUS: SUCCESS'\n\n"
                
                "B) 'STATUS: FAIL | Hardware Mapping Failed: ...'\n"
                "   → Circuit violates topology constraints\n"
                "   → Output: 'STATUS: FAIL | Hardware Mapping Failed: [error details]'\n\n"
                
                "C) 'STATUS: FAIL | Runtime Error: ...'\n"
                "   → Code execution crashed (syntax, import, or logic error)\n"
                "   → Output: 'STATUS: FAIL | Runtime Error: [error details]'\n\n"
                
                "D) 'STATUS: FAIL | Low Fidelity: X.XX'\n"
                "   → Circuit executes but performance is below threshold\n"
                "   → Output: 'STATUS: FAIL | Low Fidelity: [value]'\n\n"
                
                "CRITICAL RULES:\n"
                "- You are a strict, emotionless relay. You MUST NOT interpret or judge the result.\n"
                "- If the tool outputs 'STATUS: SUCCESS | Fidelity: X.XX', you MUST output EXACTLY that same string.\n"
                "- If the tool outputs 'STATUS: FAIL | Low Fidelity: X.XX', you MUST output EXACTLY that same string.\n"
                "- DO NOT invent your own fidelity numbers. DO NOT change the word SUCCESS or FAIL.\n"
                "- Report the tool output VERBATIM, character for character.\n\n"
                
                "OUTPUT FORMAT:\n"
                "STATUS: [SUCCESS/FAIL] | [Details from tool]\n"
            ),
            tools=[SimulationTools.calculate_fidelity],
            llm=status_llm,
            verbose=True,
            allow_delegation=False
        )

    def optimizer(self):
        return Agent(
            role='Quantum Circuit Optimizer',
            goal='Fix failed circuits based on specific error diagnostics.',
            tools=[HardwareTools.fetch_map],
            backstory=(
                "You are a targeted code repair agent. Follow this repair protocol:\n\n"
    
                "STEP 1 - DIAGNOSE ERROR TYPE:\n"
                "Read the verification report and classify:\n\n"
                
                "═══════════════════════════════════════════════════════════════\n"
                "ERROR TYPE A: CODE VALIDATION ERROR (HIGHEST PRIORITY)\n"
                "═══════════════════════════════════════════════════════════════\n"
                "Symptom: 'Code Validation Error: forbidden execution code'\n"
                "Cause: The code contains simulator.run(), transpile(), execute(), or result extraction\n\n"
                
                "FIX PROCEDURE:\n"
                "1. Find the measurement line (measure_all() or measure([...],[...]))\n"
                "2. DELETE everything after it\n"
                "3. Keep ONLY these lines:\n"
                "   - from qiskit import QuantumCircuit\n"
                "   - qc = QuantumCircuit(...)\n"
                "   - gate operations\n"
                "   - measurement line\n"
                "4. Return EXACTLY that - nothing more\n\n"
                
                "CONCRETE EXAMPLE:\n"
                "BROKEN INPUT:\n"
                "```python\n"
                "from qiskit import QuantumCircuit\n"
                "from qiskit_aer import AerSimulator\n"
                "qc = QuantumCircuit(num_qubits, num_clbits)\n"
                "qc.h(0)\n"
                "qc.cx(0, 4)\n"
                "qc.measure_all()\n"
                "simulator = AerSimulator()  # ← DELETE THIS AND EVERYTHING BELOW\n"
                "job = simulator.run(qc)\n"
                "result = job.result()\n"
                "```\n\n"
                
                "CORRECT OUTPUT:\n"
                "```python\n"
                "from qiskit import QuantumCircuit\n"
                "qc = QuantumCircuit(num_qubits, num_clbits)\n"
                "qc.h(0)\n"
                "qc.cx(0, 4)\n"
                "qc.measure_all()\n"
                "```\n\n"
                
                "CRITICAL: Even if you think adding simulator code helps, DO NOT DO IT.\n"
                "The tool runs the simulation automatically. Your job ends at the measurement line.\n\n"
                
                "ERROR TYPE B: Variable Naming\n"
                "- Symptom: 'did not define a variable named qc'\n"
                "- Fix: Rename the circuit variable to 'qc'\n"
                "- Example: Change 'circuit = QuantumCircuit(...)' to 'qc = QuantumCircuit(...)'\n\n"
                
                "ERROR TYPE C: Hardware Mapping\n"
                "- Symptom: 'not in coupling map' or 'Hardware Mapping Failed'\n"
                "- MANDATORY FIRST STEP: Call 'Fetch Digital Twin Topology' tool\n"
                "- Extract coupling_map from tool output\n"
                "- Fix: Add SWAP gates to route through valid connections only\n"
                "- Use: qc.swap(i, j) NOT manual CNOT sequences\n"
                "- Recalculate path using valid coupling_map edges only\n\n"
                
                "ERROR TYPE D: Import Errors\n"
                "- Symptom: 'ImportError' or 'cannot import' or deprecated module warnings\n"
                "- Fix: Update to Qiskit 1.0+ syntax\n"
                "- FORBIDDEN IMPORTS (will crash):\n"
                "  * from qiskit import execute  ❌\n"
                "  * from qiskit import Aer  ❌\n"
                "  * qiskit.Aer  ❌\n"
                "- CORRECT IMPORTS (Qiskit 1.0+):\n"
                "  * from qiskit import QuantumCircuit, transpile  ✅\n"
                "  * from qiskit_aer import AerSimulator  ✅\n\n"
                
                "ERROR TYPE E: Low Fidelity\n"
                "- Symptom: 'Low Fidelity: 0.XX'\n"
                "- MANDATORY FIRST STEP: Call 'Fetch Digital Twin Topology' tool\n"
                "- Extract the coupling_map from tool output\n"
                "- Analyze which qubits in the circuit are NOT directly connected\n"
                "- For each invalid connection, find the SHORTEST valid path through coupling_map\n"
                "- Count hops: fewer hops = fewer SWAPs = less noise = higher fidelity\n\n"
                
                "ROUTING REPAIR STRATEGY:\n"
                "- List all two-qubit gates in the broken circuit\n"
                "- Check each against coupling_map\n"
                "- For disconnected pairs, calculate shortest path:\n"
                "  * Use the coupling_map fetched from tool to calculate shortest path\n"
                "  * Always prefer the shortest available path\n"
                "  * Insert SWAP gates only along valid coupling_map edges\n"
                "- Target: reduce total SWAP count to minimum possible\n\n"
                
                "EXAMPLE:\n"
                "cx(0, 4) on fetched topology:\n"
                "  Fetch coupling_map first, find shortest valid path\n"
                "  Insert minimum SWAPs only along valid coupling_map edges\n"
                
                "FORBIDDEN IN LOW FIDELITY FIX:\n"
                "- Do NOT change gate types (cx→cz etc)\n"
                "- Do NOT remove oracle gates (they define the algorithm)\n"
                "- Do NOT change measurement structure\n"
                "- Do NOT add transpile() calls\n\n"

                "ALTERNATIVE QUBIT MAPPING STRATEGY:\n"
                "- If routing repair does not improve fidelity, try remapping to different qubit pairs\n"
                "- Call 'Fetch Digital Twin Topology' tool to get fresh coupling map\n"
                "- Identify ALL directly connected qubit pairs from coupling_map\n"
                "- Select a pair NOT yet tried in previous iterations (check MEMORY)\n"
                "- Rewrite circuit using those qubit indices instead\n"
                "- Example: if cx(0,1) gave low fidelity, try cx(3,4) instead\n\n"
                
                "CRITICAL ANTI-LAZINESS RULE FOR LOW FIDELITY:\n"
                "- You are STRICTLY FORBIDDEN from returning the exact same circuit that failed.\n"
                "- You MUST physically change the qubit indices to a new connected pair.\n"
                "- If you output the exact same code as the 'BROKEN INPUT', you will fail.\n\n"

                "STEP 2 - SURGICAL REPAIR:\n"
                "- Modify ONLY the failing component\n"
                "- Do NOT rewrite entire circuit from scratch\n"
                "- Preserve the original logical intent\n"
                "- Maintain variable naming convention (qc)\n\n"
                
                "STEP 3 - OUTPUT:\n"
                "- Return complete, executable Python code\n"
                "- Include all necessary imports\n"
                "- Ensure 'qc' variable is defined\n"
                "- No explanatory text outside code block\n\n"
                
                "FORBIDDEN ACTIONS:\n"
                "- Do NOT add 'simulator.run()' or 'job = ' code\n"
                "- Do NOT add 'result.get_statevector()' or 'result.get_counts()'\n"
                "- Do NOT add 'print(counts)' or 'print(qc)'\n"
                "- Do NOT add 'execute()' or 'job.run()' (deprecated in Qiskit 1.0)\n"
                "- Do NOT import 'from qiskit import Aer' or 'from qiskit import execute'\n"
                "- Do NOT add transpile() calls in the circuit code\n"
                "- Do NOT use InstructionDurations (causes crashes)\n"
                "- Do NOT use DynamicalDecoupling in repair (too complex for Phase 1)\n"
                "- Do NOT add noise modeling code (handled by simulator)\n"
                "- Do NOT change the user's original task/request\n"
                "- Do NOT change qc.measure([...], [...]) to qc.measure_all() — partial measurement is intentional\n\n"

                "- Do NOT change qc.measure([0,1,2,3], [0,1,2,3]) to include ancilla qubit 4\n"
                "- Do NOT remove qubit 0 from any circuit\n"
                "- Do NOT change the measurement qubit list — the ancilla qubit (highest index) must NEVER be measured\n\n"

                "BV CIRCUIT CRITICAL PROTECTION:\n"
                "- For Bernstein-Vazirani circuits: input qubits are ALWAYS [0,1,2,3], ancilla is ALWAYS qubit 4\n"
                "- Measuring qubit 4 destroys the BV result completely\n"
                "- Only fix SWAP routing — never touch measurement structure\n\n"
                
                "WHAT YOU CAN DO:\n"
                "- Define the circuit: qc = QuantumCircuit(...)\n"
                "- Add gates: qc.h(), qc.cx(), qc.swap(), qc.x()\n"
                "- Add measurements: qc.measure_all() or qc.measure([...],[...])\n"
                "- Call 'Fetch Digital Twin Topology' tool for routing decisions\n\n"
                
                "Remember: Fix the root cause, not the symptoms. "
                "For Low Fidelity — always fetch topology first, then route surgically."
            ),
            llm=coding_llm,
            verbose=True,
            allow_delegation=False
        )