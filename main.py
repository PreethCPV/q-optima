import os
import sys
import re
import time
import logging
from crewai import Task, Crew
from src.agents import QOptimaAgents
from src.memory import ConversationMemory   
from src.validator import SchemaValidator
from src.visualizer import generate_circuit_diagram, generate_measurement_chart, generate_fidelity_graph
from src.bv_circuit import generate_bv_prompt, get_expected_result
from src.zz_feature_map import get_iris_features, generate_zz_prompt, get_zz_description
from src.ecg_features import get_ecg_features, generate_ecg_prompt, get_ecg_description
from src.result_saver import save_run_results
from datetime import datetime
from src.visualizer import generate_ecg_waveform, generate_topology_map, generate_bloch_sphere
from tools.simulation_tools import run_simulation_direct

# 1. Configuration to bypass internal checks
os.environ["OPENAI_API_KEY"] = "NA"

# 2. Setup Split Logging
def setup_logger(name, log_file):
    """Create separate loggers for each agent with clean formatting."""
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')        
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    return logger

# Ensure logs directory exists
if not os.path.exists('logs'):
    os.makedirs('logs')

# Clear old logs and setup new ones
log_arch = setup_logger('architect', 'logs/architect_log.txt')
log_verif = setup_logger('verifier', 'logs/verifier_log.txt')
log_optim = setup_logger('optimizer', 'logs/optimizer_log.txt')

def extract_code(text):
    """
    Extract Python code from markdown code blocks.
    Handles both ```python and ``` formats.
    Strips out empty lines to prevent LLM JSON escaping bugs on '\n\n'.
    """
    text_str = str(text)
    
    # Try to find ```python code block first
    match = re.search(r'```python\n(.*?)\n```', text_str, re.DOTALL)
    if match:
        code = match.group(1).strip()
    else:
        # Try generic ``` code block
        match = re.search(r'```\n(.*?)\n```', text_str, re.DOTALL)
        if match:
            code = match.group(1).strip()
        else:
            code = text_str.strip()
            
    # Strip empty lines so LLMs don't generate invalid \n\qc escape sequences
    lines = [line for line in code.split('\n') if line.strip() != '']
    return '\n'.join(lines)

def print_separator(title):
    """Print a clean section separator."""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")

