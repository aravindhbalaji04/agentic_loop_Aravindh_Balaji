import json
from typing import Dict, Any, List, Callable
from agent.prompts import SYSTEM_PROMPT, REASONING_PROMPT_TEMPLATE
from agent.tools import tools_schema, TOOL_HANDLERS

def perceive(input_data: str) -> Dict[str, Any]:
    """
    Parse and structure raw input. Extract intent, constraints,
    context, and any relevant signals from the user's input.
    Returns a structured observation dict.
    """
    baseline_friction = TOOL_HANDLERS["score_clarity_friction"](input_data)
    return {
        "original_text": input_data.strip(),
        "best_text": input_data.strip(),
        "best_friction_score": baseline_friction["friction_score"],
        "target_friction_score": 0.0,
        "iteration": 0,
        "max_iterations": 4,
        "baseline_metrics": baseline_friction
    }

def reason(observation: Dict[str, Any], memory: List[str], llm_call: Callable[[str, str], str]) -> Dict[str, Any]:
    """
    Call the LLM to decide what to do next.
    Returns a plan dict: chosen action, parameters, reasoning trace.
    """
    memory_context = "\n".join(f"- {m}" for m in memory[-4:]) if memory else "No prior attempts yet."
    tools_doc = json.dumps(tools_schema, indent=2)
    
    prompt = REASONING_PROMPT_TEMPLATE.format(
        original_text=observation["original_text"],
        best_text=observation["best_text"],
        memory_context=memory_context,
        tools_doc=tools_doc
    )
    
    raw_response = llm_call(SYSTEM_PROMPT, prompt)
    
    # Parse structured JSON plan emitted by LLM
    try:
        clean_json = raw_response.strip()
        if "```json" in clean_json:
            clean_json = clean_json.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_json:
            clean_json = clean_json.split("```")[1].split("```")[0].strip()
        plan = json.loads(clean_json)
    except Exception:
        plan = {
            "reasoning_trace": "Direct rewrite fallback.",
            "chosen_action": "rewrite_and_evaluate",
            "candidate_text": raw_response.strip()
        }
        
    return plan

def act(plan: Dict[str, Any], tools: Dict[str, Callable], observation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute the planned action by calling the appropriate tools.
    Returns the result of the action.
    """
    candidate = plan.get("candidate_text", "").strip()
    
    # Execute Diagnostic Tools
    friction_res = tools["score_clarity_friction"](candidate)
    integrity_res = tools["check_semantic_integrity"](
        original_text=observation["original_text"],
        candidate_text=candidate
    )
    
    return {
        "candidate_text": candidate,
        "friction": friction_res,
        "integrity": integrity_res,
        "reasoning_trace": plan.get("reasoning_trace", "")
    }

def reflect(result: Dict[str, Any], observation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate whether the goal was met.
    Return a reflection dict: is_done flag, quality score, next instruction.
    """
    candidate = result["candidate_text"]
    friction = result["friction"]
    integrity = result["integrity"]
    curr_score = friction["friction_score"]
    best_score = observation["best_friction_score"]
    
    # Gate 1: Check semantic preservation (Rollback trigger)
    if not integrity["safe"]:
        return {
            "is_done": False,
            "status": "ROLLBACK",
            "accepted": False,
            "quality_score": curr_score,
            "next_instruction": (
                f"REJECTED: Lost core entities/meaning (Retention: {integrity['retention_ratio']*100}%). "
                f"Rollback to best checkpoint: '{observation['best_text']}'."
            )
        }
    
    # Gate 2: Check clarity friction improvement (Checkpoint trigger)
    if curr_score < best_score:
        is_clear = friction["is_clear"]
        return {
            "is_done": is_clear,
            "status": "CHECKPOINT",
            "accepted": True,
            "quality_score": curr_score,
            "updated_best_text": candidate,
            "next_instruction": (
                f"ACCEPTED: Friction reduced from {best_score} to {curr_score}."
                + (" Target clarity met!" if is_clear else " Further refinement needed.")
            )
        }
    else:
        return {
            "is_done": False,
            "status": "ROLLBACK",
            "accepted": False,
            "quality_score": curr_score,
            "next_instruction": f"REJECTED: Friction score did not improve ({curr_score} vs best {best_score})."
        }

def run_agentic_loop(input_text: str, llm_callable: Callable[[str, str], str]) -> str:
    """Orchestrates perceive -> reason -> act -> reflect execution."""
    observation = perceive(input_text)
    memory: List[str] = [f"Initial Friction Score: {observation['best_friction_score']}"]
    
    print(f"\n[PERCEIVE] Baseline Friction Score: {observation['best_friction_score']}")
    
    while observation["iteration"] < observation["max_iterations"]:
        observation["iteration"] += 1
        print(f"\n{'='*20} ITERATION {observation['iteration']} {'='*20}")
        
        # 1. REASON
        plan = reason(observation, memory, llm_callable)
        print(f"[REASON Trace]: {plan.get('reasoning_trace')}")
        
        # 2. ACT
        result = act(plan, TOOL_HANDLERS, observation)
        print(f"[ACT Candidate]: \"{result['candidate_text']}\"")
        
        # 3. REFLECT
        reflection = reflect(result, observation)
        print(f"[REFLECT Feedback]: {reflection['next_instruction']}")
        
        memory.append(f"Iteration {observation['iteration']}: {reflection['next_instruction']}")
        
        # Update State Checkpoints
        if reflection["accepted"]:
            observation["best_text"] = reflection["updated_best_text"]
            observation["best_friction_score"] = reflection["quality_score"]
            
        if reflection["is_done"]:
            print("\n[LOOP TERMINATED] Target clarity reached successfully.")
            break
            
    return observation["best_text"]