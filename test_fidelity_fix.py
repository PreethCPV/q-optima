
import sys
import os

# Add current directory to path so we can import tools and simulation_tools
sys.path.append(os.getcwd())

from tools.simulation_tools import calculate_hellinger_fidelity

def test_fidelity_calculation():
    print("--- Testing Fidelity Calculation Fix ---")

    # Case 1: Matching distributions with 1024 shots (Old Default)
    counts1 = {'00': 512, '11': 512}
    counts2 = {'00': 512, '11': 512}
    fid1 = calculate_hellinger_fidelity(counts1, counts2)
    print(f"1024 Shots (Matching): Fidelity = {fid1:.4f} (Expected: 1.0000)")

    # Case 2: Matching distributions with 100 shots (Cloud Deployment)
    counts100_1 = {'00': 50, '11': 50}
    counts100_2 = {'00': 50, '11': 50}
    
    # Passing explicitly
    fid2 = calculate_hellinger_fidelity(counts100_1, counts100_2, shots=100)
    print(f"100 Shots (Matching, Explicit): Fidelity = {fid2:.4f} (Expected: 1.0000)")

    # Auto-detection (New Logic)
    fid3 = calculate_hellinger_fidelity(counts100_1, counts100_2)
    print(f"100 Shots (Matching, Auto-Detected): Fidelity = {fid3:.4f} (Expected: 1.0000)")

    # Case 3: Slightly noisy 100 shots
    counts_noisy = {'00': 48, '11': 48, '01': 2, '10': 2}
    fid4 = calculate_hellinger_fidelity(counts100_1, counts_noisy)
    print(f"100 Shots (Slightly Noisy, Auto): Fidelity = {fid4:.4f} (Expected: ~0.96)")

    # Case 4: Verify the bug reproduction (what it was before)
    # Using default 1024 shots with 100 count data
    all_outcomes = set(counts100_1.keys()) | set(counts100_2.keys())
    prob1 = {outcome: counts100_1.get(outcome, 0) / 1024 for outcome in all_outcomes}
    prob2 = {outcome: counts100_2.get(outcome, 0) / 1024 for outcome in all_outcomes}
    overlap_sum = sum((prob1[o] * prob2[o])**0.5 for o in all_outcomes)
    fid_bug = overlap_sum ** 2
    print(f"Reproduction of Bug (100 shots counts / 1024 default): Fidelity = {fid_bug:.4f} (User reported ~0.01)")

    assert abs(fid1 - 1.0) < 1e-9
    assert abs(fid2 - 1.0) < 1e-9
    assert abs(fid3 - 1.0) < 1e-9
    assert 0.9 < fid4 < 1.0
    assert abs(fid_bug - 0.0095) < 0.001

    print("\n✅ Verification Successful!")

if __name__ == "__main__":
    try:
        test_fidelity_calculation()
    except Exception as e:
        print(f"❌ Verification Failed: {e}")
        sys.exit(1)
