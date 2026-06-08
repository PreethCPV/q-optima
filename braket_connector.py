"""
braket_connector.py
====================
Standalone AWS Braket Real-Time Quantum Hardware Connector for Q-Optima
------------------------------------------------------------------------
PURPOSE:
    Bridges Q-Optima's compiled Qiskit circuits to AWS Braket real quantum
    hardware (e.g. IQM Garnet, Rigetti Ankaa, IonQ Aria) without modifying
    any existing Q-Optima source files.

USAGE:
    python braket_connector.py

PREREQUISITES:
    pip install amazon-braket-sdk qiskit-braket-provider boto3

AWS SETUP:
    1. Configure AWS credentials:
           aws configure
       or set environment variables:
           AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION

    2. Enable an AWS Braket QPU in the AWS Console (us-east-1 recommended).

    3. Optionally set your S3 bucket for storing Braket job results:
           export BRAKET_S3_BUCKET=your-braket-bucket-name

ARCHITECTURE NOTE:
    This file is intentionally self-contained. It imports nothing from src/
    or tools/ and does not alter main.py, api.py, or any agent configuration.
    It can be run independently at any time to submit a circuit to Braket and
    retrieve results without touching the main Q-Optima pipeline.
"""

import os
import json
from datetime import datetime

# ── AWS Braket SDK ────────────────────────────────────────────────────────────
try:
    import boto3
    from braket.aws import AwsDevice, AwsSession
    from braket.circuits import Circuit as BraketCircuit
    from braket.devices import LocalSimulator
    BRAKET_AVAILABLE = True
except ImportError:
    BRAKET_AVAILABLE = False
    print("⚠️  AWS Braket SDK not installed.")
    print("   Run: pip install amazon-braket-sdk boto3")

# ── Qiskit → Braket Transpiler ────────────────────────────────────────────────
try:
    from qiskit_braket_provider import BraketProvider
    QISKIT_BRAKET_AVAILABLE = True
except ImportError:
    QISKIT_BRAKET_AVAILABLE = False
    print("⚠️  qiskit-braket-provider not installed.")
    print("   Run: pip install qiskit-braket-provider")

# ── Qiskit (for circuit building) ─────────────────────────────────────────────
try:
    from qiskit import QuantumCircuit, transpile
    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False
    print("⚠️  Qiskit not installed. Run: pip install qiskit")


# =============================================================================
# CONFIGURATION
# =============================================================================

# AWS Region where Braket QPUs are available
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

# S3 bucket for storing Braket job results (required for real QPU runs)
S3_BUCKET = os.getenv("BRAKET_S3_BUCKET", "amazon-braket-your-bucket-name")
S3_PREFIX = "q-optima-results"

# Number of shots to run on the QPU
SHOTS = 100

# Available AWS Braket QPU ARNs (as of 2025)
QPU_DEVICES = {
    "iqm_garnet":    "arn:aws:braket:eu-north-1::device/qpu/iqm/Garnet",
    "rigetti_ankaa": "arn:aws:braket:us-west-1::device/qpu/rigetti/Ankaa-9Q-3",
    "ionq_aria":     "arn:aws:braket:us-east-1::device/qpu/ionq/Aria-1",
    "local_sim":     "local",   # free local braket simulator (no AWS cost)
}

# Default device to use (set to "local_sim" for free testing)
DEFAULT_DEVICE = os.getenv("BRAKET_DEVICE", "local_sim")


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
# STEP 2 — CONVERT QISKIT → NATIVE BRAKET CIRCUIT
# =============================================================================

def qiskit_to_braket_circuit(qc: "QuantumCircuit") -> "BraketCircuit":
    """
    Converts a Qiskit QuantumCircuit to a native AWS Braket Circuit.
    Uses the qiskit-braket-provider transpiler under the hood.

    Falls back to a manually constructed Braket circuit if the provider
    is unavailable (demonstrating the Braket SDK's own API).
    """
    if QISKIT_BRAKET_AVAILABLE:
        from qiskit_braket_provider.providers.braket_backend import convert_qiskit_to_braket_circuit
        braket_circuit = convert_qiskit_to_braket_circuit(qc)
        print("✅ Converted Qiskit circuit → Braket circuit via qiskit-braket-provider")
        return braket_circuit
    else:
        # Manual fallback — Bell state using native Braket SDK
        print("⚠️  Using manual Braket circuit fallback (install qiskit-braket-provider for full support)")
        braket_circuit = BraketCircuit()
        braket_circuit.h(0)
        braket_circuit.cnot(0, 1)
        return braket_circuit


# =============================================================================
# STEP 3 — SELECT THE AWS BRAKET DEVICE
# =============================================================================

