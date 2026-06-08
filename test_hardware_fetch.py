import os
import sys
from dotenv import load_dotenv
load_dotenv()

# Add current directory to path so we can import our tools
sys.path.append(os.getcwd())

from tools.hardware_tools import HardwareTools

def test_ibm_topology():
    print("--- Testing IBM Cloud Simulator Topology Fetch ---")
    
    # Set backend to cloud simulator
    os.environ["QOPTIMA_BACKEND"] = "ibm_cloud_simulator"
    
    try:
        # Since fetch_map is a CrewAI @tool, we call its underlying .func
        result = HardwareTools.fetch_map.func()
        print("\nTOOL OUTPUT:")
        print(result)
        
        from qiskit_ibm_runtime import QiskitRuntimeService
        token = os.getenv("IBM_QUANTUM_TOKEN")
        
        for channel in ["ibm_cloud", "ibm_quantum_platform"]:
            print(f"\n--- Listing backends for channel: {channel} ---")
            try:
                # Use QiskitRuntimeService directly to avoid save_account issues in loop
                service = QiskitRuntimeService(channel=channel, token=token)
                backends = service.backends()
                print(f"Connection Successful! Found {len(backends)} backends.")
                for b in backends:
                    print(f" >>> BACKEND: {b.name} ({b.num_qubits}Q)")
            except Exception as ex:
                if "Account not found" in str(ex):
                    try:
                        QiskitRuntimeService.save_account(channel=channel, token=token, overwrite=True)
                        service = QiskitRuntimeService(channel=channel)
                        backends = service.backends()
                        print(f"Connection Successful (Saved)! Found {len(backends)} backends.")
                        for b in backends:
                            print(f" >>> BACKEND: {b.name} ({b.num_qubits}Q)")
                    except Exception as ex2:
                        print(f"Failed to save/connect to {channel}: {str(ex2)}")
                else:
                    print(f"Failed to connect to {channel}: {str(ex)}")
        
        # Basic Validation
        if "HARDWARE SPECIFICATION" in result and "COUPLING MAP" in result:
            print("\n✅ Verification PASSED: Topology data retrieved and formatted correctly.")
            
    except Exception as e:
        print(f"\n❌ Test Script CRASHED: {str(e)}")

if __name__ == "__main__":
    test_ibm_topology()
