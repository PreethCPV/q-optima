"""
Bernstein-Vazirani Circuit Generator for Q-Optima
Generates BV circuit code as a string to feed into the architect.
Hidden string is encoded into the oracle.
"""

def generate_bv_prompt(hidden_string: str) -> str:
    """
    Generates a natural language prompt for the architect
    describing the BV circuit to build.
    
    Args:
        hidden_string: binary string e.g. "1011" (max 4 bits for FakeManilaV2)
    
    Returns:
        Prompt string to pass to Q-Optima pipeline
    """
    # Build explicit CNOT instructions based on hidden string
    n = len(hidden_string)

    reversed_string = hidden_string[::-1]
    cnot_instructions = []
    for i, bit in enumerate(reversed_string):
        if bit == '1':
            cnot_instructions.append(f"apply CNOT from qubit {i} to ancilla qubit {n}")

    cnot_text = ", then ".join(cnot_instructions) if cnot_instructions else "no CNOT gates needed"

    # prompt = (
    #     f"Create a Bernstein-Vazirani circuit with {n+1} qubits and {n+1} classical bits. "
    #     f"Step 1: Apply H gate to qubits 0,1,2,3. "
    #     f"Step 2: Apply X gate then H gate to ancilla qubit {n}. "
    #     f"Step 3: {cnot_text}. "
    #     f"CRITICAL: Connect each input qubit DIRECTLY to ancilla qubit {n} using qc.cx(i, {n}). "  
    #     f"Do NOT route through intermediate qubits. The transpiler handles routing automatically. "  
    #     f"Step 4: Apply H gate again to qubits 0,1,2,3. "
    #     f"Step 5: Measure ONLY input qubits 0,1,2,3 using qc.measure([0,1,2,3], [0,1,2,3]). "
    #     f"Do NOT use measure_all(). Do NOT measure ancilla qubit {n}. "
    #     f"IMPORTANT: The CNOT gates in Step 3 are fixed oracle gates. "  
    #     f"Do NOT change their targets. Only fix measurement or import issues if needed. "  
    #     f"Write clean static code only — no loops, no if statements, no variables. "
    #     f"Just direct gate instructions line by line."
    # )

    input_qubits = ",".join(str(i) for i in range(n)) 

    prompt = (
        f"Create a Bernstein-Vazirani circuit with {n+1} qubits and {n} classical bits. "
        f"Step 1: Apply H gate to qubits {input_qubits}. "
        f"Step 2: Apply X gate then H gate to ancilla qubit {n}. "
        
        f"Step 3: Apply ONLY these exact CNOT gates and nothing else: {cnot_text}. "
        f"STRICT: Apply CNOT gates ONLY for qubits explicitly listed above. "
        f"Do NOT apply CNOT to any other qubit. "
        f"The transpiler handles physical routing automatically. "
        f"Step 4: Apply H gate again to qubits {input_qubits}. "
        f"Step 5: Measure ONLY input qubits {input_qubits} using qc.measure([{input_qubits}], [{input_qubits}]). "
        f"Do NOT use measure_all(). Do NOT measure ancilla qubit {n}. "
        f"IMPORTANT: The CNOT gates in Step 3 are fixed oracle gates. "  
        f"Do NOT change their targets. Only fix measurement or import issues if needed. " 
        f"Write clean static code only — no loops, no if statements, no variables. "
        f"Just direct gate instructions line by line."
    )
    return prompt


def get_expected_result(hidden_string: str) -> str:
    """
    Returns the expected measurement result for verification.
    In BV, the output should exactly match the hidden string.
    """
    n = len(hidden_string)
    reversed_string = hidden_string[::-1]  
    padded = reversed_string.zfill(5) 
    return padded