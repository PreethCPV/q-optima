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
    """
    text_str = str(text)
    
    # Try to find ```python code block first
    match = re.search(r'```python\n(.*?)\n```', text_str, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # Try generic ``` code block
    match = re.search(r'```\n(.*?)\n```', text_str, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    # If no code blocks found, return the entire text (it might be raw code)
    return text_str.strip()

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
    user_input = input("Enter your quantum circuit request\n(e.g., 'Create a Bell state between qubit 0 and qubit 4'): ").strip()
    
    if not user_input:
        print("❌ Error: Empty request. Please provide a circuit description.")
        return
    
    print(f"\n📋 Task: {user_input}")
    
    # --- PHASE 1: ARCHITECT GENERATES INITIAL CIRCUIT ---
    print_separator("[PHASE 1/3] ARCHITECT: Generating Circuit")
    print("⚙️  Fetching hardware topology from Digital Twin...")
    print("⚙️  Compiling circuit with hardware constraints...\n")

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
        agent=architect_agent                   # ← FIX: reuse same instance
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
        print("🔬 Running noisy simulation on FakeManilaV2...")
        print("🔬 Computing quantum state fidelity...\n")

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
            print("✅ SUCCESS: Circuit validated on Digital Twin!")
            print(f"✅ Fidelity meets threshold (>= 0.70)")
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
            
            try:
                result_optimize = crew_optimize.kickoff()
                fixed_code = extract_code(result_optimize)

                # ← NEW: Update memory with what fix was applied
                # memory.history[-1]["fix_applied"] = f"Iteration {iteration} fix attempt on error: {result_verify[:100]}"

                memory.record_fix(f"Iteration {iteration} fix on: {result_verify[:100]}")

                current_code = fixed_code
                log_optim.info(f"Iteration {iteration} Fix:\n{current_code}")
                print(f"\n✅ Optimizer completed. Fixed code logged to logs/optimizer_log.txt")
            except Exception as e:
                print(f"\n❌ Optimizer failed: {str(e)}")
                log_optim.error(f"Iteration {iteration} - Optimizer Error: {str(e)}")
                break
            
            # Rate limiting for Groq API with exponential backoff
            wait_time = 10 + (iteration * 5)  # 15s, 20s, 25s
            print(f"\n⏳ Waiting {wait_time} seconds before next iteration (API rate limiting)...")
            time.sleep(wait_time)
        else:
            print(f"\n❌ Maximum iterations ({max_iterations}) reached without success.")
    
    # --- PHASE 3: FINAL OUTPUT ---
    print_separator("[PHASE 3/3] FINAL RESULT")
    
    if success:
        print("🎉 CIRCUIT COMPILATION SUCCESSFUL\n")
        print("The following code has been validated on the Digital Twin:")
        print("It respects hardware topology and meets fidelity requirements.\n")

        print("🎨 Generating visualizations...")
        generate_circuit_diagram(current_code)
        generate_measurement_chart(current_code)
        if len(fidelity_history) > 1:
            generate_fidelity_graph(fidelity_history)
        print(f"📁 Visualizations saved in: visualizations/\n")
    else:
        print("⚠️  COMPILATION INCOMPLETE\n")
        print("The circuit did not pass all validation checks.")
        print("Review the logs for detailed error information.\n")
    
    # ← NEW: Log memory summary at end of session
    memory_summary = memory.get_summary()
    log_optim.info(f"Session Memory Summary: {memory_summary}")
    
    print("="*70)
    print("FINAL CERTIFIED CODE:")
    print("="*70)
    print(current_code)
    print("="*70)
    
    print(f"\n📁 Full logs available in:")
    print(f"   - logs/architect_log.txt")
    print(f"   - logs/verifier_log.txt")
    print(f"   - logs/optimizer_log.txt")
    
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