"""
ibm_connector.py
====================
Standalone IBM Quantum Real-Time Hardware Connector for Q-Optima
------------------------------------------------------------------------
PURPOSE:
    Bridges Q-Optima's compiled Qiskit circuits directly to IBM Quantum cloud
    hardware (e.g., real IBM superconducting QPUs or cloud simulators) without
    modifying any existing Q-Optima source files.

USAGE:
    python ibm_connector.py

PREREQUISITES:
    pip install qiskit qiskit-ibm-runtime

IBM CLOUD SETUP:
    1. Create a free IBM Quantum account:
           https://quantum.ibm.com/
           
    2. Copy your API token from the IBM Quantum dashboard (top right corner
       profile -> API token).
    
    3. Configure your environment variables in your terminal:
       Windows (PowerShell):
           $env:IBM_QUANTUM_TOKEN="your_api_token_here"
       Windows (CMD):
           set IBM_QUANTUM_TOKEN=your_api_token_here
       macOS/Linux:
           export IBM_QUANTUM_TOKEN="your_api_token_here"

ARCHITECTURE NOTE:
    This file is intentionally self-contained. It imports nothing from src/
    or tools/ and does not alter main.py, api.py, or any agent configuration.
    It can be run independently at any time to submit a circuit to IBM and
    retrieve results without touching the main Q-Optima pipeline.
"""

import os
import json
from datetime import datetime

# ── Qiskit & IBM Runtime ──────────────────────────────────────────────────────
try:
    from qiskit import QuantumCircuit, transpile
    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False
    print("⚠️  Qiskit not installed. Run: pip install qiskit")

try:
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2 as Sampler
    IBM_RUNTIME_AVAILABLE = True
except ImportError:
    IBM_RUNTIME_AVAILABLE = False
    print("⚠️  qiskit-ibm-runtime not installed.")
    print("   Run: pip install qiskit-ibm-runtime")


# =============================================================================
# CONFIGURATION
# =============================================================================

# Fetch the API token from the environment
IBM_TOKEN = os.getenv("IBM_QUANTUM_TOKEN", None)

# Number of shots (executions) to run on the QPU
SHOTS = 100

# Device selection modes available:
# "simulator"      -> IBM Cloud simulator (ibmq_qasm_simulator - fast, free, good for testing)
# "least_busy_qpu" -> Finds the least busy real quantum computer available to you
# "specific_qpu"   -> Targets a specific system by name (e.g., 'ibm_brisbane')
DEFAULT_MODE = os.getenv("IBM_DEVICE_MODE", "least_busy_qpu")
SPECIFIC_QPU_NAME = os.getenv("IBM_QPU_NAME", "ibm_brisbane")


# =============================================================================
# STEP 1 — BUILD A SAMPLE CIRCUIT (mirrors Q-Optima output)
# =============================================================================

def build_sample_qiskit_circuit() -> "QuantumCircuit":
    """
    Builds a simple Bell-state circuit — the same type Q-Optima's Architect
    agent would generate for a 'Create Bell state' request.
    Replace this function's body with any code block from Q-Optima's output.
    """
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])
    return qc


# =============================================================================
# STEP 2 — SELECT THE IBM QUANTUM BACKEND
# =============================================================================

def get_ibm_backend(service: "QiskitRuntimeService", mode: str = DEFAULT_MODE):
    """
    Retrieves the appropriate IBM Quantum backend based on the configured mode.
    """
    print(f"\n🔍 Searching for IBM Quantum backend (Mode: {mode})...")
    
    try:
        if mode == "simulator":
            # Some dynamic handling for deprecated simulators
            backend = service.backend("ibmq_qasm_simulator") if hasattr(service, 'backend') else service.get_backend("ibmq_qasm_simulator")
            print(f"🖥️  Selected Cloud Simulator: {backend.name}")
            return backend
            
        elif mode == "specific_qpu":
            # Target a very specific QPU
            backend = service.backend(SPECIFIC_QPU_NAME) if hasattr(service, 'backend') else service.get_backend(SPECIFIC_QPU_NAME)
            print(f"⚛️  Selected Specific QPU: {backend.name}")
            return backend
            
        elif mode == "least_busy_qpu":
            pass # handled below securely

    except Exception as e:
        print(f"⚠️  Requested backend unavailable on this plan. Automatically falling back to least busy QPU. (Reason: {e})")
        mode = "least_busy_qpu"
        
    if mode == "least_busy_qpu":
        # Find the least busy real quantum hardware (min 2 qubits)
        print("   Querying real quantum hardware status (this may take a moment)...")
        from qiskit_ibm_runtime import QiskitRuntimeService
        backend = service.least_busy(operational=True, simulator=False, min_num_qubits=2)
        print(f"⚛️  Selected Least Busy QPU: {backend.name} (Pending jobs: {backend.status().pending_jobs})")
        return backend
        
    raise ValueError(f"Unknown device mode: '{mode}'")


# =============================================================================
# STEP 3 — SUBMIT TO IBM CLOUD AND RETRIEVE RESULTS
# =============================================================================

