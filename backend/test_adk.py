import asyncio
from google.adk import Agent, Runner
from google.adk.agents import SequentialAgent, ParallelAgent
import os
from dotenv import load_dotenv
load_dotenv()
import google.genai as genai

# Setup
if "GEMINI_API_KEY" in os.environ:
    print("API Key loaded successfully.")
else:
    print("WARNING: GEMINI_API_KEY not found in environment!")

researcher = Agent(
    name="researcher",
    model="gemini-2.5-flash",
    instruction="What is 2+2? Only output the number.",
    output_key="math_result"
)

parallel_team = ParallelAgent(
    name="parallel_team",
    sub_agents=[
        Agent(
            name="writer1",
            model="gemini-2.5-flash",
            instruction="Given this number: { math_result? }, multiply by 2. Output number only.",
            output_key="result1"
        ),
        Agent(
            name="writer2",
            model="gemini-2.5-flash",
            instruction="Given this number: { math_result? }, multiply by 3. Output number only.",
            output_key="result2"
        )
    ]
)

pipeline = SequentialAgent(
    name="pipeline",
    sub_agents=[researcher, parallel_team]
)

async def run_test():
    try:
        final_state = None
        async for event in pipeline.run_async("Hello"):
            print("Event type:", type(event))
            if hasattr(event, "state"):
                final_state = event.state
        
        print("\nFinal State:", final_state)
            
    except Exception as e:
        print("ADK execution error:", e)

if __name__ == "__main__":
    asyncio.run(run_test())
