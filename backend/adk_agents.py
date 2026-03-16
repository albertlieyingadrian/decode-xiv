import os
import asyncio
from google.adk import Agent, Runner
from google.adk.models import Gemini
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from dotenv import load_dotenv

load_dotenv()

def get_gemini_model():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found")
    return Gemini(model="gemini-2.5-flash", api_key=api_key)

async def extract_concepts_with_adk(title: str, summary: str) -> str:
    """
    Uses Google ADK Agent to extract key visual concepts from a paper.
    """
    try:
        model = get_gemini_model()
        
        # Define the agent
        concept_agent = Agent(
            name="concept_extractor",
            model=model,
            instruction="""
You are an expert in scientific visualization and education.
Your task is to analyze a research paper's title and summary and identify the 3-5 most important concepts that should be visualized.
For each concept, briefly describe how it could be visualized in 2D (animation) or 3D.
Output the result as a bulleted list.
Do not include any conversational filler.
""",
        )
        
        # Create runner
        session_service = InMemorySessionService()
        runner = Runner(
            agent=concept_agent, 
            app_name="visual_arxiv_adk", 
            session_service=session_service, 
            auto_create_session=True
        )
        
        # Prepare input
        user_prompt = f"Paper Title: {title}\n\nPaper Summary: {summary}"
        new_message = Content(role="user", parts=[Part(text=user_prompt)])
        
        # Run
        response_text = ""
        async for event in runner.run_async(user_id="system", session_id="concept_extraction", new_message=new_message):
            if hasattr(event, "content") and event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text
                        
        return response_text.strip()
        
    except Exception as e:
        print(f"ADK Concept Extraction failed: {e}")
        return "" # Fallback to empty string