def main():
    agents = QOptimaAgents()
    memory = ConversationMemory()           # ← NEW: initialize memory for this session

    fidelity_history = []

    print_separator("⚛️  Q-OPTIMA: DIGITAL TWIN QUANTUM COMPILER (Qiskit 1.0)")
    print("This system uses a multi-agent loop to compile quantum circuits")
    print("that are validated against real hardware topology constraints.\n")
    
    # Get user input
    print("Select mode:")
    print("1. Free input (any circuit request)")
    print("2. Bernstein-Vazirani demo")
    print("3. ZZ Feature Map — Iris Data Encoding demo")
    print("4. ECG Arrhythmia — MIT-BIH Cardiac Encoding demo")
    mode = input("Enter 1, 2, 3 or 4: ").strip() 

    if mode == "2":
        hidden = input("Enter hidden binary string (e.g. 1011, max 4 bits): ").strip()
        if not all(c in '01' for c in hidden) or len(hidden) > 4:
            print("❌ Invalid string. Use only 0s and 1s, max 4 bits.")
            return
        user_input = generate_bv_prompt(hidden)
        expected = get_expected_result(hidden)
        print(f"\n🔍 BV Demo: Hidden string = '{hidden}'")
        print(f"🎯 Expected measurement result: '{expected}'")
    elif mode == "3":
        print("\n ZZ Feature Map — Iris Dataset Encoding")
        print("Encoding classical flower measurements into quantum state...\n")
        
        try:
            sample_idx = int(input("Enter Iris sample index (0-149, default 0): ").strip() or "0")
            if sample_idx < 0 or sample_idx > 149:
                print(" Invalid index. Using default 0.")
                sample_idx = 0
        except ValueError:
            sample_idx = 0
        
        features, feature_names, class_name = get_iris_features(sample_idx, num_features=2)
        user_input = generate_zz_prompt(features, feature_names)
        zz_info = get_zz_description(features, feature_names, class_name)
        expected = None
        
        print(f" Sample {sample_idx}: {class_name}")
        print(f"   {feature_names[0]}: {round(features[0], 4)} rad")
        print(f"   {feature_names[1]}: {round(features[1], 4)} rad")
        print(f" Encoding into 2-qubit ZZ Feature Map circuit...\n")

    elif mode == "4":
        print("\n ECG Arrhythmia — MIT-BIH Cardiac Encoding")
        print("Encoding ECG heartbeat features into quantum state...\n")

        record_id = input("Enter MIT-BIH record ID (e.g. 100, 200, 231, default 100): ").strip() or "100"

        try:
            beat_idx = int(input("Enter beat index (5-100, default 10): ").strip() or "10")
            if beat_idx < 10 or beat_idx > 200:
                print("Invalid index. Using default 10.")
                beat_idx = 10
        except ValueError:
            beat_idx = 10

        try:
            num_feat = int(input("Enter number of features (2 or 4, default 2): ").strip() or "2")
            if num_feat not in (2, 4):
                print("Invalid. Using default 2.")
                num_feat = 2
        except ValueError:
            num_feat = 2

        features, feature_names, beat_label, waves_info = get_ecg_features(record_id, beat_idx, num_feat)
        user_input = generate_ecg_prompt(features, feature_names)
        ecg_info = get_ecg_description(features, feature_names, beat_label, record_id)
        expected = None

        print(f"  Record: {record_id} | Beat {beat_idx}: {beat_label}")
        for name, val in zip(feature_names, features):
            print(f"   {name}: {round(val, 4)} rad")
        print(f"  Encoding into {num_feat}-qubit ZZ Feature Map circuit...\n")
        generate_ecg_waveform(waves_info, f"ecg_{record_id}_beat{beat_idx}_waveform.png")

      
    else:
        user_input = input("Enter your quantum circuit request: ").strip()
        expected = None
    if mode != "4":
        num_feat = 2
        record_id = "na"
        beat_idx = 0 

    print("\nSelect backend:")
    print("1. FakeManilaV2    — 5 qubits, linear topology")
    print("2. FakeJakartaV2   — 7 qubits, heavy-hex topology")
    print("3. FakeGuadalupeV2 — 16 qubits, heavy-hex topology")
    print("--- LIVE CLOUD HARDWARE (Requires API Token & Queue Wait) ---")
    print("4. IBM Cloud Sim   — 32 qubits (ibmq_qasm_simulator)")
    print("5. IBM Brisbane    — 127 qubits (ibm_brisbane, Real QPU)")
    print("6. IBM Osaka       — 127 qubits (ibm_osaka, Real QPU)")
    print("--- HYBRID PIPELINE ---")
    print("7. Hybrid (Brisbane) — Local Sim with downloaded IBM Cloud Noise profile")
    backend_choice = input("Enter 1-7 (default 1): ").strip() or "1"

    backend_map = {
        "1": ("manila",    "FakeManilaV2",    "Manila (5Q Local)"),
        "2": ("jakarta",   "FakeJakartaV2",   "Jakarta (7Q Local)"),
        "3": ("guadalupe", "FakeGuadalupeV2", "Guadalupe (16Q Local)"),
        "4": ("ibmq_qasm_simulator", "ibmq_qasm_simulator", "IBM Cloud Simulator"),
        "5": ("ibm_brisbane", "ibm_brisbane", "IBM Brisbane (127Q Live)"),
        "6": ("ibm_osaka", "ibm_osaka", "IBM Osaka (127Q Live)"),
        "7": ("hybrid_brisbane", "ibm_brisbane", "Hybrid (Local Sim + IBM Cloud Noise - Brisbane)")
    }
    backend_key, backend_full_name, backend_display = backend_map.get(backend_choice, backend_map["1"])
    os.environ["QOPTIMA_BACKEND"] = backend_key
    print(f"\n Backend selected: {backend_display}")

    generate_topology_map(backend_key, list(range(num_feat)), f"ecg_{backend_key}_{record_id}_beat{beat_idx}_topology.png")
    
    if not user_input:
        print(" Error: Empty request. Please provide a circuit description.")
        return
    
    print(f"\n Task: {user_input}")
    
    # --- PHASE 1: ARCHITECT GENERATES INITIAL CIRCUIT ---
    print_separator("[PHASE 1/3] ARCHITECT: Generating Circuit")
    print(" Fetching hardware topology from Digital Twin...")
    print(" Compiling circuit with hardware constraints...\n")

    # FIX: Create agent once, reuse the same instance
    architect_agent = agents.architect()

    task_build = Task(
        description=(
            f"User Request: '{user_input}'\n\n"
            "YOUR WORKFLOW:\n"
            "1. Call 'Fetch Digital Twin Topology' tool first\n"
            "2. Extract coupling_map, num_qubits from tool output\n"
            "3. Design circuit that satisfies the request\n"
            "4. Ensure all two-qubit gates respect coupling_map\n"
            "5. Add SWAP gates if needed (use qc.swap(i,j))\n"
            "6. Name the circuit variable 'qc'\n"
            "7. Return executable Python code only"
        ),
        expected_output="Python code defining a QuantumCircuit named 'qc'",
        agent=architect_agent                 
    )
    
    crew_phase_1 = Crew(
        agents=[architect_agent],               
        tasks=[task_build],
        verbose=True
    )
    
    try:
        result_1 = crew_phase_1.kickoff()
        current_code = extract_code(result_1)
        log_arch.info(f"Generated Code:\n{current_code}")

        valid, reason = SchemaValidator.validate_code(current_code)
        if not valid:
            print(f"❌ Architect output invalid: {reason}")
            log_arch.error(f"Schema validation failed: {reason}")
            return
        print(f"✅ Code schema valid.")

        print(f"\n✅ Architect completed. Code logged to logs/architect_log.txt")
    except Exception as e:
        print(f"\n❌ Architect failed: {str(e)}")
        log_arch.error(f"Architect Error: {str(e)}")
        return

    # --- PHASE 2: ITERATIVE VERIFICATION AND OPTIMIZATION LOOP ---
    max_iterations = 3
    success = False
    
    # Add initial delay after architect phase to allow API quota reset
    print("\n⏳ Waiting 15 seconds to avoid rate limiting...")
    time.sleep(15)
    
    for iteration in range(1, max_iterations + 1):
        print_separator(f"[PHASE 2/3] ITERATION {iteration}: Testing on Digital Twin")
        
        # STEP 2A: VERIFY THE CIRCUIT
        print(f" Running noisy simulation on {backend_full_name} Digital Twin...")
        print(" Computing quantum state fidelity...\n")

        # FIX: Create verifier agent once per iteration (not twice)
        verifier_agent = agents.verifier()

        task_verify = Task(
            description=(
                f"Execute this quantum circuit code on the Digital Twin:\n\n"
                f"```python\n{current_code}\n```\n\n"
                "YOUR WORKFLOW:\n"
                "1. Call 'Run Noisy Simulation' tool with the code above\n"
                "2. Wait for tool output\n"
                "3. Report the exact STATUS from tool output\n"
                "4. Do NOT modify or interpret the result\n\n"
                "Expected output format:\n"
                "STATUS: [SUCCESS or FAIL] | [Details]"
            ),
            expected_output="STATUS report from simulation tool",
            agent=verifier_agent                # ← FIX: single instance
        )
        
        crew_verify = Crew(
            agents=[verifier_agent],            # ← FIX: same instance
            tasks=[task_verify],
            verbose=True
        )
        
        try:
            result_verify = str(crew_verify.kickoff())
            log_verif.info(f"Iteration {iteration} - {result_verify}")


            direct_result = run_simulation_direct(current_code)

            real_fidelity_match = re.search(r'Fidelity[:\s]+([0-9.]+)', str(direct_result))
            if real_fidelity_match:
                real_fidelity = float(real_fidelity_match.group(1))
                fidelity_history.append((iteration, real_fidelity))
                if real_fidelity >= 0.60:
                    result_verify = f"STATUS: SUCCESS | Fidelity: {real_fidelity}"
                else:
                    result_verify = f"STATUS: FAIL | Low Fidelity: {real_fidelity}"
                print(f"📊 Ground truth fidelity (direct tool): {real_fidelity}")
                log_verif.info(f"Iteration {iteration} - Ground truth override: {result_verify}")
            else:
                # Fallback to verifier output if direct call fails
                fidelity_match = re.search(r'Fidelity[:\s]+([0-9.]+)', result_verify)
                if fidelity_match:
                    fidelity_history.append((iteration, float(fidelity_match.group(1))))

                fidelity_match = re.search(r'Fidelity[:\s]+([0-9.]+)', result_verify)
                if fidelity_match:
                    fidelity_history.append((iteration, float(fidelity_match.group(1))))
            
            valid, reason = SchemaValidator.validate_status(result_verify)
            if not valid:
                print(f"⚠️ Verifier output malformed: {reason}. Treating as FAIL.")
                log_verif.warning(f"Schema validation failed: {reason}")
                result_verify = f"STATUS: FAIL | Malformed verifier output: {reason}"
            # Parse the status
            print(f"\n📊 VERIFICATION REPORT:")
            print(f"{'─'*70}")
            print(result_verify)
            print(f"{'─'*70}\n")
            
        except Exception as e:
            error_msg = str(e)
            
            # Handle rate limiting with exponential backoff
            if "rate_limit" in error_msg.lower() or "RateLimitError" in error_msg:
                wait_time = 20 + (iteration * 10)  # 30s, 40s, 50s
                print(f"⚠️  Rate limit hit. Waiting {wait_time} seconds...")
                log_verif.warning(f"Iteration {iteration} - Rate limit hit, waiting {wait_time}s")
                time.sleep(wait_time)
                
                # Retry verification once
                try:
                    print("🔄 Retrying verification...")
                    result_verify = str(crew_verify.kickoff())
                    log_verif.info(f"Iteration {iteration} (Retry) - {result_verify}")

                    direct_result_retry = run_simulation_direct(current_code)
                    retry_fidelity_match = re.search(r'Fidelity[:\s]+([0-9.]+)', str(direct_result_retry))
                    if retry_fidelity_match:
                        retry_fidelity = float(retry_fidelity_match.group(1))
                        fidelity_history.append((iteration, retry_fidelity))
                        if retry_fidelity >= 0.60:
                            result_verify = f"STATUS: SUCCESS | Fidelity: {retry_fidelity}"
                        else:
                            result_verify = f"STATUS: FAIL | Low Fidelity: {retry_fidelity}"
                        log_verif.info(f"Iteration {iteration} (Retry) - Ground truth override: {result_verify}")

                    valid, reason = SchemaValidator.validate_status(result_verify)
                    if not valid:
                        print(f"⚠️ Verifier output malformed: {reason}. Treating as FAIL.")
                        log_verif.warning(f"Schema validation failed: {reason}")
                        result_verify = f"STATUS: FAIL | Malformed verifier output: {reason}"
                    print(f"\n📊 VERIFICATION REPORT:")
                    print(f"{'─'*70}")
                    print(result_verify)
                    print(f"{'─'*70}\n")
                except Exception as retry_error:
                    result_verify = f"STATUS: FAIL | Verification failed after retry: {str(retry_error)}"
                    log_verif.error(f"Iteration {iteration} - Retry failed: {str(retry_error)}")
                    print(f"❌ Retry failed: {str(retry_error)}\n")
            else:
                result_verify = f"STATUS: FAIL | Verification crashed: {str(e)}"
                log_verif.error(f"Iteration {iteration} - Verification Error: {str(e)}")
                print(f"❌ Verifier crashed: {str(e)}\n")
        
        # CHECK FOR SUCCESS
        if "STATUS: SUCCESS" in result_verify:
            print(" SUCCESS: Circuit validated on Digital Twin!")
            print(f" Fidelity meets {backend_full_name} threshold")
            success = True
            break
        
        # STEP 2B: OPTIMIZE IF FAILED
        if iteration < max_iterations:
            print(f"⚠️  Circuit failed verification. Attempting repair...")
            print(f"🔧 Optimizer analyzing error report...\n")

            # ← NEW: Record this failure in memory before calling optimizer
            memory.record_iteration(
                iteration=iteration,
                code=current_code,
                error=result_verify,
                fix_applied=None   # Will be updated after optimizer runs
            )

            # ← NEW: Get memory context to inject into optimizer task
            memory_context = memory.get_optimizer_context()

            optimizer_agent = agents.optimizer()

            circuit_constraints = ""
            if mode == "2":
                circuit_constraints = (
                    "ABSOLUTE CRITICAL FOR BV CIRCUIT — READ BEFORE ANYTHING ELSE:\n"
                    "This is a Bernstein-Vazirani oracle. The CNOT structure is MATHEMATICALLY FIXED.\n"
                    "You are FORBIDDEN from changing ANY CNOT gate in this circuit.\n"
                    "You are FORBIDDEN from adding or removing any CNOT gate.\n"
                    "You are FORBIDDEN from changing qubit indices on any CNOT gate.\n"
                    "The ONLY permitted fixes are:\n"
                    "  1. Rename variable from 'c' or other names to 'qc'\n"
                    "  2. Fix import statements\n"
                    "  3. Fix measurement syntax\n"
                    "If the circuit fails due to low fidelity on this topology, "
                    "that is a hardware limitation result — DO NOT attempt to fix it by changing gates.\n"
                    "Return the EXACT same CNOT structure with only variable naming or import fixes.\n\n"
                )
            elif mode == "3":
                circuit_constraints = (
                    "CRITICAL FOR ZZ CIRCUIT: Do NOT change Rz rotation angles or CNOT structure. "
                    "The ZZ interaction gates are fixed and encode classical data. "
                    "Only fix measurement syntax or import errors.\n\n"
                )
            elif mode == "4":
                circuit_constraints = (
                    "CRITICAL FOR ECG CIRCUIT: Do NOT change Rz rotation angles or CNOT structure. "
                    "The ZZ interaction gates encode clinical ECG features. "
                    "Only fix measurement syntax or import errors.\n\n"
                )
            task_optimize = Task(
                description=(
                    f"VERIFICATION FAILED. Error details:\n\n"
                    f"{result_verify}\n\n"
                    f"CURRENT CODE (BROKEN):\n"
                    f"```python\n{current_code}\n```\n\n"
                    # ← NEW: Inject memory so optimizer knows what NOT to try
                    f"MEMORY — WHAT HAS ALREADY BEEN TRIED AND FAILED:\n"
                    f"{memory_context}\n\n"
                    "YOUR TASK:\n"
                    "1. Analyze the error type (variable naming, topology, imports, fidelity)\n"
                    "2. Apply targeted fix — DO NOT repeat any fix listed in MEMORY above\n"
                    "3. Return the COMPLETE fixed Python code\n"
                    "4. Ensure the circuit is still named 'qc'\n"
                    "5. Do NOT change the user's original request intent\n\n"

                    f"{circuit_constraints}"
                    "Return only the corrected code, ready to execute."
                ),
                expected_output="Fixed Python code with the same variable name 'qc'",
                agent=optimizer_agent
            )
            
            crew_optimize = Crew(
                agents=[optimizer_agent],
                tasks=[task_optimize],
                verbose=True
            )
            
            # ── FIX: Robust Optimizer execution with inline rate-limit retry ──
            max_opt_retries = 2
            opt_success = False
            
            for opt_try in range(max_opt_retries):
                try:
                    # Added a mandatory pre-flight pause to prevent hitting the 12k TPM limit
                    print("⏳ Cooling down Groq API tokens for 15 seconds before Optimization...")
                    time.sleep(15)
                    
                    result_optimize = crew_optimize.kickoff()
                    fixed_code = extract_code(result_optimize)
                    
                    memory.record_fix(f"Iteration {iteration} fix on: {result_verify[:100]}")
                    current_code = fixed_code
                    log_optim.info(f"Iteration {iteration} Fix:\n{current_code}")
                    print(f"\n✅ Optimizer completed. Fixed code logged to logs/optimizer_log.txt")
                    opt_success = True
                    break # Exit retry loop on success
                    
                except Exception as e:
                    error_msg = str(e)
                    if "rate_limit" in error_msg.lower() or "RateLimitError" in error_msg:
                        wait_time = 30 + (opt_try * 15)
                        print(f"\n⚠️ Optimizer hit Rate Limit. Waiting {wait_time}s before retry {opt_try+1}/{max_opt_retries}...")
                        time.sleep(wait_time)
                    else:
                        print(f"\n❌ Optimizer failed with fatal error: {error_msg}")
                        log_optim.error(f"Iteration {iteration} - Optimizer Fatal Error: {error_msg}")
                        break # Exit on non-rate-limit errors
            
            if not opt_success:
                print("\n❌ Optimizer could not recover. Aborting compilation.")
                break # Exit the main iteration loop if optimization totally fails
        else:
            print(f"\n❌ Maximum iterations ({max_iterations}) reached without success.")
    
    # --- PHASE 3: FINAL OUTPUT ---
    print_separator("[PHASE 3/3] FINAL RESULT")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    if success:
        print("🎉 CIRCUIT COMPILATION SUCCESSFUL\n")
        print("The following code has been validated on the Digital Twin:")
        print("It respects hardware topology and meets fidelity requirements.\n")

        print("🎨 Generating visualizations...")
        
        if mode == "2":
            prefix = f"bv_{backend_key}_{timestamp}"
        elif mode == "3":
            prefix = f"zz_{backend_key}_{timestamp}"
        elif mode == "4":
            prefix = f"ecg_{backend_key}_{timestamp}"
        else:
            prefix = f"circuit_{backend_key}_{timestamp}"
        generate_circuit_diagram(current_code, f"{prefix}_diagram.png", backend_key)
        generate_measurement_chart(current_code, f"{prefix}_measurement.png", backend_key)
        if len(fidelity_history) > 1:
            generate_fidelity_graph(fidelity_history, f"{prefix}_fidelity.png", backend_key)
        
        print(f"📁 Visualizations saved in: visualizations/\n")
    else:
        print("⚠️  COMPILATION INCOMPLETE\n")
        print("The circuit did not pass all validation checks.")
        print("Review the logs for detailed error information.\n")
    
    # ← NEW: Log memory summary at end of session
    # Save results for compare_backends.py
    extra = {}
    if mode == "3":
        extra = {'zz_info': zz_info}
    elif mode == "4":
        extra = {'ecg_info': ecg_info}
    elif mode == "2":
        extra = {'hidden_string': hidden, 'expected': expected}

    save_run_results(
        backend_key=backend_key,
        backend_full_name=backend_full_name,
        mode=mode,
        current_code=current_code,
        fidelity_history=fidelity_history,
        success=success,
        timestamp=timestamp,
        extra_info=extra,
        num_features=num_feat
    )

    memory_summary = memory.get_summary()
    log_optim.info(f"Session Memory Summary: {memory_summary}")
    
    print("="*70)
    print("FINAL CERTIFIED CODE:")
    print("="*70)
    print(current_code)
    print("="*70)

    if mode == "2" and expected:
        print(f"\n Expected answer: {expected}")
        print(f" Check measurement_comparison.png to verify")
        print(f"   Ideal bars should show ~100% at state: {expected}")

    if mode == "3":
        print(f"\n ZZ ENCODING RESULT: ({backend_full_name})")
        print(f"   Sample: Iris {zz_info['class_name']}")
        print(f"   Features encoded: {zz_info['feature_names']}")
        print(f"   High fidelity = classical data preserved accurately in quantum state")
        print(f"   Low fidelity = noise corrupted the data encoding")
    
    if mode == "4":
        print(f"\n ECG ENCODING RESULT ({backend_full_name}):")
        print(f"   Record: {ecg_info['record_id']} | Beat type: {ecg_info['beat_label']}")
        print(f"   Features encoded: {ecg_info['feature_names']}")
        print(f"   High fidelity = ECG features preserved accurately in quantum state")
        print(f"   Low fidelity = noise corrupted the cardiac data encoding")

        
        generate_bloch_sphere(current_code, num_feat, f"{prefix}_bloch.png")

    print(f"\n📁 Full logs available in:")
    print(f"   - logs/architect_log.txt")
    print(f"   - logs/verifier_log.txt")
    print(f"   - logs/optimizer_log.txt")


    if success:
        print_separator("[PHASE 4/4] CLOUD DEPLOYMENT")
        deploy = input("Deploy this certified circuit to REAL IBM Hardware? (y/n): ").strip().lower()
        if deploy == 'y':
            from ibm_connector import run_cloud_validation
            
            print("\nSelect IBM Cloud Backend:")
            print("  0. ibmq_qasm_simulator (Fast connection test)")
            print("  1. ibm_brisbane (127Q Heavy-Hex)")
            print("  2. ibm_kyoto (127Q Heavy-Hex)")
            print("  3. ibm_sherbrooke (127Q Heavy-Hex Eagle r3)")
            cloud_choice = input("Enter choice (0-3, default 1): ").strip() or "1"
            
            final_local_fidelity = fidelity_history[-1][1] if fidelity_history else 0.0
            
            # Execute on real hardware
            run_cloud_validation(
                circuit_code=current_code,
                local_fidelity=final_local_fidelity,
                backend_choice=cloud_choice,
                extra_info=extra
            )
    # ==========================================================
    
    print("\n✨ Q-Optima session complete.\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Session interrupted by user. Exiting gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {str(e)}")
        sys.exit(1)