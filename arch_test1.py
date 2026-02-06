import os
import sys
from dotenv import load_dotenv
from crewai import Agent, Task, Crew
from langchain_google_genai import ChatGoogleGenerativeAI

# 1. Setup Environment
load_dotenv()
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    verbose=True,
    temperature=0.2,  # Low temp for precise planning
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

# 2. Define the Architect Agent
# Note: We give it a specific goal to "Plan" first, not just "Code".
architect_agent = Agent(
    role='Quantum Systems Architect',
    goal='Analyze user requests and generate a strict technical blueprint for a quantum circuit.',
    backstory=(
        "You are the Chief Architect. You do not write code immediately. "
        "First, you analyze the user's request to determine the Algorithm, Number of Qubits, and Validity. "
        "You reject nonsensical requests (like 'time travel circuit')."
    ),
    llm=llm,
    verbose=True
)

# 3. Dynamic User Input
# We allow the user to type their request in the terminal
print("\n--- ⚛️ Q-OPTIMA ARCHITECT INTERFACE ⚛️ ---")
user_input = input("Enter your Quantum Request (e.g., 'Build a VQE circuit for H2 molecule'): ")

# 4. The "Intent Interpretation" Task
# We force the Agent to output a specific structure.
task_interpret = Task(
    description=f"""
    Analyze the following user request: "{user_input}"

    Your job is to extract the Technical Intent. 
    You must output a summary including:
    1. **Algorithm Identified**: (e.g., VQE, Grover, QFT, Bell State, or 'Unknown')
    2. **Qubits Required**: (Estimate the number needed. If not specified, default to 2-4)
    3. **Complexity Level**: (Low, Medium, High)
    4. **Feasibility Check**: (Can this run on a simulator? Answer YES or NO)
    
    If the request is not related to Quantum Computing, explicitly state: "INVALID REQUEST".
    """,
    expected_output='A structured text summary of the proposed circuit plan.',
    agent=architect_agent
)

# 5. Run the Crew
architect_crew = Crew(agents=[architect_agent], tasks=[task_interpret])

print("\n### Architect is analyzing your intent... ###")
result = architect_crew.kickoff()

print("\n\n########################")   
print("## BLUEPRINT GENERATED ##")
print("########################\n")
print(result)