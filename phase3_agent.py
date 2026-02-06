import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew
from langchain_google_genai import ChatGoogleGenerativeAI
from quantum_tools import QuantumTools, VerificationTools # Import BOTH tools now

# 1. Setup
load_dotenv()
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    verbose=True,
    temperature=0.1, # Lower temperature = more precise/less creative
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

# 2. Define the "Safety First" Agent
optimizer_agent = Agent(
    role='Quantum Reliability Engineer',
    goal='Optimize quantum circuits for depth, but NEVER compromise on mathematical accuracy.',
    backstory='You are a senior engineer. You do not trust optimizations until you have verified them mathematically.',
    tools=[QuantumTools.optimize_circuit, VerificationTools.verify_equivalence], 
    llm=llm,
    verbose=True
)

# 3. Define the Workflow Task
task_safe_optimize = Task(
    description=(
        "1. Create an OpenQASM 2.0 string for a circuit. \n"
        "   - Use 'include \"qelib1.inc\";' \n"
        "   - The circuit should be: H on q[0], then CNOT between q[0] and q[1]. \n"
        "2. Use the 'Circuit Optimizer' tool to optimize it. Save the output string. \n"
        "3. CRITICAL STEP: Use the 'Circuit Verifier' tool. Pass it the ORIGINAL QASM string and the OPTIMIZED QASM string. \n"
        "4. If the verifier says 'SUCCESS', report the depth reduction. If it says 'DANGER', apologize and fail."
    ),
    expected_output='A final report confirming that the circuit was optimized AND verified safely.',
    agent=optimizer_agent
)

# 4. Run the Crew
my_crew = Crew(agents=[optimizer_agent], tasks=[task_safe_optimize])

print("### Agent is running Safe Optimization... ###")
result = my_crew.kickoff()
print("\n\n########################")
print("## FINAL VERIFIED REPORT ##")
print("########################\n")
print(result)