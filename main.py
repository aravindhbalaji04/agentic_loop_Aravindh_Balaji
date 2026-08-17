import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google import genai
from google.genai import types
from agent.config import load_config
from agent.loop import run_agentic_loop

# Load all parameters from config.yaml with env overrides
config = load_config("config.yaml")

api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY is missing. Please set it in environment.")

client = genai.Client(api_key=api_key)

def llm_engine(system_prompt: str, user_prompt: str) -> str:
    model_name = config["llm"]["model_name"]
    temp = config["llm"]["temperature"]
    response = client.models.generate_content(
        model=model_name,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temp,
            response_mime_type="application/json"
        )
    )
    return response.text

if __name__ == "__main__":
    dense_input = (
        "The execution of the database migration was carried out by the infrastructure engineers. "
        "This is because of the fact that latency minimization was needed for client satisfaction. "
        "It resulted in throughput optimization, although resource utilization increased."
    )

    print("=" * 70)
    print("STARTING HARNESS-WRAPPED PRODUCTION AGENTIC LOOP")
    print("=" * 70)
    print(f"ORIGINAL PARAGRAPH:\n\"{dense_input}\"\n")

    result = run_agentic_loop(
        input_text=dense_input,
        llm_callable=llm_engine,
        config=config,
        reset_memory=False
    )

    print("\n" + "=" * 70)
    print(f"RUN SUMMARY [STATUS: {result['status']} | ITERATIONS: {result['iterations_completed']}]")
    print("=" * 70)
    print(f"FINAL OUTPUT:\n\"{result['final_text']}\"")
    print(f"FINAL FRICTION SCORE: {result['final_friction_score']}\n")