def submit_circuit_to_ibm(qc: "QuantumCircuit", backend, shots: int = SHOTS) -> dict:
    """
    Transpiles the circuit for the target backend and submits it via SamplerV2.
    Waits for the cloud hardware to return the result.
    """
    # 1. Transpile to target hardware ISA (Instruction Set Architecture)
    print(f"\n⚙️  Transpiling circuit for {backend.name} ISA...")
    isa_circuit = transpile(qc, backend=backend, optimization_level=1)
    print("✅ Circuit transpiled successfully.")

    # 2. Submit using Sampler V2
    print(f"\n🚀 Submitting job to IBM Quantum cloud ({shots} shots)...")
    sampler = Sampler(mode=backend)
    
    # Run the job
    job = sampler.run([isa_circuit], shots=shots)
    print(f"📋 Job ID: {job.job_id()}")
    print("⏳ Waiting for IBM Quantum task to complete...")
    print("   (Note: Real QPU jobs are queued and may take minutes to hours based on IBM network traffic)")
    
    # Retrieve results (blocks until job is done)
    result = job.result()
    pub_result = result[0]
    
    # 3. Extract counts dynamically from SamplerV2's BitArray properties
    counts = {}
    for attr in dir(pub_result.data):
        if not attr.startswith("_"):
            data_obj = getattr(pub_result.data, attr)
            if hasattr(data_obj, "get_counts"):
                counts = data_obj.get_counts()
                break
                
    if not counts:
        print("⚠️  Warning: Could not parse measurement counts from the result.")

    # Print a text-based histogram
    print(f"\n📊 Measurement Results from {backend.name} ({shots} shots):")
    print(f"{'─'*40}")
    for state, count in sorted(counts.items(), key=lambda x: -x[1]):
        bar = "█" * int((count / shots) * 30)
        print(f"  |{state}⟩  {bar}  {count} ({100*count/shots:.1f}%)")
    print(f"{'─'*40}")

    return {
        "counts": {k: int(v) for k, v in counts.items()},
        "shots": shots,
        "backend_name": backend.name,
        "job_id": job.job_id(),
        "timestamp": datetime.now().isoformat()
    }


def submit_circuit_async(qc: "QuantumCircuit", backend, shots: int = SHOTS) -> str:
    """
    Submits a circuit to IBM Quantum and returns the Job ID immediately.
    Used by the FastAPI backend for non-blocking execution.
    """
    from qiskit import transpile
    from qiskit_ibm_runtime import SamplerV2 as Sampler
    
    print(f"⚙️  Transpiling for {backend.name}...")
    isa_circuit = transpile(qc, backend=backend, optimization_level=1)
    
    print(f"🚀 Submitting async job...")
    sampler = Sampler(mode=backend)
    job = sampler.run([isa_circuit], shots=shots)
    
    return job.job_id()


def retrieve_job_status(service: "QiskitRuntimeService", job_id: str) -> dict:
    """
    Polls the status of a specific Job ID and returns the result if COMPLETED.
    """
    try:
        job = service.job(job_id)
        status = job.status()
        
        result_data = {
            "job_id": job_id,
            "status": str(status),
            "backend": job.backend().name if hasattr(job, 'backend') else "unknown"
        }
        
        if str(status) == "JobStatus.DONE" or str(status) == "DONE":
            result = job.result()
            pub_result = result[0]
            
            counts = {}
            for attr in dir(pub_result.data):
                if not attr.startswith("_"):
                    data_obj = getattr(pub_result.data, attr)
                    if hasattr(data_obj, "get_counts"):
                        counts = data_obj.get_counts()
                        break
            
            result_data["counts"] = {k: int(v) for k, v in counts.items()}
            result_data["shots"] = 100 # Default for now
            result_data["success"] = True
        else:
            result_data["success"] = False
            
        return result_data
    except Exception as e:
        return {"job_id": job_id, "status": "ERROR", "error": str(e), "success": False}


