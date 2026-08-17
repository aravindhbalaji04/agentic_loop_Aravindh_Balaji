import os
import json
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google import genai
from google.genai import types
from agent.loop import run_agentic_loop

# Configure Gemini API Key
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=api_key) if api_key else genai.Client()

def llm_engine(system_prompt: str, user_prompt: str) -> str:
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    response = client.models.generate_content(
        model=model_name,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.4,
        )
    )
    return response.text

if __name__ == "__main__":
    # A real paragraph burdened with nominalizations, passive voice, and ambiguous pronouns
    dense_input = (
        "The execution of the database migration was carried out by the infrastructure engineers. "
        "This is because of the fact that latency minimization was needed for client satisfaction. "
        "It resulted in throughput optimization, although resource utilization increased."
    )

    print("=" * 70)
    print("STARTING ITERATIVE AGENTIC CLARITY REFINER")
    print("=" * 70)
    print(f"ORIGINAL PARAGRAPH:\n\"{dense_input}\"\n")

    final_result = run_agentic_loop(dense_input, llm_engine)

    print("\n" + "=" * 70)
    print("FINAL REFINED OUTPUT:")
    print("=" * 70)
    print(f"\"{final_result}\"\n")