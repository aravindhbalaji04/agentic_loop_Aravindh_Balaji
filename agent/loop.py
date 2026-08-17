import json
from typing import Dict, Any, List, Callable
from agent.prompts import SYSTEM_PROMPT, REASONING_PROMPT_TEMPLATE
from agent.tools import tools_schema, TOOL_HANDLERS
from agent.memory_manager import save, recall

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

def reason(observation: Dict[str, Any], session_memory: List[str], llm_call: Callable[[str, str], str]) -> Dict[str, Any]:
    """
    Call the LLM to decide what to do next.
    Requirement: Reads persistent memory at the start and passes it as context.
    """
    # 1. Read persistent memory
    retrieved_past_memories = recall(query=observation["best_text"], limit=3)

    # --- ADD THIS DEBUG PRINT ---
    print("\n" + "#" * 60)
    print(f"[CHROMADB RECALL] Found {len(retrieved_past_memories)} stored memories:")
    for i, mem in enumerate(retrieved_past_memories, 1):
        print(f"  {i}. {mem}")
    print("#" * 60 + "\n")

    retrieved_memory_str = (
        "\n".join(f"- {m}" for m in retrieved_past_memories) 
        if retrieved_past_memories 
        else "No past persistent lessons found."
    )
    
    session_context_str = "\n".join(f"- {m}" for m in session_memory[-3:]) if session_memory else "First session iteration."
    tools_doc = json.dumps(tools_schema, indent=2)
    
    prompt = REASONING_PROMPT_TEMPLATE.format(
        original_text=observation["original_text"],
        best_text=observation["best_text"],
        retrieved_memory=retrieved_memory_str,
        memory_context=session_context_str,
        tools_doc=tools_doc
    )
    
    raw_response = llm_call(SYSTEM_PROMPT, prompt)
    
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
    Execute the planned action by calling the appropriate tool.
    Returns the result of the action.
    """
    candidate = plan.get("candidate_text", "").strip()
    
    if not candidate:
        return {
            "candidate_text": observation["best_text"],
            "friction": {"friction_score": 99.0, "is_clear": False},
            "integrity": {"safe": False, "retention_ratio": 0.0},
            "reasoning_trace": "Empty candidate provided"
        }
    
    # Run diagnostic tools
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
    Requirement: Writes to persistent memory to record feedback, critiques, and lessons learned.
    """
    candidate = result["candidate_text"]
    friction = result["friction"]
    integrity = result["integrity"]
    curr_score = friction["friction_score"]
    best_score = observation["best_friction_score"]
    
    # Gate 1: Check semantic preservation (Rollback trigger)
    if not integrity["safe"]:
        feedback = (
            f"CRITICAL DRIFT: Rewrite dropped essential concepts (Retention: {integrity['retention_ratio']*100}%). "
            f"Must retain original technical nouns and metrics while untangling structure."
        )
        # Persistent write
        save(feedback, metadata={"type": "semantic_drift", "score": curr_score})
        
        return {
            "is_done": False,
            "status": "ROLLBACK",
            "accepted": False,
            "quality_score": curr_score,
            "next_instruction": feedback
        }

    # Gate 2: Check clarity friction improvement (Checkpoint trigger)
    if curr_score < best_score:
        is_clear = friction["is_clear"]
        feedback = (
            f"SUCCESSFUL PATTERN: Reduced friction score from {best_score} to {curr_score}. "
            f"Resolved vague pronouns and unpacked nominalizations."
        )
        # Persistent write
        save(feedback, metadata={"type": "success_pattern", "score": curr_score})
        
        return {
            "is_done": is_clear,
            "status": "CHECKPOINT",
            "accepted": True,
            "quality_score": curr_score,
            "updated_best_text": candidate,
            "next_instruction": feedback + (" Target clarity achieved!" if is_clear else " Further refinement needed.")
        }
    else:
        feedback = (
            f"INEFFECTIVE PATTERN: Revision failed to reduce friction ({curr_score} vs best {best_score}). "
            f"Found {friction['nominalizations_count']} smothered verbs and {friction['vague_openers_count']} vague openers."
        )
        # Persistent write
        save(feedback, metadata={"type": "friction_failure", "score": curr_score})
        
        return {
            "is_done": False,
            "status": "ROLLBACK",
            "accepted": False,
            "quality_score": curr_score,
            "next_instruction": feedback
        }

def run_agentic_loop(input_text: str, llm_callable: Callable[[str, str], str], reset_memory: bool = False) -> str:
    """Orchestrates perceive -> reason -> act -> reflect execution with persistent memory."""
    if reset_memory:
        from agent.memory_manager import clear as clear_mem
        clear_mem()
        print("[MEMORY] Cleared persistent memory for a clean run.")

    observation = perceive(input_text)
    session_memory: List[str] = [f"Initial Friction Score: {observation['best_friction_score']}"]
    
    print(f"\n[PERCEIVE] Baseline Friction Score: {observation['best_friction_score']}")
    
    while observation["iteration"] < observation["max_iterations"]:
        observation["iteration"] += 1
        print(f"\n{'='*25} ITERATION {observation['iteration']} {'='*25}")
        
        # 1. REASON (Reads persistent memory)
        plan = reason(observation, session_memory, llm_callable)
        print(f"[REASON Trace]: {plan.get('reasoning_trace')}")
        
        # 2. ACT
        result = act(plan, TOOL_HANDLERS, observation)
        print(f"[ACT Candidate]: \"{result['candidate_text']}\"")
        
        # 3. REFLECT (Writes to persistent memory)
        reflection = reflect(result, observation)
        print(f"[REFLECT Feedback]: {reflection['next_instruction']}")
        
        session_memory.append(f"Iteration {observation['iteration']}: {reflection['next_instruction']}")
        
        # Update State Checkpoints
        if reflection["accepted"]:
            observation["best_text"] = reflection["updated_best_text"]
            observation["best_friction_score"] = reflection["quality_score"]
            
        if reflection["is_done"]:
            print("\n[LOOP TERMINATED] Target clarity reached successfully.")
            break
            
    return observation["best_text"]