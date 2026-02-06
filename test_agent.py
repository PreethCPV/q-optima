import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI

# 1. Load your API keys
load_dotenv()

# 2. Set up the LLM (The Brain)
# We use Gemini Pro (or Flash) via LangChain
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    verbose=True,
    temperature=0.5,
    google_api_key=os.getenv("GOOGLE_API_KEY")
)

# 3. Define the "Architect" Agent
architect = Agent(
    role='Quantum Circuit Architect',
    goal='Write valid Qiskit code for quantum circuits.',
    backstory='You are an expert quantum physicist proficient in Python and Qiskit.',
    verbose=True,
    allow_delegation=False,
    llm=llm
)

# 4. Define the Task
task1 = Task(
    description='Create a Python script using Qiskit that creates a Bell State (entanglement) between 2 qubits. Measure both qubits.',
    expected_output='A Python code block containing the Qiskit code.',
    agent=architect
)

# 5. Create the Crew (Team of 1)
my_crew = Crew(
    agents=[architect],
    tasks=[task1],
    verbose=True,
    process=Process.sequential
)

# 6. Run it!
print("### Starting the Agent ###")
result = my_crew.kickoff()
print("\n\n########################")
print("## HERE IS THE RESULT ##")
print("########################\n")
print(result)