def run_cloud_validation(circuit_code: str, local_fidelity: float, backend_choice: str = "1", extra_info: dict = None):
    """
    Helper function for main.py to execute a certified circuit on IBM Cloud.
    Handles the entire flow: auth -> select -> run -> save.
    """
    import os
    from qiskit_ibm_runtime import QiskitRuntimeService
    
    token = os.getenv("IBM_QUANTUM_TOKEN")
    if not token:
        print("❌ Error: IBM_QUANTUM_TOKEN environment variable not set.")
        return

    try:
        QiskitRuntimeService.save_account(channel="ibm_cloud", token=token, set_as_default=True, overwrite=True)
        service = QiskitRuntimeService()
        
        # Map choice to mode
        mode_map = {"0": "simulator", "1": "specific_qpu", "2": "specific_qpu", "3": "specific_qpu"}
        name_map = {"1": "ibm_brisbane", "2": "ibm_kyoto", "3": "ibm_sherbrooke"}
        
        mode = mode_map.get(backend_choice, "simulator")
        backend_name = name_map.get(backend_choice, "ibmq_qasm_simulator")
        
        if mode == "specific_qpu":
            os.environ["IBM_QPU_NAME"] = backend_name
        
        backend = get_ibm_backend(service, mode if mode != "specific_qpu" else "specific_qpu")
        
        # Build circuit from code
        local_scope = {}
        header = "from qiskit import QuantumCircuit, transpile\nimport numpy as np\nimport math\n\n"
        exec(header + circuit_code, {}, local_scope)
        qc = local_scope.get('qc')
        
        if not qc:
            print("❌ Error: Could not find 'qc' in the provided circuit code.")
            return

        results = submit_circuit_to_ibm(qc, backend)
        
        # Verify how it has changed and affected the circuit
        try:
            from qiskit_aer import AerSimulator
            from tools.simulation_tools import calculate_hellinger_fidelity
            ideal_sim = AerSimulator()
            ideal_job = ideal_sim.run(transpile(qc, ideal_sim), shots=results.get("shots", 100))
            ideal_counts = ideal_job.result().get_counts()
            
            real_counts = results.get("counts", {})
            real_fidelity = calculate_hellinger_fidelity(ideal_counts, real_counts, shots=results.get("shots", 100))
            
            results["real_fidelity"] = real_fidelity
            results["local_fidelity"] = local_fidelity
            
            print("\n" + "="*60)
            print(" 🚀 CLOUD DEPLOYMENT VERIFICATION (HYBRID CONSTRAINT CHECK)")
            print("="*60)
            print(f" Local Simulated Fidelity : {local_fidelity:.4f}")
            print(f" Real Hardware Fidelity   : {real_fidelity:.4f}")
            
            diff = real_fidelity - local_fidelity
            if diff > 0:
                print(f" Outcome: ✅ Improved by {abs(diff):.4f} (Hardware noise is lower than expected)")
            else:
                print(f" Outcome: ⚠️ Degraded by {abs(diff):.4f} (Hardware noise impacted runtime constraints)")
            
            print("="*60 + "\n")
        except Exception as sim_err:
            print(f"⚠️ Could not compute real fidelity comparison: {sim_err}")
            
        results["extra_info"] = extra_info
        
        save_ibm_results(results)
        return results

    except Exception as e:
        print(f"❌ IBM Cloud Validation Error: {str(e)}")
        return None


# =============================================================================
# STEP 4 — SAVE RESULTS 
# =============================================================================

def save_ibm_results(results: dict, filename: str = None):
    """
    Saves execution results to the results/ directory.
    Matches the output format convention used across Q-Optima.
    """
    os.makedirs("results", exist_ok=True)
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ibm_result_{ts}.json"

    filepath = os.path.join("results", filename)
    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n💾 Results saved to: {filepath}")
    return filepath


# =============================================================================
# MAIN — END-TO-END DEMONSTRATION
# =============================================================================

def main():
    print("=" * 70)
    print("  Q-OPTIMA ↔ IBM QUANTUM REAL HARDWARE CONNECTOR")
    print("=" * 70)

    if not QISKIT_AVAILABLE or not IBM_RUNTIME_AVAILABLE:
        print("\n❌ Cannot proceed: Missing required libraries.")
        print("   Please run: pip install qiskit qiskit-ibm-runtime")
        return

    if not IBM_TOKEN:
        print("\n❌ Missing IBM_QUANTUM_TOKEN.")
        print("   Please set your environment variable with your IBM Quantum API token.")
        print("   Example (Windows): $env:IBM_QUANTUM_TOKEN=\"your_token\"")
        print("   Get yours at: https://quantum.ibm.com/")
        return

    # -- Step 0: Authenticate --
    try:
        print("\n[1/5] Authenticating with IBM Quantum Cloud...")
        # Save token to default channel
        QiskitRuntimeService.save_account(channel="ibm_cloud", token=IBM_TOKEN, set_as_default=True, overwrite=True)
        service = QiskitRuntimeService()
        print("✅ Authentication successful.")
    except Exception as e:
        print(f"\n❌ Authentication failed: {e}")
        return

    # -- Step 1: Build circuit (swap with any Q-Optima-generated code) --
    print("\n[2/5] Building quantum circuit...")
    qc = build_sample_qiskit_circuit()
    print(f"✅ Circuit created: {qc.num_qubits} qubits, depth={qc.depth()}")
    print(qc.draw(output="text"))

    # -- Step 2: Select device --
    print("\n[3/5] Selecting IBM Quantum device...")
    try:
        backend = get_ibm_backend(service, DEFAULT_MODE)
    except Exception as e:
        print(f"\n❌ Backend selection failed: {e}")
        return

    # -- Step 3: Run on IBM Quantum --
    print("\n[4/5] Executing on IBM hardware...")
    try:
        results = submit_circuit_to_ibm(qc, backend, shots=SHOTS)
    except Exception as e:
        print(f"\n❌ Execution failed: {e}")
        return

    # -- Step 4: Save --
    print("\n[5/5] Saving final results...")
    save_ibm_results(results)

    print("\n✨ IBM Quantum connector run complete.")
    print("=" * 70)


if __name__ == "__main__":
    main()
