import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew
from langchain_google_genai import ChatGoogleGenerativeAI
from quantum_tools import QuantumTools # Import the tool we just made

# 1. Setup  
load_dotenv()
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    verbose=True,
    temperature=0.4,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

# 2. Define the Agent WITH Tools
# Notice: We add 'tools=[QuantumTools.optimize_circuit]'
optimizer_agent = Agent(
    role='Quantum Optimizer',
    goal='Design quantum circuits and optimize them to be as small as possible.',
    backstory='You are a specialist in compiling quantum algorithms for noisy hardware.',
    tools=[QuantumTools.optimize_circuit], 
    llm=llm,
    verbose=True
)

# 3. Define the Task
# We specifically ask it to create a "bad" circuit first so we can see the tool fix it.
task_optimize = Task(
    description=(
        "1. Create an OpenQASM 2.0 string. \n"
        "2. IMPORTANT: The string MUST start with exactly these two lines: \n"
        "   OPENQASM 2.0;\n"
        "   include \"qelib1.inc\"; \n"
        "3. Add 3 Hadamard gates (h) on q[0]. \n"
        "4. Use your 'Circuit Optimizer' tool to process this QASM string. \n"
        "5. Report the Original Depth vs. Optimized Depth."
    ),
    expected_output='A report showing the optimization results.',
    agent=optimizer_agent
)

# 4. Run
my_crew = Crew(agents=[optimizer_agent], tasks=[task_optimize])

print("### Agent is working on Optimization... ###")
result = my_crew.kickoff()
print("\n\n########################")
print("## FINAL REPORT ##")
print("########################\n")
print(result)