def get_braket_device(device_key: str = DEFAULT_DEVICE):
    """
    Returns an AWS Braket device object.

    - 'local_sim': Free BraketLocalSimulator (no AWS account needed)
    - Any QPU key: Real quantum hardware via AwsDevice (costs $$$, requires AWS setup)
    """
    if device_key == "local_sim":
        device = LocalSimulator()
        print(f"🖥️  Using LOCAL Braket Simulator (no AWS cost)")
        return device

    arn = QPU_DEVICES.get(device_key)
    if not arn:
        raise ValueError(
            f"Unknown device key: '{device_key}'. "
            f"Available: {list(QPU_DEVICES.keys())}"
        )

    print(f"⚛️  Connecting to AWS Braket QPU: {device_key}")
    print(f"   ARN: {arn}")
    device = AwsDevice(arn)
    print(f"✅ Connected to: {device.name} | Status: {device.status}")
    return device


# =============================================================================
# STEP 4 — SUBMIT TO BRAKET AND RETRIEVE RESULTS
# =============================================================================

def submit_circuit(braket_circuit, device, shots: int = SHOTS) -> dict:
    """
    Submits the Braket circuit to the selected device (local or QPU).

    For QPU devices, results are stored in S3 and polled asynchronously.
    For the local simulator, results are returned immediately.

    Returns a dictionary with measurement counts and metadata.
    """
    print(f"\n🚀 Submitting circuit to Braket ({shots} shots)...")

    if isinstance(device, LocalSimulator):
        # Local simulation — instant result
        task = device.run(braket_circuit, shots=shots)
        result = task.result()
    else:
        # Real QPU — requires S3 bucket for result storage
        s3_folder = (S3_BUCKET, S3_PREFIX)
        task = device.run(braket_circuit, s3_destination_folder=s3_folder, shots=shots)
        print(f"📋 Task ARN: {task.id}")
        print("⏳ Waiting for QPU task to complete (this may take several minutes)...")
        result = task.result()

    counts = result.measurement_counts
    print(f"\n📊 Measurement Results ({shots} shots):")
    print(f"{'─'*40}")
    for state, count in sorted(counts.items(), key=lambda x: -x[1]):
        bar = "█" * int((count / shots) * 30)
        print(f"  |{state}⟩  {bar}  {count} ({100*count/shots:.1f}%)")
    print(f"{'─'*40}")

    return {
        "counts": {k: int(v) for k, v in counts.items()},
        "shots": shots,
        "device": str(device),
        "timestamp": datetime.now().isoformat()
    }


# =============================================================================
# STEP 5 — SAVE RESULTS (mirrors Q-Optima's result_saver.py convention)
# =============================================================================

def save_braket_results(results: dict, filename: str = None):
    """
    Saves Braket execution results to the results/ directory.
    Matches the output format convention used by Q-Optima's result_saver.py.
    """
    os.makedirs("results", exist_ok=True)
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"braket_result_{ts}.json"

    filepath = os.path.join("results", filename)
    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n💾 Results saved to: {filepath}")
    return filepath


# =============================================================================
# MAIN — END-TO-END DEMONSTRATION
# =============================================================================

def main():
    print("=" * 60)
    print("  Q-OPTIMA ↔ AWS BRAKET REAL HARDWARE CONNECTOR")
    print("=" * 60)

    if not BRAKET_AVAILABLE:
        print("\n❌ Cannot proceed: amazon-braket-sdk not installed.")
        print("   Run: pip install amazon-braket-sdk boto3")
        return

    if not QISKIT_AVAILABLE:
        print("\n❌ Cannot proceed: qiskit not installed.")
        return

    # -- Step 1: Build circuit (swap with any Q-Optima-generated code) --
    print("\n[1/4] Building quantum circuit...")
    qc = build_sample_qiskit_circuit()
    print(f"✅ Circuit: {qc.num_qubits} qubits, depth={qc.depth()}")
    print(qc.draw(output="text"))

    # -- Step 2: Convert to Braket format --
    print("\n[2/4] Converting Qiskit → Braket...")
    braket_circuit = qiskit_to_braket_circuit(qc)

    # -- Step 3: Select device --
    print("\n[3/4] Selecting Braket device...")
    print(f"   Device key: '{DEFAULT_DEVICE}'")
    print("   (Change BRAKET_DEVICE env var to: iqm_garnet | rigetti_ankaa | ionq_aria)")
    device = get_braket_device(DEFAULT_DEVICE)

    # -- Step 4: Submit and get results --
    print("\n[4/4] Running on Braket...")
    results = submit_circuit(braket_circuit, device, shots=SHOTS)

    # -- Step 5: Save --
    save_braket_results(results)

    print("\n✨ AWS Braket connector run complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
