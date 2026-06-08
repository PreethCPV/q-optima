import os
import sys
import re
import time
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.agents import QOptimaAgents
from src.memory import ConversationMemory
from src.validator import SchemaValidator
from src.visualizer import generate_circuit_diagram, generate_measurement_chart, generate_fidelity_graph, generate_ecg_waveform, generate_topology_map, generate_bloch_sphere
from crewai import Task, Crew

from src.bv_circuit import generate_bv_prompt, get_expected_result
from src.zz_feature_map import get_iris_features, generate_zz_prompt, get_zz_description
from src.ecg_features import get_ecg_features, generate_ecg_prompt, get_ecg_description
from src.result_saver import save_run_results
from tools.simulation_tools import run_simulation_direct
from tools.dynamic_hardware import hardware_router

app = FastAPI(title="Q-Optima Digital Twin Compiler API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

os.makedirs("logs", exist_ok=True)
os.makedirs("visualizations", exist_ok=True)
# make sure ecg dir exists
os.makedirs("visualizations/ecg", exist_ok=True)

app.mount("/visualizations", StaticFiles(directory="visualizations"), name="visualizations")

# Global dependencies
agents = QOptimaAgents()
os.environ["OPENAI_API_KEY"] = "NA"

class ChatRequest(BaseModel):
    message: str
    backend: str = "FakeManilaV2"
    mode: str = "1"
    workflow: str = "local"
    hidden_string: str = ""
    iris_index: str = "0"
    ecg_record: str = "100"
    ecg_beat: str = "10"
    ecg_features: str = "2"

class IBMRunRequest(BaseModel):
    code: str
    mode: str = "simulator"


def setup_logger(name, log_file):
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')        
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers = [] # Clear existing handlers
    logger.addHandler(handler)
    return logger

def extract_code(text):
    text_str = str(text)
    match = re.search(r'```python\n(.*?)\n```', text_str, re.DOTALL)
    if match: return match.group(1).strip()
    match = re.search(r'```\n(.*?)\n```', text_str, re.DOTALL)
    if match: return match.group(1).strip()
    return text_str.strip()

def get_qasm(code: str) -> str:
    try:
        local_scope = {}
        header = "from qiskit import QuantumCircuit, transpile\nimport numpy as np\n\n"
        exec(header + code, {}, local_scope)
        if 'qc' in local_scope:
            return local_scope['qc'].qasm()
        elif 'quantum_circuit' in local_scope:
            return local_scope['quantum_circuit'].qasm()
    except Exception:
        pass
    return "// QASM generation failed"

@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

# In-memory storage for comparing Fidelities in the UI
job_ideal_counts = {}
job_local_fidelities = {}

@app.post("/api/run_ibm")
async def run_ibm_endpoint(request: Request):
    """Submits the verified code to IBM Cloud and returns a Job ID immediately."""
    try:
        from ibm_connector import get_ibm_backend, submit_circuit_async
        from qiskit_ibm_runtime import QiskitRuntimeService
        from qiskit import QuantumCircuit, transpile
        from qiskit_aer import AerSimulator
        import os
        
        req_data = await request.json()
        code = req_data.get("code")
        mode = req_data.get("mode", "simulator")
        local_fidelity = req_data.get("local_fidelity", 0.0)
        
        token = os.getenv("IBM_QUANTUM_TOKEN")
        if not token:
            return JSONResponse(status_code=400, content={"error": "IBM_QUANTUM_TOKEN missing."})
        
        # Load circuit
        local_scope = {}
        header = "from qiskit import QuantumCircuit, transpile\nimport numpy as np\nimport math\n\n"
        try:
            exec(header + code, {}, local_scope)
        except Exception as e:
            return JSONResponse(status_code=400, content={"error": f"Syntax error: {str(e)}"})
        
        qc = local_scope.get('qc') or local_scope.get('quantum_circuit')
        if not qc:
             return JSONResponse(status_code=400, content={"error": "No 'qc' found in code."})
             
        # Authenticate and Submit (Non-blocking)
        QiskitRuntimeService.save_account(channel="ibm_cloud", token=token, set_as_default=True, overwrite=True)
        service = QiskitRuntimeService()
        
        backend = get_ibm_backend(service, mode)
        job_id = submit_circuit_async(qc, backend, shots=100)
        
        # Calculate and stash ideal counts for fidelity checker
        try:
            ideal_sim = AerSimulator()
            ideal_result = ideal_sim.run(transpile(qc, ideal_sim), shots=100).result()
            job_ideal_counts[job_id] = ideal_result.get_counts()
            job_local_fidelities[job_id] = local_fidelity
        except:
            pass
            
        return {"status": "submitted", "job_id": job_id, "backend": backend.name}
            
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"IBM Execution failed: {str(e)}"})

