import requests
import json

url = "http://localhost:8000/api/chat"

# Test Case 1: Mode 3 (Iris) with FakeJakartaV2
# Previously would be overridden by Manila (5Q) because Iris only needs 2Q.
payload = {
    "message": "Verify routing",
    "backend": "FakeJakartaV2",
    "mode": "3",
    "iris_index": "0"
}

print(f"Sending request with Mode 3 and Backend: {payload['backend']}")
try:
    response = requests.post(url, json=payload, timeout=60)
    data = response.json()
    
    # Check logs for backend selection
    logs = data.get("logs", "")
    print("\nLogs Output:")
    print("-" * 20)
    print(logs)
    print("-" * 20)
    
    if "User selected QPU FakeJakartaV2 is sufficient" in logs:
        print("\nSUCCESS: Routing correctly respected the user's selection.")
    elif "Dynamic Router: User selection FakeJakartaV2 (7Q) is insufficient" in logs:
        print("\nFAILURE: Logic incorrectly flagged Jakarta as insufficient.")
    elif "Dynamic Router: Automatically assigned optimal QPU -> Jakarta" in logs:
        print("\nNote: The dynamic router chose Jakarta anyway, but we should have seen the 'sufficient' message.")
    elif "Automatically assigned optimal QPU -> Manila" in logs:
        print("\nFAILURE: User selection was overridden by Manila.")
    else:
        print("\nUnknown state. Please check the logs carefully.")

except Exception as e:
    print(f"\nError during request: {e}")

# Test Case 2: Mode 2 (BV) with 5 bits (if possible) or check if Manila is sufficient for 4 bits
payload_bv = {
    "message": "Verify BV routing",
    "backend": "FakeManilaV2",
    "mode": "2",
    "hidden_string": "1111" # 4 bits + 1 ancilla = 5Q. Manila has 5Q.
}
print(f"\nSending request with Mode 2 and Backend: {payload_bv['backend']} (4-bit BV -> 5Q req)")
try:
    response = requests.post(url, json=payload_bv, timeout=60)
    data = response.json()
    logs = data.get("logs", "")
    print("\nLogs Output (BV):")
    print("-" * 20)
    print(logs)
    print("-" * 20)
    
    if "User selected QPU FakeManilaV2 is sufficient (5Q >= 5Q req)" in logs:
        print("\n✅ SUCCESS: Manila correctly identified as sufficient for 5Q circuit.")
    else:
        print("\nCheck logs for BV results.")
except Exception as e:
    print(f"\n❌ Error during BV request: {e}")
