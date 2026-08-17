import json
import time
from typing import Dict, Any, List, Callable
from agent.prompts import SYSTEM_PROMPT, REASONING_PROMPT_TEMPLATE
from agent.tools import tools_schema, TOOL_HANDLERS
from agent.memory_manager import save, recall
from agent.harness import AgentHarness
from agent.logger import StructuredStepLogger

def perceive(input_data: str, config: Dict[str, Any], harness: AgentHarness) -> Dict[str, Any]:
    """Parse raw input and establish baseline metrics."""
    baseline_friction = harness.safe_tool_call(TOOL_HANDLERS["score_clarity_friction"], text=input_data)
    return {
        "original_text": input_data.strip(),
        "best_text": input_data.strip(),
        "best_friction_score": baseline_friction["friction_score"],
        "target_friction_score": config["agent"].get("target_friction_score", 0.0),
        "iteration": 0,
        "max_iterations": config["agent"].get("max_iterations", 6),
        "baseline_metrics": baseline_friction
    }

def reason(observation: Dict[str, Any], session_memory: List[str], llm_call: Callable[[str, str], str], config: Dict[str, Any], harness: AgentHarness) -> Dict[str, Any]:
    """Reasoning step with persistent memory read fallback and LLM retries."""
    recall_limit = config["memory"].get("recall_limit", 3)
    retrieved_past_memories = harness.safe_memory_read(recall, observation["best_text"], recall_limit)
    
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

    # Execute LLM with exponential backoff & simplified fallback prompt
    def execute_llm():
        return llm_call(SYSTEM_PROMPT, prompt)

    def simplified_fallback():
        simple_prompt = f"Rewrite this paragraph to be clearer while preserving all key entities:\n\"{observation['best_text']}\""
        return llm_call("You are a helpful rewriter. Output only the revised paragraph.", simple_prompt)

    raw_response, latency_ms = harness.execute_with_retry(
        fn=execute_llm,
        iteration=observation["iteration"],
        step_name="reason",
        fallback_prompt_fn=simplified_fallback
    )

    plan = harness.safe_parse_plan_json(raw_response)
    plan["_latency_ms"] = latency_ms
    return plan

def act(plan: Dict[str, Any], tools: Dict[str, Callable], observation: Dict[str, Any], harness: AgentHarness) -> Dict[str, Any]:
    """Execute tools safely within the harness."""
    start_t = time.time()
    candidate = plan.get("candidate_text", "").strip()
    
    if not candidate:
        candidate = observation["best_text"]

    friction_res = harness.safe_tool_call(tools["score_clarity_friction"], text=candidate)
    integrity_res = harness.safe_tool_call(
        tools["check_semantic_integrity"],
        original_text=observation["original_text"],
        candidate_text=candidate,
        threshold=observation.get("semantic_threshold", 0.55)
    )
    
    return {
        "candidate_text": candidate,
        "friction": friction_res,
        "integrity": integrity_res,
        "reasoning_trace": plan.get("reasoning_trace", ""),
        "_latency_ms": (time.time() - start_t) * 1000
    }

