import os
import sys
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI

sys.path.append(os.path.abspath('tools'))
from mytools import HardwareTools 

load_dotenv()
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", verbose=True, temperature=0.1, google_api_key=os.getenv("GOOGLE_API_KEY"))

# --- 1. THE AGENTS ---

# Agent A: The Planner (What you just tested)
planner = Agent(
    role='Quantum Planner',
    goal='Create a strict technical blueprint from user text.',
    backstory='You identify the algorithm and qubit requirements.',
    llm=llm
)

# Agent B: The Coder (The new part)
# This agent has the "Hardware Tool" so it checks connections before coding.
coder = Agent(
    role='Hardware-Aware Quantum Coder',
    goal='Write Qiskit code that adheres to hardware constraints.',
    backstory='You are a developer who ensures code runs on specific hardware topologies (0-1-2-3-4).',
    tools=[HardwareTools.check_connectivity], 
    llm=llm,
    verbose=True
)

# --- 2. THE TASKS ---

print("\n--- ⚛️ Q-OPTIMA FULL SYSTEM ⚛️ ---")
user_input = input("Enter Request (e.g., 'Entangle qubit 0 and qubit 2'): ")

# Task 1: Plan
task_blueprint = Task(
    description=f"""
    Analyze this request: '{user_input}'

    Extract the technical intent and OUTPUT STRICTLY in the following JSON format.
    DO NOT add explanations or extra text.

    {{
      "algorithm": "Bell / GHZ / Grover / QFT / VQE / Unknown",
      "qubits": <integer>,
      "complexity": "Low / Medium / High",
      "feasible": true or false
    }}

    Rules:
    - If not quantum-related, set algorithm = "INVALID"
    - Default qubits = 2 if unspecified
    - feasible = false if it cannot run on a simulator
    """,
    expected_output="Strict JSON blueprint only.",
    agent=planner
)

# Task 2: Code (Updated for VQE & Hardware)
task_code = Task(
    description=(
        "You are a Quantum Compiler. You must convert the user's intent into executable Qiskit code that fits the hardware.\n"
        "HARDWARE: Linear Topology (0 -- 1 -- 2 -- 3 -- 4).\n\n"

        "!!! CRITICAL RULES (READ CAREFULLY) !!!\n"
        "1. DO NOT CHANGE THE TARGET QUBITS. If user asks for 0 and 3, you MUST involve 0 and 3.\n"
        "2. IF QUBITS ARE NOT NEIGHBORS (e.g., 0 and 3):\n"
        "   - You MUST write SWAP gates to move the state.\n"
        "   - PATHFINDING STRATEGY: To connect 0 and 3, you must SWAP 0 -> 1, then SWAP 1 -> 2, then CX 2 -> 3.\n"
        "   - Do NOT just pick a closer neighbor. That is a FAILURE.\n\n"

        "--- STEP-BY-STEP GENERATION ---\n"
        "1. Identify the 'Source' and 'Target' qubits from the blueprint.\n"
        "2. Check 'Hardware Topology Checker' for the Source and Target.\n"
        "3. If 'Invalid', WRITE DOWN the chain of swaps needed (e.g., 'Swapping 0-1, then 1-2').\n"
        "4. Generate the Qiskit code implementing those swaps.\n"
        "5. Final Output: ONLY the Python code."
    ),
    expected_output="Hardware-validated Qiskit Python code with SWAP routing implemented.",
    agent=coder
)

# --- 3. RUN ---
# We use Process.sequential so Task 1 feeds into Task 2
my_crew = Crew(
    agents=[planner, coder],
    tasks=[task_blueprint, task_code],
    process=Process.sequential,
    verbose=True
)

print("### Generating Hardware-Aware Code... ###")
result = my_crew.kickoff()

print("\n\n########################")
print("## FINAL CODE OUTPUT ##")
print("########################\n")
print(result)