@app.get("/api/ibm_status/{job_id}")
async def check_ibm_status(job_id: str):
    """Polls IBM Cloud for the status of a submitted Job ID."""
    try:
        from ibm_connector import retrieve_job_status
        from tools.simulation_tools import calculate_hellinger_fidelity
        from qiskit_ibm_runtime import QiskitRuntimeService
        import os
        
        token = os.getenv("IBM_QUANTUM_TOKEN")
        QiskitRuntimeService.save_account(channel="ibm_cloud", token=token, set_as_default=True, overwrite=True)
        service = QiskitRuntimeService()
        
        result_data = retrieve_job_status(service, job_id)
        
        # If job is successfully completed, compare real empirical counts with our stashed ideal counts
        if result_data.get("success"):
            ideal_counts = job_ideal_counts.get(job_id)
            if ideal_counts and "counts" in result_data:
                real_fidelity = calculate_hellinger_fidelity(ideal_counts, result_data["counts"])
                result_data["real_fidelity"] = real_fidelity
                result_data["local_fidelity"] = job_local_fidelities.get(job_id, 0.0)
                
        return {"job_id": job_id, "data": result_data}
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Status check failed: {str(e)}"})

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    mode = request.mode
    backend_choice = request.backend
    workflow = request.workflow
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # We'll collect console-like output to send back to the UI
    console_output = []
    def log_print(msg):
        print(msg)
        console_output.append(msg)

    # Backend selection
    backend_map = {
        "FakeManilaV2": ("manila", "FakeManilaV2", "Manila (5Q Local)"),
        "FakeJakartaV2": ("jakarta", "FakeJakartaV2", "Jakarta (7Q Local)"),
        "FakeGuadalupeV2": ("guadalupe", "FakeGuadalupeV2", "Guadalupe (16Q Local)"),
        "ibmq_qasm_simulator": ("ibmq_qasm_simulator", "IBM Cloud Simulator", "IBM Cloud Sim (32Q)"),
        "ibm_brisbane": ("ibm_brisbane", "ibm_brisbane", "IBM Brisbane (127Q)"),
        "ibm_osaka": ("ibm_osaka", "ibm_osaka", "IBM Osaka (127Q)"),
        "hybrid_brisbane": ("hybrid_brisbane", "ibm_brisbane", "Hybrid Brisbane (127Q Local)")
    }
    backend_key, backend_full_name, backend_display = backend_map.get(backend_choice, backend_map["FakeManilaV2"])
    os.environ["QOPTIMA_BACKEND"] = backend_key
    log_print(f"Backend selected: {backend_full_name}")

    # Process modes
    expected = None
    user_input = ""
    extra = {}
    
    if mode == "1":
        user_input = request.message
        num_feat = 2
        record_id = "na"
        beat_idx = 0 
    elif mode == "2":
        hidden = request.hidden_string
        if not all(c in '01' for c in hidden) or len(hidden) > 4:
            return JSONResponse(status_code=400, content={"error": "Invalid string. Use only 0s and 1s, max 4 bits."})
        user_input = generate_bv_prompt(hidden)
        expected = get_expected_result(hidden)
        extra = {'hidden_string': hidden, 'expected': expected}
        log_print(f"BV Demo: Hidden string = '{hidden}'")
        num_feat = 2
        record_id = "na"
        beat_idx = 0 
    elif mode == "3":
        try:
            sample_idx = int(request.iris_index)
        except:
            sample_idx = 0
        features, feature_names, class_name = get_iris_features(sample_idx, num_features=2)
        user_input = generate_zz_prompt(features, feature_names)
        zz_info = get_zz_description(features, feature_names, class_name)
        extra = {'zz_info': zz_info}
        log_print(f"ZZ Feature Map — Sample: {class_name}")
        num_feat = 2
        record_id = "na"
        beat_idx = 0 
    elif mode == "4":
        record_id = request.ecg_record
        try:
            beat_idx = int(request.ecg_beat)
        except:
            beat_idx = 10
        try:
            num_feat = int(request.ecg_features)
        except:
            num_feat = 2
        features, feature_names, beat_label, waves_info = get_ecg_features(record_id, beat_idx, num_feat)
        user_input = generate_ecg_prompt(features, feature_names)
        ecg_info = get_ecg_description(features, feature_names, beat_label, record_id)
        extra = {'ecg_info': ecg_info}
        log_print(f"ECG Arrhythmia — Record: {record_id} | Beat: {beat_label}")
        waveform_path = f"ecg_{record_id}_beat{beat_idx}_waveform.png"
        generate_ecg_waveform(waves_info, waveform_path)

    # Dynamic Hardware Routing (Respect UI selection if sufficient, otherwise upgrade)
    user_backend_qubits = hardware_router.get_qubit_count(backend_choice)
    
    if mode != "1":
        required_qubits = num_feat
        if mode == "2": 
            required_qubits = len(request.hidden_string) + 1  # n inputs + 1 ancilla
        
        if user_backend_qubits >= required_qubits:
            log_print(f"✅ User selected QPU {backend_choice} is sufficient ({user_backend_qubits}Q >= {required_qubits}Q req).")
            # backend_full_name and backend_key are already set from backend_map
        else:
            log_print(f"🧠 Dynamic Router: User selection {backend_choice} ({user_backend_qubits}Q) is insufficient for {required_qubits}Q circuit.")
            log_print(f"🧠 Dynamic Router: Analyzing optimal requirement...")
            backend_full_name, backend_key = hardware_router.select_backend(required_qubits)
            os.environ["QOPTIMA_BACKEND"] = backend_key
            log_print(f"🧠 Dynamic Router: Automatically assigned optimal QPU → {backend_full_name}")

    generate_topology_map(backend_key, list(range(num_feat)), f"ecg_{backend_key}_{record_id}_beat{beat_idx}_topology.png")

    if not user_input.strip():
        return JSONResponse(status_code=400, content={"error": "Empty message"})

    # Setup loggers
    log_arch = setup_logger('architect', 'logs/architect_log.txt')
    log_verif = setup_logger('verifier', 'logs/verifier_log.txt')
    log_optim = setup_logger('optimizer', 'logs/optimizer_log.txt')
    
    log_print(f"📋 Task: {user_input[:100]}...")
    log_print("[PHASE 1/3] ARCHITECT: Generating Circuit")
    log_print("⚙️  Fetching hardware topology from Digital Twin...")
    
    if backend_key == "hybrid_brisbane":
        log_print("🔗 HYBRID ARCHITECTURE: Injecting live cloud parameters...")
        log_print("⬇️  Downloading live IBM hardware calibration data for local Twin processing...")
        log_print("✅ Successfully downloaded IBM Cloud model locally: logs/ibm_cloud_download.json (Format: JSON noise parameters)")

    # Phase 1: Architect
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
    
    crew_phase_1 = Crew(agents=[architect_agent], tasks=[task_build], verbose=True)
    
    try:
        result_1 = crew_phase_1.kickoff()
        current_code = extract_code(result_1)
        log_arch.info(f"Generated Code:\n{current_code}")
        
        valid, reason = SchemaValidator.validate_code(current_code)
        if not valid:
            log_print(f"❌ Architect output invalid: {reason}")
            return {"status": "error", "logs": "\n".join(console_output), "message": f"Validation failed: {reason}"}
        log_print(f"✅ Code schema valid.")
    except Exception as e:
        log_print(f"❌ Architect failed: {str(e)}")
        return {"status": "error", "logs": "\n".join(console_output), "message": f"Architect error: {str(e)}"}

    memory = ConversationMemory()
    max_iterations = 3
    success = False
    fidelity_history = []
    
    log_print("\n⏳ Waiting 15 seconds to avoid rate limiting...")
    time.sleep(15)
    
    for iteration in range(1, max_iterations + 1):
        log_print(f"\n[PHASE 2/3] ITERATION {iteration}: Testing on Digital Twin")
        
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
            agent=verifier_agent
        )
        crew_verify = Crew(agents=[verifier_agent], tasks=[task_verify], verbose=True)
        
        try:
            result_verify = str(crew_verify.kickoff())
            log_verif.info(f"Iteration {iteration} - {result_verify}")
            
            if workflow == "cloud":
                log_print(f"☁️ Submitting direct iteration {iteration} to IBM Quantum Cloud...")
                try:
                    from tools.simulation_tools import calculate_hellinger_fidelity
                    from ibm_connector import get_ibm_backend, submit_circuit_to_ibm
                    from qiskit_ibm_runtime import QiskitRuntimeService
                    from qiskit_aer import AerSimulator
                    from qiskit import transpile
                    
                    local_scope = {}
                    exec("from qiskit import QuantumCircuit, transpile\nimport numpy as np\n\n" + current_code, globals(), local_scope)
                    qc = local_scope.get("qc") or local_scope.get("quantum_circuit")
                    
                    if not qc:
                        direct_result = "STATUS: FAIL | Missing 'qc' variable in code."
                    else:
                        ideal_sim = AerSimulator()
                        ideal_result = ideal_sim.run(transpile(qc, ideal_sim), shots=1024).result()
                        ideal_counts = ideal_result.get_counts()
                        
                        token = os.getenv("IBM_QUANTUM_TOKEN")
                        QiskitRuntimeService.save_account(channel="ibm_cloud", token=token, set_as_default=True, overwrite=True)
                        service = QiskitRuntimeService()
                        
                        if backend_key == "ibmq_qasm_simulator":
                            ibm_backend = get_ibm_backend(service, "simulator")
                        else:
                            os.environ["IBM_QPU_NAME"] = backend_key
                            ibm_backend = get_ibm_backend(service, "specific_qpu")
                            
                        ibm_res = submit_circuit_to_ibm(qc, ibm_backend, shots=1024)
                        noisy_counts = ibm_res["counts"]
                        real_fidelity = calculate_hellinger_fidelity(ideal_counts, noisy_counts, shots=1024)
                        direct_result = f"STATUS: SUCCESS | Fidelity: {real_fidelity}" if real_fidelity >= 0.60 else f"STATUS: FAIL | Low Fidelity: {real_fidelity}"
                        log_print(f"☁️ IBM Execute Completed. Job ID: {ibm_res.get('job_id')} | Fidelity: {real_fidelity}")
                except Exception as e:
                    direct_result = f"STATUS: FAIL | IBM Cloud Error: {str(e)}"
                    log_print(f"❌ IBM Cloud Error: {str(e)}")
            else:
                direct_result = run_simulation_direct(current_code)

            real_fidelity_match = re.search(r'Fidelity[:\s]+([0-9.]+)', str(direct_result))
            if real_fidelity_match:
                real_fidelity = float(real_fidelity_match.group(1))
                fidelity_history.append((iteration, real_fidelity))
                if real_fidelity >= 0.60:
                    result_verify = f"STATUS: SUCCESS | Fidelity: {real_fidelity}"
                else:
                    result_verify = f"STATUS: FAIL | Low Fidelity: {real_fidelity}"
                log_print(f"📊 Ground truth fidelity (direct tool): {real_fidelity}")
            else:
                fidelity_match = re.search(r'Fidelity[:\s]+([0-9.]+)', result_verify)
                if fidelity_match:
                    fidelity_history.append((iteration, float(fidelity_match.group(1))))
                    
            log_print(f"📊 Verifier Report:\n{result_verify}")
        except Exception as e:
            result_verify = f"STATUS: FAIL | {str(e)}"
            log_print(f"❌ Verifier error: {str(e)}")

        if "STATUS: SUCCESS" in result_verify:
            log_print("✅ SUCCESS: Circuit validated on Digital Twin!")
            success = True
            break
            
        if iteration < max_iterations:
            log_print("⚠️  Circuit failed verification. Attempting repair...")
            memory.record_iteration(iteration, current_code, result_verify)
            memory_context = memory.get_optimizer_context()
            
            optimizer_agent = agents.optimizer()
            
            circuit_constraints = ""
            if mode == "2":
                circuit_constraints = (
                    "BERNSTEIN-VAZIRANI OPTIMIZATION PROTOCOL:\n"
                    "This is a Bernstein-Vazirani oracle. The LOGICAL CNOT structure is FIXED.\n"
                    "However, if fidelity is low, you MAY remap the logical qubits to different PHYSICAL qubits.\n"
                    "For example, putting the ancilla in the CENTER of a linear topology (e.g. qubit 2 for Manila) "
                    "reduces the overall distance to other qubits.\n"
                    "1. Fetch Digital Twin Topology to find the most connected qubits.\n"
                    "2. Choose a new physical mapping that minimizes the total SWAP distance.\n"
                    "3. Return the COMPLETE fixed Python code with the new mapping.\n\n"
                )
            elif mode == "3":
                circuit_constraints = "CRITICAL FOR ZZ CIRCUIT: Do NOT change Rz rotation angles. You MAY remap qubits to better physical locations.\n\n"
            elif mode == "4":
                circuit_constraints = "CRITICAL FOR ECG CIRCUIT: Do NOT change Rz rotation angles. You MAY remap qubits to better physical locations.\n\n"

            task_optimize = Task(
                description=(
                    f"VERIFICATION FAILED. Error details:\n\n"
                    f"{result_verify}\n\n"
                    f"CURRENT CODE (BROKEN):\n"
                    f"```python\n{current_code}\n```\n\n"
                    f"MEMORY — WHAT HAS ALREADY BEEN TRIED AND FAILED:\n"
                    f"{memory_context}\n\n"
                    "YOUR TASK:\n"
                    "1. Analyze the error\n"
                    "2. Apply targeted fix — DO NOT repeat any fix listed in MEMORY above\n"
                    "3. Return the COMPLETE fixed Python code\n"
                    "4. Ensure the circuit is still named 'qc'\n"
                    f"{circuit_constraints}"
                ),
                expected_output="Fixed Python code with 'qc' variable",
                agent=optimizer_agent
            )
            crew_optimize = Crew(agents=[optimizer_agent], tasks=[task_optimize], verbose=True)
            
            log_print("⏳ Cooling down Groq API tokens for 15 seconds before Optimization...")
            time.sleep(15)
            
            try:
                result_optimize = crew_optimize.kickoff()
                current_code = extract_code(result_optimize)
                memory.record_fix(f"Iteration {iteration} fix")
                log_optim.info(f"Iteration {iteration} Fix:\n{current_code}")
            except Exception as e:
                log_print(f"❌ Optimizer failed: {str(e)}")
                break
                
            log_print("⏳ Waiting 15 seconds before next iteration...")
            time.sleep(15)
            
    # Phase 3: Final Output
    log_print("\n[PHASE 3/3] FINAL RESULT")
    
    image_urls = []
    
    # Prefix
    if mode == "2":
        prefix = f"bv_{backend_key}_{timestamp}"
    elif mode == "3":
        prefix = f"zz_{backend_key}_{timestamp}"
    elif mode == "4":
        prefix = f"ecg_{backend_key}_{timestamp}"
    else:
        prefix = f"circuit_{backend_key}_{timestamp}"

    # Generate visual files even if failed for debugging, but especially on success
    if success:
        log_print("🎉 CIRCUIT COMPILATION SUCCESSFUL")
    else:
        log_print("⚠️  COMPILATION INCOMPLETE")

    try:
        generate_circuit_diagram(current_code, f"{prefix}_diagram.png", backend_key)
        image_urls.append({"url": f"/visualizations/{prefix}_diagram.png", "title": "Quantum Circuit Diagram"})
        
        generate_measurement_chart(current_code, f"{prefix}_measurement.png", backend_key)
        image_urls.append({"url": f"/visualizations/{prefix}_measurement.png", "title": "Simulated Measurement Histogram"})
        
        if len(fidelity_history) > 1:
            generate_fidelity_graph(fidelity_history, f"{prefix}_fidelity.png", backend_key)
            image_urls.append({"url": f"/visualizations/{prefix}_fidelity.png", "title": "Fidelity Progression (per iteration)"})

        if mode == "4":
            image_urls.append({"url": f"/visualizations/ecg/ecg_{record_id}_beat{beat_idx}_waveform.png", "title": "ECG Record Waveform"})
            generate_bloch_sphere(current_code, num_feat, f"{prefix}_bloch.png")
            image_urls.append({"url": f"/visualizations/ecg/{prefix}_bloch.png", "title": "Bloch Sphere State Projection"})
            image_urls.append({"url": f"/visualizations/ecg/ecg_{backend_key}_{record_id}_beat{beat_idx}_topology.png", "title": "Digital Twin Hardware Topology"})
    except Exception as e:
        log_print(f"⚠️ Error generating visualizations: {str(e)}")

    # Read logs for frontend tabs
    arch_log = open('logs/architect_log.txt').read() if os.path.exists('logs/architect_log.txt') else ""
    verif_log = open('logs/verifier_log.txt').read() if os.path.exists('logs/verifier_log.txt') else ""
    opt_log = open('logs/optimizer_log.txt').read() if os.path.exists('logs/optimizer_log.txt') else ""

    # Generate QASM
    qasm_code = get_qasm(current_code)
    
    # Get latest fidelity
    last_fidelity = fidelity_history[-1][1] if fidelity_history else 0.0

    # Save results and get the full result dict
    results_dict = save_run_results(
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

    return {
        "status": "success" if success else "failed",
        "code": current_code,
        "qasm": qasm_code,
        "results_json": results_dict,
        "fidelity": last_fidelity,
        "logs": "\n".join(console_output),
        "architect_log": arch_log,
        "verifier_log": verif_log,
        "optimizer_log": opt_log,
        "images": image_urls
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