def reflect(result: Dict[str, Any], observation: Dict[str, Any], harness: AgentHarness) -> Dict[str, Any]:
    """Evaluate output, update memory, and guard against infinite loops."""
    start_t = time.time()
    candidate = result["candidate_text"]
    friction = result["friction"]
    integrity = result["integrity"]
    curr_score = friction["friction_score"]
    best_score = observation["best_friction_score"]

    if not integrity.get("safe", True):
        feedback = f"CRITICAL DRIFT: Rewrite dropped essential concepts. Must retain original technical terms."
        try:
            save(feedback, metadata={"type": "semantic_drift", "score": curr_score})
        except Exception:
            pass # Fail gracefully if memory write fails
            
        reflection = {
            "is_done": False,
            "status": "ROLLBACK",
            "accepted": False,
            "quality_score": curr_score,
            "next_instruction": feedback
        }
    elif curr_score < best_score:
        is_clear = friction.get("is_clear", False)
        feedback = f"SUCCESSFUL PATTERN: Friction reduced from {best_score} to {curr_score}."
        try:
            save(feedback, metadata={"type": "success_pattern", "score": curr_score})
        except Exception:
            pass
            
        reflection = {
            "is_done": is_clear,
            "status": "CHECKPOINT",
            "accepted": True,
            "quality_score": curr_score,
            "updated_best_text": candidate,
            "next_instruction": feedback + (" Target met!" if is_clear else " Refine further.")
        }
    else:
        feedback = f"INEFFECTIVE PATTERN: Failed to reduce friction ({curr_score} vs best {best_score})."
        try:
            save(feedback, metadata={"type": "friction_failure", "score": curr_score})
        except Exception:
            pass
            
        reflection = {
            "is_done": False,
            "status": "ROLLBACK",
            "accepted": False,
            "quality_score": curr_score,
            "next_instruction": feedback
        }

    # Guardrail Check
    guard_check = harness.check_guardrails(reflection["next_instruction"], candidate)
    if guard_check["is_stuck"]:
        reflection["is_stuck"] = True
        reflection["is_done"] = True
        reflection["status"] = "STUCK"
        reflection["next_instruction"] = guard_check["reason"]

    reflection["_latency_ms"] = (time.time() - start_t) * 1000
    return reflection

def run_agentic_loop(input_text: str, llm_callable: Callable[[str, str], str], config: Dict[str, Any], reset_memory: bool = False) -> Dict[str, Any]:
    """Orchestrates loop with structured logging, guardrails, and status tracking."""
    logger = StructuredStepLogger(
        log_file=config["logging"].get("log_file", "agent_execution.jsonl"),
        log_to_stdout=config["logging"].get("log_to_stdout", True)
    )
    harness = AgentHarness(config, logger)

    if reset_memory:
        try:
            from agent.memory_manager import clear as clear_mem
            clear_mem()
        except Exception as e:
            print(f"[HARNESS WARN] Failed to clear memory: {e}")

    t0 = time.time()
    observation = perceive(input_text, config, harness)
    logger.log_step(0, "perceive", input_text, observation["baseline_metrics"], (time.time() - t0)*1000)

    session_memory: List[str] = [f"Initial Friction Score: {observation['best_friction_score']}"]
    final_status = "PARTIAL"

    print(f"\n[PERCEIVE] Baseline Friction Score: {observation['best_friction_score']}")

    while observation["iteration"] < observation["max_iterations"]:
        observation["iteration"] += 1
        print(f"\n{'='*25} ITERATION {observation['iteration']} {'='*25}")

        # 1. REASON
        plan = reason(observation, session_memory, llm_callable, config, harness)
        logger.log_step(observation["iteration"], "reason", observation["best_text"], plan.get("reasoning_trace"), plan["_latency_ms"])
        print(f"[REASON Trace]: {plan.get('reasoning_trace')}")

        # 2. ACT
        result = act(plan, TOOL_HANDLERS, observation, harness)
        logger.log_step(observation["iteration"], "act", plan.get("chosen_action"), result["candidate_text"], result["_latency_ms"])
        print(f"[ACT Candidate]: \"{result['candidate_text']}\"")

        # 3. REFLECT
        reflection = reflect(result, observation, harness)
        logger.log_step(observation["iteration"], "reflect", result["candidate_text"], reflection["next_instruction"], reflection["_latency_ms"])
        print(f"[REFLECT Feedback]: {reflection['next_instruction']}")

        session_memory.append(f"Iteration {observation['iteration']}: {reflection['next_instruction']}")

        if reflection.get("accepted"):
            observation["best_text"] = reflection["updated_best_text"]
            observation["best_friction_score"] = reflection["quality_score"]

        if reflection.get("is_stuck"):
            final_status = "STUCK"
            print(f"\n[LOOP HALTED] {reflection['next_instruction']}")
            break

        if reflection.get("is_done"):
            final_status = "COMPLETE"
            print("\n[LOOP TERMINATED] Target clarity reached successfully.")
            break

    return {
        "status": final_status,
        "final_text": observation["best_text"],
        "iterations_completed": observation["iteration"],
        "final_friction_score": observation["best_friction_score"]
    }